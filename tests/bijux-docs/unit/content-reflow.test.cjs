const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(
  path.resolve(
    __dirname,
    "../../../shared/bijux-docs/scripts/content-reflow.js",
  ),
  "utf8",
);

function fixture(t, options = {}) {
  const frames = new Map(),
    observers = [],
    mutations = [];
  let nextFrame = 0;
  class Element extends EventTarget {
    constructor(kind, width = 100, scroll = width) {
      super();
      this.kind = kind;
      this.clientWidth = width;
      this.scrollWidth = scroll;
      this.scrollLeft = 0;
      this.attributes = new Map();
      this.textContent = "";
      this.innerHTML = "authored bytes";
      this.children = [];
    }
    get textContent() {
      return (
        this._textContent +
        this.children.map((child) => child.textContent || "").join("")
      );
    }
    set textContent(value) {
      this._textContent = String(value);
      this.children = [];
    }
    cloneNode(deep) {
      const clone = new Element(this.kind, this.clientWidth, this.scrollWidth);
      clone._textContent = this._textContent;
      clone.attributes = new Map(this.attributes);
      if (deep)
        for (const child of this.children) {
          const copy = child.cloneNode(true);
          copy.parentNode = clone;
          clone.children.push(copy);
        }
      return clone;
    }
    scrollTo({ left }) {
      this.scrollLeft = left;
    }
    setAttribute(key, value) {
      this.attributes.set(key, String(value));
    }
    getAttribute(key) {
      return this.attributes.get(key) ?? null;
    }
    hasAttribute(key) {
      return this.attributes.has(key);
    }
    removeAttribute(key) {
      this.attributes.delete(key);
    }
    querySelector(selector) {
      return selector === "table.highlighttable"
        ? this.lineTable || null
        : selector === "caption"
          ? this.caption || null
          : null;
    }
    querySelectorAll(selector) {
      if (selector === "pre > code") return this.codes || [];
      if (selector === '.headerlink, [aria-hidden="true"]') {
        const descendants = (node) =>
          node.children.flatMap((child) => [child, ...descendants(child)]);
        return descendants(this).filter(
          (node) =>
            (node.getAttribute("class") || "")
              .split(/\s+/)
              .includes("headerlink") ||
            node.getAttribute("aria-hidden") === "true",
        );
      }
      return [];
    }
    compareDocumentPosition() {
      return 4;
    }
    closest(selector) {
      return selector === ".highlight"
        ? this.kind === "highlight"
          ? this
          : this.block
        : null;
    }
    insertBefore(node) {
      node.parentNode = this;
      this.children.push(node);
    }
    remove() {
      if (this.parentNode)
        this.parentNode.children = this.parentNode.children.filter(
          (child) => child !== this,
        );
      this.parentNode = null;
    }
  }
  const article = new Element("article");
  const heading = new Element("heading");
  heading.textContent = "Reader context";
  const code = new Element("code", 100, options.scroll ?? 400);
  code.textContent = "line one\nline two\n";
  const block = new Element("highlight", 100, options.tableMode ? 500 : 100);
  block.codes = [code];
  block.lineTable = options.tableMode ? new Element("number table") : null;
  block.parentNode = article;
  code.block = block;
  code.parentElement = new Element("pre");
  const table = new Element("table", 100, 350);
  table.parentNode = article;
  article.blocks = [block];
  article.tables = options.table ? [table] : [];
  article.querySelectorAll = (selector) =>
    selector === ".highlight"
      ? article.blocks
      : selector === ".md-typeset__scrollwrap"
        ? article.tables
        : [heading];
  const document = {
    title: "Document",
    activeElement: null,
    querySelector: () => article,
    createElement: () => new Element("hint"),
    getElementById: (id) =>
      article.children.find((child) => child.id === id) || null,
  };
  class Resize {
    constructor(callback) {
      this.callback = callback;
      this.nodes = new Set();
      observers.push(this);
    }
    observe(node) {
      this.nodes.add(node);
    }
    unobserve(node) {
      this.nodes.delete(node);
    }
    disconnect() {
      this.nodes.clear();
      this.disconnected = true;
    }
  }
  class Mutation {
    constructor(callback) {
      this.callback = callback;
      mutations.push(this);
    }
    observe() {}
    disconnect() {
      this.disconnected = true;
    }
  }
  const window = new EventTarget();
  window.ResizeObserver = options.noResize ? undefined : Resize;
  window.MutationObserver = Mutation;
  const context = vm.createContext({
    window,
    document,
    Node: { DOCUMENT_POSITION_FOLLOWING: 4 },
    getComputedStyle: (e) => ({ direction: e.direction || "ltr" }),
    ResizeObserver: Resize,
    MutationObserver: Mutation,
    requestAnimationFrame: (callback) => {
      const id = ++nextFrame;
      frames.set(id, callback);
      return id;
    },
    cancelAnimationFrame: (id) => frames.delete(id),
  });
  vm.runInContext(source, context);
  const controller = new AbortController();
  t.after(() => controller.abort());
  const bind = () => window.bijuxShell.contentReflow.bind(controller.signal);
  const flush = () => {
    const jobs = [...frames.values()];
    frames.clear();
    for (const callback of jobs) callback();
  };
  return {
    element: (kind) => new Element(kind),
    article,
    heading,
    code,
    block,
    table,
    document,
    window,
    controller,
    frames,
    observers,
    mutations,
    bind,
    flush,
    context,
  };
}

test("only measured overflow gets a named keyboard path and visible discovery", (t) => {
  const f = fixture(t);
  f.bind();
  assert.equal(f.code.hasAttribute("tabindex"), false);
  f.flush();
  assert.equal(f.code.getAttribute("tabindex"), "0");
  assert.equal(f.code.getAttribute("role"), "region");
  assert.match(
    f.code.getAttribute("aria-label"),
    /^Scrollable code example 1: Reader context$/,
  );
  assert.equal(f.article.children.length, 1);
  assert.match(f.article.children[0].textContent, /Left and Right arrow keys/);
});
test("ordinary nonoverflowing code gets no arbitrary focus stop", (t) => {
  const f = fixture(t, { scroll: 100 });
  f.bind();
  f.flush();
  assert.equal(f.code.hasAttribute("tabindex"), false);
  assert.equal(f.article.children.length, 0);
});
test("observer delivery only schedules one frame and leaves DOM unchanged synchronously", (t) => {
  const f = fixture(t);
  f.bind();
  f.observers[0].callback();
  f.observers[0].callback();
  assert.equal(f.frames.size, 1);
  assert.equal(f.code.hasAttribute("tabindex"), false);
  f.flush();
  assert.equal(f.code.getAttribute("tabindex"), "0");
});
test("source text and line-anchor markup are untouched", (t) => {
  const f = fixture(t);
  const before = [f.code.textContent, f.code.innerHTML];
  f.bind();
  f.flush();
  assert.deepEqual([f.code.textContent, f.code.innerHTML], before);
});
test("table uses its caption while preserving table subtree", (t) => {
  const f = fixture(t, { table: true });
  f.table.caption = { textContent: "Scientific comparison" };
  const before = f.table.innerHTML;
  f.bind();
  f.flush();
  assert.match(f.table.getAttribute("aria-label"), /Scientific comparison$/);
  assert.equal(f.table.innerHTML, before);
});
test("table-mode line numbering chooses one outer code surface", (t) => {
  const f = fixture(t, { tableMode: true });
  f.bind();
  f.flush();
  assert.equal(f.block.getAttribute("tabindex"), "0");
  assert.equal(f.code.hasAttribute("tabindex"), false);
  assert.equal(f.article.children.length, 1);
});
test("owned annotations and hints restore when overflow ends", (t) => {
  const f = fixture(t);
  f.bind();
  f.flush();
  f.code.scrollWidth = 100;
  f.observers[0].callback();
  f.flush();
  assert.equal(f.code.attributes.size, 0);
  assert.equal(f.article.children.length, 0);
});
test("focused region stays stable on resize until ordinary blur", (t) => {
  const f = fixture(t);
  f.bind();
  f.flush();
  f.document.activeElement = f.code;
  f.code.scrollWidth = 100;
  f.observers[0].callback();
  f.flush();
  assert.equal(f.code.getAttribute("tabindex"), "0");
  f.document.activeElement = null;
  f.code.dispatchEvent(new Event("blur"));
  f.flush();
  assert.equal(f.code.hasAttribute("tabindex"), false);
});
test("authored role label focus and descriptions are preserved", (t) => {
  const f = fixture(t);
  for (const [key, value] of Object.entries({
    role: "group",
    tabindex: "-1",
    "aria-label": "Author label",
    "aria-describedby": "author-help",
  }))
    f.code.setAttribute(key, value);
  const before = [...f.code.attributes];
  f.bind();
  f.flush();
  assert.deepEqual([...f.code.attributes], before);
  f.controller.abort();
  assert.deepEqual([...f.code.attributes], before);
});
test("author changes after enhancement are not overwritten on disposal", (t) => {
  const f = fixture(t);
  f.bind();
  f.flush();
  f.code.setAttribute("tabindex", "3");
  f.code.setAttribute("aria-label", "Changed author label");
  f.controller.abort();
  assert.equal(f.code.getAttribute("tabindex"), "3");
  assert.equal(f.code.getAttribute("aria-label"), "Changed author label");
  assert.equal(f.code.hasAttribute("role"), false);
});
test("abort disconnects both observers and cancels pending delivery", (t) => {
  const f = fixture(t);
  f.bind();
  f.flush();
  f.observers[0].callback();
  assert.equal(f.frames.size, 1);
  f.controller.abort();
  assert.equal(f.frames.size, 0);
  assert(f.observers[0].disconnected);
  assert(f.mutations[0].disconnected);
  assert.equal(f.code.attributes.size, 0);
  assert.equal(f.article.children.length, 0);
  f.observers[0].callback();
  assert.equal(f.frames.size, 0);
});
test("already aborted lifetime never installs observers or frames", (t) => {
  const f = fixture(t);
  f.controller.abort();
  f.bind();
  assert.equal(f.observers.length, 0);
  assert.equal(f.frames.size, 0);
});
test("document removal releases its old surface and owned labels", (t) => {
  const f = fixture(t);
  f.bind();
  f.flush();
  f.article.blocks = [];
  f.mutations[0].callback();
  f.flush();
  assert.equal(f.code.attributes.size, 0);
  assert.equal(f.article.children.length, 0);
  assert.equal(f.observers[0].nodes.has(f.code), false);
});
test("new dynamic code is qualified by the document mutation boundary", (t) => {
  const f = fixture(t);
  f.article.blocks = [];
  f.bind();
  f.flush();
  f.article.blocks = [f.block];
  f.mutations[0].callback();
  f.flush();
  assert.equal(f.code.getAttribute("tabindex"), "0");
});
test("module admission is idempotent and regular resize remains fallback", (t) => {
  const f = fixture(t, { noResize: true });
  const bind = f.window.bijuxShell.contentReflow.bind;
  vm.runInContext(source, f.context);
  assert.equal(f.window.bijuxShell.contentReflow.bind, bind);
  f.bind();
  f.flush();
  assert.equal(f.code.getAttribute("tabindex"), "0");
  f.code.scrollWidth = 100;
  f.window.dispatchEvent(new Event("resize"));
  f.flush();
  assert.equal(f.code.hasAttribute("tabindex"), false);
});
test("duplicate authored IDs are avoided without changing them", (t) => {
  const f = fixture(t);
  f.article.children.push({ id: "bijux-content-scroll-1" });
  f.bind();
  f.flush();
  assert.equal(f.article.children[0].id, "bijux-content-scroll-1");
  assert.equal(f.article.children[1].id, "bijux-content-scroll-1-hint");
});
test("code-containing malformed heading is excluded from generated context", (t) => {
  const f = fixture(t);
  f.heading.querySelector = () => ({});
  f.heading.textContent = "from typing import giant source";
  f.bind();
  f.flush();
  assert.equal(
    f.code.getAttribute("aria-label"),
    "Scrollable code example 1: Document",
  );
});

function key(surface, key, extra = {}) {
  const event = new Event("keydown", { cancelable: true });
  Object.assign(event, { key, ...extra });
  surface.dispatchEvent(event);
  return event;
}
test("focused horizontal arrows and edge keys are bounded without native scroll races", (t) => {
  const f = fixture(t);
  f.bind();
  f.flush();
  f.document.activeElement = f.code;
  assert(key(f.code, "End").defaultPrevented);
  assert.equal(f.code.scrollLeft, 300);
  assert(key(f.code, "Home").defaultPrevented);
  assert.equal(f.code.scrollLeft, 0);
  assert(key(f.code, "ArrowRight").defaultPrevented);
  assert.equal(f.code.scrollLeft, 40);
  key(f.code, "ArrowLeft");
  assert.equal(f.code.scrollLeft, 0);
});
test("RTL End reaches the negative-offset content end and Home restores its origin", (t) => {
  const f = fixture(t, { table: true });
  f.table.direction = "rtl";
  f.bind();
  f.flush();
  f.document.activeElement = f.table;
  key(f.table, "End");
  assert.equal(f.table.scrollLeft, -250);
  key(f.table, "ArrowRight");
  assert.equal(f.table.scrollLeft, -210);
  key(f.table, "Home");
  assert.equal(f.table.scrollLeft, 0);
  key(f.table, "ArrowLeft");
  assert.equal(f.table.scrollLeft, -40);
});
test("modified and unrelated keys retain native and assistive behavior", (t) => {
  const f = fixture(t);
  f.bind();
  f.flush();
  f.document.activeElement = f.code;
  for (const name of ["ArrowLeft", "ArrowRight", "Home", "End"])
    for (const extra of [
      { shiftKey: true },
      { ctrlKey: true },
      { altKey: true },
      { metaKey: true },
    ])
      assert.equal(key(f.code, name, extra).defaultPrevented, false);
  for (const name of [
    "ArrowDown",
    "ArrowUp",
    "Tab",
    "Enter",
    "Escape",
    "PageDown",
    "PageUp",
  ])
    assert.equal(key(f.code, name).defaultPrevented, false);
  assert.equal(f.code.scrollLeft, 0);
});
test("unfocused or already handled keys are not taken over", (t) => {
  const f = fixture(t);
  f.bind();
  f.flush();
  assert.equal(key(f.code, "End").defaultPrevented, false);
  f.document.activeElement = f.code;
  const event = new Event("keydown", { cancelable: true });
  event.key = "End";
  event.preventDefault();
  f.code.dispatchEvent(event);
  assert.equal(f.code.scrollLeft, 0);
});
test("fitting and removed surfaces relinquish horizontal edge keys", (t) => {
  const f = fixture(t);
  f.bind();
  f.flush();
  f.document.activeElement = f.code;
  f.code.scrollWidth = 100;
  assert.equal(key(f.code, "End").defaultPrevented, false);
  f.code.scrollWidth = 400;
  f.article.blocks = [];
  f.mutations[0].callback();
  f.flush();
  assert.equal(key(f.code, "End").defaultPrevented, false);
});
test("aborted document lifetime no longer consumes edge keys", (t) => {
  const f = fixture(t);
  f.bind();
  f.flush();
  f.document.activeElement = f.code;
  f.controller.abort();
  assert.equal(key(f.code, "End").defaultPrevented, false);
  assert.equal(f.code.scrollLeft, 0);
});

test("events from code links and embedded controls retain their own keyboard behavior", (t) => {
  const f = fixture(t);
  f.bind();
  f.flush();
  f.document.activeElement = f.code;
  const event = new Event("keydown", { cancelable: true });
  event.key = "End";
  Object.defineProperty(event, "target", { value: { kind: "line anchor" } });
  f.code.dispatchEvent(event);
  assert.equal(event.defaultPrevented, false);
  assert.equal(f.code.scrollLeft, 0);
});

test("active text selection keeps edge keys available to native selection", (t) => {
  const f = fixture(t);
  f.window.getSelection = () => ({ rangeCount: 1, isCollapsed: false });
  f.bind();
  f.flush();
  f.document.activeElement = f.code;
  assert.equal(key(f.code, "End").defaultPrevented, false);
  assert.equal(f.code.scrollLeft, 0);
});

test("an empty native selection object does not block explicitly focused edge navigation", (t) => {
  const f = fixture(t);
  f.window.getSelection = () => ({
    rangeCount: 0,
    isCollapsed: false,
    type: "None",
  });
  f.bind();
  f.flush();
  f.document.activeElement = f.code;
  assert(key(f.code, "End").defaultPrevented);
  assert.equal(f.code.scrollLeft, 300);
});

test("rapid focused ArrowRight then End prevents both native scroll actions", (t) => {
  const f = fixture(t);
  f.bind();
  f.flush();
  f.document.activeElement = f.code;
  assert(key(f.code, "ArrowRight").defaultPrevented);
  assert.equal(f.code.scrollLeft, 40);
  assert(key(f.code, "End").defaultPrevented);
  assert.equal(f.code.scrollLeft, 300);
});

test("fitting numbered table names its overflowing inner code without changing native cells", (t) => {
  const f = fixture(t, { tableMode: true });
  f.block.scrollWidth = f.block.clientWidth;
  const before = [f.block.innerHTML, f.code.textContent, f.code.innerHTML];
  f.bind();
  f.flush();
  assert.equal(f.block.hasAttribute("tabindex"), false);
  assert.equal(f.code.getAttribute("role"), "region");
  assert.equal(f.code.getAttribute("tabindex"), "0");
  assert.deepEqual(
    [f.block.innerHTML, f.code.textContent, f.code.innerHTML],
    before,
  );
  f.document.activeElement = f.code;
  assert(key(f.code, "End").defaultPrevented);
  assert.equal(f.code.scrollLeft, 300);
});

test("numbered code owner changes restore prior annotations and expose the real new scroller", (t) => {
  const f = fixture(t, { tableMode: true });
  f.block.scrollWidth = f.block.clientWidth;
  f.bind();
  f.flush();
  assert.equal(f.code.getAttribute("role"), "region");
  f.block.scrollWidth = 500;
  f.window.dispatchEvent(new Event("resize"));
  f.flush();
  assert.equal(f.code.hasAttribute("tabindex"), false);
  assert.equal(f.block.getAttribute("role"), "region");
  assert.equal(f.article.children.length, 1);
  f.controller.abort();
  assert.equal(f.block.hasAttribute("role"), false);
  assert.equal(f.article.children.length, 0);
});

test("reader context excludes a native permalink without mutating its heading", (t) => {
  const f = fixture(t);
  const permalink = f.element("anchor");
  permalink.setAttribute("class", "headerlink");
  permalink.textContent = "¶";
  permalink.parentNode = f.heading;
  f.heading.children.push(permalink);
  const original = f.heading.textContent;
  f.bind();
  f.flush();
  assert.equal(
    f.code.getAttribute("aria-label"),
    "Scrollable code example 1: Reader context",
  );
  assert.equal(f.heading.textContent, original);
  assert.equal(f.heading.children[0], permalink);
});

test("reader context preserves an authored literal pilcrow beside native decoration", (t) => {
  const f = fixture(t);
  f.heading.textContent = "Authored ¶ context";
  const permalink = f.element("anchor");
  permalink.setAttribute("class", "headerlink");
  permalink.textContent = "¶";
  permalink.parentNode = f.heading;
  f.heading.children.push(permalink);
  f.bind();
  f.flush();
  assert.equal(
    f.code.getAttribute("aria-label"),
    "Scrollable code example 1: Authored ¶ context",
  );
  assert.equal(f.heading.textContent, "Authored ¶ context¶");
});

test("reader context excludes hidden decoration while preserving exposed child text", (t) => {
  const f = fixture(t);
  const hidden = f.element("decoration");
  hidden.setAttribute("aria-hidden", "true");
  hidden.textContent = " decorative symbol";
  const visible = f.element("emphasis");
  visible.setAttribute("aria-hidden", "false");
  visible.textContent = " visible annotation";
  hidden.parentNode = visible.parentNode = f.heading;
  f.heading.children.push(hidden, visible);
  f.bind();
  f.flush();
  assert.equal(
    f.code.getAttribute("aria-label"),
    "Scrollable code example 1: Reader context visible annotation",
  );
  assert.equal(
    f.heading.textContent,
    "Reader context decorative symbol visible annotation",
  );
});
