from odoo import models, api, fields


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    """
    done this WAY to avoid a dependency on sale. Sets links between invoice lines and move and move lines
    """

    def reverse_moves(self):
        action = super(AccountMoveReversal, self).reverse_moves()
        moves = False
        if action.get('domain', None):
            domain = action.domain
            moves = self.env['account.move'].search(domain)
        elif action.get('res_id', None):
            moves = self.env['account.move'].browse(action['res_id'])

        if moves:
            for move in moves:
                if hasattr(move, 'sale_orders'):
                    move.sale_orders = False
                if hasattr(move.line_ids[0], 'sale_line_ids'):
                    move.line_ids.sale_line_ids = False
        return action
