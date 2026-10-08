"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");
const crypto = require("node:crypto");
const { rgba, composite, luminance, contrast, textThreshold } = require("../ui/generated-specs/contrast-targets/color.cjs");
test("WCAG luminance handles the linear branch and known white/black ratio", () => {
  assert.equal(luminance([0, 0, 0]), 0);
  assert.equal(luminance([255, 255, 255]), 1);
  assert.equal(contrast([255, 255, 255], [0, 0, 0]), 21);
  assert.ok(Math.abs(luminance([10, 10, 10]) - 10 / 255 / 12.92) < 1e-10);
});
test("foreground alpha and ancestor opacity change actual contrast", () => {
  assert.deepEqual(rgba("rgba(255, 255, 255, 0.5)"), [255, 255, 255, 0.5]);
  assert.deepEqual(composite([255, 255, 255, 0.5], [0, 0, 0], 0.5), [63.75, 63.75, 63.75]);
  assert.throws(() => rgba("CanvasText"), /Unsupported/);
  const backdrop = [15, 118, 110];
  assert.ok(contrast(composite([255, 255, 255, 1], backdrop), backdrop) >= 4.5);
  assert.ok(contrast(composite([255, 255, 255, 1], backdrop, 0.7), backdrop) < 4.5);
});
test("large text thresholds use CSS pixel size and actual weight", () => {
  assert.equal(textThreshold(23.99, 400), 4.5);
  assert.equal(textThreshold(24, 400), 3);
  assert.equal(textThreshold(18.6667, 700), 3);
  assert.equal(textThreshold(56 / 3, 700), 3);
  assert.equal(textThreshold(18.6667, 600), 4.5);
  assert.equal(textThreshold(18.66, 700), 4.5);
});
test("dedicated contrast renderer/server share an origin and exact nonzero case counts", () => {
  const historical = fs.readFileSync(path.resolve(__dirname, "../ui/generated-specs/contrast-targets/historical/06-components.css"));
  assert.equal(crypto.createHash("sha256").update(historical).digest("hex"), "2b42aee03be77a0d0ef33fb3dd49cc7315b3afff6faec57dc579ffd54b45c25d");
  const config = require("../playwright.contrast.config");
  assert.equal(config.use.baseURL, "http://127.0.0.1:62599");
  assert.equal(config.webServer.url, config.use.baseURL + "/");
  assert.match(config.webServer.command, /http.server 62599/);
  assert.equal(config.projects.length, 9);
  assert.equal(config.projects.reduce((sum, p) => sum + p.metadata.required_case_count, 0), 39);
  for (const project of config.projects) {
    assert.equal(project.metadata.required_case_count, project.name.endsWith("-phone") ? 5 : 4);
  }
  const make = fs.readFileSync(path.resolve(__dirname, "../../../makes/bijux-docs.mk"), "utf8");
  assert.match(make, /--base-url "http:\/\/127.0.0.1:62599"/);
  assert.match(make, /playwright.contrast.config.js/);
});
