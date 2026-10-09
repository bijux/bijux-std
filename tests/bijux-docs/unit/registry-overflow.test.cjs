const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(process.env.BIJUX_NAV_REVEAL_SOURCE || path.resolve(__dirname, "../../../shared/bijux-docs/scripts/nav-reveal.js"), "utf8");

function fixture(t, options = {}) {
  const document = { activeElement: null };
  const observers = [];
  const state = { width: options.width ?? 400, content: options.content ?? 900, offset: 0, scrolls: [] };
  const fonts = Promise.withResolvers();
  class Element extends EventTarget {
    constructor(kind) { super(); this.kind = kind; this.hidden = kind === "previous" || kind === "next"; this.attributes = new Map(); }
    get clientWidth() {
      if (this.kind === "list") return Math.max(0, state.width - (previous.hidden ? 0 : 44) - (next.hidden ? 0 : 44));
      return this.kind === "strip" ? state.width : this.hidden ? 0 : this.kind === "drawer" ? 44 : 100;
    }
    get scrollWidth() { return this.kind === "list" ? state.content : this.clientWidth; }
    getBoundingClientRect() {
      if (this.kind === "previous" || this.kind === "next" || this.kind === "drawer") return { left: 0, right: 44, top: 0, bottom: 44, width: 44, height: 44 };
      const width = this.clientWidth;
      if (this.kind === "strip" || this.kind === "list") return { left: 0, right: width, top: 0, bottom: 44, width, height: 44 };
      const index = links.indexOf(this);
      const left = (options.rtl ? list.clientWidth - 100 - index * (state.content - 100) / 2 : index * (state.content - 100) / 2) - state.offset;
      return { left, right: left + 100, top: 0, bottom: 44, width: 100, height: 44 };
    }
    getClientRects() { return this.hidden || (this !== drawer && state.width === 0) ? [] : [this.getBoundingClientRect()]; }
    getAttribute(key) { return this.attributes.get(key) ?? null; }
    setAttribute(key, value) { this.attributes.set(key, String(value)); }
    removeAttribute(key) { this.attributes.delete(key); }
    focus() {
      const previous = document.activeElement;
      if (previous === this) return;
      document.activeElement = this;
      previous?.dispatchEvent(new Event("blur"));
      this.dispatchEvent(new Event("focus"));
      if (links.includes(this)) list.dispatchEvent(new Event("focusin"));
    }
    querySelector(selector) {
      if (this === strip) return selector === ".bijux-tabs__list" ? list : selector.includes("previous") ? previous : selector.includes("next") ? next : null;
      if (this === list) return selector === ":focus" ? links.includes(document.activeElement) ? document.activeElement : null : selector === "a" ? links[0] : selector.includes("aria-current") || selector.includes("item--active") ? current : null;
      return null;
    }
    querySelectorAll(selector) { return this === list && selector === "a" ? links : []; }
    scrollBy(request) {
      state.scrolls.push({ ...request });
      const max = Math.max(0, state.content - list.clientWidth);
      state.offset = options.rtl ? Math.max(-max, Math.min(0, state.offset + request.left)) : Math.max(0, Math.min(max, state.offset + request.left));
      list.dispatchEvent(new Event("scroll"));
    }
  }
  const previous = new Element("previous"), next = new Element("next"), list = new Element("list"), strip = new Element("strip"), drawer = new Element("drawer");
  const links = [new Element("first"), new Element("middle"), new Element("last")];
  const current = links[1];
  document.body = new Element("body");
  document.querySelector = selector => selector.includes("drawer-toggle") ? drawer : null;
  document.querySelectorAll = selector => selector === ".bijux-hub-strip" ? options.missingList ? [] : [strip] : [list];
  document.fonts = options.noFonts ? undefined : { ready: fonts.promise };
  const window = new EventTarget();
  class ResizeObserver {
    constructor(callback) { this.callback = callback; this.disconnected = false; this.observed = []; observers.push(this); }
    observe(node) { this.observed.push(node); if (options.observeFault) throw new Error("Owned resize registration failed"); }
    disconnect() { this.disconnected = true; }
  }
  vm.runInNewContext(source, { window, document, ResizeObserver: options.noObserver ? undefined : ResizeObserver, queueMicrotask, getComputedStyle: () => ({ direction: options.rtl ? "rtl" : "ltr" }) });
  const leases = [];
  const bind = (controller = new AbortController()) => { leases.push(controller); window.bijuxShell.navReveal.bind(controller.signal); return controller; };
  t.after(() => leases.forEach(controller => controller.abort()));
  return { document, window, previous, next, list, strip, drawer, current, links, observers, state, fonts, bind, reveal: window.bijuxShell.navReveal };
}

test("a fitted registry keeps authored controls hidden", t => {
  const f = fixture(t, { content: 300 }); f.bind();
  assert.equal(f.previous.hidden, true); assert.equal(f.next.hidden, true); assert.equal(f.state.scrolls.length, 0);
});
test("overflow exposes discovery controls with truthful endpoint state", t => {
  const f = fixture(t); f.bind();
  assert.equal(f.previous.hidden, false); assert.equal(f.next.hidden, false);
  assert.equal(f.previous.getAttribute("aria-disabled"), "true"); assert.equal(f.next.getAttribute("aria-disabled"), "false");
  f.previous.dispatchEvent(new Event("click")); assert.equal(f.state.scrolls.length, 0);
  f.next.dispatchEvent(new Event("click")); assert.equal(f.state.scrolls.length, 1); assert(f.state.offset > 0);
});
test("forward and backward commands retain logical direction under RTL", t => {
  const f = fixture(t, { rtl: true }); f.bind();
  f.next.dispatchEvent(new Event("click")); assert(f.state.scrolls[0].left < 0);
  f.previous.dispatchEvent(new Event("click")); assert(f.state.scrolls.at(-1).left > 0);
});
test("keyboard focus reveals the offscreen current destination through its real scroller", t => {
  const f = fixture(t); f.bind(); f.links[2].focus(); f.list.dispatchEvent(new Event("focusin"));
  assert(f.state.scrolls.length > 0); assert.equal(f.document.activeElement, f.links[2]);
  const target = f.links[2].getBoundingClientRect(), box = f.list.getBoundingClientRect();
  assert(target.left >= box.left && target.right <= box.right);
});
test("a fitted resize returns focus from retiring controls to the current destination", t => {
  const f = fixture(t); f.bind(); f.next.focus(); f.state.width = 1200; f.window.dispatchEvent(new Event("resize"));
  assert.equal(f.next.hidden, true); assert.equal(f.document.activeElement, f.current);
});
test("a phone transition returns retired desktop control focus to the visible menu", t => {
  const f = fixture(t); f.bind(); f.next.focus(); f.state.width = 0; f.window.dispatchEvent(new Event("resize"));
  assert.equal(f.next.hidden, true); assert.equal(f.document.activeElement, f.drawer);
});
test("an already aborted lifetime cannot allocate an observer or enhance controls", t => {
  const f = fixture(t); const lease = new AbortController(); lease.abort(); f.bind(lease);
  assert.equal(f.observers.length, 0); assert.equal(f.previous.hidden, true); assert.equal(f.next.hidden, true);
});
test("failed resize registration remains owned through mount rollback", t => {
  const f = fixture(t, { observeFault: true }); const lease = new AbortController();
  assert.throws(() => f.bind(lease), /Owned resize registration failed/); lease.abort();
  assert.equal(f.observers.length, 1); assert.equal(f.observers[0].disconnected, true);
  assert.equal(f.previous.hidden, true); assert.equal(f.next.hidden, true);
});
test("abort retires actions and restores native authored visibility and attributes", t => {
  const f = fixture(t); const lease = f.bind(); assert.equal(f.next.hidden, false); lease.abort();
  assert.equal(f.observers[0].disconnected, true); assert.equal(f.previous.hidden, true); assert.equal(f.next.hidden, true);
  assert.equal(f.previous.getAttribute("aria-disabled"), null); assert.equal(f.next.getAttribute("aria-disabled"), null);
  f.next.dispatchEvent(new Event("click")); f.window.dispatchEvent(new Event("resize")); assert.equal(f.state.scrolls.length, 0);
});
test("missing ResizeObserver retains ordinary resize and scroll controls", t => {
  const f = fixture(t, { noObserver: true, noFonts: true }); f.bind(); f.next.dispatchEvent(new Event("click"));
  assert.equal(f.observers.length, 0); assert(f.state.scrolls.length > 0);
  f.state.width = 1200; f.window.dispatchEvent(new Event("resize")); assert.equal(f.next.hidden, true);
});
test("instant remount permits one scroll command and disconnects the former owner", t => {
  const f = fixture(t); const prior = f.bind(); prior.abort(); f.bind(); f.next.dispatchEvent(new Event("click"));
  assert.equal(f.state.scrolls.length, 1); assert.equal(f.observers[0].disconnected, true); assert.equal(f.observers[1].disconnected, false);
});
test("late font readiness cannot mutate retired controls", async t => {
  const f = fixture(t); const lease = f.bind(); lease.abort(); f.previous.hidden = true; f.next.hidden = true;
  f.fonts.resolve(); await Promise.resolve(); await Promise.resolve();
  assert.equal(f.previous.hidden, true); assert.equal(f.next.hidden, true);
});

test("abort returns retiring control focus to a visibly revealed native destination", t => {
  const f = fixture(t); const lease = f.bind(); f.reveal.runDesktopNavigationSync();
  f.next.dispatchEvent(new Event("click")); f.next.focus(); lease.abort();
  assert.equal(f.document.activeElement, f.current);
  const target = f.current.getBoundingClientRect(), box = f.list.getBoundingClientRect();
  assert(target.left >= box.left && target.right <= box.right, "Retired action focus is visible in the fallback scroller");
});

test("rollback while the desktop registry is hidden recovers visible menu focus", t => {
  const f = fixture(t); const lease = f.bind(); f.next.focus(); f.state.width = 0; lease.abort();
  assert.equal(f.document.activeElement, f.drawer); assert(f.drawer.getClientRects().length > 0);
  assert.equal(f.previous.hidden, true); assert.equal(f.next.hidden, true); assert.equal(f.observers[0].disconnected, true);
});
test("queued resize callbacks cannot resurrect retired controls", t => {
  const f = fixture(t); const lease = f.bind(); lease.abort(); f.state.width = 300;
  f.observers[0].callback();
  assert.equal(f.previous.hidden, true); assert.equal(f.next.hidden, true);
  assert.equal(f.previous.getAttribute("aria-disabled"), null); assert.equal(f.next.getAttribute("aria-disabled"), null);
});

test("CSS hiding that blurs a scroll action before resize still recovers menu focus", async t => {
  const f = fixture(t); f.bind(); f.next.focus(); f.state.width = 0;
  f.document.activeElement = f.document.body; f.next.dispatchEvent(new Event("blur"));
  await Promise.resolve(); f.window.dispatchEvent(new Event("resize"));
  assert.equal(f.document.activeElement, f.drawer); assert.equal(f.next.hidden, true);
});
test("an ordinary visible blur is not stolen by a later phone transition", async t => {
  const f = fixture(t); f.bind(); f.next.focus();
  f.document.activeElement = f.document.body; f.next.dispatchEvent(new Event("blur"));
  await Promise.resolve(); f.state.width = 0; f.window.dispatchEvent(new Event("resize"));
  assert.equal(f.document.activeElement, f.document.body);
});

test("intrinsic destination-label growth updates overflow without a window resize", t => {
  const f = fixture(t, { content: 300 }); f.bind();
  assert.equal(f.next.hidden, true);
  f.state.content = 900;
  for (const observer of f.observers) {
    if (observer.observed.includes(f.links[1])) observer.callback();
  }
  assert.equal(f.previous.hidden, false); assert.equal(f.next.hidden, false);
  assert.equal(f.next.getAttribute("aria-disabled"), "false");
  f.next.dispatchEvent(new Event("click")); assert(f.state.offset > 0);
});
