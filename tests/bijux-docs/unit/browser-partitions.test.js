"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { configureProjects, unsharded } = require("../reporting/projects");
const { engines, profiles } = require("../execution/browser_partitions.json");
const projects = engines.flatMap(engine => profiles.map(profile => ({
  name: `${engine}-${profile}`, use: { browserName: engine }, metadata: { required_case_count: 14 },
})));
const config = { projects, reporter: [["generated/strict-reporter.js", {}], ["junit", { outputFile: "junit.xml" }]] };
for (const engine of engines) {
  test(`${engine} viewport partitions retain exact canonical ownership`, () => {
    const claimed = [];
    for (const profile of profiles) {
      const selected = configureProjects(config, { BIJUX_UI_BROWSER_ENGINE: engine, BIJUX_UI_PROFILE: profile });
      assert.deepEqual(selected.projects.map(project => project.name), [`${engine}-${profile}`]);
      assert.equal(selected.projects[0].metadata.required_case_count, 14);
      assert.equal(selected.reporter[0][1].assignedShard, true);
      assert.deepEqual(selected.reporter[0][1].requiredProjects, [`${engine}-${profile}`]);
      assert.deepEqual(selected.reporter[0][1].canonicalProjects, projects.map(project => ({
        name: project.name, engine: project.use.browserName, count: project.metadata.required_case_count,
      })));
      assert.equal(unsharded(selected), config);
      claimed.push(...selected.projects.map(project => project.name));
    }
    assert.deepEqual(claimed, projects.filter(project => project.use.browserName === engine).map(project => project.name));
    assert.equal(new Set(claimed).size, claimed.length);
  });
}
test("canonical and ordinary engine-only selections stay unchanged", () => {
  assert.equal(configureProjects(config, {}).projects.length, 9);
  assert.equal(configureProjects(config, { BIJUX_UI_BROWSER_ENGINE: "webkit" }).projects.length, 3);
  assert.equal(configureProjects(config, { BIJUX_UI_PROJECTS: "chromium-phone,firefox-desktop" }).projects.length, 2);
});
test("profile selection rejects missing engine, ambiguity, unknown and empty values", () => {
  for (const env of [
    { BIJUX_UI_PROFILE: "phone" },
    { BIJUX_UI_BROWSER_ENGINE: "chromium", BIJUX_UI_PROFILE: "" },
    { BIJUX_UI_BROWSER_ENGINE: "chromium", BIJUX_UI_PROFILE: "tablet" },
    { BIJUX_UI_BROWSER_ENGINE: "chromium", BIJUX_UI_PROFILE: "phone", BIJUX_UI_PROJECTS: "chromium-phone" },
  ]) assert.throws(() => configureProjects(config, env));
});
test("a phone-only companion cannot claim a compact or desktop profile", () => {
  const phone = { ...config, projects: projects.filter(project => project.name.endsWith("-phone")) };
  assert.throws(() => configureProjects(phone, { BIJUX_UI_BROWSER_ENGINE: "chromium", BIJUX_UI_PROFILE: "compact" }), /execute cases/);
  assert.equal(configureProjects(phone, { BIJUX_UI_BROWSER_ENGINE: "chromium" }).projects.length, 1);
});
const fs = require("node:fs"), path = require("node:path"), crypto = require("node:crypto"), cp = require("node:child_process");
const artifactRoot = path.resolve(__dirname, "../../../artifacts/bijux-docs/browser-partition-controls");
fs.mkdirSync(artifactRoot, { recursive: true });
function aggregateControl(name, mutate = () => {}) {
  const output = path.join(artifactRoot, name);
  fs.mkdirSync(output, { recursive: true });
  const source = { head: "a".repeat(40), tree_sha256: "b".repeat(64) };
  const fixture = { manifest_sha256: "c".repeat(64) };
  const canonical = projects.map(project => ({ name: project.name, engine: project.use.browserName, count: 1 }));
  const cases = canonical.map((project, index) => ({ id: `${project.name}-case`, project: project.name, title: "ordinary route handoff", file: "fixture.spec.js", line: index + 1 }));
  const inventory = { qualification_scope: "controlled_profiles", source_identity: source, fixture_identity: fixture, canonical_projects: canonical, cases };
  const reports = canonical.map((project, index) => {
    const xml = `<testsuites tests="1" failures="0" skipped="0" errors="0"><testsuite hostname="${project.name}" tests="1"><testcase name="ordinary route handoff"/></testsuite></testsuites>`;
    const junit = path.join(output, `${project.name}.xml`);
    fs.writeFileSync(junit, xml);
    return { status: "passed", qualification_kind: "assigned_engine_shard", qualification_scope: inventory.qualification_scope,
      source_identity: source, fixture_identity: fixture, canonical_projects: canonical, assigned_project_names: [project.name],
      expected_cases: [cases[index]], projects: { [project.name]: { expected: 1, executed: 1, passed: 1, failed: 0, skipped: 0 } },
      results: [{ case_id: cases[index].id, project: project.name, status: "passed", retry: 0, errors: [], annotations: [{ type: "browser-version", description: "controlled-unit-version" }] }],
      junit: { path: junit, sha256: crypto.createHash("sha256").update(xml).digest("hex") } };
  });
  mutate(reports);
  const inventoryPath = path.join(output, "inventory.json");
  fs.writeFileSync(inventoryPath, JSON.stringify(inventory));
  const args = [path.resolve(__dirname, "../reporting/aggregate.py"), "--inventory", inventoryPath];
  reports.forEach((report, index) => {
    const file = path.join(output, `report-${index}.json`);
    fs.writeFileSync(file, JSON.stringify(report));
    args.push("--report", file);
  });
  args.push("--output", path.join(output, "qualification.json"));
  return cp.spawnSync(process.env.BIJUX_UI_PYTHON || "python3", args, { encoding: "utf8", env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" } });
}
test("exact disjoint viewport reports qualify the same complete canonical inventory", () => {
  assert.equal(aggregateControl("complete-profile-coverage").status, 0);
});
for (const [name, mutate] of [
  ["missing viewport", reports => reports.splice(1, 1)],
  ["duplicate viewport", reports => reports.push(reports[0])],
  ["cross-profile case", reports => reports[0].results[0].project = "chromium-desktop"],
  ["nonterminal receipt", reports => reports[0].status = "running"],
]) test(`${name} cannot qualify canonical coverage`, () => {
  assert.equal(aggregateControl(name.replaceAll(" ", "-"), mutate).status, 1);
});
