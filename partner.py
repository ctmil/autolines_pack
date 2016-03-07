# -*- coding: utf-8 -*-
from openerp import fields, models, _


class Partner(models.Model):
    _inherit = 'res.partner'

    # Add a new column to the res.partner model
    # to be able to link Auto Line rules to the selected partner.

    rule_ids = fields.One2many('autoline.autoline', 'partner_id',  string="Auto Line Rules", readonly=True)
    product_owner = fields.Boolean(string = _('Partner is a product owner'), default=False)
    #Military = fields.Boolean(string="Military", default=False, help="The partner is Military")
    #Automotive = fields.Boolean(string="Automotive", default=False, help="The partner is Automotive")

