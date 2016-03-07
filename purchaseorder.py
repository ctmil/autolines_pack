# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#    Author of this funny thing is André Grant, Tinderbox AS
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

from openerp import models, fields, api, exceptions, osv
from datetime import datetime, timedelta
import math

class purchase_order_line(models.Model):
    _inherit = 'purchase.order.line'

    is_autoline = fields.Boolean('Is a Auto Line', default=False)


class purchase_order(models.Model):
    _inherit = 'purchase.order'

    autoline_weight = fields.Float('Autoline weight', digits=(6, 2))
    customer_id = fields.Many2one('res.partner', string="Final Customer", domain=[('customer', '=', True)])


    @api.multi
    def autoline_purchase_run(self):

        if self.state not in ('draft','sent','bid'):
            raise osv.except_osv('Quote / PO not in Draft State!'),('The Quote or PO must be in draft to run Auto Lines!')
            return
        # Get the input values to run the Auto Lines procedure
        supplier_id = self.partner_id.id
        # final customer id
        customer_id = self.customer_id.id
        line_prod_id = 0
        product_ctg_id = 0
        weight = 0
        del_tot = 0
        # traverse the order lines, but we want the first line that is the PCB in question
        # Should in a later version use a filter to be sure we get correct item by using product category.
        # supports only one product per Quote.


        q = None
        for line in self.order_line:
            if not line.product_id.product_tmpl_id.ntty_id:
                continue

            line_prod_id = line.product_id.id
            # Get the product and supplier id and product category
            product_ctg = self.env['product.template'].search([('id', '=', line_prod_id)])
            del_tot = self.env['product.template'].search([('id', '=', line_prod_id)]).sale_delay
            product_ctg_id = product_ctg.categ_id.id
            # product_sup = self.env['product.supplierinfo'].search([('product_tmpl_id', '=', line_prod_id)])
            # supplier_id = product_sup.name.id
            q = line.product_qty
            weight = product_ctg.weight * q
            # the weight field is not the correct one, problem extending the Sale Order model with a new autoline_weight field.
            self.autoline_weight = weight
            break

        # get the Auto Lines used by these objects.
        customer_autolines_obj = self.env['autoline.autoline'].search([('customer_id', '=', customer_id), ('active', '=', True), ('sales_purchase', '=', False)])
        if len(customer_autolines_obj) > 0:
            self._check_rule(customer_autolines_obj, customer_id, supplier_id, line_prod_id, product_ctg_id, q, weight)

        product_ctg_autolines_obj = self.env['autoline.autoline'].search([('product_ctg_id', '=', product_ctg_id), ('active', '=', True), ('sales_purchase', '=', False)])
        if len(product_ctg_autolines_obj) > 0:
            self._check_rule(product_ctg_autolines_obj, customer_id, supplier_id, line_prod_id, product_ctg_id, q, weight)

        product_autolines_obj = self.env['autoline.autoline'].search([('product_id', '=', line_prod_id), ('sales_purchase', '=', False)])
        if len(product_autolines_obj) > 0:
            self._check_rule(product_autolines_obj, customer_id, supplier_id, line_prod_id, product_ctg_id, q, weight)

        company_wide_autolines_obj = self.env['autoline.autoline'].search([('active', '=', True), ('company_wide', '=', True), ('sales_purchase', '=', False)])
        if len(company_wide_autolines_obj) > 0:
            self._check_rule(company_wide_autolines_obj, customer_id, supplier_id, line_prod_id, product_ctg_id, q, weight)


        # this one is a special one...
        supplier_autolines_obj = self.env['autoline.autoline'].search([('supplier_id', '=', supplier_id), ('active', '=', True), ('sales_purchase', '=', False)])
        for autolines_obj in supplier_autolines_obj:
            res = False
            for rule in autolines_obj.rule_ids:
                if not rule.active is True:
                    continue
                operator = rule.operator
                value_to_check = rule.chk_value
                field = rule.model_field.name
                model = rule.model_id
                if rule.model_subset is False:
                    rule.model_subset == 'customer'

                partner_subset = rule.model_subset
                if model.model == 'res.partner' and partner_subset == 'customer':
                    obj = self.env[model.model].search([(field, operator, value_to_check), ('id', '=', customer_id)])
                elif model.model == 'res.partner' and partner_subset == 'supplier':
                    obj = self.env[model.model].search([(field, operator, value_to_check), ('id', '=', supplier_id)])
                elif model.model == 'product.template':
                    obj = self.env[model.model].search([(field, operator, value_to_check), ('id', '=', line_prod_id)])
                elif model.model == 'product.category':
                    obj = self.env[model.model].search([(field, operator, value_to_check), ('id', '=', product_ctg_id)])
                elif model.model == 'purchase.order':
                    obj = self.env[model.model].search([(field, operator, value_to_check), ('id', '=', self.id)])
                else:
                    obj = None
                print "OBJ?", obj, len(obj) > 0
                if len(obj) > 0:
                    # Rule was True
                    res = True
                else:
                    # if more than rule is applied for the same Autoline the rules are AND'ed together.
                    # This means that if one rule fails, the result is False
                    res = False
                    break
            if res:
                # do not add lines that are already added
                sku_id = autolines_obj.sku_id.id
                sku = self.env['product.template'].search([('id', '=', sku_id)])
                sku_del = sku.sale_delay
                line_exists = self.order_line.search([('product_id', '=', sku_id), ('order_id', '=', self.id)])
                print "Sku already added", line_exists, len(line_exists) == 0
                if len(line_exists) == 0:
                    # computation on SKU
                    if autolines_obj.sku_option == 'multiply':
                        self.order_line.create({'name': sku.name, 'order_id': self.id, 'product_id': sku_id, 'is_autoline': True, 'date_planned': datetime.today(), 'product_uom_qty': q, 'price_unit': sku.price, 'delay': sku_del,'is_autoline': True})
                    elif autolines_obj.sku_option == 'special':
                        i_s = autolines_obj.supplier_id.name
                        weight = math.ceil(weight)
                        if weight > 50:
                            basis = 49
                            rest = weight - 50
                        else:
                            basis = weight - 1
                            rest = 0
                        if i_s == 'KBC':
                            kg1 = 6.5
                            kg2to50 = 0.65
                            kg_plus = 0.52
                        elif i_s == 'WMD':
                            kg1 = 2.3
                            kg2to50 = 0.77
                            kg_plus = 0.77
                        else:
                            print "Unknown supplier", i_s, weight
                            quit()
                        comp_price = kg1 + (basis * kg2to50) + (rest * kg_plus)
                        print "For ", weight, " kilos, freight to be charged: ", comp_price
                        self.order_line.create({'name': sku.name, 'order_id': self.id, 'product_id': sku_id, 'is_autoline': True, 'date_planned': datetime.today(), 'product_uom_qty': 1,  'price_unit': comp_price, 'is_autoline': True})

                    else:
                        self.order_line.create({'name': sku.name, 'order_id': self.id, 'product_id': sku_id, 'is_autoline': True, 'date_planned': datetime.today(), 'product_uom_qty': 1, 'price_unit': sku.price, 'delay': sku_del, 'is_autoline': True})
	for line in self.order_line:
		if not line.product_id.product_tmpl_id.ntty_id or line.product_id.product_tmpl_id.ntty_id == '':
			# Product is not a PCB
			vals = {
				'leadtime': 0,
				}
			line.write(vals)
        print "Supplier - Done"

    @api.multi
    def _check_rule(self, autoline_objects, customer_id, supplier_id, line_prod_id, product_ctg_id, q, weight):
        res = False
        #current_obj = None
        for current_obj in autoline_objects:
            res = False
            for rule in current_obj.rule_ids:
                if not rule.active is True:
                    continue
                operator = rule.operator
                value_to_check = rule.chk_value
                field = rule.model_field
                model = rule.model_id
                if rule.model_subset is False:
                    rule.model_subset == 'customer'

                partner_subset = rule.model_subset
                if model.model == 'res.partner' and partner_subset == 'customer':
                    try:
                        obj = self.env[str(model.model)].search([(str(field.name), str(operator), str(value_to_check)), ('id', '=', customer_id)])
                    except ValueError:
                        print 'Error occured checking rule name ', rule.name, ' in auto line ', current_obj.name

                elif model.model == 'res.partner' and partner_subset == 'supplier':
                    try:
                        obj = self.env[str(model.model)].search([(str(field.name), str(operator), str(value_to_check)), ('id', '=', supplier_id)])
                    except ValueError:
                        print 'Error occured checking rule name ', rule.name, ' in auto line ', current_obj.name

                elif model.model == 'product.template':
                    try:
                        obj = self.env[str(model.model)].search([(str(field.name), str(operator), str(value_to_check)), ('id', '=', line_prod_id)])
                    except ValueError:
                        print 'Error occured checking rule name ', rule.name, ' in auto line ', current_obj.name

                elif model.model == 'product.category':
                    try:
                        obj = self.env[str(model.model)].search([(str(field.name), str(operator), str(value_to_check)), ('id', '=', product_ctg_id)])
                    except ValueError:
                        print 'Error occured checking rule name ', rule.name, ' in auto line ', current_obj.name

                elif model.model == 'purchase.order':
                    try:
                        obj = self.env[str(model.model)].search([(str(field.name), str(operator), str(value_to_check)), ('id', '=', self.id)])
                    except ValueError:
                        print 'Error occured checking rule name ', rule.name, ' in auto line ', current_obj.name

                else:
                    obj = None

                if obj:
			if len(obj) > 0:
	                    # Rule was True
        	            res = True
			else:
			    res = False
			    break
                else:
                    # if more than rule is applied for the same Autoline the rules are AND'ed together.
                    # This means that if one rule fails, the result is False
                    res = False
                    break
            if res:
                # do not add lines that are already added
                sku_id = current_obj.sku_id.id
                sku_del = self.env['product.template'].search([('id', '=', sku_id)]).sale_delay
                line_exists = self.order_line.search([('product_id', '=', sku_id), ('order_id', '=', self.id)])
                print "Sku already added", line_exists, len(line_exists) == 0
                if len(line_exists) == 0:
                    # computation on SKU
                    if current_obj.sku_option == 'multiply':
                        # self.order_line.create({'name': current_obj.name,'order_id': self.id, 'product_id': sku_id, 'is_autoline': True, 'date_planned': datetime.today(), 'product_uom_qty': q, 'price_unit': current_obj.price, 'delay': sku_del})
                        self.order_line.create({'name': current_obj.name,'order_id': self.id, 'product_id': sku_id, 'is_autoline': True, 'date_planned': datetime.today(), 'product_uom_qty': q, 'price_unit': current_obj.sku_id.standard_price, 'delay': sku_del, 'is_autoline': True})
                    else:
                        # self.order_line.create({'name': current_obj.name, 'order_id': self.id, 'product_id': sku_id, 'is_autoline': True, 'date_planned': datetime.today(), 'product_uom_qty': 1, 'price_unit': current_obj.price, 'delay': sku_del})
                        self.order_line.create({'name': current_obj.name, 'order_id': self.id, 'product_id': sku_id, 'is_autoline': True, 'date_planned': datetime.today(), 'product_uom_qty': 1, 'price_unit': current_obj.sku_id.standard_price, 'delay': sku_del, 'is_autoline': True})

        if not current_obj is None:
            print "Done with ", current_obj.name
        else:
            print "No rules to apply"
