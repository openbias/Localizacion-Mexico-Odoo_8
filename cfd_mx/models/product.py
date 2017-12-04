# -*- coding: utf-8 -*-

from openerp import api, fields, models, _

#Productos
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    cuenta_predial = fields.Char(string="Cuenta Predial", help="Numero de Cuenta Predial")
    clave_prodser_id = fields.Many2one("cfd_mx.prodserv", string='Clave SAT')

class ProductUOM(models.Model):
    _inherit = 'product.uom'

    clave_unidadesmedida_id = fields.Many2one("cfd_mx.unidadesmedida", string='Clave SAT')

