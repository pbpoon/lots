#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by pbpoon on 2018/1/25

from odoo import api, models, fields


class ProcurementRule(models.Model):
    _inherit = 'procurement.rule'

    def _get_stock_move_values(self, product_id, product_qty, product_uom, location_id, name, origin, values, group_id):
        result = super(ProcurementRule, self)._get_stock_move_values(product_id, product_qty, product_uom, location_id,
                                                                     name, origin, values, group_id)
        if values.get('lot_id', False):
            result['lot_id'] = values['lot_id']
        if values.get('package_list_id', False):
            result['package_list_id'] = values['package_list_id']
        if values.get('pcs', False):
            result['pcs'] = values['pcs']

        return result


class StockMove(models.Model):
    _inherit = 'stock.move'

    lot_id = fields.Many2one('stock.production.lot', '批次号', ondelete='set null')
    package_list_id = fields.Many2one('package.list', '码单')
    qty = fields.Float('数量', readonly=True, compute='_compute_qty', store=True)
    part = fields.Integer('夹数', related='package_list_id.part', store=True)
    uom = fields.Selection(selection=(('t', 't'), ('m3', 'm3'), ('m2', 'm2')), string='计价单位', related='lot_id.uom',
                           readonly=True)
    # product_uom_qty = fields.Float(string='件数', compute='_compute_qty', inverse='_set_qty', store=True)
    package_list_visible = fields.Boolean('是否显示码单', related='product_id.package_list_visible', default=False)
    # package_list_visible = fields.Boolean('是否显示码单', related='product_id.package_list_visible', default=False)
    pcs = fields.Integer('件数', help='用于计算荒料毛板时候输入件数', default=0)

    @api.onchange('product_id')
    def _onchange_package_list_visible(self):
        if self.product_id:
            self.package_list_visible = self.product_id.package_list_visible

    @api.depends('package_list_id.slab_ids.qty', 'package_list_id.slab_ids')
    def _compute_qty(self):
        for record in self:
            if record.product_id.product_tmpl_id.product_stone_type == 'slab':
                if record.package_list_id:
                    # record.product_uom_qty = len(record.package_list_id.slab_ids)
                    record.qty = sum(record.package_list_id.mapped('slab_ids.qty'))
                    # record.product_uom_qty = record.pcs
                else:
                    # record.product_uom_qty = 0
                    record.qty = 0
                    # record.product_uom_qty = record.pcs

            elif record.product_id.product_tmpl_id.product_stone_type == 'pbom':
                # record.product_uom_qty = record.pcs
                record.qty = record.lot_id.qty * record.pcs
                # record.product_uom_qty = record.pcs

            else:
                record.product_uom_qty = 1
                record.qty = record.lot_id.product_block_id.cost_qty
                # record.product_uom_qty = record.pcs

    # def _set_qty(self):
    #     for record in self:
    #         if record.product_id.product_stone_type == 'pbom':
    #             record.pcs = record.product_uom_qty
    # else:
    #     record.pcs = len(record.package_list_id.slab_ids)

    # product_uom_qty = fields.Float(readonly=True, compute='_compute_product_qty', store=True)

    def _update_reserved_quantity(self, need, available_quantity, location_id, lot_id=None, package_id=None,
                                  owner_id=None, strict=True):
        self.ensure_one()
        lot_id = self.lot_id or None
        return super(StockMove, self)._update_reserved_quantity(need, available_quantity, location_id,
                                                                lot_id=lot_id, package_id=None, owner_id=None,
                                                                strict=True)

    @api.onchange('product_id')
    def _onchange_product_id_set_lot_domain(self):
        available_lot_ids = []
        if self.picking_id.location_id and self.product_id:
            location = self.picking_id.location_dest_id
            quants = self.env['stock.quant'].read_group([
                ('product_id', '=', self.product_id.id),
                ('location_id', 'child_of', location.id),
                ('lot_id', '!=', False), ],
                ['lot_id'], 'lot_id'
            )
            available_lot_ids = [quant['lot_id'][0] for quant in quants]
        self.lot_id = False
        return {
            'domain': {'lot_id': [('id', 'in', available_lot_ids)]}
        }

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        # 以下为了在采购订单时候存入lot_id
        res = super(StockMove, self)._prepare_move_line_vals(quantity=quantity, reserved_quant=reserved_quant)
        if not res.get('lot_id', False) and self.lot_id and (
                self.picking_type_id.use_create_lots or self.picking_type_id.use_existing_lots) and self.location_id.usage in (
                'supplier', 'inventory', 'production', 'customer'):
            res['lot_id'] = self.lot_id.id
        if not res.get('pcs', False):
            res['pcs'] = self.pcs
        return res

    def _split(self, qty, restrict_partner_id=False):
        # 把move_line_ids的码单取出,在context传入,在新建的move的码单中剔除已提货的slab
        remove_package_list_ids = False
        for move in self:
            remove_package_list_ids = move.move_line_ids.filtered(lambda r: r.package_list_id).mapped(
                'package_list_id.id')

        return super(StockMove, self.with_context(remove_package_list_ids=remove_package_list_ids))._split(qty,
                                                                                                           restrict_partner_id=restrict_partner_id)

    def _action_done(self):
        moves = super(StockMove, self)._action_done()
        done_slab_ids = moves.mapped('move_line_ids').filtered(lambda r: r.package_list_id).package_list_id.mapped(
            'slab_ids')
        for move in moves:
            if move.package_list_id:
                slab_ids = move.package_list_id.mapped('slab_ids')
                slab_ids &= done_slab_ids
                move.package_list_id.write({'slab_ids': [(6, 0, slab_ids.mapped('id'))]})
        return moves

    @api.model
    def create(self, vals):
        if vals.get('package_list_id', False):
            package = self.env['package.list']
            # 如果是提货后续move,就剔除已提货码单包含的slab
            remove_package_list_ids = self._context.get('remove_package_list_ids', False)
            slab_ids_list = self.env['product.slab']._get_available_slab(lot_id=vals.get('lot_id'),
                                                                         location_id=vals.get('location_id'),
                                                                         package_list_id=vals.get('package_list_id'),
                                                                         remove_package_list_ids=remove_package_list_ids)
            package_list = package.browse(vals['package_list_id']).copy(default={'slab_ids': [(6, 0, slab_ids_list)]})
            vals.update({'package_list_id': package_list.id})
        return super(StockMove, self).create(vals)

    @api.multi
    def action_show_package_list(self):
        self.ensure_one()
        if self.product_id:
            if self.product_id.product_tmpl_id.product_stone_type != 'slab':
                return {}
        ctx = self.env.context.copy()
        ctx.update({
            'res_model': self._name,
            'res_id': self.id,
            'default_lot_id': self.lot_id.id,
            'default_product_id': self.product_id.id,
        })
        if self.package_list_id:
            res_model = 'package.list'
            res_id = self.package_list_id.id
            ctx['search_default_group_part_num'] = True
            ctx['domain_slab_ids'] = self.env['product.slab']._get_available_slab(location_id=self.location_id.id,
                                                                                  lot_id=self.lot_id.id,
                                                                                  package_list_id=self.package_list_id.id)
        else:
            ctx['product_id'] = self.product_id.id
            ctx['search_default_group_part_num'] = True
            ctx['location_id'] = self.location_id.id
            res_model = 'package.list.wizard'
            res_id = False

        return {
            'name': 'package list',
            'res_model': res_model,
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': res_id,
            'target': 'new',
            'src_model': 'sale.order.line',
            'context': ctx
        }


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    package_list_id = fields.Many2one('package.list', '码单')
    qty_done = fields.Float('提货件数', compute='_compute_qty', inverse='_set_qty', store=True)
    qty = fields.Float('提货数量', readonly=True, compute='_compute_qty', store=True)
    part = fields.Integer('提货夹数', related='package_list_id.part', store=True)
    pcs = fields.Integer('件数', help='用于计算荒料毛板时候输入件数', default=0)
    uom = fields.Selection(selection=(('t', 't'), ('m3', 'm3'), ('m2', 'm2')), string='计价单位', related='lot_id.uom',
                           readonly=True)
    # product_uom_qty = fields.Float(string='件数', compute='_compute_product_qty', inverse='_set_product_qty', store=True)
    package_list_visible = fields.Boolean('是否显示码单', related='product_id.package_list_visible', default=False)

    @api.onchange('product_id')
    def _onchange_package_list_visible(self):
        if self.product_id:
            self.package_list_visible = self.product_id.package_list_visible

    @api.depends('package_list_id.slab_ids.qty', 'package_list_id.slab_ids')
    def _compute_qty(self):
        for record in self:
            if record.product_id.product_stone_type == 'slab':
                if record.package_list_id:
                    record.qty_done = len(record.package_list_id.slab_ids)
                    record.qty = sum(record.package_list_id.mapped('slab_ids.qty'))
                    # record.qty_done = record.pcs
                else:
                    record.qty_done = 0
                    record.qty = 0
                    # record.qty_done = record.pcs

            elif record.product_id.product_stone_type == 'pbom':
                record.qty_done = record.pcs
                record.qty = record.lot_id.qty * record.pcs
                # record.qty_done = record.pcs

            else:
                record.qty_done = 1
                record.qty = record.lot_id.product_block_id.cost_qty
                # record.qty_done = record.pcs

    def _set_qty(self):
        for record in self:
            if record.product_id.product_stone_type == 'pbom':
                record.pcs = record.qty_done
            # else:
            #     record.pcs = len(record.package_list_id.slab_ids)

    def _action_done(self):
        super(StockMoveLine, self)._action_done()
        for ml in self:
            slab_ids = ml.filtered(lambda r: r.package_list_id).mapped('package_list_id.slab_ids')
            slab_ids._move_done(location_id=ml.location_dest_id, is_reserved=False)

    @api.multi
    def action_show_package_list(self):
        self.ensure_one()
        if self.product_id and self.product_id.product_stone_type != 'slab':
            return {}

        ctx = self.env.context.copy()

        if self.move_id.package_list_id:
            ctx['domain_slab_ids'] = self.env['product.slab']._get_available_slab(location_id=self.location_id.id,
                                                                                  lot_id=self.lot_id.id,
                                                                                  package_list_id=self.move_id.package_list_id.id)
        res_id = self.package_list_id.id if self.package_list_id else False
        name = '码单' if self.package_list_id else '新建码单'

        ctx.update({
            'res_model': self._name,
            'res_id': self.id,
            'default_lot_id': self.lot_id.id,
            'default_product_id': self.product_id.id,
        })

        return {
            'name': name,
            'res_model': 'package.list',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': res_id,
            'context': ctx,
        }
