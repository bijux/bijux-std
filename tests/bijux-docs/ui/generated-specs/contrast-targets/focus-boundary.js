"use strict";
const { contrast } = require("./color.cjs");
const { settle } = require("./measurement");

function geometry(rectangle, width, offset, clips) {
  const values = [rectangle.x, rectangle.y, rectangle.width, rectangle.height, width, offset];
  if (!values.every(Number.isFinite) || rectangle.width <= 0 || rectangle.height <= 0 || width <= 0) {
    throw new Error("Focus boundary needs finite, nonempty geometry and outline width");
  }
  if (!Array.isArray(clips) || !clips.length || clips.some(clip =>
    ![clip.left, clip.right, clip.top, clip.bottom].every(Number.isFinite) ||
    clip.right <= clip.left || clip.bottom <= clip.top)) {
    throw new Error("Focus boundary needs nonempty finite clipping surfaces");
  }
  const right = rectangle.x + rectangle.width, bottom = rectangle.y + rectangle.height;
  const extent = offset + width;
  const outer = { x: rectangle.x - extent, y: rectangle.y - extent,
    right: right + extent, bottom: bottom + extent };
  const distance = offset + width / 2;
  const ring = [
    { x: rectangle.x - distance, y: rectangle.y + rectangle.height / 2 },
    { x: right + distance, y: rectangle.y + rectangle.height / 2 },
    { x: rectangle.x + rectangle.width / 2, y: rectangle.y - distance },
    { x: rectangle.x + rectangle.width / 2, y: bottom + distance },
  ];
  // Samples just inside the indicator avoid a header-only or transparent-paint model.
  const inset = Math.max(4, -offset + 2);
  if (rectangle.width <= inset * 2 || rectangle.height <= inset * 2) {
    throw new Error("Control cannot contain distinct outline and adjacent paint samples");
  }
  const adjacent = [
    { x: rectangle.x + inset, y: rectangle.y + rectangle.height / 2 },
    { x: right - inset, y: rectangle.y + rectangle.height / 2 },
    { x: rectangle.x + rectangle.width / 2, y: rectangle.y + inset },
    { x: rectangle.x + rectangle.width / 2, y: bottom - inset },
  ];
  const clippedBy = clips.filter(clip =>
    (clip.x && (outer.x < clip.left || outer.right > clip.right)) ||
    (clip.y && (outer.y < clip.top || outer.bottom > clip.bottom)));
  return { outer, ring, adjacent, clippedBy, contained: clippedBy.length === 0 };
}

function paint(samples) {
  if (!Array.isArray(samples) || samples.length !== 8 || samples.some(pixel =>
    !Array.isArray(pixel) || pixel.length !== 4 || pixel[3] !== 255 ||
    !pixel.every(channel => Number.isFinite(channel) && channel >= 0 && channel <= 255))) {
    throw new Error("Focus paint requires four opaque outline and adjacent pixel pairs");
  }
  const ratios = samples.slice(0, 4).map((pixel, index) => contrast(pixel, samples[index + 4]));
  return { outlinePixels: samples.slice(0, 4), adjacentPixels: samples.slice(4),
    ratios, minimum: Math.min(...ratios) };
}

async function tabTo(page, control, browserName) {
  for (let attempt = 0; attempt < 80; attempt++) {
    if (await control.evaluate(node => node === document.activeElement)) return;
    const reverse = await control.evaluate(node => Boolean(
      document.activeElement.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_PRECEDING));
    await page.keyboard.press(`${browserName === "webkit" ? "Alt+" : ""}${reverse ? "Shift+" : ""}Tab`);
  }
  throw new Error("Ordinary directional keyboard traversal did not reach the focus control");
}

async function settleGeometry(control, { now = () => Date.now(),
  pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds)) } = {}) {
  const started = now(), observations = [];
  let previous = null, unchanged = 0;
  for (let attempt = 0; attempt < 100; attempt++) {
    const sample = await control.evaluate(async node => {
      // A compositor can repeat cached boxes before exposing a finite transition.
      // Observe a rendering frame without completing or modifying that transition.
      const frame = await new Promise(resolve => {
        const timer = setTimeout(() => { cancelAnimationFrame(request); resolve(null); }, 100);
        const request = requestAnimationFrame(time => { clearTimeout(timer); resolve(time); });
      });
      const rectangle = element => {
        const box = element.getBoundingClientRect();
        return { x: box.x, y: box.y, width: box.width, height: box.height };
      };
      // Layout reads precede animation enumeration: opening styles can create a transition.
      const target = rectangle(node), ancestors = [];
      const elements = [node];
      for (let parent = node.parentElement; parent; parent = parent.parentElement) {
        const style = getComputedStyle(parent);
        ancestors.push({ name: `${parent.tagName}.${parent.className}`, rectangle: rectangle(parent),
          transform: style.transform, opacity: style.opacity,
          clientLeft: parent.clientLeft, clientTop: parent.clientTop,
          clientWidth: parent.clientWidth, clientHeight: parent.clientHeight });
        elements.push(parent);
      }
      const animations = new Set(node.getAnimations({ subtree: true }));
      for (const element of elements.slice(1)) {
        for (const animation of element.getAnimations()) animations.add(animation);
      }
      const running = [...animations].filter(animation => animation.playState === "running" &&
        Number.isFinite(animation.effect?.getComputedTiming().endTime)).length;
      const sidebar = node.closest(".md-sidebar--primary");
      const drawer = document.getElementById("__drawer");
      const ownedOpenDrawer = Boolean(sidebar && drawer?.checked &&
        document.body.dataset.bijuxDrawerReady === "true");
      const openDrawer = ownedOpenDrawer ? {
        transform: getComputedStyle(sidebar).transform,
        identity: new DOMMatrixReadOnly(getComputedStyle(sidebar).transform).isIdentity,
      } : null;
      // The shared open-drawer rule is translateX(0). Stable offscreen boxes are
      // not its endpoint, even when the engine reports no running animations.
      return { target, ancestors, running, frame, openDrawer };
    });
    const signature = JSON.stringify({ target: sample.target, ancestors: sample.ancestors });
    const admitted = sample.running === 0 && sample.frame !== null &&
      (sample.openDrawer === null || sample.openDrawer.identity === true);
    unchanged = admitted && signature === previous ? unchanged + 1 : 0;
    observations.push({ elapsedMs: now() - started, ...sample });
    if (unchanged >= 2) return { elapsedMs: now() - started, observations };
    previous = admitted ? signature : null;
    if (now() - started >= 2000) break;
    await pause(20);
  }
  throw new Error(`Focused control geometry did not settle within two seconds: ${JSON.stringify(observations)}`);
}

async function observe(page, control) {
  await settle(control);
  const settlement = await settleGeometry(control);
  const observed = await control.evaluate(node => {
    const rectangle = node.getBoundingClientRect(), style = getComputedStyle(node);
    const clips = [{ name: "viewport", x: true, y: true,
      left: 0, right: innerWidth, top: 0, bottom: innerHeight }];
    for (let parent = node.parentElement; parent; parent = parent.parentElement) {
      const computed = getComputedStyle(parent), box = parent.getBoundingClientRect();
      const x = computed.overflowX !== "visible", y = computed.overflowY !== "visible";
      if (x || y) clips.push({ name: `${parent.tagName}.${parent.className}`, x, y,
        left: box.x + parent.clientLeft, right: box.x + parent.clientLeft + parent.clientWidth,
        top: box.y + parent.clientTop, bottom: box.y + parent.clientTop + parent.clientHeight });
    }
    return { rectangle: { x: rectangle.x, y: rectangle.y, width: rectangle.width, height: rectangle.height },
      width: parseFloat(style.outlineWidth), offset: parseFloat(style.outlineOffset),
      outlineStyle: style.outlineStyle, outlineColor: style.outlineColor, clips,
      focused: document.activeElement === node, focusVisible: node.matches(":focus-visible"),
      forcedActive: matchMedia("(forced-colors: active)").matches };
  });
  const boundary = geometry(observed.rectangle, observed.width, observed.offset, observed.clips);
  if (!boundary.contained) return { ...observed, settlement, boundary, paint: null };
  const screenshot = await page.screenshot({ scale: "css" });
  const samples = await page.evaluate(async ({ data, points }) => {
    const image = new Image(); image.src = `data:image/png;base64,${data}`; await image.decode();
    const canvas = document.createElement("canvas"); canvas.width = image.width; canvas.height = image.height;
    const context = canvas.getContext("2d"); context.drawImage(image, 0, 0);
    return points.map(point => {
      if (point.x < 0 || point.y < 0 || point.x >= canvas.width || point.y >= canvas.height) return null;
      return Array.from(context.getImageData(Math.floor(point.x), Math.floor(point.y), 1, 1).data);
    });
  }, { data: screenshot.toString("base64"), points: [...boundary.ring, ...boundary.adjacent] });
  return { ...observed, settlement, boundary, paint: paint(samples),
    method: "Ordinary keyboard focus; complete outline versus actual ancestor clips and unmodified adjacent screenshot paint" };
}
module.exports = { geometry, paint, tabTo, settleGeometry, observe };
