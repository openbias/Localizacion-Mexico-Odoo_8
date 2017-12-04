# -*- coding: utf-8 -*-

from openerp import models, fields, api, _

class LlenarComprontes(models.Model):
    _name = "contabilidad_electronica.llenar.comprobantes"

    @api.multi
    def create_move_comprobantes(self):
        r = self.env['account.invoice'].create_move_comprobantes()
        return r

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: