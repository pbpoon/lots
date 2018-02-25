# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions
PRODUCT_TYPE_SELECTION = [
    ('block', '荒料'),
    ('slab', '板材'),
    ('pbom', '毛板')
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_stone_type = fields.Selection(PRODUCT_TYPE_SELECTION, '石材产品类型')
    uom = fields.Selection(selection=(('t', 't'), ('m3', 'm3'), ('m2', 'm2')), string='计价单位', default='m2')
    package_list_visible = fields.Boolean('是否显示码单', compute='_compute_package_list_visible', default=False,
                                          readonly=True)

    @api.depends('product_stone_type')
    def _compute_package_list_visible(self):
        for record in self:
            if record.product_stone_type == 'slab':
                record.package_list_visible = True
            else:
                record.package_list_visible = False


class ProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    name = fields.Char(
        'Lot/Serial Number', related='product_block_id.name', compute='_compute_name', store=True, required=True,
        help="Unique Lot/Serial Number", )
    product_block_id = fields.Many2one('product.block', '荒料编号', ondelete='cascade', required=True)
    qty = fields.Float('单个数量', compute='_compute_qty', store=True)
    uom = fields.Selection(selection=(('t', 't'), ('m3', 'm3'), ('m2', 'm2')),
                           string='单位', compute='_compute_uom',
                           readonly="1", help="用于计算价值的单位")
    available_qty = fields.Float(string='可售数量', compute='_get_available_qty', store=True)

    @api.depends('product_block_id.cost_uom')
    def _compute_uom(self):
        for record in self:
            if record.product_id.product_stone_type == 'block':
                record.uom = record.product_block_id.cost_uom
            else:
                record.uom = 'm2'

    @api.depends('product_block_id.name')
    def _compute_name(self):
        for record in self:
            if record.product_block_id:
                record.name = '{}'.format(record.product_block_id.name)
            else:
                record.name = lambda self: self.env['ir.sequence'].next_by_code('stock.lot.serial')

    @api.depends('product_block_id.cost_qty')
    def _compute_qty(self):
        for record in self:
            if record.product_id.product_stone_type != 'slab':
                record.qty = record.product_block_id.cost_qty
            else:
                record.qty = 0

    @api.multi
    def _get_available_qty(self):
        for record in self:
            quants = record.quant_ids.filtered(
                lambda q: (q.location_id.usage in ['internal', 'transit'] and (q.quantity - q.reserved_quantity) > 0))
            if quants:
                record.available_qty = sum(quants.mapped(lambda r: r.quantity - r.reserved_quantity))
            else:
                record.available_qty = 0
