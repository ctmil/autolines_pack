# -*- coding: utf-8 -*-

# Auto Lines Models
from openerp import models, fields, api, exceptions


class AutoLine(models.Model):
    _name = 'autoline.autoline'

    name = fields.Char(string="Title", required=True)
    description = fields.Text()

    active = fields.Boolean(default=True)
    company_wide = fields.Boolean(string="Company Wide Rule", default=False)
    partner_id = fields.Integer()
    supplier_id = fields.Many2one('res.partner', string="Supplier",
                                  domain=[('supplier', '=', True)], readonly=False)
    customer_id = fields.Many2one('res.partner', string="Customer",
                                  domain=[('customer', '=', True)], readonly=False)
    product_ctg_id = fields.Many2one('product.category', string="Product Category", readonly=False)
    product_id = fields.Many2one('product.product', string="Product", readonly=False)
    sku_id = fields.Many2one('product.product', required=True, string="Action", help="The line that is added to the Quote")
    sku_option = fields.Selection([('multiply', 'Multiply'), ('percentage', 'Percentage'), ('special', 'KBC/WMD freight calc'), ('manual_lt', 'User Lead Time')],
                                  string="Select an Action option",
                                  help="If the Action added should be a function of the product sold")
    sku_option_value = fields.Char(string="Percentage", help="A value between 0.00 and 1.00")
    rule_ids = fields.One2many('autoline.rule', 'rule_id', string="Rules")
    sales_purchase = fields.Boolean(string="Sales or Purchase", default=True,
                                    help="If True Then Sales, False then Purchase")


    @api.one
    @api.depends('customer_id', 'supplier_id')
    def _check_supplier_customer(self):
        if len(self.customer_id) > 0:
            self.write({'partner_id': self.customer_id})
        if len(self.supplier_id) > 0:
            self.write({'partner_id': self.supplier_id})

    @api.one
    def grid_get_customer(self, cr, uid, customer_id, context=None):
        customer = self.pool.get('res.partner').browse(cr, uid, customer_id, context=context)
        for autoline in self.browse(customer, context=context):
            for grid in autoline.rule_ids:
                get_id = lambda x: x.id
                return grid.id
        return False

    @api.one
    def copy(self, default=None):
        default = dict(default or {})

        copied_count = self.search_count(
            [('name', '=like', u"Copy of {}%".format(self.name))])
        if not copied_count:
            new_name = u"Copy of {}".format(self.name)
        else:
            new_name = u"Copy of {} ({})".format(self.name, copied_count)

        default['name'] = new_name
        return super(AutoLine, self).copy(default)


class Rule(models.Model):
    _name = 'autoline.rule'

    rule_id = fields.Many2one('autoline.autoline', ondelete='cascade', string="Auto Line", required=True)
    name = fields.Char(string="Name", required=False)
    active = fields.Boolean(default=True)
    model_id = fields.Many2one('ir.model', string="Related Document Model",
                               required=True, domain=['|', ('model', '=', 'res.partner'), '|',
                                                      ('model', '=', 'product.template'), '|',
                                                      ('model', '=', 'product.category'), '|',
                                                      ('model', '=', 'sale.order'), ('model', '=', 'purchase.order')])
    model_subset = fields.Selection([('customer', 'Customer'), ('supplier', 'Supplier'), ('product_owner', 'Product Owner')],
                                    string="Type of Partner",
                                    help="If Partner model is selected, please select a type of partner option, otherwise type defaults to Customer")
    model_field = fields.Many2one('ir.model.fields', string="Field", domain="[('model_id', '=', model_id)]", required=True, readonly=False)
    operator = fields.Selection([('=', '='), ('<=', '<='), ('<', '<'), ('>=', '>='), ('>', '>'), ('!=', '!='),('ilike','Contains')],
                                string="Operator", required=True)
    chk_value = fields.Char(required=True, string="Value")

