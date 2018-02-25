# -*- coding: utf-8 -*-
{
    'name': "sale_select_lost",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['sale', 'stock', 'purchase','procurement_jit', 'sale_stock'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/product_block_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/product_slab_views.xml',
        'views/production_lot.xml',
        'views/product_block_number_views.xml',
        'views/purchase_views.xml',
        'views/product_views.xml',
        'wizard/package_list_wizard_views.xml',
        'views/package_list_views.xml',
        'views/stock_quant_views.xml',

    ],
    # only loaded in demonstration mode
    'demo': [
        # 'demo/demo.xml',
    ],
}
