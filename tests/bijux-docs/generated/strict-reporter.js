const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { sourceIdentity, fixtureIdentity, cases, digest } = require("../reporting/identity");
class StrictReporter {
  constructor(options) { this.options = options; this.projects = {}; this.results = []; }
  onBegin(config, suite) {
    if (this.options.assignedShard) {
      this.sourceIdentity = sourceIdentity(); this.fixtureIdentity = fixtureIdentity(this.options); this.expectedCases = cases(suite);
    }
    this.requiredProjectCounts = Object.fromEntries((config.projects || []).map((project) => [project.name, project.metadata?.required_case_count]));
    for (const test of suite.allTests()) {
      const project = test.parent.project().name;
      this.projects[project] ??= { expected: 0, executed: 0, passed: 0, failed: 0, skipped: 0 };
      this.projects[project].expected += 1;
    }
  }
  onTestEnd(test, result) {
    const project = test.parent.project().name;
    const counts = this.projects[project];
    counts.executed += result.status === "skipped" ? 0 : 1;
    counts[result.status === "passed" ? "passed" : result.status === "skipped" ? "skipped" : "failed"] += 1;
    this.results.push({ case_id: test.id, project, title: test.title, status: result.status, duration_ms: result.duration, retry: result.retry, annotations: test.annotations, errors: result.errors.map((error) => error.message) });
  }
  onEnd(result) {
    const manifestBytes = this.options.liveBaseUrl
      ? Buffer.from(JSON.stringify({ kind: "live_url", base_url: this.options.liveBaseUrl, deployment_identity: "not_independently_verified" }))
      : fs.readFileSync(path.join(this.options.generatedRoot, "manifest.json"));
    const expectedProjects = this.options.requiredProjects || ["chromium", "firefox", "webkit"].flatMap((engine) => ["phone", "compact", "desktop"].map((profile) => `${engine}-${profile}`));
    const missingProjects = process.env.BIJUX_UI_FULL_GATE === "1" ? expectedProjects.filter((name) => !this.projects[name]) : [];
    const incompleteProjects = process.env.BIJUX_UI_FULL_GATE === "1" ? expectedProjects.filter((name) => !Number.isInteger(this.requiredProjectCounts[name]) || this.projects[name]?.expected !== this.requiredProjectCounts[name]) : [];
    const badAttempts = this.results.some(entry => entry.retry !== 0) || new Set(this.results.map(entry => `${entry.project}:${entry.case_id || entry.title}`)).size !== this.results.length;
    const badVersions = this.options.assignedShard && this.results.some(entry => entry.annotations.filter(annotation => annotation.type === "browser-version" && annotation.description).length !== 1);
    const invalid = (this.options.assignedShard && process.env.BIJUX_UI_FULL_GATE !== "1") || badAttempts || badVersions || missingProjects.length > 0 || incompleteProjects.length > 0 || Object.values(this.projects).some((entry) => entry.expected === 0 || entry.executed !== entry.expected || entry.skipped > 0 || entry.failed > 0) || this.results.length === 0;
    const report = {
      schema: 1, status: invalid ? "failed" : result.status, qualification_scope: this.options.scope || "generated_frontend", required_project_names: expectedProjects,
      source: JSON.parse(manifestBytes), manifest_sha256: crypto.createHash("sha256").update(manifestBytes).digest("hex"),
      qualification_kind: this.options.assignedShard ? "assigned_engine_shard" : process.env.BIJUX_UI_FULL_GATE === "1" ? "complete_engine_matrix" : "selected_diagnosis",
      canonical_projects: this.options.canonicalProjects, assigned_project_names: expectedProjects,
      source_identity: this.sourceIdentity, fixture_identity: this.fixtureIdentity, expected_cases: this.expectedCases,
      bad_attempts: badAttempts, missing_versions: Boolean(badVersions),
      projects: this.projects, missing_projects: missingProjects, incomplete_projects: incompleteProjects, required_project_counts: this.requiredProjectCounts, results: this.results,
      limits: ["Headless engine qualification is not physical mobile, actual zoom or human assistive review."],
    };
    this.report = report;
    fs.mkdirSync(path.dirname(this.options.output), { recursive: true });
    fs.writeFileSync(this.options.output, `${JSON.stringify(report, null, 2)}\n`);
    return { status: invalid ? "failed" : result.status };
  }
  onExit() {
    if (!this.options.assignedShard || !this.report) return;
    // Playwright completes every reporter's onEnd before onExit, so JUnit is now durable.
    try {
      const bytes = fs.readFileSync(this.options.junitFile);
      this.report.junit = { path: path.relative(path.dirname(this.options.output), this.options.junitFile), sha256: digest(bytes) };
      if (JSON.stringify(sourceIdentity()) !== JSON.stringify(this.sourceIdentity) || JSON.stringify(fixtureIdentity(this.options)) !== JSON.stringify(this.fixtureIdentity)) throw new Error("Source or fixture changed during shard execution");
    } catch (error) { this.report.status = "failed"; this.report.binding_error = error.message; }
    fs.writeFileSync(this.options.output, `${JSON.stringify(this.report, null, 2)}\n`);
  }
}
module.exports = StrictReporter;
