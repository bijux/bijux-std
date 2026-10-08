"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { geometry, paint, settleGeometry } = require("../ui/generated-specs/contrast-targets/focus-boundary");
const rectangle = { x: 0, y: 60, width: 230, height: 44 };
const viewport = { name: "viewport", x: true, y: true, left: 0, right: 320, top: 0, bottom: 900 };

test("an external drawer outline is clipped even when its target is inside the viewport", () => {
  const observed = geometry(rectangle, 2, 3, [viewport]);
  assert.equal(observed.contained, false);
  assert.deepEqual(observed.clippedBy, [viewport]);
});
test("an inset outline and distinct adjacent samples fit the boundary control", () => {
  const observed = geometry(rectangle, 2, -2, [viewport]);
  assert.equal(observed.contained, true);
  assert.equal(observed.ring[0].x, 1);
  assert.equal(observed.adjacent[0].x, 4);
});
test("scroll-container clipping is checked independently of viewport containment", () => {
  const scroll = { name: "scroll", x: true, y: false, left: 0, right: 228, top: 100, bottom: 200 };
  assert.deepEqual(geometry(rectangle, 2, -2, [viewport, scroll]).clippedBy, [scroll]);
});
test("visible-axis overflow cannot hide clipping on the other axis", () => {
  const vertical = { name: "vertical", x: false, y: true, left: 99, right: 100, top: 61, bottom: 200 };
  assert.deepEqual(geometry(rectangle, 2, -2, [viewport, vertical]).clippedBy, [vertical]);
});
test("invalid or empty geometry cannot pass containment", () => {
  for (const width of [0, NaN, Infinity]) assert.throws(() => geometry(rectangle, width, -2, [viewport]), /finite/);
  assert.throws(() => geometry({ ...rectangle, width: 4 }, 2, -2, [viewport]), /distinct/);
  assert.throws(() => geometry(rectangle, 2, -2, []), /clipping surfaces/);
  assert.throws(() => geometry(rectangle, 2, -2, [{ ...viewport, right: NaN }]), /clipping surfaces/);
});
test("actual invisible paint fails contrast regardless of the computed outline color", () => {
  const white = [255, 255, 255, 255], black = [0, 0, 0, 255];
  assert.equal(paint([...Array(4).fill(black), ...Array(4).fill(white)]).minimum, 21);
  assert.equal(paint(Array(8).fill(white)).minimum, 1);
});
test("missing, transparent or malformed screenshot pixels cannot qualify paint", () => {
  assert.throws(() => paint([]), /four opaque/);
  assert.throws(() => paint(Array(8).fill(null)), /four opaque/);
  assert.throws(() => paint(Array(8).fill([0, 0, 0, 0])), /four opaque/);
  assert.throws(() => paint(Array(8).fill([NaN, 0, 0, 255])), /four opaque/);
});

test("clipping counterfactual retains the exact reviewed shared focus stylesheet", () => {
  const source = fs.readFileSync(path.resolve(__dirname,
    "../ui/generated-specs/contrast-targets/historical/07-utilities.css"));
  assert.equal(crypto.createHash("sha256").update(source).digest("hex"),
    "737712de0e607038b75218be1c03494175ccaa624b932b152f8ee4800ba72628");
});

function probe(sequence, delay = 20) {
  let time = 0, index = 0;
  return { control: { evaluate: async () => sequence[Math.min(index++, sequence.length - 1)] },
    options: { now: () => time, pause: async () => { time += delay; } },
    get reads() { return index; } };
}
const sample = (x, running = 0, transform = `matrix(1, 0, 0, 1, ${x}, 0)`) => ({
  target: { x, y: 247, width: 230, height: 44 }, running,
  ancestors: [{ name: "DIV.md-sidebar", rectangle: { x, y: 60, width: 359, height: 784 },
    transform, opacity: "1", clientLeft: 0, clientTop: 0, clientWidth: 359, clientHeight: 784 }] });
test("missing reported animations cannot admit a translating focused drawer", async () => {
  const p = probe([sample(-355.5003), sample(-275.7758), sample(0), sample(0), sample(0)]);
  const receipt = await settleGeometry(p.control, p.options);
  assert.equal(p.reads, 5);
  assert.deepEqual(receipt.observations.map(o => o.target.x), [-355.5003, -275.7758, 0, 0, 0]);
  assert.equal(receipt.elapsedMs, 80);
});
test("unchanged rectangles with a running finite transition remain pending", async () => {
  const p = probe([sample(0, 1), sample(0, 1), sample(0), sample(0), sample(0)]);
  const receipt = await settleGeometry(p.control, p.options);
  assert.equal(p.reads, 5);
  assert.deepEqual(receipt.observations.map(o => o.running), [1, 1, 0, 0, 0]);
});
test("ancestor transform changes reset stability even when target bounds match", async () => {
  const p = probe([sample(0, 0, "matrix(1,0,0,1,-1,0)"), sample(0), sample(0), sample(0)]);
  await settleGeometry(p.control, p.options);
  assert.equal(p.reads, 4);
});
test("never-settling focus geometry fails with its actual observation history", async () => {
  const p = probe([sample(0, 1)], 500);
  await assert.rejects(settleGeometry(p.control, p.options), /did not settle.*running.*1/);
  assert.equal(p.reads, 5);
});
