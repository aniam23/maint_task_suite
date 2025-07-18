# -*- coding: utf-8 -*-
{
    'name': "Task Maintenance Suite",

    'summary': """
        Task Maintenance Suite""",

    'description': """
       Automated Task Management Suite for Odoo
    """,  
    'author': "Anilu Amado Aguero",
    'website': "http://www.horizontrailers.com",
    'sequence': 3,
    'category': 'All',

    'version': '1.0',

    'depends': ['base','maintenance','maintenance_task'], 
    'data': [
        'security/ir.model.access.csv',
        'views/task_maint_suite.xml',
        'views/maintenance_request_activity.xml'
       
    ],

    'images': ['static/description/Task status and subtasks.png'],
    
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    
}