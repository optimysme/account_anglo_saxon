# -*- coding: utf-8 -*-
from odoo import models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _get_computed_account(self):
        # this overrides stock_account which does an
        # OVERRIDE to use the stock input account by default on vendor bills when dealing
        # with anglo-saxon accounting.
        # but if this invoice is not from a stock receipt then we should just use the normal expense account
        # NOTE - enterprise module account_predictive _bills OVERRIDES this logic so can give unexpected results

        self.ensure_one()
        if not self.purchase_line_id:
            fiscal_position = self.move_id.fiscal_position_id
            accounts = self.product_id.product_tmpl_id.get_product_accounts(fiscal_pos=fiscal_position)
            if self.move_id.is_sale_document(include_receipts=True):
                # Out invoice.
                return accounts['income']
            elif self.move_id.is_purchase_document(include_receipts=True):
                # In invoice.
                return accounts['expense']

        return super(AccountMoveLine, self)._get_computed_account()
