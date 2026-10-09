const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const source = fs.readFileSync(
  process.env.BIJUX_DIAGRAM_READER_SOURCE || path.resolve(__dirname, "../../../shared/bijux-docs/scripts/mermaid-init.js"),
  "utf8",
);
const href = "https://example.test/reader/";
const position = { owner: "bijux-docs", version: 1, href, x: 0, y: 13000 };

function setup({ state = null, type = "navigate", figures = true, anchors = [] } = {}) {
  const events = new Map(), frames = [], scrolls = [], writes = [];
  const listen = (owner, name, callback) => {
    const key = owner + name;
    events.set(key, [...(events.get(key) || []), callback]);
  };
  const history = {
    state,
    replaceState(value) {
      this.state = value;
      writes.push(value);
    },
  };
  const window = {
    scrollX: 0,
    scrollY: 13000,
    addEventListener: (name, callback) => listen("window:", name, callback),
    scrollTo: value => scrolls.push(value),
  };
  const document = {
    currentScript: { src: "https://example.test/assets/mermaid-init.js" },
    readyState: "loading",
    querySelector: () => figures ? {} : null,
    querySelectorAll: selector => selector === ".md-content article a[href]" ? anchors : [],
    addEventListener: (name, callback) => listen("document:", name, callback),
  };
  const context = {
    window, document, history, location: new URL(href),
    performance: { getEntriesByType: () => [{ type }] },
    URL, WeakMap, Promise, setTimeout, clearTimeout,
    requestAnimationFrame: callback => frames.push(callback),
  };
  // Exercise the actual script and its registered events. The test seam admits
  // layout-frame completion without fabricating a Mermaid implementation.
  const observed = source.replace(
    /\}\)\(\);\s*$/,
    'window.readerTestRestore = typeof restoreReaderPosition === "function" ? () => restoreReaderPosition(generation) : null;})();',
  );
  vm.runInNewContext(observed, context);
  return {
    history, writes, scrolls, frames,
    fire(owner, name, event = {}) {
      for (const callback of events.get(owner + ":" + name) || []) callback(event);
    },
    restore() { window.readerTestRestore?.(0); },
    flush() { while (frames.length) frames.shift()(); },
  };
}

function click(overrides = {}, linkOverrides = {}) {
  return {
    isTrusted: true,
    defaultPrevented: false,
    button: 0,
    target: {
      closest: () => ({
        href: "https://example.test/other/",
        target: "",
        hasAttribute: name => name === "download" && !!linkOverrides.download,
        ...linkOverrides,
      }),
    },
    ...overrides,
  };
}

function restoredReader() {
  return setup({ state: { bijuxDiagramReaderPosition: position }, type: "back_forward" });
}

test("trusted authored navigation records the departing entry and preserves unrelated state", () => {
  const app = setup({ state: { x: 0, y: 650, readerPreference: { mode: "wide" } } });
  app.fire("document", "click", click());
  assert.equal(app.writes.length, 1);
  assert.equal(app.history.state.y, 650);
  assert.equal(app.history.state.readerPreference.mode, "wide");
  assert.deepEqual(JSON.parse(JSON.stringify(app.history.state.bijuxDiagramReaderPosition)), position);
});

test("trusted keyboard link activation records the same native departure position", () => {
  const app = setup();
  app.fire("document", "click", click({ detail: 0 }));
  assert.equal(app.writes.length, 1);
});

for (const flag of ["ctrlKey", "metaKey", "altKey", "shiftKey"]) {
  test(`modified ${flag} activation leaves the native entry untouched`, () => {
    const app = setup();
    app.fire("document", "click", click({ [flag]: true }));
    assert.equal(app.writes.length, 0);
  });
}

const nativeActions = [
  ["synthetic", { isTrusted: false }, {}],
  ["prevented", { defaultPrevented: true }, {}],
  ["middle", { button: 1 }, {}],
  ["new tab", {}, { target: "_blank" }],
  ["named target", {}, { target: "reader" }],
  ["download", {}, { download: true }],
  ["fragment", {}, { href: href + "#section" }],
  ["mail", {}, { href: "mailto:reader@example.test" }],
  ["malformed URL", {}, { href: "http://[" }],
];
for (const [name, options, link] of nativeActions) {
  test(`${name} action preserves existing browser ownership`, () => {
    const app = setup();
    app.fire("document", "click", click(options, link));
    assert.equal(app.writes.length, 0);
  });
}

const opaqueStates = [
  42, "opaque", [], new Date("2026-01-01"), new Map([["author", true]]),
  { bijuxDiagramReaderPosition: 0 },
  { bijuxDiagramReaderPosition: { owner: "author", version: 1 } },
];
for (const state of opaqueStates) {
  test(`opaque or foreign history state is retained: ${JSON.stringify(state)}`, () => {
    const app = setup({ state });
    app.fire("document", "click", click());
    assert.equal(app.writes.length, 0);
    assert.equal(app.history.state, state);
  });
}

test("fresh native Back restores after the owned layout frames settle", () => {
  const app = restoredReader();
  app.restore();
  assert.equal(app.scrolls.length, 0);
  app.flush();
  assert.equal(app.scrolls.length, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(app.scrolls[0])), { left: 0, top: 13000, behavior: "instant" });
});

function anchor({ text = "Reading checkpoint", href: destination = "https://example.test/other/", top = 3400, connected = true } = {}) {
  return { href: destination, textContent: text, target: "", hasAttribute: () => false, isConnected: connected, getBoundingClientRect: () => ({ top }) };
}

test("trusted authored departure retains a unique article anchor and its viewport offset", () => {
  const link = anchor({ top: 350 });
  const app = setup({ anchors: [link] });
  const event = click();
  event.target.closest = () => link;
  app.fire("document", "click", event);
  assert.deepEqual(JSON.parse(JSON.stringify(app.history.state.bijuxDiagramReaderPosition.context)), {
    href: link.href, text: link.textContent, top: 350,
  });
});

test("duplicate article destinations retain the coordinate-only departure", () => {
  const link = anchor({ top: 350 });
  const app = setup({ anchors: [link, anchor()] });
  const event = click();
  event.target.closest = () => link;
  app.fire("document", "click", event);
  assert.equal(app.history.state.bijuxDiagramReaderPosition.context, undefined);
  assert.equal(app.history.state.bijuxDiagramReaderPosition.y, position.y);
});

test("native Back follows the same reader anchor after diagram layout changes", () => {
  const link = anchor({ top: 3400 });
  const context = { href: link.href, text: link.textContent, top: 350 };
  const app = setup({ state: { bijuxDiagramReaderPosition: { ...position, context } }, type: "back_forward", anchors: [link] });
  app.restore();
  app.flush();
  assert.equal(app.scrolls[0].top, 16050);
});

for (const anchors of [[], [anchor(), anchor()], [anchor({ connected: false })]]) {
  test(`removed ambiguous or disconnected reader anchors preserve coordinates: ${anchors.length}`, () => {
    const context = { href: "https://example.test/other/", text: "Reading checkpoint", top: 350 };
    const app = setup({ state: { bijuxDiagramReaderPosition: { ...position, context } }, type: "back_forward", anchors });
    app.restore();
    app.flush();
    assert.equal(app.scrolls[0].top, position.y);
  });
}

for (const link of [anchor({ text: "Different reader destination" }), anchor({ href: "https://example.test/different/" })]) {
  test(`changed reader identity preserves coordinates: ${link.href} ${link.textContent}`, () => {
    const context = { href: "https://example.test/other/", text: "Reading checkpoint", top: 350 };
    const app = setup({ state: { bijuxDiagramReaderPosition: { ...position, context } }, type: "back_forward", anchors: [link] });
    app.restore();
    app.flush();
    assert.equal(app.scrolls[0].top, position.y);
  });
}

test("inherited optional reader context cannot override owned coordinates", () => {
  const context = { href: "https://example.test/other/", text: "Reading checkpoint", top: 350 };
  const saved = Object.assign(Object.create({ context }), position);
  const app = setup({ state: { bijuxDiagramReaderPosition: saved }, type: "back_forward", anchors: [anchor()] });
  app.restore();
  app.flush();
  assert.equal(app.scrolls[0].top, position.y);
});

for (const [name, context] of [
  ["null context", null],
  ["empty context", {}],
  ["nonfinite anchor offset", { href: "https://example.test/other/", text: "Reading checkpoint", top: Infinity }],
  ["inherited context fields", Object.create({ href: "https://example.test/other/", text: "Reading checkpoint", top: 350 })],
]) {
  test(`unqualified reader context preserves coordinate fallback: ${name}`, () => {
    const app = setup({ state: { bijuxDiagramReaderPosition: { ...position, context } }, type: "back_forward", anchors: [anchor()] });
    app.restore();
    app.flush();
    assert.equal(app.scrolls[0].top, position.y);
  });
}

test("trusted input cancels anchor restoration after layout changes", () => {
  const link = anchor();
  const context = { href: link.href, text: link.textContent, top: 350 };
  const app = setup({ state: { bijuxDiagramReaderPosition: { ...position, context } }, type: "back_forward", anchors: [link] });
  app.restore();
  app.fire("window", "wheel", { isTrusted: true });
  app.flush();
  assert.equal(app.scrolls.length, 0);
});

for (const event of ["wheel", "pointerdown", "touchstart", "keydown"]) {
  test(`trusted ${event} input cancels queued restoration`, () => {
    const app = restoredReader();
    app.restore();
    app.fire("window", event, { isTrusted: true });
    app.flush();
    assert.equal(app.scrolls.length, 0);
  });
}

test("synthetic input does not impersonate reader intent", () => {
  const app = restoredReader();
  app.restore();
  app.fire("window", "wheel", { isTrusted: false });
  app.flush();
  assert.equal(app.scrolls.length, 1);
});

test("pagehide cancels stale work without writing into the destination entry", () => {
  const app = restoredReader();
  app.restore();
  app.fire("window", "pagehide");
  app.flush();
  assert.equal(app.scrolls.length, 0);
  assert.equal(app.writes.length, 0);
});

const invalidPositions = [
  { ...position, href: href + "?other" },
  { ...position, y: Infinity },
  { ...position, x: -1 },
  { ...position, owner: "other" },
  { ...position, version: 2 },
];
for (const saved of invalidPositions) {
  test(`unqualified saved position is ignored: ${JSON.stringify(saved)}`, () => {
    const app = setup({ state: { bijuxDiagramReaderPosition: saved }, type: "back_forward" });
    app.restore();
    app.flush();
    assert.equal(app.scrolls.length, 0);
  });
}

test("ordinary navigation keeps native fragment and first-view behavior", () => {
  const app = setup({ state: { bijuxDiagramReaderPosition: position }, type: "navigate" });
  app.restore();
  app.flush();
  assert.equal(app.scrolls.length, 0);
});

test("a page without diagrams does not acquire a reader-history marker", () => {
  const app = setup({ figures: false });
  app.fire("document", "click", click());
  assert.equal(app.writes.length, 0);
});


test("an inherited reader-history marker does not acquire component ownership", () => {
  const state = Object.assign(Object.create({ bijuxDiagramReaderPosition: position }), { author: "retained" });
  const app = setup({ state, type: "back_forward" });
  app.restore();
  app.flush();
  assert.equal(app.scrolls.length, 0);
  assert.equal(app.history.state, state);
});

for (const field of ["owner", "version", "href", "x", "y"]) {
  test(`an inherited ${field} field does not qualify a reader-history marker`, () => {
    const own = { ...position };
    delete own[field];
    const saved = Object.assign(Object.create({ [field]: position[field] }), own);
    const app = setup({ state: { bijuxDiagramReaderPosition: saved }, type: "back_forward" });
    app.restore();
    app.flush();
    assert.equal(app.scrolls.length, 0);
    assert.equal(app.writes.length, 0);
  });
}

test("boxed primitive history does not become an owned reader entry", () => {
  const state = new String("author-owned");
  state.bijuxDiagramReaderPosition = position;
  const app = setup({ state, type: "back_forward" });
  app.restore();
  app.flush();
  assert.equal(app.scrolls.length, 0);
  assert.equal(app.history.state, state);
});

test("own fields on null-prototype reader records preserve native Back restoration", () => {
  const saved = Object.assign(Object.create(null), position);
  const state = Object.assign(Object.create(null), { bijuxDiagramReaderPosition: saved, author: "retained" });
  const app = setup({ state, type: "back_forward" });
  app.restore();
  app.flush();
  assert.equal(app.scrolls.length, 1);
  assert.equal(app.history.state, state);
  assert.equal(app.history.state.author, "retained");
  assert.equal(app.writes.length, 0);
});


test("persisted pageshow acquires the freshly captured current history entry", () => {
  const app = setup();
  const fresh = { ...position, x: 12, y: 8700 };
  app.fire("window", "pagehide");
  app.history.state = { bijuxDiagramReaderPosition: fresh, author: "retained" };
  app.fire("window", "pageshow", { persisted: true });
  app.restore();
  app.flush();
  assert.deepEqual(JSON.parse(JSON.stringify(app.scrolls)), [{ left: 12, top: 8700, behavior: "instant" }]);
  assert.equal(app.history.state.author, "retained");
  assert.equal(app.writes.length, 0);
});

test("persisted pageshow replaces stale layout work with the fresh entry anchor", () => {
  const link = anchor({ top: 1275 });
  const app = setup({ state: { bijuxDiagramReaderPosition: position }, type: "back_forward", anchors: [link] });
  app.restore();
  app.fire("window", "pagehide");
  app.history.state = { bijuxDiagramReaderPosition: { ...position, x: 19, y: 8700,
    context: { href: link.href, text: link.textContent, top: 250 } } };
  app.fire("window", "pageshow", { persisted: true });
  app.restore();
  app.flush();
  assert.deepEqual(JSON.parse(JSON.stringify(app.scrolls)), [{ left: 19, top: 14025, behavior: "instant" }]);
  assert.equal(app.writes.length, 0);
});

test("pagehide after persisted pageshow cancels its newly queued layout restoration", () => {
  const app = setup();
  app.history.state = { bijuxDiagramReaderPosition: position };
  app.fire("window", "pageshow", { persisted: true });
  app.restore();
  app.fire("window", "pagehide");
  app.flush();
  assert.equal(app.scrolls.length, 0);
});

for (const type of ["navigate", "reload"]) {
  test(`ordinary pageshow does not acquire an owned entry on ${type}`, () => {
    const app = setup({ type, state: { bijuxDiagramReaderPosition: position } });
    app.fire("window", "pageshow", { persisted: false });
    app.restore();
    app.flush();
    assert.equal(app.scrolls.length, 0);
  });
}

for (const [name, state] of [
  ["missing marker", { author: "retained" }],
  ["array state", []],
  ["primitive state", "author"],
  ["boxed state", new String("author")],
  ["inherited marker", Object.create({ bijuxDiagramReaderPosition: position })],
  ...invalidPositions.map((value, index) => [`invalid position ${index}`, { bijuxDiagramReaderPosition: value }]),
  ...["owner", "version", "href", "x", "y"].map(field => {
    const own = { ...position };
    delete own[field];
    return [`inherited ${field}`, { bijuxDiagramReaderPosition: Object.assign(Object.create({ [field]: position[field] }), own) }];
  }),
]) {
  test(`persisted pageshow rejects ${name} without reviving prior owned state`, () => {
    const app = restoredReader();
    app.fire("window", "pagehide");
    app.history.state = state;
    app.fire("window", "pageshow", { persisted: true });
    app.restore();
    app.flush();
    assert.equal(app.scrolls.length, 0);
    assert.equal(app.writes.length, 0);
    assert.equal(app.history.state, state);
  });
}

for (const type of ["pointerdown", "touchstart", "wheel", "keydown"]) {
  test(`trusted ${type} after persisted pageshow retains reader control`, () => {
    const app = setup();
    app.history.state = { bijuxDiagramReaderPosition: position };
    app.fire("window", "pageshow", { persisted: true });
    app.restore();
    app.fire("window", type, { isTrusted: true });
    app.flush();
    assert.equal(app.scrolls.length, 0);
  });
}

test("synthetic input after persisted pageshow cannot cancel the fresh owned entry", () => {
  const app = setup();
  app.history.state = { bijuxDiagramReaderPosition: position };
  app.fire("window", "pageshow", { persisted: true });
  app.restore();
  app.fire("window", "wheel", { isTrusted: false });
  app.flush();
  assert.equal(app.scrolls.length, 1);
});
