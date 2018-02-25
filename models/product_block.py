# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions

COST_BY_SELECTION = (
    ('weight', '按重量'),
    ('m3', '按立方'),
    ('m2', '按平方'),
)


class Quarry(models.Model):
    _name = 'product.quarry'

    name = fields.Char('品种名称', required=True)
    desc = fields.Char('描述')
    SG = fields.Float('比重')

    @api.constrains('name')
    def _unique_name(self):
        for record in self:
            count = record.search_count([('name', '=', record.name)])
            if count > 1:
                raise ValueError('{}已经存在,请确保该编号的唯一性!'.format(record.name))


class Batch(models.Model):
    _name = 'product.batch'

    name = fields.Char("批次编号", required=True, index=True)
    desc = fields.Char('描述')

    @api.constrains('name')
    def _unique_name(self):
        for record in self:
            count = record.search_count([('name', '=', record.name)])
            if count > 1:
                raise ValueError('{}已经存在,请确保该编号的唯一性!'.format(record.name))


class ProductBlock(models.Model):
    _name = 'product.block'
    _inherit = ['mail.thread']

    name = fields.Char('编号', required=True, index=True)
    quarry_id = fields.Many2one('product.quarry', '矿口')
    batch_id = fields.Many2one('product.batch', '批次')
    # ------------荒料数据--------------------
    weight = fields.Float('重量', digits=(3, 2), help='单位为:t')
    m3 = fields.Float('立方', digits=(3, 2), compute='_compute_m3', store=True)
    long = fields.Integer('长', help='单位为:cm')
    width = fields.Integer('宽', help='单位为:cm')
    height = fields.Integer('高', help='单位为:cm')
    cost_by = fields.Selection(selection=COST_BY_SELECTION, string='成本计算方式', default='weight')
    cost_unit_price = fields.Float('成本单价')
    SG = fields.Float(related='quarry_id.SG', string='比重')
    cost_qty = fields.Float('计价数量', compute='_compute_qty', store=True, readonly=True)
    cost_uom = fields.Selection(selection=(('t', 't'), ('m3', 'm3')), string='计价单位', default='t',
                                compute='_compute_qty',
                                readonly=True, store=True)
    lot_ids = fields.One2many('stock.production.lot', 'product_block_id', 'Lot/Serial Number')

    block_type_ids = fields.One2many('stock.production.lot', 'product_block_id', string='荒料形态',
                                     domain=[('product_id.product_stone_type', '=', 'block')])
    pbom_type_ids = fields.One2many('stock.production.lot', 'product_block_id', string='毛板形态',
                                    domain=[('product_id.product_stone_type', '=', 'pbom')])
    slab_type_ids = fields.One2many('stock.production.lot', 'product_block_id', string='板材形态',
                                    domain=[('product_id.product_stone_type', '=', 'slab')])

    all_slab_ids = fields.One2many('product.slab', 'product_block_id', string='入库板材')
    all_slab_qty = fields.Float('入库数量', compute='_compute_slab_qty', store=True)
    available_slab_qty = fields.Float('入库数量', compute='_compute_slab_qty', store=True)
    available_slab_ids = fields.One2many('product.slab', 'product_block_id', string='入库板材',
                                         compute='_get_available_slab_ids')

    ratio = fields.Float('出材率', compute='_compute_ratio')
    ratio_uom = fields.Char('出材率单位', compute='_compute_ratio')

    _sql_constraints = [('name unique', 'unique(name)', u'该荒料名称已存在!')]

    @api.depends('cost_by', 'm3', 'weight')
    def _compute_qty(self):
        for record in self:
            if record.cost_by == 'weight':
                record.cost_qty = record.weight
                record.cost_uom = 't'
            else:
                record.cost_qty = record.m3
                record.cost_uom = 'm3'

    @api.depends('long', 'width', 'height')
    def _compute_m3(self):
        for r in self:
            if r.cost_by == 'm3':
                if r.long and r.width and r.height:
                    r.m3 = r.long * r.width * r.height * 0.00001
                else:
                    r.m3 = None
            else:
                r.m3 = r.weight / 2.8

    @api.onchange('long', 'width', 'height', 'weight')
    def _onchange_m3(self):
        for r in self:
            if r.cost_by == 'm3':
                if r.long and r.width and r.height:
                    r.m3 = r.long * r.width * r.height * 0.00001
                else:
                    r.m3 = None
            else:
                r.m3 = r.weight / 2.8

    @api.depends('all_slab_ids')
    def _get_available_slab_ids(self):
        for record in self:
            record.available_slab_ids = record.all_slab_ids.filtered(lambda slab: slab._check_available())

    @api.depends('all_slab_ids.qty', 'available_slab_ids.qty')
    def _compute_slab_qty(self):
        for record in self:
            if record.all_slab_ids:
                record.all_slab_qty = sum(record.all_slab_ids.mapped('qty'))
            if record.available_slab_ids:
                record.available_slab_qty = sum(record.available_slab_ids.mapped('qty'))

    @api.depends('all_slab_qty')
    def _compute_ratio(self):
        for record in self:
            record.ratio_uom = 'm2/{}'.format(record.cost_uom)
            if not record.all_slab_qty:
                record.ratio = 0
                return
            record.ratio = record.all_slab_qty / record.cost_qty

    @api.multi
    def action_show_all_slab(self):
        self.ensure_one()
        action = self.env.ref('sale_select_lots.product_slab_action').read()[0]
        data = {
            'domain': [('id', 'in', self.all_slab_ids.mapped('id'))],
            'view_mode': 'tree',
            'target': 'new'
        }
        action.update(data)
        return action

    @api.multi
    def action_show_available_slab(self):
        self.ensure_one()
        action = self.env.ref('sale_select_lots.product_slab_action').read()[0]
        data = {
            'domain': [('id', 'in', self.available_slab_ids.mapped('id'))],
            'view_mode': 'tree',
            'target': 'new'
        }
        action.update(data)
        return action


class ProductSale(models.Model):
    _name = 'product.slab'
    _description = u'板材规格'

    lot_id = fields.Many2one('stock.production.lot', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', '荒料编号', related='lot_id.product_id', store=True)
    product_block_id = fields.Many2one('product.block', '荒料编号', related='lot_id.product_block_id', store=True)
    quant_id = fields.Many2one('stock.quant', 'Quants', compute='_compute_quant', help='查库存地址')
    location_id = fields.Many2one('stock.location', 'Location', readonly=True)
    is_reserved = fields.Boolean('已保留', default=False)

    # package_list_id = fields.Many2many('package.list', relation='package_slab',string='码单')

    long = fields.Integer('长')
    height = fields.Integer('高')
    kl1 = fields.Integer('扣迟长')
    kh1 = fields.Integer('扣迟高')
    kl2 = fields.Integer('扣迟2长')
    kh2 = fields.Integer('扣迟2高')
    qty = fields.Float('数量', compute='_compute_total', store=True)

    sequence = fields.Integer('#', default=10)
    num = fields.Integer('#', related='sequence')
    # set_sequence = fields.Integer('#', default=10, help='设定序号,用于显示')
    # default_sequence = fields.Integer('#', default=10, help='默认序号,用于重置')
    # default_part_num = fields.Integer('夹#', default=1, help='默认夹号,用于重置')
    # set_part_num = fields.Integer('夹#', default=1, help='设定夹号,用于显示')
    part_num = fields.Integer('夹#', default=1)

    @api.depends('location_id', 'lot_id')
    def _compute_quant(self):
        quant = self.env['stock.quant']
        for record in self:
            record.quant = quant.search([('lot_id', '=', record.lot_id.id),
                                         ('location_id', '=', record.location_id.id)])

    @api.multi
    def _move_done(self, location_id=None, is_reserved=False):
        return self.write({'location_id': location_id.id, 'is_reserved': is_reserved})

    @api.depends('long', 'height', 'kl1', 'kh1', 'kl2', 'kh2')
    @api.multi
    def _compute_total(self):
        for record in self:

            m2 = record.long * record.height * 0.0001
            if record.kl1 and record.kh1:
                k1m2 = record.kl1 * record.kh1 * 0.0001
                m2 = m2 - k1m2
            if record.kl2 and record.kh2:
                k2m2 = record.kl2 * record.kh2 * 0.0001
                m2 = m2 - k2m2

            record.qty = m2

    @api.model
    def _get_available_slab(self, lot_id=None, location_id=None, is_reserved=None, package_list_id=None,
                            remove_package_list_ids=None):
        domain = [
            ('lot_id', '=', lot_id), ('location_id', 'child_of', location_id),
        ]
        if is_reserved is not None:
            is_reserved = is_reserved
            domain.append(('is_reserved', '=', is_reserved))
        if package_list_id:
            ids_lst = self.env['package.list'].browse(package_list_id).mapped('slab_ids')
            if remove_package_list_ids:
                remove_ids_lst = self.env['package.list'].search([('id', 'in', remove_package_list_ids)]).mapped(
                    'slab_ids')
                ids_lst -= remove_ids_lst
            domain.append(('id', 'in', ids_lst.mapped('id')))
        ids = self.search(domain).mapped('id')
        return ids

    @api.multi
    def _check_available(self):
        for slab in self:
            if slab.location_id.usage in ['internal', 'transit']:
                return True
            return False
