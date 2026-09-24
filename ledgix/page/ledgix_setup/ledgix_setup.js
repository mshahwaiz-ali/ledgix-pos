frappe.pages["ledgix-setup"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __("Ledgix Client Setup"),
    single_column: true,
  });
  wrapper.ledgix_setup = new LedgixClientSetup(page, wrapper);
};

class LedgixClientSetup {
  constructor(page, wrapper) {
    this.page = page;
    this.wrapper = wrapper;
    this.boot = null;
    this.evaluation = null;
    this.onboarding = null;
    this.make_fields();
    this.make_body();
    this.bind_actions();
    this.load();
  }

  make_fields() {
    this.company = this.page.add_field({
      fieldname: "company",
      label: __("Company"),
      fieldtype: "Link",
      options: "Company",
      change: () => this.check(false),
    });
    this.profile = this.page.add_field({
      fieldname: "business_profile",
      label: __("Business Profile"),
      fieldtype: "Select",
      options: "Invoice + FBR Only\nSmall Retail\nFull Retail\nB2B\nMixed",
      change: () => this.check(false),
    });
    this.warehouse = this.page.add_field({
      fieldname: "warehouse",
      label: __("Warehouse"),
      fieldtype: "Link",
      options: "Warehouse",
      get_query: () => ({
        filters: {
          company: this.company.get_value() || "",
          is_group: 0,
          disabled: 0,
        },
      }),
      change: () => this.check(false),
    });
    this.price_list = this.page.add_field({
      fieldname: "selling_price_list",
      label: __("Selling Price List"),
      fieldtype: "Link",
      options: "Price List",
      get_query: () => ({ filters: { enabled: 1, selling: 1 } }),
      change: () => this.check(false),
    });
    this.pos_profile = this.page.add_field({
      fieldname: "pos_profile",
      label: __("POS Profile"),
      fieldtype: "Link",
      options: "POS Profile",
      get_query: () => ({
        filters: {
          company: this.company.get_value() || "",
          disabled: 0,
        },
      }),
      change: () => this.check(false),
    });
    this.apply_defaults = this.page.add_field({
      fieldname: "apply_standard_defaults",
      label: __("Apply ERPNext Site Defaults"),
      fieldtype: "Check",
      default: 1,
      description: __("Set the selected Company, Selling Price List and Warehouse as site defaults where applicable."),
    });
  }

  make_body() {
    this.$body = $(this.wrapper).find(".layout-main-section");
    this.$body.html(`
      <div class="ledgix-setup-shell">
        <div class="ledgix-setup-hero">
          <h3>${__("Configure Ledgix without forking the product")}</h3>
          <div class="ledgix-setup-muted">
            ${__("Choose a product preset and existing ERPNext configuration. This wizard does not create duplicate Items, Customers, accounting ledgers or stock ledgers.")}
          </div>
        </div>
        <div class="ledgix-setup-grid">
          <div class="ledgix-setup-card" data-role="preset"></div>
          <div class="ledgix-setup-card" data-role="state"></div>
        </div>
        <div class="ledgix-setup-card">
          <h5>${__("Configuration readiness")}</h5>
          <div data-role="checks" class="ledgix-setup-muted">${__("Loading setup status...")}</div>
          <div data-role="ready" class="ledgix-setup-ready"></div>
        </div>
        <div class="ledgix-setup-card">
          <h5>${__("Operational onboarding")}</h5>
          <div class="ledgix-setup-muted" style="margin-bottom:10px;">
            ${__("Handover checks reuse ERPNext authority and verify accounting/payment prerequisites, named Ledgix users, FBR safety state and operational evidence. FBR Production remains a separate activation gate.")}
          </div>
          <div data-role="onboarding-checks" class="ledgix-setup-muted">${__("Loading onboarding readiness...")}</div>
          <div data-role="onboarding-ready" class="ledgix-setup-ready"></div>
        </div>
      </div>
    `);
  }

  bind_actions() {
    this.page.set_primary_action(__("Apply Configuration"), () => this.apply(), "check");
    this.page.add_inner_button(__("Check Readiness"), () => this.check(true));
    this.page.add_inner_button(__("Refresh Onboarding"), () => this.refreshOnboarding(true));
    this.page.add_inner_button(__("Business Profile"), () => frappe.set_route("Form", "Ledgix Business Profile"));
    this.page.add_inner_button(__("Tax & FBR Center"), () => frappe.set_route("ledgix-tax-center"));
  }

  payload() {
    return {
      company: this.company.get_value(),
      business_profile: this.profile.get_value(),
      warehouse: this.warehouse.get_value(),
      selling_price_list: this.price_list.get_value(),
      pos_profile: this.pos_profile.get_value(),
      apply_standard_defaults: this.apply_defaults.get_value() ? 1 : 0,
    };
  }

  async load() {
    this.page.set_indicator(__("Loading"), "orange");
    const response = await frappe.call({
      method: "ledgix_saas.api.client_setup.get_client_setup_boot",
      freeze: false,
    });
    this.boot = response.message || {};
    const current = this.boot.current || {};
    const resolved = current.resolved || {};
    const state = this.boot.state || {};

    this.company.set_value(resolved.company || state.setup_company || "");
    this.profile.set_value(current.business_profile || state.business_profile || "Small Retail");
    this.warehouse.set_value(resolved.warehouse || "");
    this.price_list.set_value(resolved.selling_price_list || "");
    this.pos_profile.set_value(resolved.pos_profile || "");
    this.apply_defaults.set_value(1);
    this.render(current);
    await this.refreshOnboarding(false);
    this.page.clear_indicator();
  }

  async check(showAlert = false) {
    if (!this.profile.get_value()) return;
    const response = await frappe.call({
      method: "ledgix_saas.api.client_setup.evaluate_client_setup",
      args: { payload: this.payload() },
      freeze: false,
    });
    this.render(response.message || {});
    if (showAlert) {
      frappe.show_alert({
        message: this.evaluation?.ready ? __("Client setup is ready to apply.") : __("Resolve the blocking setup checks first."),
        indicator: this.evaluation?.ready ? "green" : "orange",
      });
    }
  }

  async refreshOnboarding(showAlert = false) {
    const response = await frappe.call({
      method: "ledgix_saas.api.client_readiness.get_client_readiness",
      args: { strict_evidence: 0 },
      freeze: false,
    });
    this.onboarding = response.message || {};
    this.renderOnboarding(this.onboarding);
    if (showAlert) {
      frappe.show_alert({
        message: this.onboarding?.ready ? __("Operational onboarding checks are green.") : __("Operational onboarding still has blockers."),
        indicator: this.onboarding?.ready ? "green" : "orange",
      });
    }
  }

  presetFor(name) {
    return (this.boot?.presets || []).find((row) => row.name === name) || {};
  }

  checkHtml(row) {
    const klass = row.passed ? "is-ok" : (row.blocking ? "is-blocker" : "is-warning");
    const indicator = row.passed ? "✓" : (row.blocking ? "✕" : "!");
    const category = row.category ? `<div class="ledgix-setup-muted">${frappe.utils.escape_html(row.category)}</div>` : "";
    const target = row.target ? `<div class="ledgix-setup-muted">${__("Configure")}: ${frappe.utils.escape_html(row.target)}</div>` : "";
    return `
      <div class="ledgix-setup-check ${klass}">
        <div class="indicator">${indicator}</div>
        <div>
          <div>${frappe.utils.escape_html(row.message || "")}</div>
          ${category}
          ${target}
        </div>
      </div>
    `;
  }

  render(evaluation) {
    this.evaluation = evaluation || {};
    const preset = this.presetFor(this.evaluation.business_profile || this.profile.get_value());
    const state = this.boot?.state || {};
    const setupState = state.setup_complete
      ? `${__("Configured")} · v${state.setup_version || 0} · ${frappe.utils.escape_html(state.setup_company || "")}`
      : __("Not yet completed through the Phase 13 wizard");

    this.$body.find('[data-role="preset"]').html(`
      <h5>${frappe.utils.escape_html(preset.title || this.profile.get_value() || "")}</h5>
      <div>${frappe.utils.escape_html(preset.summary || "")}</div>
      <div class="ledgix-setup-muted" style="margin-top:8px;">${frappe.utils.escape_html(preset.best_for || "")}</div>
    `);
    this.$body.find('[data-role="state"]').html(`
      <h5>${__("Site setup state")}</h5>
      <div>${frappe.utils.escape_html(setupState)}</div>
      <div class="ledgix-setup-muted" style="margin-top:8px;">${__("ERPNext remains the business authority; Ledgix presets only curate configuration and product surface.")}</div>
    `);

    const checks = this.evaluation.checks || [];
    if (!checks.length) {
      this.$body.find('[data-role="checks"]').html(__("No readiness result yet."));
      return;
    }

    this.$body.find('[data-role="checks"]').html(checks.map((row) => this.checkHtml(row)).join(""));
    this.$body.find('[data-role="ready"]').html(
      this.evaluation.ready
        ? `<span class="text-success">${__("Ready to apply configuration")}</span>`
        : `<span class="text-warning">${__("Setup has blocking prerequisites")}</span>`
    );
  }

  renderOnboarding(readiness) {
    const checks = readiness?.checks || [];
    if (!checks.length) {
      this.$body.find('[data-role="onboarding-checks"]').html(__("No onboarding readiness result yet."));
      this.$body.find('[data-role="onboarding-ready"]').empty();
      return;
    }
    this.$body.find('[data-role="onboarding-checks"]').html(checks.map((row) => this.checkHtml(row)).join(""));
    const next = frappe.utils.escape_html(readiness.next_workstream || "");
    this.$body.find('[data-role="onboarding-ready"]').html(
      readiness.ready
        ? `<span class="text-success">${__("Operational onboarding checks are green")}</span>${next ? `<div class="ledgix-setup-muted">${__("Next")}: ${next}</div>` : ""}`
        : `<span class="text-warning">${__("Operational onboarding has blocking prerequisites")}</span>`
    );
  }

  async apply() {
    await this.check(false);
    if (!this.evaluation?.ready) {
      frappe.msgprint({
        title: __("Setup blocked"),
        message: __("Resolve the blocking readiness checks before applying this client profile."),
        indicator: "orange",
      });
      return;
    }

    frappe.confirm(
      __("Apply this Ledgix client profile and the selected safe ERPNext site defaults?"),
      async () => {
        const response = await frappe.call({
          method: "ledgix_saas.api.client_setup.apply_client_setup",
          args: { payload: this.payload() },
          freeze: true,
          freeze_message: __("Applying Ledgix client configuration..."),
        });
        const result = response.message || {};
        this.boot.state = result.state || this.boot.state;
        this.render(result.evaluation || {});
        await this.refreshOnboarding(false);
        frappe.show_alert({ message: result.message || __("Client setup applied."), indicator: "green" }, 6);
      }
    );
  }
}
