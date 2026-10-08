"use strict";
const fs = require("node:fs"), path = require("node:path"), crypto = require("node:crypto"), cp = require("node:child_process");
const root = path.resolve(__dirname, "../../..");
const digest = bytes => crypto.createHash("sha256").update(bytes).digest("hex");
function sourceIdentity() {
  let head = null, files;
  try {
    const owner = cp.execFileSync("git", ["rev-parse", "--show-toplevel"], { cwd: root, encoding: "utf8" }).trim();
    if (owner === root) {
      head = cp.execFileSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" }).trim();
      files = cp.execFileSync("git", ["ls-files", "-z"], { cwd: root, encoding: "utf8" }).split("\0").filter(Boolean);
    }
  } catch { /* Artifact archives have no owned Git history; file identities remain authoritative. */ }
  if (!files) {
    files = [];
    function walk(dir) { for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if ([".git", "artifacts", "node_modules", "__pycache__", ".pytest_cache"].includes(entry.name)) continue;
      const file = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(file); else if (entry.isFile()) files.push(path.relative(root, file));
    } }
    walk(root);
  }
  const hashes = Object.fromEntries(files.sort().map(file => [file, digest(fs.readFileSync(path.join(root, file)))]));
  return { head, tree_sha256: digest(JSON.stringify(hashes)), files: hashes };
}
function fixtureIdentity(options) {
  if (options.liveBaseUrl) return { kind: "live_url", base_url: options.liveBaseUrl, deployment_identity: "not_independently_verified" };
  const file = path.join(options.generatedRoot, "manifest.json"), bytes = fs.readFileSync(file), manifest = JSON.parse(bytes);
  for (const [name, expected] of Object.entries(manifest.site_files || {})) {
    if (digest(fs.readFileSync(path.join(options.generatedRoot, "site", name))) !== expected) throw new Error(`Rendered fixture differs: ${name}`);
  }
  if (!Object.keys(manifest.site_files || {}).length) throw new Error("Rendered fixture inventory is empty");
  for (const [name, expected] of Object.entries(manifest.source_files || {})) {
    if (digest(fs.readFileSync(path.join(root, "shared/bijux-docs", name))) !== expected) throw new Error(`Producer source differs: ${name}`);
  }
  return { kind: "generated_fixture", manifest_sha256: digest(bytes), base_url: manifest.base_url, toolchain: manifest.toolchain,
    source_files_sha256: digest(JSON.stringify(manifest.source_files)), site_files_sha256: digest(JSON.stringify(manifest.site_files)) };
}
function cases(suite) { return suite.allTests().map(test => ({ id: test.id, project: test.parent.project().name, title: test.titlePath().slice(3).join(" › "), file: path.relative(root, test.location.file), line: test.location.line })); }
module.exports = { digest, sourceIdentity, fixtureIdentity, cases };
