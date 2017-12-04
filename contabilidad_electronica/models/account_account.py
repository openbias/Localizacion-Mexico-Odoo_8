# -*- encoding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.exceptions import except_orm, Warning, RedirectWarning

class account_account(models.Model):
    _inherit = 'account.account'

    codigo_agrupador = fields.Many2one('contabilidad_electronica.codigo.agrupador', 
                string=u"Código agrupador SAT")
    naturaleza = fields.Many2one('contabilidad_electronica.naturaleza', 
                string=u"Naturaleza")


class account_move_line(models.Model):
    _inherit = "account.move.line"

    comprobantes = fields.One2many("contabilidad_electronica.comprobante", "move_line_id", 
                string="Comprobantes", ondelete="cascade")
    comprobantes_cfd_cbb = fields.One2many("contabilidad_electronica.comprobante.otro", "move_line_id", 
                string="Comprobantes (CFD o CBB)", ondelete="cascade")
    comprobantes_ext = fields.One2many("contabilidad_electronica.comprobante.ext", "move_line_id", 
                string="Comprobantes extranjeros", ondelete="cascade")
    cheques = fields.One2many("contabilidad_electronica.cheque", "move_line_id", 
                string="Cheques", ondelete="cascade")
    transferencias = fields.One2many("contabilidad_electronica.transferencia", "move_line_id", 
                string="Transferencias", ondelete="cascade")
    otros_metodos = fields.One2many("contabilidad_electronica.otro.metodo.pago", "move_line_id", 
                string=u"Otros métodos de pago", ondelete="cascade")

    # Funcion para actualizar los nodos de la contabilidad electronica de los pagos
    #
    # Del anexo 24: "Se considera que se debe indentificar el soporte documental
    # tanto en la provisión como en el pago y/o cobro de cada una de las cuentas
    # y subcuentas que se vean afectadas"        
    def create_move_comprobantes_pagos(self, cr, uid, ids, context=None):
        move_obj = self.pool.get("account.move")
        move_line_obj = self.pool.get("account.move.line")
        comp_obj = self.pool.get("contabilidad_electronica.comprobante")
        for move_line in self.browse(cr, uid, ids):
            invoice = False
            if move_line.reconcile_id:
                for line in move_line.reconcile_id.line_id:
                    if line.invoice:
                        invoice = line.invoice
                        break
            elif move_line.reconcile_partial_id:
                for line in move_line.reconcile_partial_id.line_partial_ids:
                    if line.invoice:
                        invoice = line.invoice
                        break
            if not invoice:
                continue
            if invoice.uuid:
                uuid = invoice.uuid
                uuid = uuid[0:8]+'-'+uuid[8:12]+'-'+uuid[12:16]+'-'+uuid[16:20]+'-'+uuid[20:32]
                vals = {
                    'uuid': uuid,
                    'rfc': invoice.partner_id.vat,
                    'monto': invoice.amount_total,
                    'move_line_id': move_line.id
                }
                if invoice.currency_id.name != 'MXN':
                    vals.update({
                        'moneda': invoice.currency_id.id,
                        'tipo_cambio': invoice.tipo_cambio
                    })
                if not comp_obj.search(cr, uid, [('uuid','=',uuid),('move_line_id','=',move_line.id)]):
                    comp_obj.create(cr, uid, vals)
        return True

class account_move(models.Model):
    _inherit = "account.move"

    @api.one
    def _get_tipo_poliza(self):
        tipo = '3'
        for move in self:
            if move.journal_id.type == 'bank':
                if move.journal_id.default_debit_account_id.id != move.journal_id.default_credit_account_id.id:
                    raise except_orm(_('Warning!'),
                        _('La cuenta deudora por defecto y la cuenta acreedora por defecto no son la misma en el diario %s'%move.journal_id.name ))
                if len(move.line_id) == 2:
                    if move.line_id[0].account_id.user_type.code == 'bank' and move.line_id[0].account_id.user_type.code == 'bank':
                        tipo = '3'
                        break
                for line in move.line_id:
                    if line.account_id.id == move.journal_id.default_debit_account_id.id:
                        if line.debit != 0 and line.credit == 0:
                            tipo = '1'
                            break
                        elif line.debit == 0 and line.credit != 0:
                            tipo = '2'
                            break
            else:
                tipo = '3'
        self.tipo_poliza = tipo
    

    tipo_poliza = fields.Selection([
            ('1','Ingresos'),
            ('2','Egresos'),
            ('3','Diario'),
        ], string=u"Tipo póliza", compute='_get_tipo_poliza',
        default='3')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: