"use strict";
const { rgba, composite, contrast, textThreshold } = require("./color.cjs");

async function tabTo(page, locator, browserName, maximum = 80) {
  const key = browserName === "webkit" ? "Alt+Tab" : "Tab";
  for (let index = 0; index < maximum; index++) {
    if (await locator.evaluate(node => node === document.activeElement)) return;
    await page.keyboard.press(key);
  }
  throw new Error("Ordinary keyboard traversal did not reach the named control");
}

async function state(locator, icon = false) {
  await settle(locator);
  return locator.evaluate((node, isIcon) => {
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
  }, icon);
}

async function screenshotPixels(page, points) {
  const screenshot = await page.screenshot({ animations: "disabled", scale: "css" });
  return page.evaluate(async ({ data, samples }) => {
    const image = new Image();
    image.src = `data:image/png;base64,${data}`;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = image.width;
    canvas.height = image.height;
    const context = canvas.getContext("2d");
    context.drawImage(image, 0, 0);
    return samples.map(point => Array.from(context.getImageData(
      Math.floor(point.x), Math.floor(point.y), 1, 1).data));
  }, { data: screenshot.toString("base64"), samples: points });
}

async function settle(locator) {
  // Synchronous browser observations also work in Firefox's no-script contexts.
  for (let attempt = 0; attempt < 100; attempt++) {
    const running = await locator.evaluate(node => {
      // Ancestor transforms and opacity affect the glyph's sampled paint coordinates.
      const animations = new Set(node.getAnimations({ subtree: true }));
      for (let ancestor = node.parentElement; ancestor; ancestor = ancestor.parentElement) {
        for (const animation of ancestor.getAnimations()) animations.add(animation);
      }
      return [...animations].filter(animation => animation.playState === "running" &&
        Number.isFinite(animation.effect?.getComputedTiming().endTime)).length;
    });
    if (!running) return;
    await new Promise(resolve => setTimeout(resolve, 20));
  }
  throw new Error("Relevant finite control animation did not settle within two seconds");
}

async function textOrIcon(page, locator, { icon = false } = {}) {
  await settle(locator);
  const observed = await state(locator, icon);
  if (!observed.points.length) throw new Error("No visible, hit-tested text/background sample");
  for (const group of observed.opacityGroups) {
    if (rgba(group.background)[3] !== 0 || group.image !== "none") {
      throw new Error("Opacity group with its own backdrop needs a separate paint model");
    }
  }
  // This diagnostic temporarily removes glyph paint only, after recording geometry/state.
  // It never changes control state or supplies input to the acceptance journey.
  const token = `bijux-contrast-${Date.now()}`;
  await locator.evaluate((node, key) => node.setAttribute("data-bijux-contrast-sample", key), token);
  const style = await page.addStyleTag({ content: icon ?
    `[data-bijux-contrast-sample="${token}"] { visibility: hidden !important; }` :
    `[data-bijux-contrast-sample="${token}"], [data-bijux-contrast-sample="${token}"] * { -webkit-text-fill-color: transparent !important; text-shadow: none !important; text-decoration-color: transparent !important; }` });
  let backgrounds;
  try { backgrounds = await screenshotPixels(page, observed.points); }
  finally {
    await style.evaluate(node => node.remove());
    await locator.evaluate(node => node.removeAttribute("data-bijux-contrast-sample"));
  }
  const foreground = rgba(observed.fill === "currentcolor" ? observed.color : observed.fill);
  const ratios = backgrounds.map(background => contrast(composite(foreground, background, observed.opacity), background));
  return { ...observed, backgrounds, ratios, minimum: Math.min(...ratios),
    threshold: icon ? 3 : textThreshold(observed.size, observed.weight),
    method: "computed glyph color composited against diagnostic screenshot background; visible samples only" };
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
module.exports = { tabTo, state, screenshotPixels, textOrIcon, focus, settle };
