# -*- coding: utf-8 -*-
{
    'name': "BIAS Base",

    'summary': """Agrega informacion basica para el timbrado""",
    'author': 'OpenBIAS',
    'website': "http://bias.com.mx",
    'category' : 'Accounting & Finance',
    'version': '2.0.2',
    'license': 'AGPL-3',
    'depends': [
        'sale', 'purchase', 'account'
    ],
    'data': [
        'data/report_data.xml',
        'views/models_views.xml'
    ],
    'installable': True,
}
