# -*- coding: utf-8 -*-
from odoo import http

# class SaleSelectLost(http.Controller):
#     @http.route('/sale_select_lost/sale_select_lost/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/sale_select_lost/sale_select_lost/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('sale_select_lost.listing', {
#             'root': '/sale_select_lost/sale_select_lost',
#             'objects': http.request.env['sale_select_lost.sale_select_lost'].search([]),
#         })

#     @http.route('/sale_select_lost/sale_select_lost/objects/<model("sale_select_lost.sale_select_lost"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('sale_select_lost.object', {
#             'object': obj
#         })