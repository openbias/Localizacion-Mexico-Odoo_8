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


class AccountMoveLine(models.Model):
    _name = "account.move.line"
    _inherit = ['mail.thread', 'account.move.line', 'account.cfdi']

    @api.one
    def _showxml(self):
        url_id = self.env["ir.config_parameter"].search([('key', '=', "web.base.url")])
        xml_id = self.env["ir.attachment"].search([('res_model', '=', "account.move.line"), ("res_id", "=", self.id)])
        url = '%s/web/content/%s?download=true'%(url_id.value, xml_id.id)
        self.url_xml = url

    url_xml = fields.Char(string="XML",compute="_showxml", default="")
    uuid = fields.Char(string='Timbre fiscal', copy=False)
    number = fields.Char(string='Number')
    date_invoice = fields.Datetime(string='Invoice Date',
        readonly=True, index=True,
        help="Keep empty to use the current date", copy=False)

    @api.multi
    def get_xml(self):
        url_id = self.env["ir.config_parameter"].search([('key', '=', "web.base.url")])
        xml_id = self.env["ir.attachment"].search([('res_model', '=', "account.move.line"), ("res_id", "=", self.id)])
        url = '%s/web/binary/saveas?model=ir.attachment&field=datas&filename_field=datas_fname&id=%s'%(url_id.value, xml_id.id)
        return {
            'type': 'ir.actions.act_url',
            'url':url,
            'nodestroy': True
        }

    @api.multi
    def get_pdf(self):
        return {}

    def action_write_date_invoice_cfdi(self, inv_id):
        dtz = False
        if not self.date_invoice_cfdi:
            tz = self.env.user.tz
            if not tz:
                message = '<li>El usuario no tiene definido Zona Horaria</li>'
                self.action_raise_message(message)
                return message
            cr = self._cr
            hora_factura_utc = datetime.now(timezone("UTC"))
            dtz = hora_factura_utc.astimezone(timezone(tz)).strftime("%Y-%m-%d %H:%M:%S")
            dtz = dtz.replace(" ", "T")
            logging.info('---DATE %s '%(dtz) )
            cr.execute("UPDATE account_move_line SET date_invoice_cfdi='%s' WHERE id=%s "%(dtz, inv_id) )
        return dtz

    @api.one
    def reconcile_create_cfdi(self):
        message = ""
        ctx = dict(self._context) or {}
        ctx['type'] = "pagos"
        ctx['journal_id'] = self.journal_id.id

        res = self.with_context(**ctx).stamp(self)
        if res.get('message'):
            message = res['message']
        else:
            self.get_process_data(self, res.get('result'))
        if message:
            message = message.replace("(u'", "").replace("', '')", "")
            self.action_raise_message("Error al Generar el XML \n\n %s "%( message.upper() ))
            return False
        return True