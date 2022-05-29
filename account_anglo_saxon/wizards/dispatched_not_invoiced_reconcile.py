# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import pytz
from datetime import timedelta
import xlsxwriter
from io import BytesIO as StringIO
import base64
import logging

log = logging.getLogger(__name__)


class DispatchedNotInvoicedReconcile(models.TransientModel):
    _name = 'account.anglo.saxon.dni.reconcile'
    _description = 'Anglo Saxon Reconciliation for Dispatched Not Invoiced'

    as_at_date = fields.Date(string='Up To Date', help='Leave blank for today')
    account = fields.Many2one(comodel_name='account.account', string='Dispatched Not invoiced Account',
                              default=lambda self: self.env.company.stock_output_account.id)
    print_report = fields.Boolean(string='Create Report', default=False)
    data = fields.Binary('Download File', readonly=True)
    report_name = fields.Char(size=64, string='Report Name', readonly=False)

    def _get_stock_move_filter_date(self):
        """
        Convert the as_at_date to a UTC date time.
        """
        local_tz = pytz.timezone(self.env.user.sudo().tz)
        end_datetime = (fields.Datetime.from_string(self.as_at_date) + timedelta(days=1))
        end_datetime = local_tz.localize(end_datetime)
        end_datetime = end_datetime.astimezone(pytz.UTC)
        return end_datetime

    def add_reconcile_to_lines(self, lines):
        name = self.env['ir.sequence'].next_by_code('account.reconcile')
        if not name:
            name = 'Anglo'
        reconcile_id = self.env['account.full.reconcile'].sudo().create({'name': name})

        for line in lines:
            line.write({'full_reconcile_id': reconcile_id.id,
                        'matching_number': reconcile_id.name,
                        'reconciled': True})

    def process(self):
        log.info('Starting at {now}'.format(now=fields.Datetime.now()))
        prec = self.env["decimal.precision"].precision_get('accounting')
        if not self.account:
            raise UserError('Set up the account on the company record or enter manually before running')
        if not self.as_at_date:
            self.as_at_date = fields.Date.context_today(self)

        # first we check that all items reconciled in the account have debits=credits and unreconcile if any exceptions

        sql_select = """
        SELECT full_reconcile_id from account_move_line where account_id = {account} and 
        date <= '{date}' and parent_state = 'posted' group by full_reconcile_id having sum(debit-credit) != 0.0
        """
        self.env.cr.execute(sql_select.format(account=self.account.id ,date=self.as_at_date))
        log.info('SQL Executed at {now}'.format(now=fields.Datetime.now()))
        recs = self.env.cr.fetchall()
        log.info('Fetchall completed at {now} with {count} results'.format(now=fields.Datetime.now(), count=len(recs)))
        if recs and recs[0] and recs[0][0]:
            for i in range(0, len(recs)):
                reconcile_id = recs[i][0]
                account_move_lines = self.env['account.move.line'].search([('full_reconcile_id', '=', reconcile_id)])
                account_move_lines.write({'full_reconcile_id': False, 'reconciled': False, 'matching_number': False})

        log.info('Completed check of reconciliations at {now}'.format(now=fields.Datetime.now()))

        account_move_lines = self.env['account.move.line'].search([('account_id', '=', self.account.id),
                                                                   ('full_reconcile_id', '=', False),
                                                                   ('date', '<=', self.as_at_date),
                                                                   ('parent_state', '=', 'posted')])

        processed_lines = []
        counter = 0
        max_count = len(account_move_lines)
        for line in account_move_lines:
            log.info('Up to {counter} of {max_count}'.format(counter=counter, max_count=max_count))
            counter += 1
            if line.id in [x.id for x in processed_lines]:
                continue

            # first try and match by product id:
            if line.product_id:
                lines_with_this_product = account_move_lines.filtered(lambda x: x.product_id.id == line.product_id.id and x.parent_state == 'posted')
                balance = sum(x.debit-x.credit for x in lines_with_this_product)
                if abs(float_round(balance, precision_digits=prec)) == 0.00:
                    self.add_reconcile_to_lines(lines_with_this_product)
                    processed_lines.extend([x for x in lines_with_this_product])

            # if we have a stock move then work up to source and down to invoice - if many invoice lines (due to back-order) this will not work
            if line.move_id.stock_move_id.sale_line_id:
                sale_move_lines = line.move_id.stock_move_id.sale_line_id.invoice_lines # these are the lines to the customer
                sale_moves = [x.move_id for x in sale_move_lines if x.move_id.state == 'posted']
                sale_move_lines = [x.line_ids.filtered(lambda m: m.account_id.id == self.account.id and m.product_id.id == line.product_id.id)
                                   for x in sale_moves]
                balance = 0.0
                for i in range(0, len(sale_move_lines)):
                    balance += sum([x.debit - x.credit for x in sale_move_lines[i]])
                balance = balance + (line.debit - line.credit)
                if abs(float_round(balance, precision_digits=prec)) == 0.00:
                    lines_to_reconcile = [line]
                    lines_to_reconcile.extend([x for x in sale_move_lines])
                    self.add_reconcile_to_lines(lines_to_reconcile)
                    processed_lines.extend([x for x in lines_to_reconcile])

            # if we have a single sale_line associated then link to stock moves. This will work
            # for kits which have a single sale lines, many stock moves, single invoice line
            # sale_line_ids not populated on aml so assume product is unique on sale order

            if line.move_id.sale_order_id:
                sale_order_lines = line.move_id.sale_order_id.order_line.filtered(lambda x: x.product_id.id == line.product_id.id)
                cutoff_date = self._get_stock_move_filter_date()
                stock_moves = self.env['stock.move'].search([('sale_line_id', 'in', sale_order_lines.ids),
                                                             ('state', '=', 'done'),
                                                             ('date', '<=', cutoff_date)])

                move_lines_for_stock = self.env['account.move.line'].search([('account_id', '=', self.account.id),
                                                                             ('date', '<=', self.as_at_date),
                                                                             ('move_id.stock_move_id', 'in', [x.id for x in stock_moves]),
                                                                             ('parent_state', '=', 'posted')])
                balance = 0.0
                for i in range(0, len(move_lines_for_stock)):
                    balance += (move_lines_for_stock[i].debit - move_lines_for_stock[i].credit)
                balance += (line.debit - line.credit)
                if abs(float_round(balance, precision_digits=prec)) == 0.00:
                    lines_to_reconcile = [line]
                    lines_to_reconcile.extend([x for x in move_lines_for_stock])
                    self.add_reconcile_to_lines(lines_to_reconcile)
                    processed_lines.extend([x for x in lines_to_reconcile])

        if self.print_report:
            lines_to_report = []
            for line in account_move_lines:
                if line.id not in [x.id for x in processed_lines]:
                    lines_to_report.extend(line)
            self.do_report(lines_to_report)
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.anglo.saxon.dni.reconcile',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new'}
        else:
            return {'type': 'ir.actions.act_window_close'}

    def do_report(self, lines_to_report):
        data = StringIO()
        workbook = xlsxwriter.Workbook(data, {'in_memory': True})
        worksheet = workbook.add_worksheet('Data')
        format_number = workbook.add_format({'num_format': '#,##0.00', 'align': 'right'})

        # write headings
        worksheet.write(0, 0, 'Date')
        worksheet.write(0, 1, 'Ref')
        worksheet.write(0, 2, 'Name')
        worksheet.write(0, 3, 'Product Description')
        worksheet.write(0, 4, 'Picking')
        worksheet.write(0, 5, 'Sale order')
        worksheet.write(0, 6, 'Quantity')
        worksheet.write(0, 7, 'Debit')
        worksheet.write(0, 8, 'Credit')
        worksheet.write(0, 9, 'Balance')
        worksheet.write(0, 10, 'Move')
        row = 1
        for line in lines_to_report:
            if line.move_id.stock_move_id:
                picking = line.move_id.stock_move_id.picking_id.name
                sale_order = ''
            elif line.move_id.sale_order_id:
                sale_order = line.move_id.sale_order_id.name
                picking = ''
            else:
                sale_order = ''
                picking = ''

            worksheet.write(row, 0, line.date)
            worksheet.write(row, 1, line.ref)
            worksheet.write(row, 2, line.name)
            worksheet.write(row, 3, line.product_id.name if line.product_id else '')
            worksheet.write(row, 4, picking)
            worksheet.write(row, 5, sale_order)
            worksheet.write(row, 6, line.quantity, format_number)
            worksheet.write(row, 7, line.debit, format_number)
            worksheet.write(row, 8, line.credit, format_number)
            worksheet.write(row, 9, line.balance, format_number)
            worksheet.write(row, 10, line.move_id.name)
            row += 1

        workbook.close()
        data.seek(0)
        output = base64.encodebytes(data.read())
        self.write({'data': output,
                    'report_name': 'Analysis for Dispatched Not Invoiced.xlsx'})
        data.close()











