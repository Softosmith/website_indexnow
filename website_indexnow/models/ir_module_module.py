from odoo import models


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    def button_immediate_uninstall(self):
        """Return to the complete Apps list after uninstalling this app."""
        return_to_apps = 'website_indexnow' in self.mapped('name')
        apps_action = None
        if return_to_apps:
            apps_action = self.env['ir.actions.actions']._for_xml_id(
                'base.open_module_tree'
            )

        result = super().button_immediate_uninstall()
        return apps_action if return_to_apps else result
