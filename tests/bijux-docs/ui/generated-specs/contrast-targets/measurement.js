"use strict";
const { rgba, composite, contrast, textThreshold } = require("./color.cjs");
const { PNG } = require("playwright-core/lib/utilsBundle");

async function tabTo(page, locator, browserName, maximum = 80) {
  const key = browserName === "webkit" ? "Alt+Tab" : "Tab";
  for (let index = 0; index < maximum; index++) {
    if (await locator.evaluate(node => node === document.activeElement)) return;
    await page.keyboard.press(key);
  }
  throw new Error("Ordinary keyboard traversal did not reach the named control");
}

function readStates(input, icon = false) {
  const samples = Array.isArray(input) ? input : [{ node: input, icon }];
  return samples.map(({ node, icon: isIcon }) => {
    const style = getComputedStyle(node);
    const rectangle = node.getBoundingClientRect();
    let opacity = 1;
    const opacityGroups = [];
    for (let parent = node; parent; parent = parent.parentElement) {
      const computed = getComputedStyle(parent);
      if (Number(computed.opacity) !== 1) {
        opacityGroups.push({ tag: parent.tagName, opacity: Number(computed.opacity),
          background: computed.backgroundColor, image: computed.backgroundImage });
      }
      opacity *= Number(computed.opacity);
    }
    const points = [];
    if (isIcon) {
      points.push({ x: rectangle.x + rectangle.width / 2, y: rectangle.y + rectangle.height / 2 });
    } else {
      const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        if (!walker.currentNode.textContent.trim()) continue;
        const range = document.createRange();
        range.selectNodeContents(walker.currentNode);
        for (const rect of range.getClientRects()) {
          for (const fraction of [0.1, 0.5, 0.9]) {
            const x = rect.x + rect.width * fraction;
            const y = rect.y + rect.height / 2;
            const hit = document.elementFromPoint(x, y);
            if (x >= 0 && x < innerWidth && y >= 0 && y < innerHeight &&
                hit && (hit === node || node.contains(hit) || hit.contains(node))) points.push({ x, y });
          }
        }
      }
    }
    const center = { x: rectangle.x + rectangle.width / 2, y: rectangle.y + rectangle.height / 2 };
    const hit = document.elementFromPoint(center.x, center.y);
    return { text: node.textContent.trim(), color: style.color,
      fill: isIcon ? style.fill : style.webkitTextFillColor,
      size: parseFloat(style.fontSize), weight: Number(style.fontWeight), opacity, opacityGroups,
      background: style.backgroundColor, image: style.backgroundImage,
      rectangle: { x: rectangle.x, y: rectangle.y, width: rectangle.width, height: rectangle.height },
      centerOwned: hit === node || node.contains(hit), focused: node === document.activeElement,
      focusVisible: node.matches(":focus-visible"), outline: style.outlineColor,
      outlineWidth: parseFloat(style.outlineWidth), outlineOffset: parseFloat(style.outlineOffset), outlineStyle: style.outlineStyle, points };
  });
}

async function state(locator, icon = false) {
  await settle(locator);
  return (await locator.evaluate(readStates, icon))[0];
}

async function screenshotPixels(page, points) {
  const screenshot = await page.screenshot({ animations: "disabled", scale: "css" });
  return pixels(screenshot, points);
}

function pixels(screenshot, points) {
  // Playwright's pinned PNG reader avoids transferring and decoding the same
  // viewport again inside the page and recording it twice in each trace.
  const image = PNG.sync.read(screenshot);
  return points.map(point => {
    const x = Math.floor(point.x), y = Math.floor(point.y);
    if (x < 0 || y < 0 || x >= image.width || y >= image.height) {
      throw new Error("Contrast sample is outside the actual viewport image");
    }
    return [...image.data.subarray((y * image.width + x) * 4, (y * image.width + x) * 4 + 4)];
  });
}

function runningAnimations(input) {
  const nodes = Array.isArray(input) ? input : [input];
  const animations = new Set();
  for (const node of nodes) {
    // Ancestor transforms and opacity affect sampled paint coordinates.
    for (const animation of node.getAnimations({ subtree: true })) animations.add(animation);
    for (let ancestor = node.parentElement; ancestor; ancestor = ancestor.parentElement) {
      for (const animation of ancestor.getAnimations()) animations.add(animation);
    }
  }
  return [...animations].filter(animation => animation.playState === "running" &&
    Number.isFinite(animation.effect?.getComputedTiming().endTime)).length;
}

async function settleObservation(observe) {
  // Synchronous browser observations also work in Firefox's no-script contexts.
  for (let attempt = 0; attempt < 100; attempt++) {
    if (!await observe()) return;
    await new Promise(resolve => setTimeout(resolve, 20));
  }
  throw new Error("Relevant finite control animation did not settle within two seconds");
}

async function settle(locator) {
  await settleObservation(() => locator.evaluate(runningAnimations));
}

async function textOrIcons(page, nodes, { icon = false } = {}) {
  if (!nodes.length) throw new Error("A contrast measurement needs actual nodes");
  // A single cohort keeps its viewport and control state throughout the paint.
  await settleObservation(() => page.evaluate(runningAnimations, nodes));
  const observations = await page.evaluate(readStates, nodes.map(node => ({ node, icon })));
  for (const observed of observations) {
    if (!observed.points.length) throw new Error("No visible, hit-tested text/background sample");
    for (const group of observed.opacityGroups) {
      if (rgba(group.background)[3] !== 0 || group.image !== "none") {
        throw new Error("Opacity group with its own backdrop needs a separate paint model");
      }
    }
  }
  const token = `bijux-contrast-${Date.now()}`;
  await page.evaluate(({ samples, key }) => {
    for (const node of samples) node.setAttribute("data-bijux-contrast-sample", key);
  }, { samples: nodes, key: token });
  let style;
  let backgrounds;
  try {
    // Remove only glyph paint; retain every node's geometry and backdrop.
    style = await page.addStyleTag({ content: icon ?
      `[data-bijux-contrast-sample="${token}"] { visibility: hidden !important; }` :
      `[data-bijux-contrast-sample="${token}"], [data-bijux-contrast-sample="${token}"] * { -webkit-text-fill-color: transparent !important; text-shadow: none !important; text-decoration-color: transparent !important; }` });
    backgrounds = await screenshotPixels(page, observations.flatMap(observed => observed.points));
  } finally {
    if (!page.isClosed()) {
      await page.evaluate(({ samples, sheet }) => {
        sheet?.remove();
        for (const node of samples) node.removeAttribute("data-bijux-contrast-sample");
      }, { samples: nodes, sheet: style });
      await style?.dispose();
    }
  }
  let offset = 0;
  return observations.map(observed => {
    const backdrop = backgrounds.slice(offset, offset += observed.points.length);
    const foreground = rgba(observed.fill === "currentcolor" ? observed.color : observed.fill);
    const ratios = backdrop.map(background => contrast(composite(foreground, background, observed.opacity), background));
    return { ...observed, backgrounds: backdrop, ratios, minimum: Math.min(...ratios),
      threshold: icon ? 3 : textThreshold(observed.size, observed.weight),
      method: "computed glyph color composited against diagnostic screenshot background; visible samples only" };
  });
}

async function textOrIcon(page, locator, options = {}) {
  const node = await locator.elementHandle();
  if (!node) throw new Error("Contrast target is missing");
  try { return (await textOrIcons(page, [node], options))[0]; }
  finally { await node.dispose(); }
}

async function focus(page, locator) {
  await settle(locator);
  const observed = await state(locator);
  const backdrop = await locator.evaluate(node => {
    const header = document.querySelector("header[data-bijux-drawer-target]");
    const style = getComputedStyle(header);
    const box = header.getBoundingClientRect();
    const target = node.getBoundingClientRect();
    const targetStyle = getComputedStyle(node);
    const extent = Math.max(0, parseFloat(targetStyle.outlineOffset) + parseFloat(targetStyle.outlineWidth));
    return { color: style.backgroundColor, image: style.backgroundImage,
      opacity: Number(style.opacity), contained: target.x - extent >= box.x &&
        target.right + extent <= box.right && target.y - extent >= box.y && target.bottom + extent <= box.bottom };
  });
  if (backdrop.image !== "none" || backdrop.opacity !== 1 || rgba(backdrop.color)[3] !== 1 || !backdrop.contained) {
    throw new Error("Focus does not have the qualified opaque flat header backdrop");
  }
  return { ...observed, backdrop, ratio: contrast(composite(rgba(observed.outline), rgba(backdrop.color), observed.opacity), rgba(backdrop.color)),
    method: "computed outline with effective ancestor opacity versus verified flat opaque header; complete ring inside that surface" };
}
module.exports = { tabTo, state, pixels, screenshotPixels, textOrIcon, textOrIcons, focus, settle };
