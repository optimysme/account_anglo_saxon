# -*- coding: utf-8 -*-
from odoo import models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _get_product_accounts(self):
        """
        Consult res.company:stock_[input|output]_account as ultimate fallback.
        """
        accounts = super(ProductTemplate, self)._get_product_accounts()
        if not accounts.get("stock_input", False):
            accounts["stock_input"] = self.company_id.stock_input_account
        if not accounts.get("stock_output", False):
            accounts["stock_output"] = self.company_id.stock_output_account
        return accounts
