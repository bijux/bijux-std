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
function configurationIdentity(manifest) {
  const validDigest = value => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
  if (!validDigest(manifest.configurations_sha256)) throw new Error("Fixture configuration aggregate digest is required");
  if (!Array.isArray(manifest.scenarios) || !manifest.scenarios.length || manifest.scenarios.length > 100000) throw new Error("Fixture scenario configurations are required");
  const records = new Map(), routes = new Set();
  for (const scenario of manifest.scenarios) {
    const route = scenario?.route;
    if (typeof route !== "string" || !route.startsWith("/") || !route.endsWith("/") || routes.has(route)) throw new Error("Invalid or duplicate fixture scenario route");
    routes.add(route);
    const relative = route === "/" ? "hub" : route.slice(1, -1);
    if (relative.length > 4096 || /[\\:\x00-\x1f\x7f]/.test(relative) || relative.split("/").some(part => !part || part === "." || part === ".." || part.length > 255)) throw new Error("Invalid fixture configuration path");
    const label = relative.replaceAll("/", "-");
    if (relative.split("/").length > 128 || label.length > 255) throw new Error("Invalid fixture configuration path");
    const name = `inputs/${label}/mkdocs.yml`, config = scenario.configuration;
    if (!config || typeof config !== "object" || Array.isArray(config) || Object.keys(config).sort().join(",") !== "bytes,path,sha256") throw new Error("Fixture scenario configuration identity is required");
    if (config.path !== name || records.has(name)) throw new Error("Fixture configuration path differs or is duplicated");
    if (!validDigest(config.sha256) || !Number.isInteger(config.bytes) || config.bytes <= 0 || config.bytes > 64 * 1024 * 1024) throw new Error("Invalid fixture configuration digest or byte count");
    records.set(name, { bytes: config.bytes, sha256: config.sha256 });
  }
  const canonical = JSON.stringify(Object.fromEntries([...records].sort(([left], [right]) => Buffer.compare(Buffer.from(left), Buffer.from(right))))).replace(/[^\x00-\x7f]/g, character => `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`);
  if (digest(canonical) !== manifest.configurations_sha256) throw new Error("Fixture configuration aggregate differs");
  return manifest.configurations_sha256;
}
function fixtureIdentity(options) {
  if (options.liveBaseUrl) return { kind: "live_url", base_url: options.liveBaseUrl, deployment_identity: "not_independently_verified" };
  const file = path.join(options.generatedRoot, "manifest.json"), bytes = fs.readFileSync(file), manifest = JSON.parse(bytes);
  const configurations_sha256 = configurationIdentity(manifest);
  for (const [name, expected] of Object.entries(manifest.site_files || {})) {
    if (digest(fs.readFileSync(path.join(options.generatedRoot, "site", name))) !== expected) throw new Error(`Rendered fixture differs: ${name}`);
  }
  if (!Object.keys(manifest.site_files || {}).length) throw new Error("Rendered fixture inventory is empty");
  for (const [name, expected] of Object.entries(manifest.source_files || {})) {
    if (digest(fs.readFileSync(path.join(root, "shared/bijux-docs", name))) !== expected) throw new Error(`Producer source differs: ${name}`);
  }
  return { kind: "generated_fixture", manifest_sha256: digest(bytes), base_url: manifest.base_url, toolchain: manifest.toolchain,
    configurations_sha256, source_files_sha256: digest(JSON.stringify(manifest.source_files)), site_files_sha256: digest(JSON.stringify(manifest.site_files)) };
}
function cases(suite) { return suite.allTests().map(test => ({ id: test.id, project: test.parent.project().name, title: test.titlePath().slice(3).join(" › "), file: path.relative(root, test.location.file), line: test.location.line })); }
module.exports = { digest, sourceIdentity, fixtureIdentity, configurationIdentity, cases };
