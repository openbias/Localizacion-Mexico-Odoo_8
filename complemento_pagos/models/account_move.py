# -*- encoding: utf-8 -*-

from openerp import models, fields as field2, api, _
from openerp.exceptions import Warning

import time
from openerp.osv import osv, fields

class AccountVoucher(osv.Model):
    _inherit = "account.voucher"

    _columns = {
        "formapago_id": fields.many2one("cfd_mx.formapago", string="Forma de Pago"),
    }

    def proforma_voucher(self, cr, uid, ids, context=None):
        move_line_obj = self.pool.get("account.move.line")
        res = super(AccountVoucher, self).proforma_voucher(cr, uid, ids, context=context)

        move_ids = {}
        for rec in self.browse(cr, uid, ids):
            for x in rec.move_ids:
                if x.invoice:
                    # and x.invoice.uuid != False and x.invoice.tipo_comprobante in ['I', 'E']
                    x.action_write_date_invoice_cfdi(x.id)
                    move_ids[x.id] = {
                        "line_id": x,
                        "inv_id": x.invoice
                    }
        print "move_ids", move_ids
        if len(move_ids):
            print "mmmmmmmmmmmmmmm", mmmmmmmmmmmmmmmm
            # move_line_obj.create_move_comprobantes_pagos(cr, uid, move_ids)
        return res



class AccountMoveLine(models.Model):
    _name = "account.move.line"
    _inherit = ['mail.thread', 'account.move.line', 'account.cfdi']

    @api.one
    def _showxml(self):
        url_id = self.env["ir.config_parameter"].search([('key', '=', "web.base.url")])
        xml_id = self.env["ir.attachment"].search([('res_model', '=', "account.move.line"), ("res_id", "=", self.id)])
        url = '%s/web/content/%s?download=true'%(url_id.value, xml_id.id)
        self.url_xml = url

    url_xml = field2.Char(string="XML",compute="_showxml", default="")
    uuid = field2.Char(string='Timbre fiscal', copy=False)
    number = field2.Char(string='Number')
    date_invoice = field2.Datetime(string='Invoice Date',
        readonly=True, states={'draft': [('readonly', False)]}, index=True,
        help="Keep empty to use the current date", copy=False)


    def action_write_date_invoice_cfdi(self, inv_id):
        dtz = False
        if not self.date_invoice_cfdi:
            tz = self.env.user.tz or "UTC"
            cr = self._cr
            hora_factura_utc = datetime.now(timezone("UTC"))
            dtz = hora_factura_utc.astimezone(timezone(tz)).strftime("%Y-%m-%d %H:%M:%S")
            dtz = dtz.replace(" ", "T")
            cr.execute("UPDATE account_move_line SET date_invoice_cfdi='%s' WHERE id=%s "%(dtz, inv_id) )
            cr.commit()
        print "dtz", dtz
        return dtz