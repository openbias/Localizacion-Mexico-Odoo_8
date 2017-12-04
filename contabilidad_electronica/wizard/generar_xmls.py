# -*- encoding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.exceptions import except_orm, Warning, RedirectWarning

# from xml_catalogo import xml_catalogo, cadena_original as cadena_catalogo
# from xml_balanza import xml_balanza, cadena_original as cadena_balanza
# from xml_polizas import xml_polizas, cadena_original as cadena_polizas
# from xml_aux_folios import xml_aux_folios, cadena_original as cadena_aux_folios
# from xml_aux_cuentas import xml_aux_cuentas, cadena_original as cadena_aux_cuentas
# from validar_xml import validate_xml_schema
import xml.etree.ElementTree as ET
import time
import base64

import os

class wizard_poliza_line(models.TransientModel):
    _name = 'contabilidad_electronica.wizard.poliza.line'

    move_id = fields.Many2one('account.move', string=u"Pólizas")
    tipo_poliza = fields.Selection([
        ('1', 'Ingresos'),
        ('2', 'Egresos'),
        ('3', 'Diario')
    ], string=u"Tipo póliza")
    partner_id = fields.Many2one('res.partner', string="Empresa")
    journal_id = fields.Many2one('account.journal', string="Diario")
    date = fields.Date("Fecha")
    parent_id = fields.Many2one('contabilidad_electronica.wizard.generar.xmls', invisible=True)
    

class wizard_balanza_line(models.TransientModel):
    _name = 'contabilidad_electronica.wizard.balanza.line'

    account_id = fields.Many2one('account.account', string="Cuenta")
    codigo = fields.Char(u"Código")
    saldo_inicial = fields.Float('Saldo inicial')
    debe = fields.Float("Debe")
    haber = fields.Float("Haber")
    saldo_final = fields.Float("Saldo final")
    parent_id = fields.Many2one('contabilidad_electronica.wizard.generar.xmls', invisible=True)

class wizard_generar_xmls(models.TransientModel):
    _name = 'contabilidad_electronica.wizard.generar.xmls'

    
    documento_id = fields.Selection([
            ('01', 'Catalogo de Cuentas'), 
            ('02', 'Balanza de Comprobacion'), 
            ('03', 'Polizas del Periodo'),
            ('04', 'Auxiliar Folios'),
            ('05', 'Auxiliar Cuentas')],
        string="Tipo de Documento Digital", default="01")
    tipo_solicitud = fields.Selection([
        ('AF', 'Acto de fiscalización'),
        ('FC', 'Fiscalización Compulsa'),
        ('DE', 'Devolución'),
        ('CO', 'Compensación')
    ], string=u"Tipo de solicitud de la póliza")
    num_orden = fields.Char(u"Número de orden")
    num_tramite = fields.Char(u"Número de trámite")
    tipo_envio = fields.Selection([('N', 'Normal'),('C','Complementaria')], 
        string=u"Tipo de envío de la balanza", required=True, default='N')
    fecha_mod_bal = fields.Date(u"Última modificación")
    solo_con_codigo = fields.Boolean(u"Sólo cuentas con código agrupador", default=True)
    limite_nivel = fields.Integer(u"Límite nivel")
    chart_account_id = fields.Many2one("account.account", string="Plan contable", domain=[('parent_id','=',False)], required=True)
    company_id = fields.Many2one("res.company", string=u"Compañía", required=True)
    mes = fields.Many2one("account.period", string=u"Periodo (Mes y año)", required=True)
    xml = fields.Binary("Archivo xml")
    fname = fields.Char("Filename")
    csv = fields.Binary("Archivo csv")
    fname_csv = fields.Char("Filename CSV")
    show_balanza = fields.Boolean(u'Mostrar previsualización balanza')
    show_polizas = fields.Boolean(u'Mostrar previsualización pólizas')
    balanza_lines = fields.One2many('contabilidad_electronica.wizard.balanza.line', 'parent_id', string=u'Previsualización balanza')
    polizas_lines = fields.One2many('contabilidad_electronica.wizard.poliza.line', 'parent_id', string=u"Previsualización pólizas")
    message_validation_xml = fields.Html("Validar XML")

    xlsx = fields.Binary("Archivo XLSX")
    fname_xlsx = fields.Char("Filename XLSX")

    def onchange_chart_id(self, cr, uid, ids, chart_account_id=False, context=None):
        res = {}
        if chart_account_id:
            company_id = self.pool.get('account.account').browse(cr, uid, chart_account_id, context=context).company_id.id
            now = time.strftime('%Y-%m-%d')
            domain = [('company_id', '=', company_id)]
            res['value'] = {'company_id': company_id}
            res['domain'] = {'mes': domain}
        return res

    def validar_contabilidad_electronica(self, cr, uid, ids, context=None):
        address_obj= self.pool.get('res.partner.address')
        url="https://ceportalvalidacionprod.clouda.sat.gob.mx/"
        return {
        'type': 'ir.actions.act_url',
        'url':url,
        }

    def _get_cadena_original(self, xml_func):
        return {
            xml_catalogo: cadena_catalogo,
            xml_balanza: cadena_balanza,
            xml_polizas: cadena_polizas,
            xml_aux_folios: cadena_aux_folios,
            xml_aux_cuentas: cadena_aux_cuentas,
        }[xml_func]

    def _sellar_xml(self, cr, uid, root, company_id, xml_func):
        invoice_obj = self.pool.get("account.invoice")
        tmpfiles = invoice_obj.get_temp_file_trans()
        
        xml = '<?xml version="1.0" encoding="utf-8"?>' + ET.tostring(root, encoding="utf-8")
        fname_xml = tmpfiles.create('xml_sin_sello')
        with open(fname_xml, 'w') as f:
            f.write(xml)
        
        cadena_original = self._get_cadena_original(xml_func)(xml)
        #print cadena_original
        fname_cadena = tmpfiles.save(cadena_original, "cadenaori")
        certificate = self.pool.get("account.invoice")._get_certificate(cr, uid, [], company_id)
        fname_cer_pem = tmpfiles.decode_and_save(certificate.cer_pem)
        fname_key_pem = tmpfiles.decode_and_save(certificate.key_pem)

        sello = invoice_obj.get_openssl().sign_and_encode(fname_cadena, fname_key_pem)
        certificado = ''.join(open(fname_cer_pem).readlines()[1:-1])
        certificado = certificado.replace('\n', '')
        
        root.attrib.update({
            "Sello": "%s"%sello,
            "noCertificado": "%s"%certificate.serial,
            "Certificado": "%s"%certificado
        })
        tmpfiles.clean()
        return '<?xml version="1.0" encoding="utf-8"?>' + ET.tostring(root, encoding="utf-8")

    
    def _validar_xml(self, xml_sellado, context):
        path = os.path.abspath(os.path.dirname(__file__))
        path_xsd = path + "/%s"%(context.get('xml_xsd'))
        path_xml_datas = context.get('xml_file')

        validar_xml = ""
        try:
            text_xml = open("/tmp/xml_contabilidad.xml", "w")
            text_xml.write(xml_sellado)
            text_xml.close()

            validate= validate_xml_schema(path_xsd, '/tmp/xml_contabilidad.xml')
            validar_xml = validate.validate_xml()
            validar_xml = validate.return_validate()
        except:
            pass
        return validar_xml
        
    def _save_xml(self, cr, uid, id, data, xml_func, fname, context=None):
        this = self.browse(cr, uid, id)
        xml_sellado = self._sellar_xml(cr, uid, xml_func(data), this.company_id, xml_func)
        xml_base64 = base64.encodestring(xml_sellado)
        validar_xml = self._validar_xml(xml_sellado, context)
        self.write(cr, uid, id, {'xml': xml_base64, 'fname': fname, 'message_validation_xml': validar_xml})
        
    def _quote_and_escape(self, value):
        if type(value) != str and type(value) != unicode:
            value = str(value)
        value.replace('"', r'\"')
        return '"%s"'%(value)
        
    def _save_csv(self, cr, uid, id, data, header, fname):
        rows = []
        for record in data:
            row = []
            for col in header:
                row.append(record.get(col, 'N/A'))
            rows.append(row)
        csv = ",".join([self._quote_and_escape(x) for x in header]) + "\n"
        for row in rows:
            csv += ",".join([self._quote_and_escape(x) for x in row]) + "\n"
        csv_base64 = base64.encodestring(csv.encode("utf-8"))
        self.write(cr, uid, id, {'csv': csv_base64, 'fname_csv': fname})

    def _return_action(self, cr, uid, id, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        view_rec = model_data_obj.get_object_reference(cr, uid, 'contabilidad_electronica', 'wizard_generar_xmls_view_form')
        view_id = view_rec and view_rec[1] or False
        return {
           'res_id': id,
           'view_type': 'form',
           'view_id' : [view_id],
           'view_mode': 'form',
           'res_model': 'contabilidad_electronica.wizard.generar.xmls',
           'type': 'ir.actions.act_window',
           'target': 'new',
           'context': context
        }

    def _get_accounts(self, cr, uid, fiscalyear_id, period_id, company_id, context=None):
        return self.pool.get("account.account").search(cr, uid, [('company_id', '=', company_id)])


    @api.multi
    def _save_xml(self, datas):
        self.ensure_one()
        cfdi = self.env['account.cfdi']
        message = ""
        # res = cfdi.with_context(**datas).contabilidad(self)
        try:
            res = cfdi.with_context(**datas).contabilidad(self)
            if res.get('message'):
                message = res['message']
            else:
                return self.get_process_data(res.get('result'))
        except ValueError, e:
            message = str(e)
        except Exception, e:
            message = str(e)
        if message:
            message = message.replace("(u'", "").replace("', '')", "")
            cfdi.action_raise_message("%s "%( message.upper() ))
            return False
        return True

    def get_process_data(self, res):
        context = dict(self._context)
        vals = {
            'xml': res.get("xml"), 
            'fname': context.get('fname'),
        }
        self.write(vals)

    @api.multi
    def _return_action(self):
        self.ensure_one()
        context = dict(self._context)
        data_obj = self.env['ir.model.data']
        view = data_obj.xmlid_to_res_id('contabilidad_electronica.wizard_generar_xmls_form')
        return {
             'name': _('Generar XMLs'),
             'type': 'ir.actions.act_window',
             'view_type': 'form',
             'view_mode': 'form',
             'res_model': 'contabilidad_electronica.wizard.generar.xmls',
             'views': [(view, 'form')],
             'view_id': view,
             'target': 'new',
             'res_id': self.id,
             'context': context,
         }


    # 1. XML CATALOGO DE CUENTAS
    def action_xml_catalogo(self, cr, uid, ids, context=None):
        this = self.browse(cr, uid, ids[0])
        data = {
            'mes': this.mes.name.split("/")[0],
            'ano': this.mes.fiscalyear_id.name,
            'rfc': this.company_id.partner_id.vat,
            'cuentas': []
        }
        vce = this.company_id.conta_elect_version or '1_3'
        account_obj = self.pool.get("account.account")
        account_ids = self._get_accounts(cr, uid, this.mes.fiscalyear_id.id, this.mes.id, this.company_id.id)
        for account in account_obj.browse(cr, uid, account_ids):
            cuenta = {
                'codigo': account.code,
                'codigo_agrupador': account.codigo_agrupador and account.codigo_agrupador.name or False,
                'descripcion': account.name,
                'nivel': account.level + 1,
                'naturaleza': account.naturaleza and account.naturaleza.code or False
            }
            if account.parent_id:
                cuenta.update({'padre': account.parent_id.code})
            if (this.limite_nivel >= account.level + 1) and (not this.solo_con_codigo or account.codigo_agrupador):
                data['cuentas'].append(cuenta)

        fname = '%s%s%sCT'%(this.company_id.partner_id.vat or '', data.get('ano'), data.get('mes') )
        ctx = {
            'xml_file': 'xml_catalogo.xml',
            'xml_xsd': 'CatalogoCuentas_%s.xsd'%(vce),
            'xml_xslt': 'CatalogoCuentas_%s.xslt'%(vce),
            'fname': fname+'.xml',
            'version': vce
        }
        self._save_xml(cr, uid, this.id, data, context=ctx)
        return self._return_action(cr, uid, this.id, context=ctx)
    
    def _balanza(self, cr, uid, ids, context=None):
        this = self.browse(cr, uid, ids[0])
        account_obj = self.pool.get("account.account")
        period_obj = self.pool.get("account.period")
        ctx = context.copy()
        ctx.update({
            'company_id': this.company_id.id,
            'fiscalyear': this.mes.fiscalyear_id.id,
            'all_fiscalyear': True,
            'state': 'posted',
            'periods': [this.mes.id],
            'chart_account_id': this.chart_account_id.id
        })
        account_ids = self._get_accounts(cr, uid, this.mes.fiscalyear_id.id, this.mes.id, this.company_id.id)
        account_data = {}
        for account in account_obj.browse(cr, uid, account_ids, context=ctx):
            account_data[account.id] = {
                'balance': account.balance, #Esto es el debe menos el haber
                'credit': account.credit,
                'debit': account.debit,
                'code': account.code,
                'id': account.id
            }
            
        # Todo eso se obtiene mejor pasando el parámetro initial_bal
        ctx['initial_bal'] = True
        for account in account_obj.read(cr, uid, account_ids, ["balance"], context=ctx):
            account_data[account["id"]]['initial_balance'] = account["balance"]
            
        lines = []
        for id, acc_data in account_data.iteritems():
            vals = {
                'saldo_inicial': acc_data['initial_balance'],
                # El saldo final es el inicial + (debe - haber)
                'saldo_final': acc_data['initial_balance'] + acc_data['balance'],
                'debe': acc_data['debit'],
                'haber': acc_data['credit'],
                'account_id': acc_data['id'],
                'codigo': acc_data['code']
            }
            acc_brw = account_obj.browse(cr, uid, acc_data['id'])
            if (this.limite_nivel >= acc_brw.level + 1) and (not this.solo_con_codigo or acc_brw.codigo_agrupador):
                lines.append((0,0,vals))
        line_obj = self.pool.get("contabilidad_electronica.wizard.balanza.line")
        line_obj.unlink(cr, uid, line_obj.search(cr, uid, [('parent_id','=',this.id)]))
        self.write(cr, uid, this.id, {'balanza_lines': lines})
         
    def action_previsualizar_balanza(self, cr, uid, ids, context=None):
        self._balanza(cr, uid, ids, context=context)
        self.write(cr, uid, ids, {'show_balanza': True, 'show_polizas': False, 'xml':False})
        return self._return_action(cr, uid, ids[0], context=context)
         
    
    # 2. XML BALANZA
    def action_xml_balanza(self, cr, uid, ids, context=None):
        this = self.browse(cr, uid, ids[0])
        vce = this.company_id.conta_elect_version or '1_3'
        data = {
            'mes': this.mes.name.split("/")[0],
            'ano': this.mes.fiscalyear_id.name,
            'rfc': this.company_id.partner_id.vat,
            'cuentas': [],
            'tipo_envio': this.tipo_envio,
            'fecha_mod_bal': this.fecha_mod_bal
        }        
        balanza_lines = this.balanza_lines
        if not this.balanza_lines:
            self._balanza(cr, uid, ids, context=context)
            balanza_lines = self.browse(cr, uid, ids[0]).balanza_lines
        for line in balanza_lines:
            cuenta = {
                'inicial': line.saldo_inicial,
                'final': line.saldo_final,
                'debe': line.debe,
                'haber': line.haber,
                'codigo': line.account_id.code,
                'descripcion': line.account_id.name
            }
            data["cuentas"].append(cuenta)
        data["cuentas"].sort(key=lambda x: x["codigo"])

        fname = '%s%s%sB%s'%(this.company_id.partner_id.vat or '', data.get('ano'), data.get('mes'), data.get('tipo_envio') )
        ctx = {
            'version': vce,
            'xml_file': 'xml_balanza.xml',
            'xml_xsd': 'BalanzaComprobacion_%s.xsd'%(vce),
            'xml_xslt': 'BalanzaComprobacion_%s.xslt'%(vce),
            'fname': fname+'.xml'
        }
        self._save_xml(cr, uid, this.id, data, context=ctx)
        return self._return_action(cr, uid, this.id, context=ctx)

       
    def _polizas(self, cr, uid, ids, context=None):
        this = self.browse(cr, uid, ids[0])
        if not this.tipo_solicitud:
            raise except_orm(_('Error!'),_('Favor de indicar el tipo de solicitud'))
        move_obj = self.pool.get("account.move")
        move_ids = move_obj.search(cr, uid, ['&', ('period_id','=',this.mes.id), ('company_id', '=', this.company_id.id)])
        lines = []
        for move in move_obj.browse(cr, uid, move_ids):
            lines.append((0,0,{
              'move_id': move.id,
              'partner_id': move.partner_id.id,
              'journal_id': move.journal_id.id,
              'tipo_poliza': move.tipo_poliza,
              'date': move.date
            }))
        line_obj = self.pool.get("contabilidad_electronica.wizard.poliza.line")
        line_obj.unlink(cr, uid, line_obj.search(cr, uid, [('parent_id','=',this.id)]))
        self.write(cr, uid, this.id, {'polizas_lines': lines})

    def action_previsualizar_polizas(self, cr, uid, ids, context=None):
        this = self.browse(cr, uid, ids[0])
        self._polizas(cr, uid, ids, context=context)
        self.write(cr, uid, this.id, {'show_polizas': True, 'show_balanza': False, 'xml': False})
        return self._return_action(cr, uid, this.id, context=context)

    def _get_tipo_cambio(self, cr, uid, currency_id, fecha):
        cr.execute("SELECT rate FROM res_currency_rate WHERE currency_id = %s AND name <= '%s' ORDER BY name DESC LIMIT 1"%(currency_id.id, fecha))
        if cr.rowcount:
            rate = cr.fetchone()[0]
        else:
            raise except_orm(_('Error!'),
                    _(u'No hay tipo de cambio definido para %s para la fecha %s'%(currency_id.name, fecha) ))
        return rate

    # 3. XML POLIZAS
    def action_xml_polizas(self, cr, uid, ids, context=None):
        curr_obj = self.pool.get("res.currency")
        model_data = self.pool.get("ir.model.data")
        this = self.browse(cr, uid, ids[0])
        data = {
            'mes': this.mes.name.split("/")[0],
            'ano': this.mes.fiscalyear_id.name,
            'rfc': this.company_id.partner_id.vat,
            'tipo_solicitud': this.tipo_solicitud,
            'polizas': []
        }
        if this.num_orden: data['num_orden'] = this.num_orden
        if this.num_tramite: data['num_tramite'] = this.num_tramite
        polizas_lines = this.polizas_lines
        if not this.polizas_lines:
            self._polizas(cr, uid, ids, context=context)
            polizas_lines = self.browse(cr, uid, ids[0]).polizas_lines
        for line in polizas_lines:
            poliza = {
                "num": "%s-%s"%(line.move_id.tipo_poliza, line.move_id.name),
                "fecha": line.move_id.date,
                "concepto": line.move_id.ref or line.move_id.name,
                "transacciones": []
            }
            for move_line in line.move_id.line_id:
                transaccion = {
                    "num_cta": move_line.account_id.code,
                    "des_cta": move_line.account_id.name,
                    "concepto": move_line.name,
                    "debe": move_line.debit,
                    "haber": move_line.credit,
                    'cheques': [],
                    'transferencias': [],
                    'otros_metodos': [],
                    'comprobantes': [],
                    'comprobantes_cfd_cbb': [],
                    'comprobantes_ext': []
                }
                #-----------------------------------------------------------
                for cheque in move_line.cheques:
                    vals = {
                        "num": cheque.num,
                        "banco": cheque.cta_ori.bank.code_sat,
                        "cta_ori": cheque.cta_ori.acc_number,
                        "fecha": cheque.fecha,
                        "monto": cheque.monto,
                        "benef": cheque.benef.name,
                        "rfc": cheque.benef.vat
                    }
                    if cheque.cta_ori.bank.extranjero:
                        vals["banco_ext"] = cheque.cta_ori.bank.name
                    if cheque.moneda:
                        vals.update({
                            "moneda": cheque.moneda.name,
                            "tip_camb": cheque.tipo_cambio
                        })
                    transaccion["cheques"].append(vals)
                #-----------------------------------------------------------
                for trans in move_line.transferencias:
                    vals = {
                        "cta_ori": trans.cta_ori.acc_number,
                        "banco_ori": trans.cta_ori.bank.code_sat,
                        "monto": trans.monto,
                        "cta_dest": trans.cta_dest.acc_number,
                        "banco_dest": trans.cta_dest.bank.code_sat,
                        "fecha": trans.fecha,
                        "benef": trans.cta_dest.partner_id.name,
                        "rfc": trans.cta_ori.partner_id.vat if trans.move_line_id.move_id.tipo_poliza == '1' else trans.cta_dest.partner_id.vat
                    }
                    if trans.cta_ori.bank.extranjero:
                        vals["banco_ori_ext"] = trans.cta_ori.bank.name
                    if trans.cta_dest.bank.extranjero:
                        vals["banco_dest_ext"] = trans.cta_dest.bank.name
                    if trans.moneda:
                        vals.update({
                            "moneda": trans.moneda.name,
                            "tip_camb": trans.tipo_cambio
                        })
                    transaccion["transferencias"].append(vals)
                #-----------------------------------------------------------                    
                for met in move_line.otros_metodos:
                    vals = {
                        "met_pago": met.metodo.code,
                        "fecha": met.fecha,
                        "benef": met.benef.name,
                        "rfc": met.benef.vat,
                        "monto": met.monto
                    }
                    if met.moneda:
                        vals.update({
                            "moneda": met.moneda.name,
                            "tip_camb": met.tipo_cambio
                        })
                    transaccion["otros_metodos"].append(vals)
                #-----------------------------------------------------------                    
                for comp in move_line.comprobantes:
                    vals = {
                        "uuid": comp.uuid,
                        "monto": comp.monto,
                        "rfc": comp.rfc
                    }
                    if comp.moneda:
                        vals.update({
                            "moneda": comp.moneda.name,
                            "tip_camb": comp.tipo_cambio
                        })
                    transaccion["comprobantes"].append(vals)
                #-----------------------------------------------------------                    
                for comp in move_line.comprobantes_cfd_cbb:
                    vals = {
                        "folio": comp.uuid,
                        "monto": comp.monto,
                        "rfc": comp.rfc
                    }
                    if comp.serie:
                        vals["serie"] = this.serie
                    if comp.moneda:
                        vals.update({
                            "moneda": comp.moneda.name,
                            "tip_camb": comp.tipo_cambio
                        })
                    transaccion["comprobantes"].append(vals)
                #-----------------------------------------------------------                    
                for comp in move_line.comprobantes_ext:
                    vals = {
                        "num": comp.num,
                        "monto": comp.monto,
                    }
                    if comp.tax_id: vals["tax_id"] = comp.tax_id
                    if comp.moneda:
                        vals.update({
                            "moneda": comp.moneda.name,
                            "tip_camb": comp.tipo_cambio
                        })
                    transaccion["comprobantes"].append(vals)
                poliza["transacciones"].append(transaccion)
            data["polizas"].append(poliza)

        vce = this.company_id.conta_elect_version or '1_3'
        fname = '{0}{1}{2}PL'.format(this.company_id.partner_id.vat or '', data.get('ano'), data.get('mes'))
        ctx = {
            'fname': fname+'.xml',
            'version': vce,
            'xml_file': 'xml_polizas.xml',
            'xml_xsd': 'PolizasPeriodo_%s.xsd'%(vce),
            'xml_xslt': 'PolizasPeriodo_%s.xslt'%(vce),
        }
        self._save_xml(cr, uid, this.id, data, context=ctx)
        return self._return_action(cr, uid, this.id, context=ctx)


    # 4. XML POLIZAS
    def action_xml_aux_folios(self, cr, uid, ids, context=None):
        curr_obj = self.pool.get("res.currency")
        model_data = self.pool.get("ir.model.data")
        code_cheque = model_data.get_object(cr, uid, "contabilidad_electronica", "metodo_pago_2").code
        code_transferencia = model_data.get_object(cr, uid, "contabilidad_electronica", "metodo_pago_3").code
        this = self.browse(cr, uid, ids[0])
        data = {
            'mes': this.mes.name.split("/")[0],
            'ano': this.mes.fiscalyear_id.name,
            'rfc': this.company_id.partner_id.vat,
            'tipo_solicitud': this.tipo_solicitud,
            'detalles': []
        }
        if this.num_orden: data['num_orden'] = this.num_orden
        if this.num_tramite: data['num_tramite'] = this.num_tramite
        polizas_lines = this.polizas_lines
        if not this.polizas_lines:
            self._polizas(cr, uid, ids, context=context)
            polizas_lines = self.browse(cr, uid, ids[0]).polizas_lines
        for line in polizas_lines:
            poliza = {
                "num": "%s-%s"%(line.move_id.tipo_poliza, line.move_id.name),
                "fecha": line.move_id.date,
                "concepto": line.move_id.ref or line.move_id.name,
                "comprobantes": [],
                "comprobantes_cfd_cbb": [],
                "comprobantes_ext": []
            }
            uuids = []
            for move_line in line.move_id.line_id:
                metodo_pago = False
                if move_line.transferencias:
                    metodo_pago = code_transferencia
                elif move_line.cheques:
                    metodo_pago = code_cheque
                elif move_line.otros_metodos:
                    metodo_pago = move_line.otros_metodos[0].metodo.code
                for comp in move_line.comprobantes:
                    if comp.uuid in uuids:
                        continue
                    uuids.append(comp.uuid)
                    vals = {
                        "uuid": comp.uuid,
                        "monto": comp.monto,
                        "rfc": comp.rfc
                    }
                    if comp.moneda:
                        vals.update({
                            "moneda": comp.moneda.name,
                            "tip_camb": comp.tipo_cambio
                        })
                    if metodo_pago:
                        vals.update({"MetPagoAux": metodo_pago})
                    poliza["comprobantes"].append(vals)
                #-----------------------------------------------------------                    
                for comp in move_line.comprobantes_cfd_cbb:
                    vals = {
                        "folio": comp.uuid,
                        "monto": comp.monto,
                        "rfc": comp.rfc
                    }
                    if comp.serie:
                        vals["serie"] = comp.serie
                    if comp.moneda:
                        vals.update({
                            "moneda": comp.moneda.name,
                            "tip_camb": comp.tipo_cambio
                        })
                    if metodo_pago:
                        vals.update({"MetPagoAux": metodo_pago})
                    poliza["comprobantes_cfd_cbb"].append(vals)
                #-----------------------------------------------------------                    
                for comp in move_line.comprobantes_ext:
                    vals = {
                        "num": comp.num,
                        "monto": comp.monto,
                    }
                    if comp.tax_id: vals["tax_id"] = comp.tax_id
                    if comp.moneda:
                        vals.update({
                            "moneda": comp.moneda.name,
                            "tip_camb": comp.tipo_cambio
                        })
                    if metodo_pago:
                        vals.update({"MetPagoAux": metodo_pago})
                    poliza["comprobantes_ext"].append(vals)
            if len(poliza["comprobantes"]) > 0:
                data["detalles"].append(poliza)
        
        ctx = context.copy()
        vce = this.company_id.conta_elect_version or '1_3'
        fname = '{0}{1}{2}XF'.format(this.company_id.partner_id.vat or '', data.get('ano'), data.get('mes'))
        ctx = {
            'version': vce,
            'xml_file': 'xml_aux_folios.xml',
            'xml_xsd': 'AuxiliarFolios_%s.xsd'%(vce),
            'xml_xslt': 'AuxiliarFolios_%s.xslt'%(vce),
            'fname': fname+'.xml'
        }
        self._save_xml(cr, uid, this.id, data, context=ctx)
        return self._return_action(cr, uid, this.id, context=ctx)


    def action_xml_aux_cuentas(self, cr, uid, ids, context=None):
        this = self.browse(cr, uid, ids[0])
        if not this.tipo_solicitud:
            raise osv.except_osv("Error", "Favor de indicar el tipo de solicitud")
        data = {
            'mes': this.mes.name.split("/")[0],
            'ano': this.mes.fiscalyear_id.name,
            'rfc': this.company_id.partner_id.vat,
            'tipo_solicitud': this.tipo_solicitud,
            'cuentas': [],
        }        
        if this.num_orden: data['num_orden'] = this.num_orden
        if this.num_tramite: data['num_tramite'] = this.num_tramite
        self._balanza(cr, uid, ids, context=context)
        balanza_lines = self.browse(cr, uid, ids[0]).balanza_lines
        move_line_obj = self.pool.get("account.move.line")
        for line in balanza_lines:
            cuenta = {
                'inicial': line.saldo_inicial,
                'final': line.saldo_final,
                'codigo': line.account_id.code,
                'descripcion': line.account_id.name,
                'transacciones': []
            }
            transacciones_ids = move_line_obj.search(cr, uid, [('company_id','=',this.company_id.id),
                ('account_id','=',line.account_id.id),('period_id','=',this.mes.id)])
            for t in move_line_obj.browse(cr, uid, transacciones_ids):
                cuenta["transacciones"].append({
                    'fecha': t.date, 
                    'num': "%s-%s"%(t.move_id.tipo_poliza, t.move_id.name),
                    'debe': t.debit,
                    'haber': t.credit,
                    'concepto': t.name
                })
            if len(cuenta["transacciones"]) > 0:
                data["cuentas"].append(cuenta)

        ctx = context.copy()
        vce = this.company_id.conta_elect_version or '1_3'
        fname = '{0}{1}{2}XC'.format(this.company_id.partner_id.vat or '', data.get('ano'), data.get('mes'))
        ctx = {
            'version': vce,
            'xml_file': 'xml_aux_cuentas.xml',
            'xml_xsd': 'AuxiliarCtas_%s.xsd'%(vce),
            'xml_xslt': 'AuxiliarCtas_%s.xslt'%(vce),
            'fname': fname+'.xml'
        }
        self._save_xml(cr, uid, this.id, data, context=ctx)
        return self._return_action(cr, uid, this.id, context=ctx)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: