#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by pbpoon on 2018/1/23

from odoo import models, fields, api, exceptions


class PackageList(models.Model):
    _name = 'package.list'

    name = fields.Char('码单名称', compute='_compute_total', store=True)
    lot_id = fields.Many2one('stock.production.lot', '编号', required=True, readonly=True)
    product_id = fields.Many2one('product.product', '产品规格', required=True, index=True, readonly=True,
                                 domain=[('product_tmpl_id.product_stone_type', '=', 'sale')])
    slab_ids = fields.Many2many('product.slab',
                                string='板材规格')  # relation='package_slab', column1='package_list_id', column2='slab_id',

    qty = fields.Float('数量', compute='_compute_total', store=True, readonly=True)
    part = fields.Integer('夹数', compute='_compute_total', store=True, readonly=True)
    pcs = fields.Integer('件数', compute='_compute_total', store=True, readonly=True)
    uom = fields.Many2one(
        'product.uom', '单位',
        readonly="1", help="This comes from the product form.")
    state = fields.Selection([
        ('draft', 'New'), ('cancel', 'Cancelled'),
        ('done', 'Done')], string='Status',
        copy=True, default='draft', index=True, readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super(PackageList, self).default_get(fields_list)
        # if 'state' in self._context:
        #     res['state'] = self._context.get('state')
        return res

    @api.onchange('slab_ids')
    def _onchange_slab_ids(self):
        self.ensure_one()
        self.update({
            'qty': sum(self.slab_ids.mapped('qty')),
            'pcs': len(self.slab_ids),
            'part': len(set(self.slab_ids.mapped('part_num'))),
        })

    @api.depends('slab_ids')
    def _compute_total(self):
        for record in self:
            qty = sum(record.mapped('slab_ids.qty'))
            part = len(set(record.mapped('slab_ids.part_num')))
            pcs = len(record.slab_ids)
            name = '{}/{}夹/{}件/{}m2'.format(record.lot_id.name, part, pcs, qty)

            record.update({
                'qty': qty,
                'part': part,
                'pcs': pcs,
                'name': name,
            })

    @api.multi
    def _get_res_model(self):
        res_model = self._context.get('res_model', False)
        res_id = self._context.get('res_id', False)
        if res_model and res_id:
            return self.env[res_model].browse(res_id)

        raise ValueError('错误的创建!')

    @api.model
    def create(self, vals):
        res = super(PackageList, self).create(vals)
        if self._context.get('res_model', False):
            self._get_res_model().write({'package_list_id': res.id})
        return res

    @api.multi
    def choice_slab(self):
        action = self.env.ref('sale_select_lots.product_slab_action').read()[0]
        # action['target'] = 'new'
        # action['model_type'] = 'tree'
        # action['view_id'] = 'sale_select_lots.product_slab_tree_view'
        # action['search_view_id'] = 'sale_select_lots.product_slab_search_view'
        action['domain'] = [('lot_id', '=', self.lot_id.id),
                            ('id', 'in', list(range(120)))]
        return action

    @api.multi
    def clear_slab(self):
        self.ensure_one()
        if self.state in ['cancel', 'done']:
            return {}
        res_id = self.id
        self.write({'slab_ids': [(5, False, False)]})
        return {
            'name': 'package list',
            'res_model': 'package.list',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': res_id,
            'context': self._context,
        }

    @api.multi
    def _set_done(self):
        self.write({'state': 'done'})

    @api.multi
    def _set_draft(self):
        self.write({'state': 'draft'})

    @api.multi
    def _set_reserved(self):
        self.mapped('slab_ids').write({'is_reserved': True})

    @api.multi
    def _set_unreserved(self):
        self.mapped('slab_ids').write({'is_reserved': False})



#
# class PackageLine(models.Model):
#     _name = 'package.line'
#     _order = 'part_num, sequence'
#
#     name = fields.Char('名称', compute='_compute_name', store=True)
#     package_list_id = fields.Many2one('package.list', '码单id', required=True, ondelete='cascade')
#     slab_id = fields.Many2one('product.slab', '板材', required=True)
#
#     line_id = fields.Many2one('package_line', '码单')
#     long = fields.Integer('长', related='slab_id.long', store=True)
#     height = fields.Integer('高', related='slab_id.height', store=True)
#     kl1 = fields.Integer('扣迟长', related='slab_id.kl1', store=True)
#     kh1 = fields.Integer('扣迟高', related='slab_id.kh1', store=True)
#     kl2 = fields.Integer('扣迟2长', related='slab_id.kl2', store=True)
#     kh2 = fields.Integer('扣迟2高2', related='slab_id.kh2', store=True)
#     qty = fields.Float('数量', compute='_compute_total', store=True)
#
#     part_num = fields.Integer('夹#', default=1)
#     num = fields.Integer('#', related='sequence')
#     sequence = fields.Integer('sequence', default=10)
#
#     # @api.onchange('is_choice')
#     # def onchange_is_choice(self):
#     #     self.ensure_one()
#     #     lines = self.package_list_id.line_ids.filtered(lambda r: r.is_choice)
#     #     qty = sum(lines.mapped('qty'))
#     #     pcs = len(lines)
#     #     part = len(set(lines.mapped('part_num')))
#     #     self.package_list_id.update({'c_qty': qty, 'c_pcs': pcs, 'c_part': part})
#
#     @api.depends('long', 'height', 'kl1', 'kh1', 'kl2', 'kh2', 'slab_id')
#     def _compute_total(self):
#         for record in self:
#             m2 = record.long * record.height * 0.0001
#             if record.kl1 and record.kh1:
#                 k1m2 = record.kl1 * record.kh1 * 0.0001
#                 m2 = m2 - k1m2
#             if record.kl2 and record.kh2:
#                 k2m2 = record.kl2 * record.kh2 * 0.0001
#                 m2 = m2 - k2m2
#             record.qty = m2
#
#     @api.onchange('lot_id')
#     def _onchange_lot_id(self):
#         for record in self:
#             record.update({
#                 'long': record.slab_id.long,
#                 'height': record.slab_id.height,
#                 'kl1': record.slab_id.kl1,
#                 'kh1': record.slab_id.kh1,
#                 'kl2': record.slab_id.kl2,
#                 'kh2': record.slab_id.kh2,
#                 'part_num': record.slab_id.part_num,
#                 'sequence': record.slab_id.sequence,
#             })
