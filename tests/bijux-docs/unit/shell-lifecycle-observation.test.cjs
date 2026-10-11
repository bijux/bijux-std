"use strict";
const assert = require("node:assert/strict");
const test = require("node:test");
const vm = require("node:vm");
const { observeLifecycle } = require("../ui/generated-specs/shell/lifecycle");

function observedRuntime() {
  class Target extends EventTarget {}
  class Element extends Target {
    constructor() { super(); this.tagName = "BUTTON"; this.id = "drawer"; this.isConnected = true; }
    getAttribute() { return "drawer-toggle"; }
    matches() { return true; }
  }
  const window = {};
  vm.runInNewContext(`(${observeLifecycle.toString()})()`, { EventTarget: Target, Element, window });
  return { element: new Element(), window };
}

test("observed listeners forward native dispatch and count duplicate identity once", () => {
  const { element, window } = observedRuntime();
  const lifetime = new AbortController();
  let calls = 0;
  const action = () => calls++;
  element.addEventListener("click", action, { signal: lifetime.signal });
  element.addEventListener("click", action, { signal: lifetime.signal });
  element.dispatchEvent(new Event("click"));
  assert.equal(calls, 1);
  assert.equal(window.bijuxLifecycleObservation().active, 1);
  lifetime.abort();
  element.dispatchEvent(new Event("click"));
  assert.equal(calls, 1);
  assert.equal(window.bijuxLifecycleObservation().active, 0);
  assert.ok(window.bijuxLifecycleObservation().aborted > 0);
});

test("replacement lifetimes cannot disguise multiple active registrations", () => {
  const { element, window } = observedRuntime();
  const previous = new AbortController(), replacement = new AbortController();
  element.addEventListener("click", () => {}, { signal: previous.signal });
  element.addEventListener("click", () => {}, { signal: replacement.signal });
  assert.equal(window.bijuxLifecycleObservation().active, 2);
  previous.abort();
  assert.equal(window.bijuxLifecycleObservation().active, 1);
  replacement.abort();
  assert.equal(window.bijuxLifecycleObservation().active, 0);
});

test("explicit removal and detached controls do not retain active census entries", () => {
  const { element, window } = observedRuntime();
  const lifetime = new AbortController(), action = () => {};
  element.addEventListener("click", action, { signal: lifetime.signal, capture: true });
  element.removeEventListener("click", action, { capture: false });
  assert.equal(window.bijuxLifecycleObservation().active, 1);
  element.removeEventListener("click", action, { capture: true });
  assert.equal(window.bijuxLifecycleObservation().active, 0);
  element.addEventListener("click", action, { signal: lifetime.signal });
  element.isConnected = false;
  assert.equal(window.bijuxLifecycleObservation().active, 0);
});


test("ordinary palette bindings expose duplicate callbacks without abort signals", () => {
  const { element, window } = observedRuntime();
  const action = () => {};
  element.addEventListener("change", action);
  element.addEventListener("change", action);
  assert.equal(window.bijuxLifecycleObservation().active, 1);
  element.addEventListener("change", () => {});
  assert.equal(window.bijuxLifecycleObservation().active, 2);
  element.removeEventListener("change", action);
  assert.equal(window.bijuxLifecycleObservation().active, 1);
});
