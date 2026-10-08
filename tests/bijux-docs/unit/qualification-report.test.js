const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const Reporter = require("../generated/strict-reporter");
const root = path.resolve(__dirname, "../../../artifacts/bijux-docs/reporter-fixtures");
fs.mkdirSync(root, { recursive: true });
const projects = ["chromium", "firefox", "webkit"].flatMap((engine) => ["phone", "compact", "desktop"].map((profile) => `${engine}-${profile}`));
function item(project) { return { title: "required journey", parent: { project: () => ({ name: project }) }, annotations: [] }; }
function run(label, names, statuses, full = false, required = 1) {
  const output = path.join(root, `${label}.json`);
  const reporter = new Reporter({ output, liveBaseUrl: "https://example.invalid/" });
  const items = names.map(item);
  const previous = process.env.BIJUX_UI_FULL_GATE;
  if (full) process.env.BIJUX_UI_FULL_GATE = "1";
  else delete process.env.BIJUX_UI_FULL_GATE;
  try {
    reporter.onBegin({ projects: projects.map((name) => ({ name, metadata: { required_case_count: required } })) }, { allTests: () => items });
    items.forEach((entry, index) => {
      if (statuses[index]) reporter.onTestEnd(entry, { status: statuses[index], duration: 1, retry: 0, errors: [] });
    });
    const result = reporter.onEnd({ status: "passed" });
    return { result, receipt: JSON.parse(fs.readFileSync(output)) };
  } finally {
    if (previous === undefined) delete process.env.BIJUX_UI_FULL_GATE;
    else process.env.BIJUX_UI_FULL_GATE = previous;
  }
}
test("zero tests cannot create a passing qualification", () => {
  assert.equal(run("zero", [], []).result.status, "failed");
});
test("a missing required engine rejects full qualification", () => {
  const result = run("missing-engine", projects.filter((name) => !name.startsWith("firefox")), Array(6).fill("passed"), true);
  assert.equal(result.result.status, "failed");
  assert.deepEqual(result.receipt.missing_projects, projects.filter((name) => name.startsWith("firefox")));
});
test("skipped and unexecuted cases cannot become passing evidence", () => {
  assert.equal(run("skipped", ["chromium-phone"], ["skipped"]).result.status, "failed");
  assert.equal(run("unexecuted", ["chromium-phone"], []).result.status, "failed");
});
test("failed ordinary input remains failure despite a green outer status", () => {
  assert.equal(run("failure", ["chromium-phone"], ["failed"]).result.status, "failed");
});
test("all required engine profiles preserve expected execution counts", () => {
  const result = run("complete", projects, Array(9).fill("passed"), true);
  assert.equal(result.result.status, "passed");
  for (const entry of Object.values(result.receipt.projects)) assert.deepEqual(entry, { expected: 1, executed: 1, passed: 1, failed: 0, skipped: 0 });
  assert.equal(result.receipt.source.deployment_identity, "not_independently_verified");
});
test("a filtered journey set cannot satisfy a complete project contract", () => {
  const result = run("filtered", projects, Array(9).fill("passed"), true, 2);
  assert.equal(result.result.status, "failed");
  assert.deepEqual(result.receipt.incomplete_projects, projects);
});
