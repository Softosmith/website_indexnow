/** @odoo-module **/

import { registry } from "@web/core/registry";

async function refreshIndexNowSettings(env, action) {
    const controller = env.services.action.currentController;
    if (!controller) {
        return;
    }

    await env.services.action.restore(controller.jsId);

    const settingId = action.params?.setting_id;
    if (!settingId) {
        return;
    }

    const setting = document.getElementById(settingId);
    if (setting) {
        setting.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}

registry.category("actions").add(
    "website_indexnow_refresh_settings",
    refreshIndexNowSettings
);
