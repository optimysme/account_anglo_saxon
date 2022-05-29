# -*- coding: utf-8 -*-
from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.company'

    stock_input_account = fields.Many2one(comodel_name='account.account', string='Received Not Invoiced Account')
    stock_output_account = fields.Many2one(comodel_name='account.account', string='Dispatched Not Invoiced Account')
    price_variance_account = fields.Many2one(comodel_name='account.account', string='Price Variance Account')
    max_writeoff = fields.Integer(string='Maximum Write-Off')
    write_off_journal = fields.Many2one(comodel_name='account.journal', string='Journal')
    anglo_saxon_report_user = fields.Many2one(comodel_name='res.users',
                                              string='Reports Recipient for scheduled anglo-saxon reconcile')
