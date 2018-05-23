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

class AccountVoucher(models.Model):

    _inherit = "account.voucher"

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
 
    @api.multi
    def proforma_voucher(self):
        ctx = dict(self._context)
        res = super(AccountVoucher, self).proforma_voucher()
        partial_lines = lines = self.env['account.move.line']
        for line in self.move_id.line_id:
            if line.reconcile_id:
                lines |= line.reconcile_id.line_id
            elif line.reconcile_partial_id:
                lines |= line.reconcile_partial_id.line_partial_ids
            partial_lines += line
        m_ids = self.move_id.line_id.ids
        inv_ids = self.env['account.invoice']
        line_ids = self.env['account.move.line']
        for line in (lines - partial_lines).sorted():
            if line.invoice:
                for payment_id in line.invoice.payment_ids:
                    if payment_id.id in m_ids:
                        payment_id.action_write_date_invoice_cfdi(line.invoice.id)
                        ctx.update({'payment_id': self.id, 'invoice_id': line.invoice.id})
                        payment_id.with_context(**ctx).reconcile_create_cfdi()
        return res

    def action_validate_cfdi(self):
        ctx = dict(self._context) or {}
        user_id = self.env.user
        tz = user_id.tz or False
        message = ''
        if self.formapago_id:
            codigo_postal_id = self.journal_id and self.journal_id.codigo_postal_id or False
            regimen_id = self.company_id.partner_id.regimen_id or False
            if not codigo_postal_id:
                message += '<li>No se definio Lugar de Expedicion (C.P.)</li>'
            if not regimen_id: 
                message += '<li>No se definio Regimen Fiscal para la Empresa</li>'
            if not tz:
                message += '<li>El usuario no tiene definido Zona Horaria</li>'
            if not self.partner_id.vat:
                message += '<li>No se especifico el RFC para el Cliente</li>'
            if not self.company_id.partner_id.vat:
                message += '<li>No se especifico el RFC para la Empresa</li>'
        self.action_raise_message(message)
        return message

    def action_raise_message(self, message):
        context = dict(self._context) or {}
        if not context.get('batch', False):
            if len(message) != 0:
                message = message.replace('<li>', '').replace('</li>', '\n')
                raise Warning(message)
        else:
            self.mensaje_validar += message
        return True


