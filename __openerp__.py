# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


{
    'name': 'Auto Lines Pack',
    'version': '0.1',
    'category': 'Sales Management',
    'description': """
Allows you to add rules that can add order lines to a Sales Order or Quotation.
================================================================================

You can define your own rules on customers, suppliers Product categories and products that when
run will result in lines added to the Sales Order.
""",
    'author': 'Tinderbox AS',
    'website': "http://www.tinderbox.no",
    'depends': ['base', 'crm', 'sale', 'product','elmatica_partner'],
    'data': [
        # 'security/ir.model.access.csv',
        'views/autolines.xml',
        'views/partner.xml',
        'views/saleorder.xml',
        #'views/purchaseorder.xml',
        'views/product_category.xml',
        'views/product.xml',
        #'views/manual_leadtime_view.xml'
    ],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'images': ['icon.png'],
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
