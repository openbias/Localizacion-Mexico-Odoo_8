# -*- encoding: utf-8 -*-

import time
from openerp.osv import osv, fields

class account_voucher(osv.Model):
    _inherit = "account.voucher"
    
    def onchange_date(self, cr, uid, ids, date, currency_id, payment_rate_currency_id, amount, company_id, context=None):
        res = super(account_voucher, self).onchange_date(cr, uid, ids, date, currency_id, payment_rate_currency_id, amount, company_id, context=context)
        res.setdefault("value", {})["fecha_trans"] = date
        return res
    
    def default_get(self, cr, uid, fields, context=None):
        res = super(account_voucher, self).default_get(cr, uid, fields, context=context)
        company_partner_id = self.pool.get("res.users").browse(cr, uid, uid).company_id.partner_id.id
        if "type" in res:
            if res["type"] == "payment":
                res["cta_origen_partner"] = company_partner_id
                res["cta_destino_partner"] = context.get("default_partner_id", False)
            elif res["type"] == "receipt":
                res["cta_origen_partner"] = context.get("default_partner_id", False)
                res["cta_destino_partner"] = company_partner_id
        return res
        
    def onchange_partner_id(self, cr, uid, ids, partner_id, journal_id, amount, currency_id, type, date, context=None):
        res = super(account_voucher, self).onchange_partner_id(cr, uid, ids, partner_id, journal_id, amount, currency_id, type, date, context=context)
        if type == 'payment':
            res.setdefault('value', {})['cta_destino_partner'] = partner_id
        elif type == 'receipt':
            res.setdefault('value', {})['cta_origen_partner'] = partner_id
        return res

    def onchange_journal(self, cr, uid, ids, journal_id, line_ids, tax_id, partner_id, date, amount, ttype, company_id, context=None):
        res = super(account_voucher, self).onchange_journal(cr, uid, ids, journal_id, line_ids, tax_id, partner_id, date, amount, ttype, company_id, context=context)
        if not res:
          return res
        res.setdefault('value', {}).update({'cta_destino': False})
        if journal_id:
            result = self.pool.get("res.partner.bank").search(cr, uid, [('journal_id', '=', journal_id)])
            if result:
                field = False
                if ttype == 'payment':
                    field = 'cta_origen'
                    other_field = 'cta_destino'
                elif ttype == 'receipt':
                    field = 'cta_destino'
                    other_field = 'cta_origen'
                if field:
                    res["value"][field] = result[0]
                #if partner_id:
                #    res["domain"] = {other_field: [('partner_id', '=', partner_id)]}
                #elif 'default_partner_id' in context:
                #    res["domain"] = {other_field: [('partner_id', '=', context["default_partner_id"])]}
        return res
        
    def _check_accounts(self, cr, uid, ids, context=None):
        user_company_id = self.pool.get("res.users").browse(cr, uid, uid).company_id
        for rec in self.browse(cr, uid, ids):
            check = {'trans': [rec.cta_destino, rec.cta_origen, rec.fecha_trans],
                'cheque': [rec.cta_origen, rec.fecha_trans, rec.benef],
                'otro': [rec.benef, rec.metodo_pago, rec.fecha_trans]}
            if not rec.tipo_pago:
                return True
            elif not all(check[rec.tipo_pago]):
                return False
            if rec.cta_origen and rec.cta_destino:
                if rec.type == 'receipt':
                    if rec.cta_destino.partner_id.id != user_company_id.partner_id.id or rec.cta_origen.partner_id.id != rec.partner_id.id:
                        return False
                elif rec.type == 'payment':
                    if rec.cta_origen.partner_id.id != user_company_id.partner_id.id or rec.cta_destino.partner_id.id != rec.partner_id.id:
                        return False
        return True
        
    def _get_tipo_cambio(self, cr, uid, currency_id, fecha):
        cr.execute("SELECT rate FROM res_currency_rate WHERE currency_id = %s AND name = '%s' ORDER BY name DESC LIMIT 1"%(currency_id.id, fecha))
        if cr.rowcount:
            rate = cr.fetchone()[0]
        else:
            raise osv.except_osv("Error", u"No hay tipo de cambio definido para %s para la fecha %s"%(currency_id.name, fecha))
        return rate

    def action_move_line_create(self, cr, uid, ids, context=None):
        move_obj = self.pool.get("account.move")
        move_line_obj = self.pool.get("account.move.line")
        obj = {
            'trans': self.pool.get("contabilidad_electronica.transferencia"),
            'cheque': self.pool.get("contabilidad_electronica.cheque"),
            'otro': self.pool.get("contabilidad_electronica.otro.metodo.pago")
        }
        res = super(account_voucher, self).action_move_line_create(cr, uid, ids, context=context)
        for rec in self.browse(cr, uid, ids):
            if rec.tipo_pago:
                for move_line in rec.move_id.line_id:
                    if rec.tipo_pago == 'trans':
                        vals = {
                            'cta_ori': rec.cta_origen.id,
                            'cta_dest': rec.cta_destino.id,
                            'fecha': rec.fecha_trans,
                        }
                    elif rec.tipo_pago == 'cheque':
                        vals = {
                            'cta_ori': rec.cta_origen.id,
                            'num': rec.num_cheque,
                            'benef': rec.benef.id,
                            'fecha': rec.fecha_trans
                        }
                    else:
                        vals = {
                            'metodo': rec.metodo_pago.id,
                            'benef': rec.benef.id,
                            'fecha': rec.fecha_trans
                        }
                    vals.update({
                        "move_line_id": move_line.id,
                        "monto": rec.amount
                    })
                    if rec.journal_id.currency and rec.journal_id.currency.name != "MXN":
                        cur_obj = self.pool.get("res.currency")
                        currency_id = rec.journal_id.currency.id
                        mxn_currency_id = self.pool.get("ir.model.data").get_object(cr, uid, 'base', 'MXN').id
                        ctx = {'date': rec.fecha_trans}
                        if cur_obj.read(cr, uid, currency_id, ["base"])["base"]:
                            rate_other = 1.0
                        else:
                            rate_other = cur_obj._get_current_rate(cr, uid, [currency_id], True, context=ctx)[currency_id]
                        rate_mxn = cur_obj._get_current_rate(cr, uid, [mxn_currency_id], True, context=ctx)[mxn_currency_id]
                        tipo_cambio = (1.0 / rate_other) * rate_mxn
                        vals.update({
                            "moneda": rec.journal_id.currency.id,
                            "tipo_cambio":  tipo_cambio
                        })
                        
                    obj[rec.tipo_pago].create(cr, uid, vals)
        return res
        
    def proforma_voucher(self, cr, uid, ids, context=None):
        move_line_obj = self.pool.get("account.move.line")
        res = super(account_voucher, self).proforma_voucher(cr, uid, ids, context=context)
        for rec in self.browse(cr, uid, ids):
            move_ids = [x.id for x in rec.move_ids]
            move_line_obj.create_move_comprobantes_pagos(cr, uid, move_ids)
        return res
    
    _columns = {
        "cta_destino": fields.many2one("res.partner.bank", string="Cuenta destino"),
        "cta_origen": fields.many2one("res.partner.bank", string="Cuenta origen"),
        "cta_destino_partner": fields.many2one("res.partner", string="Partner cuenta destino"),
        "cta_origen_partner": fields.many2one("res.partner", string="Partner cuenta origen"),
        "fecha_trans": fields.date("Fecha de la transferencia"),
        "num_cheque": fields.char(u"Número"),
        "benef": fields.many2one("res.partner", string="Beneficiario"),
        "metodo_pago": fields.many2one("contabilidad_electronica.metodo.pago", string=u"Código"),
        "tipo_pago": fields.selection([("trans", "Transferencia"),("cheque", "Cheque"), ("otro", "Otro")], string=u"Tipo del pago")
    }
    
    _defaults = {
        "tipo_pago": 'trans',
        "fecha_trans": lambda *a: time.strftime('%Y-%m-%d'),
    }
    
    _constraints = [(_check_accounts, u"Error en los campos de la forma de pago. Por favor verificar los siguientes puntos\n"+\
      "1.- Deben estar llenos los campos obligatorios (por ejemplo en el caso de transferencia, la cuenta origen, la cuenta destino y la fecha de transferencia)\n"+\
      "2.- La cuenta origen debe pertenecer al cliente y la de destino a la empresa, o viceversa en caso de pago a proveedor", 
        ["cta_destino", "cta_origen", "fecha_trans", "benef", "metodo_pago"])]
    


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: