"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const vm = require("node:vm");
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
  const state = { request: null, waiter: null };
  const observer = { evaluate: async callback => callback(state), dispose: async () => {} };
  return { control: { evaluateHandle: async () => observer,
    evaluate: async () => sequence[Math.min(index++, sequence.length - 1)] },
    options: { now: () => time, pause: async () => { time += delay; } },
    get reads() { return index; } };
}
const sample = (x, running = 0, transform = `matrix(1, 0, 0, 1, ${x}, 0)`) => ({
  target: { x, y: 247, width: 230, height: 44 }, running, frame: 10, openDrawer: null,
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

const openDrawerSample = x => ({ ...sample(x),
  openDrawer: { transform: `matrix(1, 0, 0, 1, ${x}, 0)`, identity: x === 0 } });
test("three identical cached offscreen drawer boxes cannot admit the open endpoint", async () => {
  const p = probe([...Array(4).fill(openDrawerSample(-357.41632080078125)),
    openDrawerSample(0), openDrawerSample(0), openDrawerSample(0)]);
  const receipt = await settleGeometry(p.control, p.options);
  assert.equal(p.reads, 7);
  assert.deepEqual(receipt.observations.map(o => o.openDrawer.identity),
    [false, false, false, false, true, true, true]);
  assert.equal(receipt.observations[0].running, 0);
});
test("a permanently translated owned open drawer fails closed with endpoint history", async () => {
  const p = probe([openDrawerSample(-218.50131225585938)], 500);
  await assert.rejects(settleGeometry(p.control, p.options), /did not settle.*openDrawer.*identity.*false/);
  assert.equal(p.reads, 5);
});
test("missing rendering frames cannot admit stable focus geometry", async () => {
  const p = probe([{ ...sample(0), frame: null }], 500);
  await assert.rejects(settleGeometry(p.control, p.options), /did not settle.*frame.*null/);
  assert.equal(p.reads, 5);
});
test("controls outside the owned open drawer retain ordinary stable geometry admission", async () => {
  const p = probe([sample(20), sample(20), sample(20)]);
  const receipt = await settleGeometry(p.control, p.options);
  assert.equal(p.reads, 3);
  assert.equal(receipt.observations[0].openDrawer, null);
});

function renderingProbe({ delay = 150, deliverFrame = true, x = 0 } = {}) {
  const pending = new Map();
  let requests = 0, callbacks = 0, cancellations = 0;
  const node = { tagName: "BUTTON", id: "close", className: "close", parentElement: null,
    getBoundingClientRect: () => ({ x, y: 60, width: 230, height: 44 }),
    getAnimations: () => [], closest: () => node };
  const document = { visibilityState: "visible", hidden: false, hasFocus: () => true,
    timeline: { get currentTime() { return performance.now(); } }, activeElement: node,
    body: { dataset: { bijuxDrawerReady: "true", bijuxDrawerOpen: "true" } },
    getElementById: () => ({ checked: true }) };
  const context = vm.createContext({ document, performance, setTimeout, clearTimeout,
    getComputedStyle: () => ({ transform: `matrix(1, 0, 0, 1, ${x}, 0)` }),
    DOMMatrixReadOnly: class { constructor() { this.isIdentity = x === 0; } },
    requestAnimationFrame: callback => {
      const id = ++requests;
      pending.set(id, setTimeout(() => {
        pending.delete(id);
        if (deliverFrame) { callbacks++; callback(performance.now()); }
      }, deliverFrame ? delay : 10_000));
      return id;
    },
    cancelAnimationFrame: id => {
      if (pending.has(id)) { clearTimeout(pending.get(id)); pending.delete(id); cancellations++; }
    },
  });
  const evaluate = async (callback, args) => {
    context.args = args;
    return vm.runInContext(`(${callback})(...args)`, context);
  };
  const control = {
    evaluateHandle: async callback => {
      const state = await evaluate(callback, []);
      return { state, evaluate: callback => evaluate(callback, [state]), dispose: async () => {} };
    },
    evaluate: (callback, argument) => evaluate(callback, [node, argument && {
      observer: argument.observer.state, waitMs: argument.waitMs }]),
  };
  return { control, get requests() { return requests; }, get callbacks() { return callbacks; },
    get cancellations() { return cancellations; }, get pending() { return pending.size; } };
}

test("delayed rendering frames survive timer samples and retain three distinct admitted frames", async () => {
  const p = renderingProbe();
  const receipt = await settleGeometry(p.control);
  const frames = receipt.observations.filter(observation => observation.frame !== null);
  assert.equal(frames.length, 3);
  assert.equal(new Set(frames.map(observation => observation.frame)).size, 3);
  assert.ok(receipt.observations.some(observation => observation.frame === null));
  assert.ok(receipt.elapsedMs >= 450 && receipt.elapsedMs < 2000);
  assert.equal(p.requests, 3);
  assert.equal(p.callbacks, 3);
  assert.equal(p.cancellations, 0);
  assert.equal(p.pending, 0);
  for (const observation of receipt.observations) {
    assert.equal(observation.rendering.beforeFrame.visibility, "visible");
    assert.equal(observation.rendering.afterFrame.focused, true);
    assert.ok(observation.rendering.afterFrame.timelineTime >= observation.rendering.beforeFrame.timelineTime);
  }
});

test("absent rendering frames still fail within the total budget and cancel the owned outstanding request", async () => {
  const p = renderingProbe({ deliverFrame: false });
  await assert.rejects(settleGeometry(p.control), /did not settle.*frame.*null.*rendering/);
  assert.equal(p.requests, 1);
  assert.equal(p.callbacks, 0);
  assert.equal(p.cancellations, 1);
  assert.equal(p.pending, 0);
});

test("delayed callbacks cannot admit a stable translated open drawer", async () => {
  const p = renderingProbe({ x: -41.37973 });
  await assert.rejects(settleGeometry(p.control), /did not settle.*identity.*false/);
  assert.ok(p.callbacks >= 3);
  assert.equal(p.pending, 0);
});

test("timer samples cannot manufacture the third admitted frame", async () => {
  const p = probe([sample(0), sample(0), { ...sample(0), frame: null }], 500);
  await assert.rejects(settleGeometry(p.control, p.options), /did not settle.*frame.*null/);
});

test("geometry changes between delayed frames reset the admitted frame sequence", async () => {
  const p = probe([sample(0), sample(0), { ...sample(10), frame: null },
    sample(0), sample(0), sample(0)]);
  await settleGeometry(p.control, p.options);
  assert.equal(p.reads, 6);
});
