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

    pack_id = fields.Many2one('product.product',string='Pack')

    @api.multi
    def autoline_sol_run(self):
        so_id = self.order_id.id

        if self.order_id.state in ('done', 'cancel', 'manual', 'progress'):
            return

        if self.order_id.state not in ('draft','sent'):
            raise osv.except_osv('Quote / SO not in Draft State!','The Quote or SO must be in draft to run Auto Lines!')
            return

        if not self.product_id.ntty_id:
            raise osv.except_osv('Error!','Product must be a PCB in order to create a pack!')
            return



        # Get the input values to run the Auto Lines procedure
        customer_id = self.order_id.partner_id.id
        product_owner_id = self.order_id.product_owner_id.id
        line_prod_id = 0
        product_ctg_id = 0
        supplier_id = 0
        weight = 0
        del_tot = 0
	line = self
	product_weight = self.product_id.weight
	sqm_pcb = self.product_id.sqm_pcb
        # traverse the order lines, but we want the first line that is the PCB in question
        # Should in a later version use a filter to be sure we get correct item by using product category.
        # supports only one product per Quote.
        line_prod_id = line.product_id.id
        # Get the product and supplier id and product category
        product_ctg = line.product_id #self.env['product.template'].search([('id', '=', line_prod_id)])
        del_tot = line.product_id.sale_delay #self.env['product.template'].search([('id', '=', line_prod_id)]).sale_delay
        product_ctg_id = line.product_id.categ_id.id #product_ctg.categ_id.id
        product_sup = line.product_id.seller_ids #self.env['product.supplierinfo'].search([('product_tmpl_id', '=', line_prod_id)])
        if len(product_sup) == 1 or self.order_id.selected_supplier is None:
        	supplier_id = product_sup.name.id
        else:
                supplier_id = self.order_id.selected_supplier.id

        q = line.product_uom_qty

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

        # changed from product.template to product.product, might do that for alle the line creates in the code
	# creates product pack
	# name_pack = self.order_id.name + '#' + line.product_id.ntty_id + '#' + str(line.id)
	name_pack = line.product_id.product_tmpl_id.name + '#' + str(line.product_uom_qty) + '#' + str(line.leadtime) + '#' + self.order_id.name
        info_prd_id = self.env['product.product'].search([('name', '=', 'info:')])
	info_prd_id = info_prd_id[0].id
        info_prod_id = self.env['product.product'].search([('name', '=', name_pack),('active','=',False)])
	if not info_prod_id:
		vals_product = {
			'active': False,
			'name': name_pack,
			'is_pack': True,
			'type': 'service',
			'uom_id': 1,
			'default_code': self.name + '#' + line.product_id.ntty_id,
			'weight': product_weight,
			'sqm_pcb': sqm_pcb,
			'taxes_id': [(6,0,[])],
			'supplier_taxes_id': [(6,0,[])],
			'categ_id': 1,
			}
		info_prod_id = self.env['product.product'].create(vals_product)
	        vals_pack = {
        	        'description': line.product_id.name,
                	'product_quantity': line.product_uom_qty,
	                'price': line.price_unit,
        	        'wk_product_template': info_prod_id.product_tmpl_id.id,
                	'product_name': line.product_id.id,
	                }
        	self.env['product.pack'].create(vals_pack)


        # get the number of the PCB ordered.
        q = 1
        for line in self.order_id.order_line:
	    if line.product_id.product_tmpl_id.ntty_id != '':
	            q = line.product_uom_qty
            break
	if q > 0:
	        # self.order_line.create({'order_id': self.id, 'product_id': info_prod_id, 'description': 'info', 'price_unit': 0.00, 'name': 'The total price per unit is: ' + "{0:.2f}".format(self.amount_total/q), 'product_uom_qty': 0})
		vals_pack = {
			'description': 'The total price per unit is: ' + "{0:.2f}".format(self.order_id.amount_total/q),
			'product_quantity': 1,
			'price': 0,
			'wk_product_template': info_prod_id.product_tmpl_id.id,	
			'product_name': info_prd_id,	
			}
		self.env['product.pack'].create(vals_pack)
	else:
	        # self.order_line.create({'order_id': self.id, 'product_id': info_prod_id, 'description': 'info', 'price_unit': 0.00, 'name': 'The total price per unit is: ' + "{0:.2f}".format(self.amount_total), 'product_uom_qty': 0})
		vals_pack = {
			'name': 'The total price per unit is: ' + "{0:.2f}".format(self.order_id.amount_total),
			'product_quantity': 1,
			'price': 0,
			'wk_product_template': info_prod_id.product_tmpl_id.id,	
			'product_name': info_prd_id,	
			}
		self.env['product.pack'].create(vals_pack)
	
        _logger.info('Comments - Done')
	vals = {
		'pack_id': info_prod_id.id,
		}
	self.write(vals)
	return info_prod_id.id
        #self._add_todo_lines

    @api.multi
    def _check_rule(self, autoline_objects, customer_id, supplier_id, line_prod_id, product_ctg_id, q, weight, line = None):
        res = False
	product_weight = self.product_id.weight
	sqm_pcb = self.product_id.sqm_pcb
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

                elif model.model == 'sale.order.line':
                    try:
                        #obj = self.env[str(model.model)].search([(str(field.name), str(operator), str(value_to_check)), ('id', '=', self.id)])
			obj = None
			if str(field.name) == 'categ_id':
				categ_ids = self.env['product.category'].search([('name','ilike',str(value_to_check))])
				if categ_ids:
					for categ_id in categ_ids:
						if categ_id.id == self.categ_id.id:
							obj = self
			if str(field.name) == 'product_brand_id':
				brand_ids = self.env['product.brand'].search([('name','ilike',str(value_to_check))])
				if brand_ids:
					for brand_id in brand_ids:
						if brand_id.id == self.product_brand_id.id:
							obj = self
                        #_logger.info('Model: %s , Model entity; %s , Field: %s , Operator: %s , Value to Check: %s , Result: %s', str(model.model), self.env[str(model.model)].search([('id', '=', self.id)]).id, field.name, operator, value_to_check, str(len(obj) > 0))
                    except ValueError:
                        _logger.info('Error occured checking rule name %s in autoline %s', rule.name, current_obj.name)
                        print 'Error occured checking rule name ', rule.name, ' in auto line ', current_obj.name
                elif model.model == 'sale.order':
                    try:
                        obj = self.env[str(model.model)].search([(str(field.name), str(operator), str(value_to_check)), ('id', '=', self.order_id.id)])
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
		namepack = self.product_id.product_tmpl_id.name + '#' + str(self.product_uom_qty) + '#' + str(self.leadtime) + '#' + self.order_id.name
		info_prod_id = self.env['product.product'].search([('name','=',namepack),('active','=',False)])
		if not info_prod_id:
	                vals_product = {
				'active': False,
				'name': namepack,
				'is_pack': True,
				'type': 'service',
				'uom_id': 1,
				'default_code': namepack,
				'weight': product_weight,
				'sqm_pcb': sqm_pcb,
				'taxes_id': [(6,0,[])],
				'supplier_taxes_id': [(6,0,[])],
				'categ_id': 1,
				}
			info_prod_id = self.env['product.product'].create(vals_product)
	                vals_pack = {
        	                'description': line.product_id.name,
                	        'product_quantity': line.product_uom_qty,
                        	'price': line.price_unit,
	                        'wk_product_template': info_prod_id.product_tmpl_id.id,
        	                'product_name': line.product_id.id,
                	        }
	                self.env['product.pack'].create(vals_pack)

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



