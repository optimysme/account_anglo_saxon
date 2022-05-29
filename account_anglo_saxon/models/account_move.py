# -*- coding: utf-8 -*-
from odoo import models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        if self.env.context.get('move_date', None):
            for move in self:
                move.date = self.env.context['move_date']
        return super(AccountMove, self)._post(soft)

    @api.model_create_multi
    def create(self, values):
        # done as try to avoid any unknown cases as move posting used in lots of places
        for i, vals in enumerate(values):
            if not vals.get('ref', None):
                if vals.get('line_ids', None):
                    try:
                        first_line = vals['line_ids'][0][2]
                        if first_line.get('name', None):
                            vals['ref'] = first_line['name']
                    except:
                        pass
        return super(AccountMove, self).create(values)

    def _stock_account_prepare_anglo_saxon_out_lines_vals(self):
        """
        Need to cater for a financial invoice or credit
        In this case there is no anglo-saxon entry as never an offsetting stock move
        """

        lines_vals_list = super(AccountMove, self)._stock_account_prepare_anglo_saxon_out_lines_vals()
        if not lines_vals_list:
            return lines_vals_list
        moves_to_remove = []
        for move in self:
            if not move.is_sale_document(include_receipts=True):
                continue
            # if this move is related to a sale order then happy to keep
            sale_line_ids = self.mapped('line_ids').filtered(lambda l: l.sale_line_ids)
            if not sale_line_ids:
                moves_to_remove.append(move)

        # therefore anything else is a financial invoice only
        for move in moves_to_remove:
            index_to_delete = 0
            for i in range(len(lines_vals_list)):
                if lines_vals_list[index_to_delete]['move_id'] == move.id:
                    del lines_vals_list[index_to_delete]
                else:
                    index_to_delete += 1
        return lines_vals_list

    def _reverse_moves(self, default_values_list=None, cancel=False):
        """
        for a financial credit remove the source sale order reference so no anglo-saxon entries created
        as will never be an offsetting stock move
        """
        reverse_moves = super(AccountMove, self)._reverse_moves(default_values_list=default_values_list, cancel=cancel)
        for move in reverse_moves:
            # Workaround removed dependency on sale orders
            if hasattr(move, 'sale_orders'):
                move.sale_orders = False
            if hasattr(move.line_ids[0], 'sale_line_ids'):
                move.line_ids.sale_line_ids = False
        return reverse_moves

    def _reverse_move_vals(self, default_values, cancel=True):
        """
        for a financial credit for a purchase, check if the source GL account is the stock input
        and if so make expense as there will never be an offsetting stock move
        added line from stock.account as always want to remove anglo-saxon lines - bug logged with Odoo
        """
        move_vals = super(AccountMove, self)._reverse_move_vals(default_values, cancel=cancel)
        move_vals['line_ids'] = [vals for vals in move_vals['line_ids'] if not vals[2]['is_anglo_saxon_line']]
        for line in move_vals.get('line_ids', None):
            if line[2] and line[2].get('purchase_line_id', None) and line[2].get('product_id'):
                fiscal_position = self.fiscal_position_id
                product = self.env['product.product'].browse(line[2].get('product_id'))
                accounts = product.product_tmpl_id.get_product_accounts(fiscal_pos=fiscal_position)
                if line[2]['account_id'] == accounts['stock_input'].id:
                    line[2]['account_id'] = accounts['expense'].id

        return move_vals
