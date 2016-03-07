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

from openerp import models, fields, api, exceptions
from openerp.tools.translate import _
from openerp.osv import osv
import math
import logging
import re

_logger = logging.getLogger(__name__)


class sale_order_line(models.Model):
    _inherit = 'sale.order.line'

    is_autoline = fields.Boolean('Is a Auto Line', default=False)


class sale_order(models.Model):
    _inherit = 'sale.order'

    autoline_weight = fields.Float('Autoline weight', digits=(6, 2))
    product_owner_id = fields.Many2one('res.partner', string="Product Owner")
    first_article = fields.Boolean('FAR', default=False)

    @api.multi
    def autoline_run(self, so_id):
        if not so_id:
            so_id = self.id
        so_id = self.id

        if self.state in ('done', 'cancel', 'manual', 'progress'):
            return

        if self.state not in ('draft','sent'):
            raise osv.except_osv('Quote / SO not in Draft State!'),('The Quote or SO must be in draft to run Auto Lines!')
            return

        # Get the input values to run the Auto Lines procedure
        customer_id = self.partner_id.id
        product_owner_id = self.product_owner_id.id
        line_prod_id = 0
        product_ctg_id = 0
        supplier_id = 0
        weight = 0
        del_tot = 0
        # traverse the order lines, but we want the first line that is the PCB in question
        # Should in a later version use a filter to be sure we get correct item by using product category.
        # supports only one product per Quote.
        for line in self.order_line:
            line_prod_id = line.product_id.id
            # Get the product and supplier id and product category
            product_ctg = line.product_id #self.env['product.template'].search([('id', '=', line_prod_id)])
            del_tot = line.product_id.sale_delay #self.env['product.template'].search([('id', '=', line_prod_id)]).sale_delay
            product_ctg_id = line.product_id.categ_id.id #product_ctg.categ_id.id
            product_sup = line.product_id.seller_ids #self.env['product.supplierinfo'].search([('product_tmpl_id', '=', line_prod_id)])
            if len(product_sup) == 1 or self.selected_supplier is None:
                supplier_id = product_sup.name.id
            else:
                supplier_id = self.selected_supplier.id

            q = line.product_uom_qty
            # the weight field is not the correct one, problem extending the Sale Order model with a new autoline_weight field.
            break

        # get the Auto Lines used by these objects.
        customer_autolines_obj = self.env['autoline.autoline'].search([('customer_id', '=', customer_id), ('active', '=', True), ('sales_purchase', '=', True)])
        _logger.info('%s Customer Autolines', len(customer_autolines_obj))
        if len(customer_autolines_obj) > 0:
            self._check_rule(customer_autolines_obj, customer_id, supplier_id, line_prod_id, product_ctg_id, q, weight, line)

        product_ctg_autolines_obj = self.env['autoline.autoline'].search([('product_ctg_id', '=', product_ctg_id), ('active', '=', True), ('sales_purchase', '=', True)])
        _logger.info('%s Product CTG Autolines', len(product_ctg_autolines_obj))
        if len(product_ctg_autolines_obj) > 0:
            self._check_rule(product_ctg_autolines_obj, customer_id, supplier_id, line_prod_id, product_ctg_id, q, weight, line)

        product_autolines_obj = self.env['autoline.autoline'].search([('product_id', '=', line_prod_id), ('sales_purchase', '=', True)])
        _logger.info('%s Product Autolines', len(product_autolines_obj))
        if len(product_autolines_obj) > 0:
            self._check_rule(product_autolines_obj, customer_id, supplier_id, line_prod_id, product_ctg_id, q, weight, line)

        company_wide_autolines_obj = self.env['autoline.autoline'].search([('active', '=', True), ('company_wide', '=', True), ('sales_purchase', '=', True)])
        _logger.info('%s Company Wide Autolines', len(company_wide_autolines_obj))
        if len(company_wide_autolines_obj) > 0:
            self._check_rule(company_wide_autolines_obj, customer_id, supplier_id, line_prod_id, product_ctg_id, q, weight, line)

        # this one is a special one...
        supplier_name = self.env['res.partner'].browse(supplier_id).name
	if not supplier_name:
		return None
	# Control 1 King Brother Limited
	list_words = ['king','brother','technology']
	control1 = True
	for list_word in list_words:
		if not list_word in supplier_name.lower():
			control1 = False
	# Control 2 WMD
	list_words = ['wmd','circuits']
	control2 = True
	for list_word in list_words:
		if not list_word in supplier_name.lower():
			control2 = False

	if (not control1) and (not control2):
		supplier_autolines_obj = self.env['autoline.autoline'].search([('supplier_id', '=', supplier_id),\
				 ('active', '=', True), ('sales_purchase', '=', True)])
	else:
		if control1:
			suppliers = self.env['res.partner'].search([('name','ilike','KING BROTHER')])
		else:
			suppliers = self.env['res.partner'].search([('name','ilike','WMD CIRCUITS')])
		supplier_ids = []
		for supplier in suppliers:
			supplier_ids.append(supplier.id)
		for supplier_id in supplier_ids:
			supplier_autolines_obj = self.env['autoline.autoline'].search([('supplier_id', '=', supplier_id),\
				 ('active', '=', True), ('sales_purchase', '=', True)])
			if supplier_autolines_obj:
				break
		if not supplier_autolines_obj:
			return None
		

        _logger.info('%s Special Supplier AutoLines', len(supplier_autolines_obj))
        for autolines_obj in supplier_autolines_obj:
            res = False
            for rule in autolines_obj.rule_ids:
                if not rule.active is True:
                    continue
                _logger.info('Autoline %s, running rule %s', autolines_obj.name, rule.name)
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
                elif model.model == 'sale.order':
                    obj = self.env[model.model].search([(field, operator, value_to_check), ('id', '=', self.id)])
                else:
                    obj = None
                _logger.info('Model: %s , Field: %s , Operator: %s , Value to Check: %s , Result: %s', str(model.model), field, operator, value_to_check, str(len(obj) > 0))
                #_logger.info('OBJ: %s %s', obj, len(obj) > 0)
                print "OBJ:", obj, len(obj) > 0
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
                #sku_del = sku.sale_delay
                line_exists = self.order_line.search([('product_id', '=', sku_id), ('order_id', '=', self.id)])
                # print "Sku already added", line_exists, len(line_exists) == 0
                if len(line_exists) == 0:
                    # computation on SKU
                    if autolines_obj.sku_option == 'multiply':
                        self.order_line.create({'order_id': self.id, 'product_id': sku_id, 'is_autoline': True, 'product_uom_qty': q, 'delay': autolines_obj.sku_id.sale_delay,'out_delay': autolines_obj.sku_id.sale_delay})
                    elif autolines_obj.sku_option == 'special':
                        i_s = autolines_obj.supplier_id.name.lower()
			# Control 1 King Brother Limited
			list_words = ['king','brother','technology']
			control1 = True
			for list_word in list_words:
				if not (re.search(r'(.*) '+list_word+' (.*)',i_s) or re.search(r''+list_word+' (.*)',i_s)):
					control1 = False
			# Control 2 WMD
			list_words = ['wmd','circuits']
			control2 = True
			for list_word in list_words:
				if not (re.search(r'(.*) '+list_word+' (.*)',i_s) or re.search(r''+list_word+' (.*)',i_s)):
					control2 = False
		
                        _logger.info('Special: %s ', i_s)
                        weight = math.ceil(weight)
                        if weight > 50:
                            basis = 49
                            rest = weight - 50
                        else:
                            basis = weight - 1
                            rest = 0
                        #if i_s == 'KING BROTHER TECHNOLOGY LIMITED (NT)':
                        if control1:
			    # before
                            # kg1 = 6.5
                            # kg2to50 = 0.65
                            # kg_plus = 0.52
			    kg1 = 2.3
			    kg2to50 = 0.77
			    kg_plus = 0.77
                        # elif i_s == 'WMD CIRCUITS LIMITED':
                        elif control2:
			    # before
                            # kg1 = 2.3
                            # kg2to50 = 0.77
                            # kg_plus = 0.77
			    kg1 = 6.5
			    kg2to50 = 0.65
			    kg_plus = 0.52
                        else:
                            _logger.info('Unknown supplier %s weight: %s', i_s, weight)
                            print "Unknown supplier", i_s, weight
                            break
                        comp_price = kg1 + (basis * kg2to50) + (rest * kg_plus)
			if self.pricelist_id.currency_id.name != self.company_id.currency_id.name:
				comp_price = comp_price * self.pricelist_id.currency_id.rate_silent
                        print "For ", weight, " kilos, freight to be charged: ", comp_price
                        self.order_line.create({'order_id': self.id, 'product_id': sku_id, 'is_autoline': True, 'product_uom_qty': 1,  'price_unit': comp_price})
                    elif autolines_obj.sku_option == 'manual_lt':
                        return {'name': 'Input Lead Time',
                                'view_type': 'form',
                                'view_mode': 'form',
                                'view_id': self.pool.get('ir.ui.view').search([('name','=','Input Lead Time')])[0],
                                'res_model': 'manual.input.lead.time',
                                'type': 'ir.actions.act_window',
                                }
                    else:
                        self.order_line.create({'order_id': self.id, 'product_id': sku_id, 'is_autoline': True, 'product_uom_qty': 1,  'delay': autolines_obj.sku_id.sale_delay,'out_delay': autolines_obj.sku_id.sale_delay})
        _logger.info('Special Supplier - Done')

        # changed from product.template to product.product, might do that for alle the line creates in the code
	# creates product pack
	name_pack = self.name + '#' + line.product_id.ntty_id
        info_prd_id = self.env['product.product'].search([('name', '=', 'info:')]).id
        info_prod_id = self.env['product.product'].search([('name', '=', name_pack)])
	if not info_prod_id:
		vals_product = {
			'name': self.name + '#'  + line.product_id.ntty_id,
			'is_pack': True,
			'type': 'product',
			'uom_id': 1,
			'default_code': self.name + '#' + line.product_id.ntty_id
			}
		info_prod_id = self.env['product.product'].create(vals_product)

        # count the total delay of the order
        del_tot = 0
        o_lines = self.order_line.search([('order_id', '=', self.id)])
        for x in o_lines:
	    if x.product_id.ntty_id:
	            # del_tot = del_tot + x.out_delay
	            del_tot = del_tot + x.calculated_leadtime
	    else:
	            del_tot = del_tot + x.delay

        #self.order_line.create({'order_id': self.id, 'product_id': info_prod_id, 'description': 'info', 'price_unit': 0.00, 'name': 'The total lead time for this order will be ' + "{0:.0f}".format(del_tot) + ' days!', 'product_uom_qty': 0})
	vals_pack = {
		'description': 'The total leadtime for this order will be ' + "{0:.0f}".format(del_tot) + ' days!',
		'product_quantity': 0,
		'price': 0,
		'wk_product_template': info_prod_id.product_tmpl_id.id,	
		'product_name': info_prd_id,	
		}
	self.env['product.pack'].create(vals_pack)
        # get the number of the PCB ordered.
        q = 1
        for line in self.order_line:
	    if line.product_id.product_tmpl_id.ntty_id != '':
	            q = line.product_uom_qty
            break
	if q > 0:
	        # self.order_line.create({'order_id': self.id, 'product_id': info_prod_id, 'description': 'info', 'price_unit': 0.00, 'name': 'The total price per unit is: ' + "{0:.2f}".format(self.amount_total/q), 'product_uom_qty': 0})
		vals_pack = {
			'description': 'The total price per unit is: ' + "{0:.2f}".format(self.amount_total/q),
			'product_quantity': 0,
			'price': 0,
			'wk_product_template': info_prod_id.product_tmpl_id.id,	
			'product_name': info_prd_id,	
			}
		self.env['product.pack'].create(vals_pack)
	else:
	        # self.order_line.create({'order_id': self.id, 'product_id': info_prod_id, 'description': 'info', 'price_unit': 0.00, 'name': 'The total price per unit is: ' + "{0:.2f}".format(self.amount_total), 'product_uom_qty': 0})
		vals_pack = {
			'name': 'The total price per unit is: ' + "{0:.2f}".format(self.amount_total),
			'product_quantity': 0,
			'price': 0,
			'wk_product_template': info_prod_id.product_tmpl_id.id,	
			'product_name': info_prd_id,	
			}
		self.env['product.pack'].create(vals_pack)
	
        _logger.info('Comments - Done')
        #self._add_todo_lines

    @api.multi
    def _check_rule(self, autoline_objects, customer_id, supplier_id, line_prod_id, product_ctg_id, q, weight, line = None):
        res = False
        #current_obj = None
        for current_obj in autoline_objects:
            res = False
            for rule in current_obj.rule_ids:
                if not rule.active is True:
                    continue
                _logger.info('Autoline %s, running rule %s', current_obj.name, rule.name)
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
                        _logger.info('Model: %s , Model entity; %s , Field: %s , Operator: %s , Value to Check: %s , Result: %s', str(model.model), self.env[str(model.model)].search([('id', '=', customer_id)]).name, field.name, operator, value_to_check, str(len(obj) > 0))
                    except ValueError:
                        _logger.info('Error occured checking rule name %s in autoline %s', rule.name, current_obj.name)
                        print 'Error occured checking rule name ', rule.name, ' in auto line ', current_obj.name

                elif model.model == 'res.partner' and partner_subset == 'supplier':
                    try:
                        obj = self.env[str(model.model)].search([(str(field.name), str(operator), str(value_to_check)), ('id', '=', supplier_id)])
                        _logger.info('Model: %s , Model entity; %s , Field: %s , Operator: %s , Value to Check: %s , Result: %s', str(model.model), self.env[str(model.model)].search([('id', '=', supplier_id)]).name, field.name, operator, value_to_check, str(len(obj) > 0))
                    except ValueError:
                        _logger.info('Error occured checking rule name %s in autoline %s', rule.name, current_obj.name)
                        print 'Error occured checking rule name ', rule.name, ' in auto line ', current_obj.name

                elif model.model == 'product.template':
                    try:
                        obj = self.env[str(model.model)].search([(str(field.name), str(operator), str(value_to_check)), ('id', '=', line_prod_id)])
                        _logger.info('Model: %s , Model entity; %s , Field: %s , Operator: %s , Value to Check: %s , Result: %s', str(model.model), self.env[str(model.model)].search([('id', '=', line_prod_id)]).name, field.name, operator, value_to_check, str(len(obj) > 0))
                    except ValueError:
                        _logger.info('Error occured checking rule name %s in autoline %s', rule.name, current_obj.name)
                        print 'Error occured checking rule name ', rule.name, ' in auto line ', current_obj.name

                elif model.model == 'product.category':
                    try:
                        obj = self.env[str(model.model)].search([(str(field.name), str(operator), str(value_to_check)), ('id', '=', product_ctg_id)])
                        _logger.info('Model: %s , Model entity; %s , Field: %s , Operator: %s , Value to Check: %s , Result: %s', str(model.model), self.env[str(model.model)].search([('id', '=', product_ctg_id)]).name, field.name, operator, value_to_check, str(len(obj) > 0))
                    except ValueError:
                        _logger.info('Error occured checking rule name %s in autoline %s', rule.name, current_obj.name)
                        print 'Error occured checking rule name ', rule.name, ' in auto line ', current_obj.name

                elif model.model == 'sale.order':
                    try:
                        obj = self.env[str(model.model)].search([(str(field.name), str(operator), str(value_to_check)), ('id', '=', self.id)])
                        _logger.info('Model: %s , Model entity; %s , Field: %s , Operator: %s , Value to Check: %s , Result: %s', str(model.model), self.env[str(model.model)].search([('id', '=', self.id)]).id, field.name, operator, value_to_check, str(len(obj) > 0))
                    except ValueError:
                        _logger.info('Error occured checking rule name %s in autoline %s', rule.name, current_obj.name)
                        print 'Error occured checking rule name ', rule.name, ' in auto line ', current_obj.name

                else:
                    obj = None

		if not obj:
		    res = False
		    break
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
                _logger.info('DEBUG: SKU added: ID %s, NAME %s, DELAY %s', current_obj.sku_id.id, current_obj.sku_id.name, current_obj.sku_id.sale_delay)
                sku_id = current_obj.sku_id.id
                #sku_del = self.env['product.template'].search([('id', '=', sku_id)]).sale_delay
                # line_exists = self.order_line.search([('product_id', '=', sku_id), ('order_id', '=', self.id)])
		info_prod_id = self.env['product.product'].search([('name','=',self.name + '#' + line.product_id.ntty_id)])
		if not info_prod_id:
	                vals_product = {
				'name': self.name + '#'  + line.product_id.ntty_id,
				'is_pack': True,
				'type': 'product',
				'uom_id': 1,
				'default_code': self.name + '#' + line.product_id.ntty_id
				}
			info_prod_id = self.env['product.product'].create(vals_product)

                # computation on SKU
                #if current_obj.sku_option == 'multiply':
                #	vals_pack = {
		#		'order_id': self.id, 
		#		'product_id': sku_id, 
		#		'is_autoline': True, 
		#		'product_uom_qty': q, 
		#		'delay': current_obj.sku_id.sale_delay,
		#		'out_delay': current_obj.sku_id.sale_delay}
                #       _logger.info('DEBUG: Sale Delay is: %s', current_obj.sku_id.sale_delay)
                #        #self.env.invalidate_all()
		#
                #elif current_obj.sku_option == 'manual_lt':
                #        mlt = True
                #	print "Autolines - Manual Lead Time Input Required"
		#       self.order_line.create({'order_id': self.id, 'product_id': sku_id, 'is_autoline': True, 'product_uom_qty': 1, 'delay': current_obj.sku_id.sale_delay,'out_delay': current_obj.sku_id.sale_delay})
                #        _logger.info('DEBUG: Sale Delay is: %s', current_obj.sku_id.sale_delay)
                #else:
                #        l_id = self.order_line.create({'order_id': self.id, 'product_id': sku_id, 'is_autoline': True, 'product_uom_qty': 1, 'delay': current_obj.sku_id.sale_delay,'out_delay': current_obj.sku_id.sale_delay})
		
                #_logger.info('DEBUG: Sale Delay is: %s ', str(current_obj.sku_id.sale_delay))
                vals_pack = {
                         'description': current_obj.sku_id.name,
                         'product_quantity': 1,
                         'price': 0,
                         'wk_product_template': info_prod_id.product_tmpl_id.id,
                         'product_name': sku_id,
			 'delay': current_obj.sku_id.sale_delay,
                         }
                self.env['product.pack'].create(vals_pack)

                #self.env.commit()

        if not current_obj is None:
            print "Done with ", current_obj.name
        else:
            print "No rules to apply"




class manual_input_lead_time(models.Model):
    _name = 'manual.input.lead.time'

    lead_time_input = fields.Integer(store=False)

    @api.one
    def input_lead_time(self):
        #if context.get('active_model') == 'sale.order.line':
        print "hei"




