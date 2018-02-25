#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by pbpoon on 2018/1/23

from odoo import models, fields, api, exceptions


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.multi
    def _action_confirm(self):
        for order in self:
            for order_line in order.order_line:
                if order_line.product_id.product_stone_type == 'slab' and not order_line.package_list_id:
                    raise exceptions.ValidationError('产品{}/编号:{},没有销售码单,不能通过确认!'.format(order_line.product_id.name,
                                                                                        order_line.lot_id.name))
        super(SaleOrder, self)._action_confirm()
        for order in self:
            for order_line in order.order_line:
                if order_line.package_list_id:
                    package_list = order.order_line.mapped('package_list_id')
                    package_list._set_done()
                    package_list._set_reserved()

    @api.multi
    def action_cancel(self):
        super(SaleOrder, self).action_cancel()
        for order in self:
            for order_line in order.order_line:
                if order_line.package_list_id:
                    package_list = order.order_line.mapped('package_list_id')
                    package_list._set_done()
                    package_list._set_unreserved()

    @api.multi
    def action_draft(self):
        super(SaleOrder, self).action_draft()
        for order in self:
            for order_line in order.order_line:
                if order_line.package_list_id:
                    package_list = order.order_line.mapped('package_list_id')
                    package_list._set_draft()
                    package_list._set_unreserved()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    lot_id = fields.Many2one('stock.production.lot', '批次号', ondelete='restrict', required=True)
    package_list_id = fields.Many2one('package.list', '码单', ondelete='set null')
    product_uom_qty = fields.Float(string='件数', compute='_compute_qty', inverse='_set_qty', store=True)
    qty = fields.Float('数量', compute='_compute_qty', store=True)
    part = fields.Integer('夹数', related='package_list_id.part', store=True)
    package_list_visible = fields.Boolean('是否显示码单', related='product_id.package_list_visible', default=False)
    pcs = fields.Integer('件数', help='用于计算荒料毛板时候输入件数', default=0)
    uom = fields.Selection(selection=(('t', 't'), ('m3', 'm3'), ('m2', 'm2')), string='计价单位', related='lot_id.uom',
                           readonly=True)

    @api.depends('qty_invoiced', 'qty_delivered', 'qty', 'order_id.state')
    def _get_to_invoice_qty(self):
        """
        Compute the quantity to invoice. If the invoice policy is order, the quantity to invoice is
        calculated from the ordered quantity. Otherwise, the quantity delivered is used.
        """
        for line in self:
            if line.order_id.state in ['sale', 'done']:
                if line.product_id.invoice_policy == 'order':
                    line.qty_to_invoice = line.qty - line.qty_invoiced
                else:
                    line.qty_to_invoice = line.qty - line.qty_invoiced
            else:
                line.qty_to_invoice = 0

    @api.depends('qty')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.qty, product=line.product_id,
                                            partner=line.order_id.partner_shipping_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    @api.multi
    def _prepare_procurement_values(self, group_id=False):
        res = super(SaleOrderLine, self)._prepare_procurement_values(group_id=group_id)
        if self.lot_id:
            res['lot_id'] = self.lot_id.id
        if self.package_list_id:
            res['package_list_id'] = self.package_list_id.id
        if self.pcs:
            res['pcs'] = self.pcs
        return res

    # @api.multi
    # def _action_launch_procurement_rule(self):
    #     res = super(SaleOrderLine, self)._action_launch_procurement_rule()
    #     for line in res:
    #         self.package_list_id.write({'state': 'done'})
    #     return res

    @api.onchange('product_id')
    def _onchange_package_list_visible(self):
        if self.product_id:
            self.package_list_visible = self.product_id.package_list_visible

    @api.onchange('product_id')
    def _onchange_product_id_set_lot_domain(self):
        available_lot_ids = []
        if not self.product_id:
            return {}
        if self.order_id.warehouse_id and self.product_id:
            location = self.order_id.warehouse_id.lot_stock_id
            quants = self.env['stock.quant'].read_group([
                ('product_id', '=', self.product_id.id),
                ('location_id', 'child_of', location.id),
                ('lot_id', '!=', False), ],
                ['lot_id'], 'lot_id'
            )
            available_lot_ids = [quant['lot_id'][0] for quant in quants]
            available_lot_ids = [lot.id for lot in self.env['stock.production.lot'].browse(available_lot_ids) if
                                 lot.available_qty > 0]
            # for i in available_lot_ids:
            #     if i.available_qty>0
        self.lot_id = False
        return {
            'domain': {'lot_id': [('id', 'in', available_lot_ids)]}
        }

    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        res = super(SaleOrderLine, self).product_id_change()
        if self.product_id:
            self.product_uom_qty = 0
        return res

    @api.onchange('package_list_id', 'qty')
    def _onchange_package_list_id(self):
        self.qty = sum(self.package_list_id.mapped('slab_ids.qty'))
        self.product_uom_qty = len(self.package_list_id)

    @api.depends('package_list_id.slab_ids.qty', 'package_list_id.slab_ids')
    def _compute_qty(self):
        for record in self:
            if record.product_id.product_tmpl_id.product_stone_type == 'slab':
                if record.package_list_id:
                    record.product_uom_qty = len(record.package_list_id.slab_ids)
                    record.qty = sum(record.package_list_id.mapped('slab_ids.qty'))
                    # record.product_uom_qty = record.pcs
                else:
                    record.product_uom_qty = 0
                    record.qty = 0
                    # record.product_uom_qty = record.pcs

            elif record.product_id.product_tmpl_id.product_stone_type == 'pbom':
                record.product_uom_qty = record.pcs
                record.qty = record.lot_id.qty * record.pcs
                # record.product_uom_qty = record.pcs

            else:
                record.product_uom_qty = 1
                record.qty = record.lot_id.product_block_id.cost_qty
                # record.product_uom_qty = record.pcs

    def _set_qty(self):
        for record in self:
            if record.product_id.product_stone_type == 'pbom':
                record.pcs = record.product_uom_qty
            # else:
            #     record.pcs = len(record.package_list_id.slab_ids)

    @api.multi
    def _get_available_slab(self):
        if self.order_id.warehouse_id.lot_stock_id:
            lotaction = self.order_id.warehouse_id.lot_stock_id
            lot = self.lot_id
        slab_ids_lst = self.env['product.slab']._get_available_slab(location_id=lotaction.id, lot_id=lot.id)
        return slab_ids_lst

    @api.multi
    def action_show_package_list(self):
        self.ensure_one()
        if self.product_id:
            if self.product_id.product_tmpl_id.product_stone_type != 'slab':
                return {}

        res_id = False
        if self.package_list_id:
            res_id = self.package_list_id.id

        ctx = self.env.context.copy()
        ctx.update({
            'res_model': self._name,
            'res_id': self.id,
            'default_lot_id': self.lot_id.id,
            'default_product_id': self.product_id.id,

        })
        ctx['domain_slab_ids'] = self._get_available_slab()
        return {
            'name': 'package list',
            'res_model': 'package.list',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': res_id,
            'context': ctx,
        }
