"use strict";
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");
const assert = require("node:assert/strict");
const source = fs.readFileSync(
  process.env.BOOTSTRAP_SOURCE ||
    path.resolve(__dirname, "../../../shared/bijux-docs/scripts/bootstrap.js"),
  "utf8",
);
const drawerStart = source.indexOf("  function bindDrawer(signal) {");
const searchStart = source.indexOf("  function bindSearch(signal) {");
const helperStart = source.indexOf("  function bindPopupIdentity(");
const helper = helperStart < 0 ? "" : source.slice(helperStart, drawerStart);
const drawer = source.slice(drawerStart, searchStart);
const search = source.slice(
  searchStart,
  source.indexOf("  function bindQueryInput(", searchStart),
);

class Element extends EventTarget {
  constructor(tag = "DIV", attrs = {}) {
    super();
    this.tagName = tag;
    this.attrs = { ...attrs };
    this.inert = false;
    this.checked = false;
    this.hidden = false;
    this.tabIndex = 0;
    this.children = [];
    this.parentElement = null;
    this.attributes = [];
  }
  getAttribute(name) {
    return this.attrs[name] ?? null;
  }
  setAttribute(name, value) {
    this.attrs[name] = String(value);
  }
  removeAttribute(name) {
    delete this.attrs[name];
  }
  hasAttribute(name) {
    return Object.hasOwn(this.attrs, name);
  }
  getClientRects() {
    return this.hidden ? [] : [{}];
  }
  contains(node) {
    return node === this || this.children.includes(node);
  }
  closest() {
    return null;
  }
  querySelectorAll() {
    return this.children;
  }
  click() {
    this.dispatchEvent(new Event("click", { cancelable: true }));
  }
}

function fixture(
  kind,
  {
    authoredId,
    duplicateId = false,
    occupied = false,
    missing = false,
    initialInert = false,
  } = {},
) {
  const document = new EventTarget();
  document.body = { dataset: {} };
  const preferred = `bijux-${kind === "drawer" ? "navigation" : "search"}-dialog`;
  const surface = new Element("DIV", {
    role: kind === "drawer" ? "navigation" : "search",
    "aria-label": "Authored popup",
    "aria-modal": "false",
    "aria-describedby": "authored-help",
  });
  if (authoredId !== undefined) surface.setAttribute("id", authoredId);
  surface.inert = initialInert;
  const control = new Element("BUTTON", {
    "aria-controls": "authored-target",
    "aria-haspopup": "false",
    "aria-expanded": "false",
  });
  const toggle = new Element("INPUT", {
    id: kind === "drawer" ? "__drawer" : "__search",
  });
  const navigation = new Element("NAV", { id: "bijux-navigation" });
  const query = new Element("INPUT");
  const back = new Element("BUTTON");
  const background = new Element();
  const unrelated = new Element("DIV", {
    id: occupied ? preferred : duplicateId ? authoredId : "unrelated",
  });
  const registry = [
    toggle,
    surface,
    control,
    navigation,
    query,
    back,
    background,
    unrelated,
  ];
  for (const node of registry)
    node.focus = () => {
      document.activeElement = node;
      node.dispatchEvent(new Event("focus"));
    };
  surface.children = kind === "drawer" ? [navigation] : [query, back];
  surface.querySelector = (selector) =>
    selector.includes("__search") ? back : query;
  document.getElementById = (id) =>
    registry.find((node) => node.getAttribute("id") === id) || null;
  document.querySelectorAll = (selector) =>
    selector === "[id]"
      ? registry.filter((node) => node.hasAttribute("id"))
      : selector.includes("data-bijux-control-target")
        ? [control]
        : [background];
  document.querySelector = (selector) => {
    if (selector === "header[data-bijux-drawer-target]")
      return new Element("HEADER");
    if (selector.includes("sidebar")) return missing ? null : surface;
    if (selector.includes("-toggle")) return control;
    if (selector.includes("search-query") || selector.includes("search__input"))
      return query;
    return missing ? null : surface;
  };
  const compact = new EventTarget();
  compact.matches = true;
  const bind = (lifetime) =>
    vm.runInNewContext(
      `let closeDrawer; let readingIntent=false;${helper}${kind === "drawer" ? drawer : search}bind${kind === "drawer" ? "Drawer" : "Search"}(signal);`,
      {
        document,
        compact,
        signal: lifetime.signal,
        Event,
        getComputedStyle: () => ({ visibility: "visible" }),
      },
    );
  const lifetime = new AbortController();
  return {
    document,
    surface,
    control,
    toggle,
    navigation,
    unrelated,
    background,
    lifetime,
    preferred,
    bind: (owner = lifetime) => bind(owner),
  };
}

for (const kind of ["drawer", "search"]) {
  test(`${kind} invoker controls its exact popup surface`, () => {
    const f = fixture(kind);
    f.bind();
    const id = f.control.getAttribute("aria-controls");
    assert.equal(f.document.getElementById(id), f.surface);
    assert.notEqual(id, kind === "drawer" ? "bijux-navigation" : "__search");
    f.control.click();
    assert.equal(f.toggle.checked, true);
    assert.equal(f.surface.getAttribute("role"), "dialog");
    assert.equal(f.surface.getAttribute("aria-modal"), "true");
    f.lifetime.abort();
  });
  test(`${kind} preserves authored identity and semantics across close and disposal`, () => {
    const f = fixture(kind, {
      authoredId: "authored-popup",
      initialInert: true,
    });
    const authoredSurface = { ...f.surface.attrs },
      authoredControl = { ...f.control.attrs };
    f.bind();
    assert.equal(f.control.getAttribute("aria-controls"), "authored-popup");
    f.control.click();
    assert.equal(f.surface.getAttribute("aria-label"), "Authored popup");
    f.control.click();
    assert.deepEqual(f.surface.attrs, authoredSurface);
    f.lifetime.abort();
    assert.deepEqual(f.surface.attrs, authoredSurface);
    assert.deepEqual(f.control.attrs, authoredControl);
    if (kind === "drawer") assert.equal(f.surface.inert, true);
  });
  test(`${kind} allocates a free identity without overwriting an occupied id`, () => {
    const f = fixture(kind, { occupied: true });
    f.bind();
    const allocated = f.surface.getAttribute("id");
    assert.ok(allocated);
    assert.notEqual(allocated, f.preferred);
    assert.equal(f.unrelated.getAttribute("id"), f.preferred);
    assert.equal(f.document.getElementById(allocated), f.surface);
    f.lifetime.abort();
    assert.equal(f.surface.getAttribute("id"), null);
  });
  test(`${kind} rejects duplicate authored identity before owned mutation`, () => {
    const f = fixture(kind, {
      authoredId: "authored-popup",
      duplicateId: true,
    });
    const surface = { ...f.surface.attrs },
      control = { ...f.control.attrs };
    assert.throws(() => f.bind(), /unique authored id/);
    assert.deepEqual(f.surface.attrs, surface);
    assert.deepEqual(f.control.attrs, control);
    f.lifetime.abort();
  });
  test(`${kind} rejects an authored id that cannot be one IDREF`, () => {
    const f = fixture(kind, { authoredId: "authored popup" });
    const surface = { ...f.surface.attrs },
      control = { ...f.control.attrs };
    assert.throws(() => f.bind(), /unique authored id/);
    assert.deepEqual(f.surface.attrs, surface);
    assert.deepEqual(f.control.attrs, control);
    f.lifetime.abort();
  });
  test(`${kind} abort restores identity and prevents stale intent before rebinding`, () => {
    const f = fixture(kind);
    const surface = { ...f.surface.attrs },
      control = { ...f.control.attrs };
    f.bind();
    const identity = f.surface.getAttribute("id");
    f.control.click();
    f.lifetime.abort();
    assert.deepEqual(f.surface.attrs, surface);
    assert.deepEqual(f.control.attrs, control);
    const retainedNativeState = f.toggle.checked;
    f.control.click();
    assert.equal(f.toggle.checked, retainedNativeState);
    f.toggle.checked = false;
    const successor = new AbortController();
    f.bind(successor);
    assert.equal(f.surface.getAttribute("id"), identity);
    f.control.click();
    assert.equal(f.toggle.checked, true);
    successor.abort();
  });
}

test("missing search surface rejects the relationship before claiming initialization", () => {
  const f = fixture("search", { missing: true });
  const original = { ...f.control.attrs };
  assert.throws(() => f.bind(), /controlled popup surface/);
  assert.deepEqual(f.control.attrs, original);
  f.lifetime.abort();
});

test("closed native inline dialog retains a bound fallback name and releases it on abort", () => {
  const f = fixture("search");
  f.surface.setAttribute("role", "dialog");
  f.surface.removeAttribute("aria-label");
  f.bind();
  assert.equal(f.surface.getAttribute("aria-label"), "Search documentation");
  f.control.click();
  f.control.click();
  assert.equal(f.surface.getAttribute("aria-label"), "Search documentation");
  f.lifetime.abort();
  assert.equal(f.surface.getAttribute("aria-label"), null);
});
