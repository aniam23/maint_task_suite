from odoo import models, fields, api, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import io
import base64
import xlsxwriter
class MaintenanceEquipment(models.Model):
    
    _inherit = 'maintenance.equipment'
    brand = fields.Char(string="Marca")
    machine_number = fields.Char(string="Numero de maquina")