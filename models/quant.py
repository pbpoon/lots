# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    slab_ids = fields.One2many('product.slab', compute='_compute_slab_ids', string='可售板材')
    reserved_slab_ids = fields.One2many('product.slab', compute='_compute_slab_ids', string='锁货板材')
    qty = fields.Float('数量', compute='_compute_qty', store=True)
    uom = fields.Selection(selection=(('t', 't'), ('m3', 'm3'), ('m2', 'm2')), default='m2',
                           string='单位', related='lot_id.uom',
                           readonly="1")
    reserved_qty = fields.Float('预留数量', compute='_compute_qty', store=True)

    @api.depends('location_id', 'lot_id')
    def _compute_slab_ids(self):
        slab = self.env['product.slab']
        for record in self:
            record.slab_ids = slab.search(
                [('lot_id', '=', record.lot_id.id), ('location_id', 'child_of', record.location_id.id),
                 ('is_reserved', '=', False)])
            record.reserved_slab_ids = slab.search(
                [('lot_id', '=', record.lot_id.id), ('location_id', 'child_of', record.location_id.id),
                 ('is_reserved', '=', True)])

    @api.depends('lot_id.qty', 'quantity')
    def _compute_qty(self):
        for record in self:
            if record.product_id.product_stone_type == 'slab':
                record.qty = sum(record.slab_ids.mapped('qty'))
                record.reserved_qty = sum(record.reserved_slab_ids.mapped('qty'))

            # elif record.product_id.product_stone_type == 'pbom':
            #     record.qty = record.lot_id.qty*
            else:
                record.qty = record.quantity * record.lot_id.qty
                record.qty = record.reserved_quantity * record.lot_id.qty
