"use strict";
const fs = require("node:fs"), path = require("node:path");
const { sourceIdentity, fixtureIdentity, cases } = require("./identity");
class InventoryReporter {
  onBegin(config, suite) {
    const strict = config.reporter.find(entry => String(entry[0]).endsWith("strict-reporter.js"))?.[1];
    // --reporter replaces configured reporters; inventory requires the explicit suite contract.
    const contract = process.env.BIJUX_UI_SUITE_CONTRACT ? JSON.parse(fs.readFileSync(process.env.BIJUX_UI_SUITE_CONTRACT)) : strict;
    if (!contract || contract.assignedShard) throw new Error("Inventory requires an unsharded suite contract");
    const items = cases(suite), projects = contract.canonicalProjects;
    if (!projects || !items.length || projects.some(project => items.filter(item => item.project === project.name).length !== project.count)) throw new Error("Canonical inventory does not match the suite contract");
    this.report = { schema: 1, kind: "canonical_case_inventory", qualification_scope: contract.scope || "generated_frontend", source_identity: sourceIdentity(), fixture_identity: fixtureIdentity(contract), canonical_projects: projects, cases: items };
  }
  onEnd() {
    if (!this.report || !process.env.BIJUX_UI_INVENTORY) throw new Error("Inventory output is required");
    fs.mkdirSync(path.dirname(process.env.BIJUX_UI_INVENTORY), { recursive: true });
    fs.writeFileSync(process.env.BIJUX_UI_INVENTORY, JSON.stringify(this.report, null, 2) + "\n");
  }
}
module.exports = InventoryReporter;
