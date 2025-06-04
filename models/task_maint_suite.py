from dateutil.relativedelta import relativedelta
from odoo import models, fields, api
from datetime import date
from odoo.fields import Date
from odoo.exceptions import UserError  
from odoo.exceptions import ValidationError

class MaintenanceRequest(models.Model):  
    _inherit = 'maintenance.request'

    
   