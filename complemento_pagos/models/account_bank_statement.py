# -*- coding: utf-8 -*-

import openerp
from openerp import models, fields, api, _
from openerp.exceptions import except_orm, Warning, RedirectWarning
from openerp.tools import float_compare
import openerp.addons.decimal_precision as dp

from datetime import date, datetime
from pytz import timezone
import json

import logging
logging.basicConfig(level=logging.INFO)

class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    hide_formapago_id = fields.Boolean(compute='_compute_hide_formapago_id',
        help="Este campo es usado para ocultar el formapago_id, cuando no se trate de Recibo Electronico de Pago")
    formapago_id = fields.Many2one('cfd_mx.formapago', string=u'Forma de Pago')
    date_invoice_cfdi = fields.Char(string="Invoice Date", copy=False)

    @api.one
    @api.depends('journal_id')
    def _compute_hide_formapago_id(self):
        if not self.journal_id:
            self.hide_formapago_id = True
            return
        if self.journal_id.id in self.company_id.cfd_mx_journal_ids.ids:
            self.hide_formapago_id = False
        else:
            self.hide_formapago_id = True

class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    @api.multi
    def process_reconciliation_pagos(self, mv_line_dicts):
        ctx = dict(self._context)
        st_line = self
        currency_id = st_line.currency_id and st_line.currency_id or st_line.company_id.currency_id or None

        partial_lines = lines = self.env['account.move.line']
        for line in st_line.journal_entry_id.line_id:
            if line.reconcile_id:
                lines |= line.reconcile_id.line_id
            elif line.reconcile_partial_id:
                lines |= line.reconcile_partial_id.line_partial_ids
            partial_lines += line

        m_ids = st_line.journal_entry_id.line_id.ids
        inv_ids = self.env['account.invoice']
        line_ids = self.env['account.move.line']
        for line in (lines - partial_lines).sorted():
            if line.invoice:
                for payment_id in line.invoice.payment_ids:
                    if payment_id.id in m_ids:
                        payment_id.action_write_date_invoice_cfdi(line.invoice.id)
                        ctx.update({'payment_id': self.id, 'model': self._name, 'invoice_id': line.invoice.id })
                        payment_id.with_context(**ctx).reconcile_create_cfdi()
        return True




    def process_reconciliation(self, cr, uid, id, mv_line_dicts, context=None):
        if context is None:
            context = {}
        super(AccountBankStatementLine, self).process_reconciliation(cr, uid, id, mv_line_dicts, context=context)
        self.process_reconciliation_pagos(cr, uid, id, mv_line_dicts, context=context)