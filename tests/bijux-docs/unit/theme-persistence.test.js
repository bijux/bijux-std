const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const SCRIPT = fs.readFileSync(
  path.join(__dirname, "../../../shared/bijux-docs/scripts/theme-persistence.js"),
  "utf8"
);
const THEME_KEY = "bijux:theme";

const PALETTES = {
  auto: { media: "(prefers-color-scheme)", scheme: "default" },
  light: { media: "(prefers-color-scheme: light)", scheme: "default" },
  dark: { media: "(prefers-color-scheme: dark)", scheme: "slate" },
};

function element(attributes = {}) {
  const values = new Map(Object.entries(attributes));
  const listeners = new Map();
  return {
    dataset: {},
    hidden: false,
    getAttribute(name) {
      return values.has(name) ? values.get(name) : null;
    },
    setAttribute(name, value) {
      values.set(name, String(value));
    },
    removeAttribute(name) {
      values.delete(name);
    },
    addEventListener(name, listener) {
      listeners.set(name, listener);
    },
    dispatchEvent(event) {
      listeners.get(event.type)?.(event);
      return true;
    },
    fire(name) {
      const listener = listeners.get(name);
      assert.ok(listener, `missing ${name} listener`);
      listener();
    },
  };
}

function page({ order = ["auto", "light", "dark"], savedChoice = null, checked = "auto" } = {}) {
  const options = order.map((mode) => {
    const palette = PALETTES[mode];
    const option = element({
      "data-md-color-media": palette.media,
      "data-md-color-scheme": palette.scheme,
      "data-md-color-primary": "teal",
      "data-md-color-accent": "cyan",
    });
    option.mode = mode;
    option._checked = mode === checked;
    Object.defineProperty(option, "checked", {
      get() {
        return this._checked;
      },
      set(value) {
        if (value) {
          for (const other of options) other._checked = false;
        }
        this._checked = Boolean(value);
      },
    });
    return option;
  });
  let currentOptions = options;
  const button = element();
  const body = element({ "data-md-color-scheme": PALETTES[checked].scheme });
  const stored = new Map(savedChoice === null ? [] : [[THEME_KEY, savedChoice]]);
  const paletteWrites = [];
  const windowListeners = new Map();
  const document = {
    body,
    querySelector(selector) {
      return selector === "[data-bijux-theme-key]"
        ? element({ "data-bijux-theme-key": THEME_KEY })
        : null;
    },
    querySelectorAll(selector) {
      if (selector === "input[name='__palette'][data-md-color-scheme]") return currentOptions;
      if (selector === "[data-bijux-theme-toggle]") return [button];
      return [];
    },
  };
  const window = {
    scrollX: 0,
    scrollY: 0,
    scrollTo() {},
    __md_set(key, value) {
      paletteWrites.push({ key, value: JSON.parse(JSON.stringify(value)) });
    },
    addEventListener(name, listener) {
      windowListeners.set(name, listener);
    },
    dispatchEvent() {},
  };
  const context = {
    document,
    document$: { subscribe(callback) { callback(); } },
    window,
    localStorage: {
      getItem(key) { return stored.get(key) ?? null; },
      setItem(key, value) { stored.set(key, value); },
    },
    Event,
    CustomEvent: class CustomEvent {
      constructor(name, options) {
        this.type = name;
        this.detail = options.detail;
      }
    },
    requestAnimationFrame(callback) { callback(); },
    setTimeout(callback) { callback(); },
  };
  vm.runInNewContext(SCRIPT, context, { filename: "theme-persistence.js" });
  return {
    options,
    button,
    body,
    stored,
    paletteWrites,
    replaceOptions(nextOptions) { currentOptions = nextOptions; },
    fireStorage(choice) {
      windowListeners.get("storage")({ key: THEME_KEY, newValue: JSON.stringify(choice) });
    },
  };
}

// This is the installed Material bundle's restore expression, including the
// indexed getAttribute access that failed when __palette lacked an index.
function nativeReader(palette, options) {
  const index = Math.max(0, Math.min(palette.index, options.length - 1));
  return options[index].getAttribute("data-md-color-scheme");
}

function lastPalette(pageState) {
  const write = pageState.paletteWrites.at(-1);
  assert.equal(write?.key, "__palette");
  assert.ok(Number.isInteger(write.value.index));
  assert.equal(write.value.color.primary, "teal");
  assert.equal(write.value.color.accent, "cyan");
  return write.value;
}

test("saved auto, light and dark choices restore through Material's native index", () => {
  for (const [mode, expectedIndex] of [["auto", 0], ["light", 1], ["dark", 2]]) {
    const state = page({
      savedChoice: JSON.stringify({ version: 2, mode, signature: {
        media: PALETTES[mode].media, scheme: PALETTES[mode].scheme,
        primary: "teal", accent: "cyan",
      } }),
    });
    const palette = lastPalette(state);
    assert.equal(palette.index, expectedIndex);
    assert.equal(state.options[expectedIndex].checked, true);
    assert.equal(nativeReader(palette, state.options), PALETTES[mode].scheme);
  }
});

test("signature restore recalculates the index after palette options reorder", () => {
  const state = page({
    order: ["dark", "auto", "light"],
    savedChoice: JSON.stringify({ version: 2, mode: "light", signature: {
      media: PALETTES.light.media, scheme: "default", primary: "teal", accent: "cyan",
    } }),
  });
  const palette = lastPalette(state);
  assert.equal(palette.index, 2);
  assert.equal(state.options[2].checked, true);
  assert.equal(nativeReader(palette, state.options), "default");
});

test("toggle cycle and cross-tab choice keep Material's next-page selection valid", () => {
  const state = page();
  for (const [mode, index] of [["light", 1], ["dark", 2], ["auto", 0]]) {
    state.button.fire("click");
    const palette = lastPalette(state);
    assert.equal(palette.index, index);
    assert.equal(nativeReader(palette, state.options), PALETTES[mode].scheme);
    assert.equal(JSON.parse(state.stored.get(THEME_KEY)).mode, mode);
  }
  state.fireStorage({ version: 2, mode: "dark", signature: {
    media: PALETTES.dark.media, scheme: "slate", primary: "teal", accent: "cyan",
  } });
  assert.equal(lastPalette(state).index, 2);
  assert.equal(nativeReader(lastPalette(state), state.options), "slate");
  assert.equal(state.options[2].checked, true);
});

test("cross-tab falls back to a present mode when the saved signature is unmatched", () => {
  const state = page({ order: ["dark", "light", "auto"] });
  state.fireStorage({ version: 2, mode: "dark", signature: {
    media: "(obsolete media)", scheme: "obsolete", primary: "x", accent: "y",
  } });
  assert.equal(lastPalette(state).index, 0);
  assert.equal(nativeReader(lastPalette(state), state.options), "slate");
});

test("a detached option cannot write an invalid palette or change the active theme", () => {
  const state = page();
  const detached = state.options[2];
  state.replaceOptions(state.options.slice(0, 2));
  const originalGlobal = state.stored.get(THEME_KEY);
  detached.checked = true;
  detached.fire("change");
  assert.equal(state.paletteWrites.length, 0);
  assert.equal(state.stored.get(THEME_KEY), originalGlobal);
  assert.equal(state.body.getAttribute("data-md-color-scheme"), "default");
});
