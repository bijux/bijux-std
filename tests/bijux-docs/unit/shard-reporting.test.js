"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), fs = require("node:fs"), path = require("node:path"), cp = require("node:child_process"), crypto = require("node:crypto");
const { configureProjects } = require("../reporting/projects");
const root = path.resolve(__dirname, "../../../artifacts/bijux-docs/shard-reporting-units");
fs.mkdirSync(root, { recursive: true });
const projects = ["chromium", "firefox", "webkit"].map(engine => ({ name: `${engine}-phone`, use: { browserName: engine }, metadata: { required_case_count: 1 } }));
const config = { projects, reporter: [["generated/strict-reporter.js", {}], ["junit", { outputFile: "junit.xml" }]] };
test("engine selection preserves the complete canonical contract", () => {
  const selected = configureProjects(config, { BIJUX_UI_BROWSER_ENGINE: "firefox" });
  assert.deepEqual(selected.projects.map(project => project.name), ["firefox-phone"]);
  assert.equal(selected.reporter[0][1].canonicalProjects.length, 3);
  assert.equal(configureProjects(config, {}).projects.length, 3);
});
test("explicit selection rejects ambiguous, unknown and empty projects", () => {
  for (const env of [{ BIJUX_UI_BROWSER_ENGINE: "" }, { BIJUX_UI_PROJECTS: "" }, { BIJUX_UI_BROWSER_ENGINE: "unknown" }, { BIJUX_UI_PROJECTS: "unknown" }, { BIJUX_UI_PROJECTS: "chromium-phone," }, { BIJUX_UI_PROJECTS: "chromium-phone,chromium-phone" }, { BIJUX_UI_PROJECTS: "chromium-phone", BIJUX_UI_BROWSER_ENGINE: "chromium" }]) assert.throws(() => configureProjects(config, env));
});
const canonical = projects.map(project => ({ name: project.name, engine: project.use.browserName, count: 1 }));
function fixture(label) {
  const dir = path.join(root, label); fs.mkdirSync(dir, { recursive: true });
  const source = { head: "a".repeat(40), tree_sha256: "b".repeat(64) }, bundle = { manifest_sha256: "c".repeat(64) };
  const cases = canonical.map((project, i) => ({ id: `case-${i}`, project: project.name, title: "ordinary input", file: "ui.spec.js", line: i + 1 }));
  const inventory = { kind: "canonical_case_inventory", qualification_scope: "fixture", source_identity: source, fixture_identity: bundle, canonical_projects: canonical, cases };
  const reports = canonical.map((project, i) => {
    const xml = `<testsuites tests="1" failures="0" skipped="0" errors="0"><testsuite hostname="${project.name}" tests="1"><testcase name="ordinary input"/></testsuite></testsuites>`;
    const file = path.join(dir, project.name + ".xml"); fs.writeFileSync(file, xml);
    return { status: "passed", qualification_kind: "assigned_engine_shard", qualification_scope: "fixture", source_identity: source, fixture_identity: bundle, canonical_projects: canonical, assigned_project_names: [project.name], expected_cases: [cases[i]], projects: { [project.name]: { expected: 1, executed: 1, passed: 1, failed: 0, skipped: 0 } }, results: [{ case_id: cases[i].id, project: project.name, status: "passed", retry: 0, errors: [], annotations: [{ type: "browser-version", description: "1.2.3" }] }], junit: { path: file, sha256: crypto.createHash("sha256").update(xml).digest("hex") } };
  });
  return { dir, inventory, reports };
}
function qualify(label, mutate = () => {}) {
  const input = fixture(label); mutate(input);
  const inventory = path.join(input.dir, "inventory.json"); fs.writeFileSync(inventory, JSON.stringify(input.inventory));
  const args = [path.resolve(__dirname, "../reporting/aggregate.py"), "--inventory", inventory];
  input.reports.forEach((report, i) => { const file = path.join(input.dir, `report-${i}.json`); fs.writeFileSync(file, JSON.stringify(report)); args.push("--report", file); });
  args.push("--output", path.join(input.dir, "aggregate.json"));
  return cp.spawnSync(process.env.BIJUX_UI_PYTHON || "python3", args, { encoding: "utf8", env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" } });
}
test("complete disjoint engine evidence qualifies", () => assert.equal(qualify("complete").status, 0));
const negatives = {
  "missing engine": input => input.reports.pop(),
  "missing case": input => input.reports[0].results.pop(),
  "failed case": input => input.reports[0].results[0].status = "failed",
  "skipped case": input => input.reports[0].results[0].status = "skipped",
  "retried case": input => input.reports[0].results[0].retry = 1,
  "duplicate shard": input => input.reports.push(input.reports[0]),
  "duplicate execution": input => input.reports[0].results.push(input.reports[0].results[0]),
  "wrong source": input => input.reports[0].source_identity = { head: "d".repeat(40) },
  "wrong bundle": input => input.reports[0].fixture_identity = { manifest_sha256: "d".repeat(64) },
  "missing version": input => input.reports[0].results[0].annotations = [],
  "wrong engine version": input => { input.reports[1].canonical_projects[1].engine = "chromium"; input.reports[1].results[0].annotations[0].description = "other"; },
  "wrong case identity": input => input.reports[0].results[0].case_id = "unknown",
  "wrong expected case": input => input.reports[0].expected_cases = [],
  "wrong count": input => input.reports[0].projects["chromium-phone"].executed = 0,
  "changed JUnit": input => fs.appendFileSync(input.reports[0].junit.path, "changed"),
  "missing JUnit": input => fs.unlinkSync(input.reports[0].junit.path),
  "JUnit wrong case": input => { const item=input.reports[0].junit, bytes=fs.readFileSync(item.path,"utf8").replace("ordinary input","other input"); fs.writeFileSync(item.path,bytes); item.sha256=crypto.createHash("sha256").update(bytes).digest("hex"); },
  "JUnit skipped status": input => { const item=input.reports[0].junit, bytes=fs.readFileSync(item.path,"utf8").replace('skipped="0"','skipped="1"'); fs.writeFileSync(item.path,bytes); item.sha256=crypto.createHash("sha256").update(bytes).digest("hex"); },
  "JUnit wrong engine": input => { const item=input.reports[0].junit, bytes=fs.readFileSync(item.path,"utf8").replace("chromium-phone","firefox-phone"); fs.writeFileSync(item.path,bytes); item.sha256=crypto.createHash("sha256").update(bytes).digest("hex"); },
  "non-shard diagnosis": input => input.reports[0].qualification_kind = "selected_diagnosis",
};
for (const [name, mutate] of Object.entries(negatives)) test(`${name} rejects qualification`, () => assert.equal(qualify(name.replaceAll(" ", "-"), mutate).status, 1));
