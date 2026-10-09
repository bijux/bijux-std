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

function setup({ state = null, type = "navigate", figures = true, anchors = [], shown = true, readyState = "loading" } = {}) {
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
    readyState,
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
  const app = {
    history, writes, scrolls, frames,
    fire(owner, name, event = {}) {
      for (const callback of events.get(owner + ":" + name) || []) callback(event);
    },
    restore() { window.readerTestRestore?.(0); },
    flush() { while (frames.length) frames.shift()(); },
    nativeScroll(y) { window.scrollY = y; },
  };
  // Ordinary layout completion tests start after the browser's initial pageshow.
  // Lifecycle controls retain the pre-pageshow document explicitly.
  if (shown) app.fire("window", "pageshow", { persisted: false });
  return app;
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

test("early diagram completion restores the owned anchor after native pageshow coordinates settle", () => {
  let top = 421.359375;
  const link = anchor();
  link.getBoundingClientRect = () => ({ top });
  const context = { href: link.href, text: link.textContent, top: 421.265625 };
  const app = setup({ state: { bijuxDiagramReaderPosition: { ...position, y: 3406, context } },
    type: "back_forward", anchors: [link], shown: false });
  app.nativeScroll(2855);
  app.restore();
  app.flush();
  assert.equal(app.scrolls.length, 0);
  app.fire("window", "pageshow", { persisted: false });
  // Native traversal can finish its coordinate restoration after pageshow.
  app.nativeScroll(2876);
  top = 400.359375;
  app.flush();
  assert.deepEqual(JSON.parse(JSON.stringify(app.scrolls)), [{ left: 0, top: 2855.09375, behavior: "instant" }]);
});

test("a complete document initialized after pageshow restores without waiting for another event", () => {
  const app = setup({ state: { bijuxDiagramReaderPosition: position }, type: "back_forward",
    shown: false, readyState: "complete" });
  app.restore();
  app.flush();
  assert.equal(app.scrolls.length, 1);
  assert.equal(app.scrolls[0].top, position.y);
});

test("pagehide clears an early pending restore before a later ordinary pageshow", () => {
  const app = setup({ state: { bijuxDiagramReaderPosition: position }, type: "back_forward", shown: false });
  app.restore();
  app.fire("window", "pagehide");
  app.fire("window", "pageshow", { persisted: false });
  app.flush();
  assert.equal(app.scrolls.length, 0);
  assert.equal(app.writes.length, 0);
});

for (const type of ["pointerdown", "touchstart", "wheel", "keydown"]) {
  test(`trusted ${type} before initial pageshow cancels pending reader restoration`, () => {
    const app = setup({ state: { bijuxDiagramReaderPosition: position }, type: "back_forward", shown: false });
    app.restore();
    app.fire("window", type, { isTrusted: true });
    app.fire("window", "pageshow", { persisted: false });
    app.flush();
    assert.equal(app.scrolls.length, 0);
  });
}

test("synthetic input before initial pageshow cannot cancel pending reader restoration", () => {
  const app = setup({ state: { bijuxDiagramReaderPosition: position }, type: "back_forward", shown: false });
  app.restore();
  app.fire("window", "wheel", { isTrusted: false });
  app.fire("window", "pageshow", { persisted: false });
  app.flush();
  assert.equal(app.scrolls.length, 1);
  assert.equal(app.scrolls[0].top, position.y);
});


// Cached documents retain their script realm while Material may reconstruct the
// authored content. Drive the real renderer through its ordinary document stream.
function cachedReader({ entryKey = "reader-entry", available = true } = {}) {
  const events = new Map(), frames = [], scrolls = [], runs = [];
  let subscription, nodes = [], entry = { key: entryKey }, currentURL = new URL(href), scheme = "default";
  class Element {
    constructor(tag) { this.localName = tag; this.namespaceURI = tag === "svg" ? "http://www.w3.org/2000/svg" : null; this.children = []; this.attributes = []; this.isConnected = true; this.text = ""; }
    get textContent() { return this.text + this.children.map(node => node.textContent).join(""); }
    set textContent(text) { this.text = text; this.children = []; }
    setAttribute() {}
    append(...children) { this.children.push(...children); }
    appendChild(child) { this.append(child); return child; }
    querySelector(tag) { return this.children.flatMap(node => [node, ...node.descendants()]).find(node => node.localName === tag) || null; }
    descendants() { return this.children.flatMap(node => [node, ...node.descendants()]); }
    querySelectorAll() { return this.descendants(); }
    addEventListener() {}
    replaceWith(next) { nodes = nodes.map(node => node === this ? next : node); this.isConnected = false; }
    replaceChildren(...children) { this.children = children; this.text = ""; }
  }
  const replace = (texts = ["graph TD; A-->B", "graph TD; C-->D"]) => {
    nodes.forEach(node => { node.isConnected = false; });
    nodes = texts.map(text => { const node = new Element("pre"), code = new Element("code"); code.textContent = text; node.append(code); return node; });
  };
  replace();
  const history = { state: null, replaceState(value) { this.state = value; } };
  const listen = (owner, name, callback) => {
    const key = owner + ":" + name;
    events.set(key, [...(events.get(key) || []), callback]);
  };
  const api = { initialize() {}, render() {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    runs.push({ resolve: () => resolve({ svg: "<svg/>" }), reject: () => reject(new Error("renderer refused")) });
    return promise;
  } };
  const window = { scrollX: 0, scrollY: 13000,
    navigation: available ? { get currentEntry() { return entry; } } : undefined,
    document$: { subscribe(callback) { subscription = callback; } },
    addEventListener: (name, callback) => listen("window", name, callback),
    scrollTo: value => scrolls.push(value),
  };
  const document = { readyState: "complete", currentScript: { src: "https://example.test/assets/mermaid-init.js" },
    body: { getAttribute: () => scheme }, createElement: tag => new Element(tag),
    querySelector: () => nodes.length ? nodes[0] : null,
    querySelectorAll: selector => selector === ".md-content article a[href]" ? [] : nodes.filter(node => node.isConnected),
    addEventListener: (name, callback) => listen("document", name, callback), importNode: node => node,
    head: { appendChild(script) { window.mermaid = api; queueMicrotask(() => script.onload()); } },
  };
  const context = { window, document, history, location: currentURL, URL,
    performance: { getEntriesByType: () => [{ type: "navigate" }] },
    requestAnimationFrame: callback => frames.push(callback), setTimeout: () => 1, clearTimeout() {},
    DOMParser: class { parseFromString() { const svg = new Element("svg"); return { body: { firstElementChild: svg, children: [svg] } }; } },
  };
  vm.runInNewContext(source, context);
  const turn = () => new Promise(resolve => setImmediate(resolve));
  const app = { history, runs, scrolls, replace,
    publish() { subscription(); },
    fire(owner, name, event = {}) { for (const callback of events.get(owner + ":" + name) || []) callback(event); },
    flush() { while (frames.length) frames.shift()(); },
    entry(key) { entry = { key }; }, url(value) { currentURL.href = value; },
    theme(value) { scheme = value; app.fire("window", "bijux:theme-change"); },
    get disclosures() { return nodes.map(node => node.querySelector("details")); },
    get statuses() { return nodes.map(node => node.children[1].textContent); },
    async render({ flush = true, reject = false } = {}) {
      // Resolve each actual serial Mermaid operation, including superseded requests.
      for (let index = 0; index < 20; index++) { await turn(); for (const run of runs) reject ? run.reject() : run.resolve(); }
      if (flush) app.flush();
    },
    depart() { app.fire("document", "click", click()); app.fire("window", "pagehide", { isTrusted: true, persisted: true }); },
    back(event = { isTrusted: true, persisted: true }) { app.fire("window", "pageshow", event); },
  };
  app.publish();
  return app;
}

async function inspectedCachedReader(options) {
  const app = cachedReader(options); await app.render();
  app.disclosures[0].open = true; app.disclosures[1].open = false;
  app.depart();
  // Material's native viewport owner stores only its offset in this entry.
  app.history.state = { x: 0, y: 13000 };
  return app;
}

test("trusted cached same-entry reconstruction preserves exact-source inspection after the shared marker is removed", async () => {
  const app = await inspectedCachedReader();
  app.back(); app.replace(); app.publish(); await app.render();
  assert.deepEqual(app.disclosures.map(details => details.open), [true, false]);
  assert.equal(app.scrolls.at(-1).top, 13000);
  assert.deepEqual(app.history.state, { x: 0, y: 13000 });
});

for (const [name, modify] of [
  ["different same-URL entry", app => app.entry("different-entry")],
  ["query change", app => app.url(href + "?different")],
  ["fragment change", app => app.url(href + "#different")],
  ["source replacement", app => app.replace(["graph TD; X-->Y", "graph TD; C-->D"])],
  ["source order", app => app.replace(["graph TD; C-->D", "graph TD; A-->B"])],
  ["source count", app => app.replace(["graph TD; A-->B"])],
]) {
  test(`cached inspection refuses ${name}`, async () => {
    const app = await inspectedCachedReader(); app.back(); app.replace(); modify(app); app.publish(); await app.render();
    assert.ok(app.disclosures.every(details => details.open === false));
    assert.equal(app.scrolls.length, 0);
  });
}

for (const options of [{ available: false }, { entryKey: "" }, { entryKey: null }, { entryKey: 42 }]) {
  test(`cached inspection requires an actual entry identity: ${JSON.stringify(options)}`, async () => {
    const app = await inspectedCachedReader(options); app.back(); app.replace(); app.publish(); await app.render();
    assert.ok(app.disclosures.every(details => details.open === false));
    assert.equal(app.scrolls.length, 0);
  });
}

for (const event of [{ isTrusted: false, persisted: true }, { isTrusted: true, persisted: false }]) {
  test(`cached inspection requires a trusted persisted return: ${JSON.stringify(event)}`, async () => {
    const app = await inspectedCachedReader(); app.back(event); app.replace(); app.publish(); await app.render();
    assert.ok(app.disclosures.every(details => details.open === false)); assert.equal(app.scrolls.length, 0);
  });
}

for (const input of ["pointerdown", "touchstart", "wheel", "keydown"]) {
  test(`trusted ${input} cancels cached inspection and scroll before reconstructed completion`, async () => {
    const app = await inspectedCachedReader(); app.back(); app.replace(); app.publish();
    app.fire("window", input, { isTrusted: true }); await app.render();
    assert.ok(app.disclosures.every(details => details.open === false)); assert.equal(app.scrolls.length, 0);
  });
}

test("synthetic input cannot impersonate cached-reader inspection cancellation", async () => {
  const app = await inspectedCachedReader(); app.back(); app.replace(); app.publish();
  app.fire("window", "wheel", { isTrusted: false }); await app.render();
  assert.deepEqual(app.disclosures.map(details => details.open), [true, false]);
});

test("a later pagehide invalidates cached inspection before reconstructed completion", async () => {
  const app = await inspectedCachedReader(); app.back(); app.replace(); app.publish();
  app.fire("window", "pagehide", { isTrusted: true, persisted: true }); await app.render();
  assert.ok(app.disclosures.every(details => details.open === true)); assert.equal(app.scrolls.length, 0);
});


for (const event of [{ isTrusted: false, persisted: true }, { isTrusted: true, persisted: false }]) {
  test(`cached inspection requires a trusted cached departure: ${JSON.stringify(event)}`, async () => {
    const app = cachedReader(); await app.render(); app.disclosures[0].open = true;
    app.fire("document", "click", click()); app.fire("window", "pagehide", event);
    app.history.state = { x: 0, y: 13000 }; app.back(); app.replace(); app.publish(); await app.render();
    assert.ok(app.disclosures.every(details => details.open === false)); assert.equal(app.scrolls.length, 0);
  });
}

for (const [name, change] of [
  ["entry", app => app.entry("another-entry")],
  ["URL", app => app.url(href + "?another")],
  ["source", app => { app.replace(["graph TD; X-->Y"]); }],
]) {
  test(`cached deferred frames cannot restore after a late ${name} change`, async () => {
    const app = await inspectedCachedReader(); app.back(); app.replace(); app.publish();
    await app.render({ flush: false }); change(app); app.flush();
    assert.equal(app.scrolls.length, 0);
  });
}

test("cached failed rendering keeps the accessible source fallback open", async () => {
  const app = await inspectedCachedReader(); app.back(); app.replace(); app.publish(); await app.render({ reject: true });
  assert.ok(app.disclosures.every(details => details.open === true));
  assert.ok(app.statuses.every(text => /preview unavailable/.test(text)));
});

test("a newer trusted departure replaces cached inspection without resurrecting older disclosure", async () => {
  const app = await inspectedCachedReader(); app.back(); await app.render();
  app.disclosures[0].open = false; app.disclosures[1].open = true; app.depart();
  app.history.state = { x: 0, y: 13000 }; app.back(); app.replace(); app.publish(); await app.render();
  assert.deepEqual(app.disclosures.map(details => details.open), [false, true]);
});

test("duplicate document emissions share one current inspection generation and one renderer lane", async () => {
  const app = await inspectedCachedReader(); app.back(); app.replace(); app.publish(); app.publish(); await app.render();
  assert.deepEqual(app.disclosures.map(details => details.open), [true, false]);
  assert.equal(app.scrolls.length, 1);
  assert.equal(app.runs.length, 4);
});


test("a failed rerender of a cached preview cannot close its readable fallback", async () => {
  const app = await inspectedCachedReader(); app.back(); await app.render();
  app.theme("slate"); await app.render({ reject: true });
  assert.ok(app.disclosures.every(details => details.open === true));
  assert.ok(app.statuses.every(text => /preview unavailable/.test(text)));
});


test("cached private authority cannot be mutated through the departing public history record", async () => {
  const app = cachedReader(); await app.render(); app.disclosures[0].open = true; app.depart();
  const publicPosition = app.history.state.bijuxDiagramReaderPosition;
  publicPosition.y = Infinity; publicPosition.href = href + "?forged";
  app.history.state = { x: 0, y: 13000 }; app.back(); app.replace(); app.publish(); await app.render();
  assert.deepEqual(app.disclosures.map(details => details.open), [true, false]);
  assert.equal(app.scrolls.at(-1).top, 13000);
});

test("a rejected newer native capture cannot retain an older cached departure", async () => {
  const app = await inspectedCachedReader(); app.back(); await app.render();
  app.history.state = "opaque owner"; app.depart(); app.history.state = { x: 0, y: 13000 };
  app.back(); app.replace(); app.publish(); await app.render();
  assert.ok(app.disclosures.every(details => details.open === false));
  assert.equal(app.scrolls.length, 1);
});


test("a second trusted cached departure preserves the same proven reader entry through reconstruction", async () => {
  const app = await inspectedCachedReader(); app.back(); app.replace(); app.publish(); await app.render();
  app.fire("window", "pagehide", { isTrusted: true, persisted: true });
  app.history.state = { x: 0, y: 13000 }; app.back(); app.replace(); app.publish(); await app.render();
  assert.deepEqual(app.disclosures.map(details => details.open), [true, false]);
  assert.equal(app.scrolls.length, 2);
});

test("trusted reader input prevents a cached departure from rearming its previous authority", async () => {
  const app = await inspectedCachedReader(); app.back(); app.replace(); app.publish(); await app.render();
  app.fire("window", "wheel", { isTrusted: true });
  app.fire("window", "pagehide", { isTrusted: true, persisted: true });
  app.history.state = { x: 0, y: 13000 }; app.back(); app.replace(); app.publish(); await app.render();
  assert.ok(app.disclosures.every(details => details.open === false));
  assert.equal(app.scrolls.length, 1);
});
