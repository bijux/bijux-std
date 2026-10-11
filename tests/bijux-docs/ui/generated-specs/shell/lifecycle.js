"use strict";

function observeLifecycle() {
  const originalAdd = EventTarget.prototype.addEventListener;
  const originalRemove = EventTarget.prototype.removeEventListener;
  const registrations = [];
  const viewportEvents = new Set(["resize", "orientationchange", "pageshow", "pagehide"]);
  EventTarget.prototype.addEventListener = function (type, listener, options) {
    const capture = typeof options === "boolean" ? options : Boolean(options?.capture);
    const viewport = !options?.once && viewportEvents.has(type) && (this === window || this === window.visualViewport);
    const component = this instanceof Element && this.matches("[data-bijux-theme-toggle], input[name='__palette'], [data-bijux-header-control], [data-bijux-control-close]");
    if ((options?.signal || viewport || component) && !registrations.some(row => !row.removed && !row.signal?.aborted &&
        row.target === this && row.type === type && row.listener === listener && row.capture === capture))
      registrations.push({ target: this, type, listener, capture, signal: options?.signal, removed: false });
    return originalAdd.call(this, type, listener, options);
  };
  EventTarget.prototype.removeEventListener = function (type, listener, options) {
    const capture = typeof options === "boolean" ? options : Boolean(options?.capture);
    for (const row of registrations)
      if (row.target === this && row.type === type && row.listener === listener && row.capture === capture) row.removed = true;
    return originalRemove.call(this, type, listener, options);
  };
  window.bijuxLifecycleObservation = () => {
    const counts = {};
    for (const row of registrations) {
      if (row.removed || row.signal?.aborted || row.target.isConnected === false) continue;
      const node = row.target;
      const identity = node instanceof Element ? `${node.tagName}:${node.id}:${node.getAttribute("data-bijux-header-control") || ""}` : node.constructor.name;
      const key = `${identity}/${row.type}/${row.capture}`;
      counts[key] = (counts[key] || 0) + 1;
    }
    return { counts, aborted: registrations.filter(row => row.signal?.aborted).length,
      active: Object.values(counts).reduce((sum, count) => sum + count, 0) };
  };
}

async function shellState(page) {
  return page.evaluate(() => {
    const visible = node => Boolean(node.getClientRects().length) && getComputedStyle(node).visibility !== "hidden";
    const controls = [...document.querySelectorAll("[data-bijux-header-control]")];
    return { profile: document.documentElement.dataset.bijuxViewport,
      controls: controls.map(node => ({ kind: node.dataset.bijuxHeaderControl, visible: visible(node),
        expanded: node.getAttribute("aria-expanded"), popup: node.getAttribute("aria-haspopup"),
        target: node.getAttribute("aria-controls"), targetCount: node.getAttribute("aria-controls") ?
          [...document.querySelectorAll("[id]")].filter(target => target.id === node.getAttribute("aria-controls")).length : 0 })),
      checkboxCounts: ["__drawer", "__search"].map(id => document.querySelectorAll(`[id='${id}']`).length),
      checked: ["__drawer", "__search"].map(id => document.getElementById(id).checked),
      navigationCount: document.querySelectorAll("#bijux-navigation").length,
      treeCount: document.querySelectorAll("#bijux-navigation .bijux-tree").length,
      links: [...document.querySelectorAll("#bijux-navigation a[href]")].map(node => node.href),
      openDetails: [...document.querySelectorAll("#bijux-navigation details")].map(node => node.open),
      modal: document.querySelector(".md-sidebar--primary").getAttribute("role"),
      inert: [".md-content", ".md-sidebar--primary", "header"].map(selector => document.querySelector(selector).inert),
      scheme: document.body.getAttribute("data-md-color-scheme"),
      themeMode: document.querySelector("[data-bijux-theme-toggle]").dataset.bijuxThemeMode,
      listeners: window.bijuxLifecycleObservation().counts };
  });
}
module.exports = { observeLifecycle, shellState };
