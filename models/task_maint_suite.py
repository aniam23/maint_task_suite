from odoo import models, fields, api, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import io
import base64
import xlsxwriter
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'
    task_ids = fields.One2many('maintenance.request.activity', 'checklist_id', string="Tareas")
    show_date_selection = fields.Boolean(default=False)
    report_type = fields.Selection([('weekly', 'Semanal'), ('monthly', 'Mensual')], string="Tipo de Reporte")
    selected_month = fields.Date(string="Mes de Referencia", default=fields.Date.today())
    document_ids = fields.Binary(string="PDF", help="Sube un PDF para previsualización")
    week_number = fields.Selection([
        ('1', 'Semana 1 (1-7)'),
        ('2', 'Semana 2 (8-14)'),
        ('3', 'Semana 3 (15-21)'),
        ('4', 'Semana 4 (22-28)'),
        ('5', 'Semana 5 (29-31)')
    ], string="Semana del Mes", default='1')
    color = fields.Integer(
        string='Color', 
        compute='compute_task_color', 
        store=True,
        help="Color automático según estado de la tarea: "
             "10=Verde(completado), 1=Rojo(vencido), 2=Amarillo(próximo), 0=Gris(sin fecha/no urgente)"
    )

    @api.constrains('schedule_date')
    def check_schedule_date(self):
        """Valida que se ingrese una fecha de programación para la tarea"""
        for request in self:
            if not request.schedule_date:
                raise ValidationError(_("Debe ingresar una fecha de inicio para la tarea."))
    def copy_activities_to_child_tasks(self):
        """
        Copy activities from parent task to child tasks, but don't copy the 'done' status.
        This ensures child tasks get the same checklist items but maintain their own completion state.
        """
        for parent_request in self:
            if not parent_request.child_request_ids:
                continue  # Skip if no child tasks
                
            for child_request in parent_request.child_request_ids:
                # Get existing activity descriptions in child task
                existing_child_descriptions = child_request.task_ids.mapped('description')
                
                # Find new activities in parent that don't exist in child
                new_activities = parent_request.task_ids.filtered(
                    lambda a: a.description and a.description not in existing_child_descriptions
                )
                
                # Create copies of the new activities for the child task
                for activity in new_activities:
                    # Copy the activity but reset 'done' to False for child tasks
                    activity.copy({
                        'checklist_id': child_request.id,
                        'done': False,  # Reset to not done for child tasks
                        'parent_id': False,  # Don't copy parent-child relationships between activities
                    })
    @api.depends('stage_id', 'repeat_until', 'schedule_date', 'task_ids.done', 
             'child_request_ids.stage_id', 'child_request_ids.repeat_until', 
             'child_request_ids.task_ids.done', 'parent_request_id.stage_id',
             'parent_request_id.repeat_until', 'parent_request_id.task_ids.done')
    def compute_task_color (self):
        """
        Asigna un color a la tarea en función de su estado y fecha de vencimiento,
        considerando tanto las tareas padre como hijas.
        """
        today = fields.Date.today()

        for request in self:
            # Función principal para asignar colores 
            def get_color(req):
                # VERDE (Completado)
                if req.stage_id and req.stage_id.sequence >= 3:
                    return 10
                elif req.task_ids and all(task.done for task in req.task_ids):
                    return 10

                # ROJO (Tarea Atrasada)
                elif req.repeat_until:
                    due_date = fields.Date.to_date(req.repeat_until)
                    if due_date < today:
                        return 1

                    # calcula la diferencia de dias entre la fecha de vencimiento y la fecha de hoy
                    delta_days = (due_date - today).days

                    # AMARILLO (1-3 días para vencer)
                    if 1 <= delta_days <= 3:
                        return 3

                    # GRIS (4-8 días para vencer)
                    elif 4 <= delta_days <= 8:
                        return 0

                # Gris (mas de 8 días para vencer)
                return 8

            # Aplicar color a la tarea actual
            request.color = get_color(request)

            # Si es una tarea padre, actualizar colores de hijas
            if request.child_request_ids:
                for child in request.child_request_ids:
                    child.color = get_color(child)
                    # Forzar la escritura en la base de datos para que se refleje inmediatamente
                    child.write({'color': child.color})

            # Si es una tarea hija, actualizar color del padre
            if request.parent_request_id:
                parent = request.parent_request_id
                parent.color = get_color(parent)
                # Forzar la escritura en la base de datos
                parent.write({'color': parent.color})

    def write(self, vals):
        """Update recurring requests based on changes to the original request
            param vals: dictionary containing the fields and values to update
            return: update tasks"""
        # Validar schedule_date si está presente en los valores
        if 'schedule_date' in vals and not vals['schedule_date']:
            raise ValidationError(_("Debe ingresar una fecha de inicio (schedule_date) para la tarea."))

        # Actualizar la solicitud de mantenimiento
        res = super().write(vals)

        # Actualiza las solicitudes recurrentes
        campos_repeticion = ['frequency', 'repeat_task', 'repeat_interval',
                             'repeat_end_type', 'repeat_until', 'repeat_count', 'schedule_date']
        # Recorre todas las solicitudes
        for request in self:
            # Si se actualiza una de las siguientes variables, actualiza las solicitudes recurrentes
            if any(field in vals for field in campos_repeticion):
                # Si es padre, actualiza las solicitudes recurrentes
                if request.frequency and not request.parent_request_id:
                    # Actualiza las tareas hijas sin duplicar ni eliminar
                    request.update_recurring_requests()

        # Copy activities to child tasks if parent's activities were modified
        if 'task_ids' in vals:
            self.copy_activities_to_child_tasks()

        return res

    def action_show_weekly_options(self):
        """
        Muestra las opciones de selección de semana y mes para el reporte semanal """
        self.write({
            'show_date_selection': True,
            'report_type': 'weekly',
            'selected_month': fields.Date.today(),
            'week_number': '1'
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_show_monthly_options(self):
        """
        Muestra las opciones de selección de mes para el reporte mensual """
        self.write({
            'show_date_selection': True,
            'report_type': 'monthly',
            'selected_month': fields.Date.today()
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def get_weekly_date_range(self):
        """
        Calcula el rango de fechas para el reporte semanal basado en la semana seleccionada."""
        month_start = self.selected_month.replace(day=1)
        week_num = int(self.week_number)
        start_date = month_start + timedelta(days=(week_num - 1) * 7)
        month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)
        end_date = min(start_date + timedelta(days=6), month_end)
        return start_date, end_date

    def generate_report(self):
        """
        Genera el reporte basado en el tipo seleccionado (semanal o mensual) """
        if not self.report_type:
            raise UserError(_('Debe seleccionar un tipo de reporte'))

        if self.report_type == 'weekly':
            if not self.week_number:
                raise UserError(_('Debe seleccionar una semana para el reporte semanal'))
            return self.generate_weekly_excel()
        else:
            return self.generate_monthly_excel()

    def generate_weekly_excel(self):
        """
        Genera el reporte semanal en formato Excel """
        start_date, end_date = self._get_weekly_date_range()
        domain = [('request_date', '>=', start_date), ('request_date', '<=', end_date)]
        filename = f"Reporte_Semanal_{start_date.strftime('%Y-%m-%d')}_al_{end_date.strftime('%Y-%m-%d')}.xlsx"
        return self.generate_excel_report(domain, filename)

    def generate_monthly_excel(self):
        """ Genera el reporte mensual en formato Excel """
        start_date = self.selected_month.replace(day=1)
        end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)
        domain = [('request_date', '>=', start_date), ('request_date', '<=', end_date)]
        filename = f"Reporte_Mensual_{start_date.strftime('%Y-%m')}.xlsx"
        return self.generate_excel_report(domain, filename)

    def generate_excel_report(self, domain, filename):
        """ Genera el reporte en formato Excel para el dominio y nombre de archivo especificados """
        requests = self.search(domain, order='request_date asc')
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Reporte')
        header_format = workbook.add_format({
            'bold': True, 'border': 1, 'bg_color': '#ff8000',
            'font_color': 'white', 'align': 'center'
        })
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})

        # Definición de encabezados y anchos de columna
        headers = [
            ('ID', 8), ('Fecha', 12), ('Equipo', 20),
            ('Nombre', 40), ('Estado', 15), ('Descripcion', 40),
            ('Responsable', 20)
        ]

        # Escribir encabezados
        for col, (header, width) in enumerate(headers):
            worksheet.write(0, col, header, header_format)
            worksheet.set_column(col, col, width)

        # Escribir datos
        for row, req in enumerate(requests, 1):
            worksheet.write(row, 0, req.id)
            worksheet.write_datetime(row, 1, req.request_date, date_format)
            worksheet.write(row, 2, req.equipment_id.name or '')
            worksheet.write(row, 3, req.name or '')  # Nombre
            worksheet.write(row, 4, req.stage_id.name or '')  # Estado
            worksheet.write(row, 5, req.description or '')  # Descripción
            worksheet.write(row, 6, req.user_id.name or '')  # Responsable

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': file_data,
            'res_model': 'maintenance.request',
            'type': 'binary',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def check_and_update_stage(self):
        """
        Verifica el estado de las tareas asociadas a una solicitud de mantenimiento:
        - Si todas las tareas están completadas, cambia a estado 'reparado' (sequence=3)
        - Si al menos una  está completada, cambia a estado 'en progreso' (sequence=2)
        """
        for request in self:
            if request.task_ids:
                # Primero verifica la condición más restrictiva (todas completadas)
                if all(task.done for task in request.task_ids):
                    new_stage = self.env['maintenance.stage'].search([('sequence', '=', 3)], limit=1)
                    if new_stage and request.stage_id != new_stage:
                        request.stage_id = new_stage
                # Luego verifica si al menos una está completada
                elif any(task.done for task in request.task_ids):
                    new_stage = self.env['maintenance.stage'].search([('sequence', '=', 2)], limit=1)
                    if new_stage and request.stage_id != new_stage:
                        request.stage_id = new_stage
    
     

    