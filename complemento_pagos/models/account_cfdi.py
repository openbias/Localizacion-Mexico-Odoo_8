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


class AccountCfdi(models.Model):
    _name = 'account.cfdi'
    _inherit = "account.cfdi"

    ################################
    #
    # Account Payment
    #
    ################################
    def pagos_info_comprobante(self):
        ctx = dict(self._context) or {}
        obj = self.obj
        journal_id = obj.journal_id
        date_invoice = obj.date_invoice_cfdi
        if not obj.date_invoice_cfdi:
            date_invoice = obj.action_write_date_invoice_cfdi(obj.id)
        cfdi_comprobante = {
            "Version": "3.3",
            "Folio": self._get_folio(),
            "Fecha": date_invoice,
            "SubTotal": 0,
            "Moneda": 'XXX',
            "Total": 0,
            "TipoDeComprobante": 'P',
            "LugarExpedicion": journal_id.codigo_postal_id.name
        }
        if journal_id.serie:
            cfdi_comprobante['Serie'] = journal_id.serie or ''
        return cfdi_comprobante

    def pagos_info_emisor(self):
        obj = self.obj
        partner_data = obj.company_id.partner_id
        emisor_attribs = {
            'Rfc': partner_data.vat or "",
            'Nombre': partner_data.name or "",
            "RegimenFiscal": partner_data.regimen_id and partner_data.regimen_id.clave or ""
        }
        return emisor_attribs

    def pagos_info_receptor(self):
        ctx = dict(self._context) or {}
        obj = self.obj
        partner_data = obj.partner_id
        receptor_attribs = {
            'Rfc': partner_data.vat or "",
            'Nombre': partner_data.name or "",
            'UsoCFDI': 'P01'
        }
        if partner_data.country_id.code_alpha3 != 'MEX':
            receptor_attribs['ResidenciaFiscal'] = partner_data.country_id.code_alpha3
            if partner_data.identidad_fiscal:
                receptor_attribs['NumRegIdTrib'] = partner_data.identidad_fiscal
        return receptor_attribs

    def pagos_info_conceptos(self):
        obj = self.obj
        cfdi_conceptos = []
        concepto_attribs = {
            "ClaveProdServ": "84111506",
            "Cantidad": 1,
            "ClaveUnidad": "ACT",
            "Descripcion": "Pago",
            "ValorUnitario": 0,
            "Importe": 0
        }
        cfdi_conceptos.append(concepto_attribs)
        return cfdi_conceptos

    def pagos_info_complemento(self):
        ctx = dict(self._context) or {}
        
        obj = self.obj
        cfdi_pagos = []
        DoctoRelacionado = []
        
        monto = '%.2f'%(abs(obj.credit))
        tipocambio = None

        Invoice = self.env['account.invoice']
        if ctx.get('model') and ctx.get('payment_id'):
            Model = self.env[ ctx['model'] ]
            payment_id = Model.browse(ctx.get('payment_id'))
            p_moneda = "MXN" if payment_id.currency_id.name in [False, None] else payment_id.currency_id.name
            formapago_id = payment_id.statement_id and payment_id.statement_id.formapago_id
        else:
            Model = self.env['account.voucher']
            payment_id = Model.browse(ctx.get('payment_id'))
            p_moneda = "MXN" if payment_id.currency_id.name in [False, None] else payment_id.currency_id.name
            formapago_id = payment_id.formapago_id


        pago_attribs = {
            "FechaPago": '%sT12:00:00'%(payment_id.date),
            "FormaDePagoP": formapago_id.clave or "01",
            "MonedaP": p_moneda,
            "Monto": monto,
        }
        if p_moneda != "MXN":
            tipocambio = self._get_tipocambio(obj.currency_id, payment_id.date)
            pago_attribs['TipoCambioP'] = '%s'%(tipocambio)
        if obj.ref:
            pago_attribs['NumOperacion'] = obj.ref

        if ctx.get('invoice_id'):
            inv = Invoice.browse(ctx['invoice_id'])
            if inv.uuid:
                TipoCambioDR = self._get_tipocambio(inv.currency_id, payment_id.date)
                ImpPagos = (inv.amount_total - inv.residual) # inv.get_cfdi_imp_pagados()
                ImpPagado =  (abs(obj.credit) / TipoCambioDR)
                if p_moneda != inv.currency_id.name:
                    ImpPagado = abs(obj.amount_currency)
                ImpSaldoAnt = (inv.amount_total - (ImpPagos - ImpPagado))
                if ImpSaldoAnt == 0.0:
                    ImpSaldoAnt = inv.amount_total
                ImpSaldoInsoluto = inv.amount_total - ImpPagos
                docto_attribs = {
                    "IdDocumento": "%s"%inv.uuid,
                    "Folio": "%s"%inv.number,
                    "MonedaDR": "%s"%inv.currency_id.name,
                    "MetodoDePagoDR": "PPD",
                    "NumParcialidad": u"%s"%(inv.parcialidad_pago or 1),
                    "ImpSaldoAnt": '%.2f'%ImpSaldoAnt,
                    "ImpPagado": '%.2f'%ImpPagado,
                    "ImpSaldoInsoluto": '%.2f'%(abs(ImpSaldoInsoluto))
                }
                if p_moneda != inv.currency_id.name:
                    docto_attribs['TipoCambioDR'] = '%s'%(TipoCambioDR)
                if inv.journal_id.serie:
                    docto_attribs['Serie'] = inv.journal_id.serie or ''
                DoctoRelacionado.append(docto_attribs)
        res = {
            'pago_attribs': pago_attribs,
            'docto_relacionados': DoctoRelacionado
        }
        return res


    def _get_tipocambio(self, currency_id, date_invoice):
        model_obj = self.env['ir.model.data']
        tipocambio = 1.0
        if date_invoice:
            if currency_id.name=='MXN':
                tipocambio = 1.0
            else:
                mxn_rate = model_obj.get_object('base', 'MXN').rate
                tipocambio = (1.0 / currency_id.with_context(date='%s'%(date_invoice)).rate) * mxn_rate
                tipocambio = round(tipocambio, 4)
        return tipocambio


class AccountInvoice(models.Model):
    _name = "account.invoice"
    _inherit = "account.invoice"

    @api.multi
    def register_payment(self, payment_line, writeoff_acc_id=False, writeoff_journal_id=False):
        self = self.with_context(opt='pagos')
        res = super(AccountInvoice, self).register_payment(payment_line, writeoff_acc_id=writeoff_acc_id, writeoff_journal_id=writeoff_journal_id)
        return res

