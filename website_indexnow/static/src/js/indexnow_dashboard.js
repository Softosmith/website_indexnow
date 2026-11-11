/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class IndexNowDashboard extends Component {
    static template = "website_indexnow.IndexNowDashboard";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            busy: false,
            days: 7,
            websiteId: false,
            data: {
                kpis: {},
                activity: [],
                websites: [],
                recent_activity: [],
                queue_preview: [],
            },
        });
        onWillStart(() => this.loadData());
    }

    async loadData() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("website", "get_indexnow_dashboard_data", [], {
                days: this.state.days,
                website_id: this.state.websiteId || false,
            });
        } finally {
            this.state.loading = false;
        }
    }

    async setPeriod(days) {
        this.state.days = days;
        await this.loadData();
    }

    async onWebsiteFilter(event) {
        this.state.websiteId = Number(event.target.value) || false;
        await this.loadData();
    }

    get maxActivity() {
        return Math.max(1, ...this.state.data.activity.map((day) => day.submitted + day.failed));
    }

    barHeight(value) {
        return Math.max(value ? 8 : 0, Math.round((value / this.maxActivity) * 100));
    }

    healthClass(health) {
        return {
            ready: "success",
            failures: "danger",
            key_unverified: "info",
            key_missing: "warning",
            domain_missing: "warning",
            disabled: "secondary",
        }[health] || "secondary";
    }

    resultClass(result) {
        return { success: "success", accepted: "info", failed: "danger" }[result] || "secondary";
    }

    async runWebsiteAction(websiteId, method) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const result = await this.orm.call("website", method, [[websiteId]]);
            if (result) {
                await this.action.doAction(result);
            }
            await this.loadData();
        } finally {
            this.state.busy = false;
        }
    }

    async openHistory(websiteId = false) {
        if (websiteId) {
            const result = await this.orm.call("website", "action_indexnow_open_history", [[websiteId]]);
            return this.action.doAction(result);
        }
        return this.action.doAction("website_indexnow.action_indexnow_submission");
    }

    openQueue(domain = []) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: "URL Queue",
            res_model: "website.indexnow.queue",
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    openSettings() {
        return this.action.doAction("website_indexnow.action_open_indexnow_settings");
    }
}

registry.category("actions").add("website_indexnow.dashboard", IndexNowDashboard);
