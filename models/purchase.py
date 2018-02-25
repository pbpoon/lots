#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by pbpoon on 2018/1/23

from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    import_product_line_id = fields.Many2one('product.create.order', string=u'导入产品明细行')

    @api.onchange('import_product_line_id')
    def onchange_import_product_line_id(self):
        if not self.import_product_line_id:
            return {}
        new_lines = self.env['purchase.order.line']
        for line in self.import_product_line_id.order_line_ids:
            data = {'product_id': line.product_id.id,
                    'lot_id': line.lot_id.id,
                    'price_unit': line.unit_price,
                    'qty': line.lot_id.product_block_id.cost_qty}
            new_line = new_lines.new(data)
            new_lines += new_line
        self.order_line += new_lines
        self.import_product_line_id = False
        for line in self.order_line:
            line.onchange_product_id()
        return {}


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # product_block_number_id = fields.Many2one('product.block.number', '荒料编号', required=True)
    lot_id = fields.Many2one('stock.production.lot', '荒料编号', required=True, ondelete='restrict')
    # product_block_number_id = fields.Many2one('product.block.number', '荒料编号', required=True)
    qty = fields.Float('计价数量', related='lot_id.product_block_id.cost_qty', store=True)
    uom = fields.Selection(selection=(('t', 't'), ('m3', 'm3')), related='lot_id.product_block_id.cost_uom', store=True,
                           readonly=True)

    @api.multi
    def _prepare_stock_moves(self, picking):
        res = super(PurchaseOrderLine, self)._prepare_stock_moves(picking)
        if self.lot_id:
            res[0]['lot_id'] = self.lot_id.id
        return res
