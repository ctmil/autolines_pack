# -*- coding: utf-8 -*-
from openerp import fields, models


class Product(models.Model):
    _inherit = 'product.template'

    # Add new columns to the product.category model
    # to be able to link Auto Line rules to the selected Product Category.
    # and added a color selection that will be used to distinguish different types of order lines on the Quote / Sales order

    rule_ids = fields.One2many('autoline.autoline', 'product_id',  string="Auto Line Rules", readonly=True)
    # product_owner_id = fields.Many2one('res.partner', string="Product Owner", domain=[('product_owner', '=', True)])
    # product_owner_id = fields.Many2one('res.partner', string="Product Owner")
