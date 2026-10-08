const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
class StrictReporter {
  constructor(options) { this.options = options; this.projects = {}; this.results = []; }
  onBegin(config, suite) {
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
    this.results.push({ project, title: test.title, status: result.status, duration_ms: result.duration, retry: result.retry, annotations: test.annotations, errors: result.errors.map((error) => error.message) });
  }
  onEnd(result) {
    const manifestBytes = this.options.liveBaseUrl
      ? Buffer.from(JSON.stringify({ kind: "live_url", base_url: this.options.liveBaseUrl, deployment_identity: "not_independently_verified" }))
      : fs.readFileSync(path.join(this.options.generatedRoot, "manifest.json"));
    const expectedProjects = this.options.requiredProjects || ["chromium", "firefox", "webkit"].flatMap((engine) => ["phone", "compact", "desktop"].map((profile) => `${engine}-${profile}`));
    const missingProjects = process.env.BIJUX_UI_FULL_GATE === "1" ? expectedProjects.filter((name) => !this.projects[name]) : [];
    const incompleteProjects = process.env.BIJUX_UI_FULL_GATE === "1" ? expectedProjects.filter((name) => !Number.isInteger(this.requiredProjectCounts[name]) || this.projects[name]?.expected !== this.requiredProjectCounts[name]) : [];
    const invalid = missingProjects.length > 0 || incompleteProjects.length > 0 || Object.values(this.projects).some((entry) => entry.expected === 0 || entry.executed !== entry.expected || entry.skipped > 0 || entry.failed > 0) || this.results.length === 0;
    const report = {
      schema: 1, status: invalid ? "failed" : result.status, qualification_scope: this.options.scope || "generated_frontend", required_project_names: expectedProjects,
      source: JSON.parse(manifestBytes), manifest_sha256: crypto.createHash("sha256").update(manifestBytes).digest("hex"),
      qualification_kind: process.env.BIJUX_UI_FULL_GATE === "1" ? "complete_engine_matrix" : "selected_diagnosis",
      projects: this.projects, missing_projects: missingProjects, incomplete_projects: incompleteProjects, required_project_counts: this.requiredProjectCounts, results: this.results,
      limits: ["Headless engine qualification is not physical mobile, actual zoom or human assistive review."],
    };
    fs.mkdirSync(path.dirname(this.options.output), { recursive: true });
    fs.writeFileSync(this.options.output, `${JSON.stringify(report, null, 2)}\n`);
    return { status: invalid ? "failed" : result.status };
  }
}
module.exports = StrictReporter;
