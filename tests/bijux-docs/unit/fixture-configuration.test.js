"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), fs = require("node:fs"), path = require("node:path"), cp = require("node:child_process");
const { configurationIdentity, fixtureIdentity, digest } = require("../reporting/identity");
const root = path.resolve(__dirname, "../../.."), output = path.join(root, "artifacts/qualification/fixture-configuration/node-controls");
fs.mkdirSync(output, { recursive: true });
function manifest() {
  const configurations = { "inputs/hub/mkdocs.yml": { bytes: Buffer.byteLength("site_name: Reader\n"), sha256: digest("site_name: Reader\n") } };
  return { scenarios: [{ identity: "bijux", route: "/", kind: "hub", configuration: { path: "inputs/hub/mkdocs.yml", ...configurations["inputs/hub/mkdocs.yml"] } }], configurations_sha256: digest(JSON.stringify(configurations)) };
}
test("actual Python metadata aggregate has the same portable identity in Node", () => {
  const script = 'import sys,json;sys.path.insert(0,"tests/bijux-docs/execution");from fixture_archive import configurations_digest;data=json.load(sys.stdin);print(configurations_digest(data["scenarios"]))';
  const input = manifest(); input.scenarios.push({ identity: "unicode", route: "/κόσμος/", kind: "project", configuration: { path: "inputs/κόσμος/mkdocs.yml", sha256: "a".repeat(64), bytes: 42 } });
  const result = cp.spawnSync(process.env.BIJUX_UI_PYTHON || "python3", ["-B", "-c", script], { cwd: root, input: JSON.stringify(input), encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr); input.configurations_sha256 = result.stdout.trim();
  assert.equal(configurationIdentity(input), input.configurations_sha256);
  input.scenarios.reverse(); assert.equal(configurationIdentity(input), input.configurations_sha256);
});
const mutations = {
  "missing aggregate": value => delete value.configurations_sha256,
  "malformed aggregate": value => value.configurations_sha256 = "A".repeat(64),
  "missing effective configuration": value => delete value.scenarios[0].configuration,
  "malformed effective digest": value => value.scenarios[0].configuration.sha256 = "bad",
  "boolean byte count": value => value.scenarios[0].configuration.bytes = true,
  "escaping configuration": value => value.scenarios[0].configuration.path = "../mkdocs.yml",
  "duplicate scenario": value => value.scenarios.push(value.scenarios[0]),
  "changed effective configuration": value => value.scenarios[0].configuration.sha256 = "f".repeat(64),
};
for (const [name, mutate] of Object.entries(mutations)) test(`${name} rejects fixture collection`, () => { const input = manifest(); mutate(input); assert.throws(() => configurationIdentity(input)); });
test("cold worker identity requires metadata while no private config is transported", () => {
  const generatedRoot = path.join(output, "cold-worker"); fs.mkdirSync(path.join(generatedRoot, "site"), { recursive: true });
  const sourceName = "config/mkdocs-baseline.json", source = fs.readFileSync(path.join(root, "shared/bijux-docs", sourceName));
  const input = { ...manifest(), base_url: "http://127.0.0.1:4173", toolchain: { mkdocs: "observed-fixture" }, source_files: { [sourceName]: digest(source) }, site_files: { "index.html": digest("Exact reader") } };
  fs.writeFileSync(path.join(generatedRoot, "site/index.html"), "Exact reader"); fs.writeFileSync(path.join(generatedRoot, "manifest.json"), JSON.stringify(input));
  assert.equal(fixtureIdentity({ generatedRoot }).configurations_sha256, input.configurations_sha256);
  assert.equal(fs.existsSync(path.join(generatedRoot, "inputs")), false);
  delete input.configurations_sha256; fs.writeFileSync(path.join(generatedRoot, "manifest.json"), JSON.stringify(input));
  assert.throws(() => fixtureIdentity({ generatedRoot }), /aggregate digest/);
});
