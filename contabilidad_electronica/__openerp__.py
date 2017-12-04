# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name' : 'Contabiliad electrónica SAT',
    'version' : '1.0',
    'author' : 'OpenBIAS',
    'website': "http://www.bias.com.mx",
    'category' : 'Accounting & Finance',
    'depends' : [
        'account', "cfd_mx", 
            # "validar_factura"
        ],
    'description': """
    """,
    'data': [
        'security/ir.model.access.csv',
        'data/contabilidad_electronica.naturaleza.xml',
        'data/contabilidad_electronica.metodo.pago.xml',
        'data/contabilidad_electronica.codigo.agrupador.xml',
        
        'views/contabilidad_electronica_view.xml',
        'views/account_account_view.xml',
        'views/account_voucher_view.xml',
        'views/account_bank_statement_view.xml',

        'wizard/account_move_comprobantes_view.xml',
        'wizard/generar_xmls_view.xml',
    ],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'images': [],
}


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
