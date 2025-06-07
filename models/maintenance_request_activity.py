from odoo import models, fields, api, _

class MaintenanceRequestActivity(models.Model):
    _name = 'maintenance.request.activity'
    _description = 'Maintenance Request Activity'
    parent_name = 'parent_id'
    parent_store = True
    rec_name = 'description'
    checklist_id = fields.Many2one('maintenance.request', string="Maintenance Request")
    parent_id = fields.Many2one('maintenance.request.activity', string="Parent Task")
    child_ids = fields.One2many('maintenance.request.activity', 'parent_id', string="Sub-tasks")
    parent_path = fields.Char(index=True)
    done = fields.Boolean(string="Done")
    description = fields.Char(string="Description")
    

    def write(self, vals):
        """
        Override the write method to automatically update the stage of the maintenance request when the task is marked as done."""
        res = super().write(vals)
        if 'done' in vals:
            for activity in self:
                if activity.checklist_id:
                    activity.checklist_id.check_and_update_stage()
        return res

   
