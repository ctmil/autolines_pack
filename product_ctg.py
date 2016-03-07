# -*- coding: utf-8 -*-
from openerp import fields, models


class Product_Ctg(models.Model):
    _inherit = 'product.category'

    # Add a new column to the product.category model
    # to be able to link Auto Line rules to the selected Product Category.

    rule_ids = fields.One2many('autoline.autoline', 'product_ctg_id',  string="Auto Line Rules", readonly=True)
