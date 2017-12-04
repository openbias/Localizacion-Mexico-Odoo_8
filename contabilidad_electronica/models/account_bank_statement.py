# -*- encoding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.exceptions import except_orm, Warning, RedirectWarning

class account_bank_statement_line(models.Model):
    _inherit = "account.bank.statement.line"

    """
        Campo para evaluar POS
    """
    @api.multi
    def _get_pos_session_id(self):
        pos_session_id = None
        if 'pos_session_id' in self.statement_id._columns:
            pos_session_id = self.statement_id.pos_session_id
        return pos_session_id


    @api.model
    def _default_benef(self):
        res = self.env.user.company_id.partner_id
        return res        

    @api.model
    def _default_metodo_pago(self):
        res = self.env['contabilidad_electronica.metodo.pago'].search([('code','=','01')], limit=1)
        return res
    
    cta_destino = fields.Many2one("res.partner.bank", string="Cuenta destino")
    cta_origen = fields.Many2one("res.partner.bank", string="Cuenta origen")
    num_cheque = fields.Char(string=u"Número")
    benef = fields.Many2one("res.partner", string="Beneficiario", default=_default_benef)
    metodo_pago = fields.Many2one("contabilidad_electronica.metodo.pago", string=u"Código", default=_default_metodo_pago)
    ttype = fields.Selection([
        ("trans", "Transferencia"),
        ("cheque", "Cheque"), 
        ("otro", "Otro")
    ], 'Type', required=True, default='otro')

    def onchange_partner_id(self, cr, uid, ids, partner_id, context=None):
        res = super(account_bank_statement_line, self).onchange_partner_id(cr, uid, ids, partner_id, context=context)
        res.setdefault("domain", {})["cta_destino"] = [('partner_id', '=', partner_id)]
        return res

    def process_reconciliation_cont_elect(self, cr, uid, id, mv_line_dicts, context=None):
        if context is None:
            context = {}
        obj = {
            'trans': self.pool.get("contabilidad_electronica.transferencia"),
            'cheque': self.pool.get("contabilidad_electronica.cheque"),
            'otro': self.pool.get("contabilidad_electronica.otro.metodo.pago")
        }
        st_line = self.browse(cr, uid, id, context=context)

        currency_id = st_line.currency_id and st_line.currency_id or st_line.company_id.currency_id or None
        for move_line in st_line.journal_entry_id.line_id:
            if st_line.ttype == 'trans':
                vals = {
                    'cta_ori': st_line.cta_origen.id,
                    'cta_dest': st_line.cta_destino.id,
                    'fecha': st_line.date,
                }
            elif st_line.ttype == 'cheque':
                vals = {
                    'cta_ori': st_line.cta_origen.id,
                    'num': st_line.num_cheque,
                    'benef': st_line.benef.id,
                    'fecha': st_line.date
                }
            else:
                vals = {
                    'metodo': st_line.metodo_pago.id,
                    'benef': st_line.benef.id,
                    'fecha': st_line.date
                }
            vals.update({
                "move_line_id": move_line.id,
                "monto": st_line.amount
            })
            if currency_id.name != "MXN":
                cur_obj = self.pool.get("res.currency")
                #currency_id = st_line.currency_id.id
                mxn_currency_id = self.pool.get("ir.model.data").get_object(cr, uid, 'base', 'MXN').id
                ctx = {'date': st_line.date}
                if cur_obj.read(cr, uid, currency_id, ["base"])["base"]:
                    rate_other = 1.0
                else:
                    rate_other = cur_obj._current_rate_computation(cr, [uid, currency_id], "rate", [], True, context=ctx)[currency_id]
                rate_mxn = cur_obj._current_rate_computation(cr, uid, [mxn_currency_id], "rate", [], True, context=ctx)[mxn_currency_id]
                tipo_cambio = (1.0 / rate_other) * rate_mxn
                vals.update({
                    "moneda": st_line.currency_id.id,
                    "tipo_cambio":  tipo_cambio
                })
            obj[st_line.ttype].create(cr, uid, vals)


    def process_reconciliation(self, cr, uid, id, mv_line_dicts, context=None):
        if context is None:
            context = {}
        super(account_bank_statement_line, self).process_reconciliation(cr, uid, id, mv_line_dicts, context=context)
        self.process_reconciliation_cont_elect(cr, uid, id, mv_line_dicts, context=context)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
