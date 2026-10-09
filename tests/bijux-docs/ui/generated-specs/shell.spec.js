const fs = require("node:fs");
const path = require("node:path");
const registry = JSON.parse(fs.readFileSync(path.resolve(__dirname, "../../../../shared/bijux-docs/config/hub-links.json"), "utf8"));
const { test, expect } = require("./helpers/document");
const { tabTo, settle, focus: measureFocus } = require("./contrast-targets/measurement");
const control = (page, kind) => page.locator(`[data-bijux-header-control='${kind}-toggle']`);
const drawer = (page) => page.locator(".md-sidebar--primary");
const exposedLinks = (page) => drawer(page).locator("a:visible");
async function ready(page, route = "/") {
  await page.goto(route);
  await expect(page.locator("main")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-bijux-viewport", /phone|normal|desktop|wide/);
}
async function phone(page, route = "/") {
  await page.setViewportSize({ width: 390, height: 844 });
  await ready(page, route);
}
async function openDrawer(page) {
  await control(page, "drawer").click();
  await expect(page.locator("#__drawer")).toBeChecked();
  await expect(exposedLinks(page).first()).toBeInViewport();
}
let registryTouchSequence = 0;
function assertRegistryTarget(target) {
  expect(target.height).toBeGreaterThanOrEqual(44);
  expect(target.width).toBeGreaterThanOrEqual(44);
  expect(target.owned).toBe(true);
  expect(target.fit).toBe(true);
  expect(target.labelFit).toBe(true);
}
async function registryDestination(page, link, expected, input = "pointer") {
  await expect(link).toHaveCount(1);
  await expect(link).toHaveAccessibleName(expected.label);
  expect(await link.evaluate(node => node.href)).toBe(expected.url);
  if (input === "keyboard") {
    await tabTo(page, link, page.context().browser().browserType().name(), 160);
    await expect(link).toBeFocused();
    await settle(link);
  } else if (input !== "touch") {
    await link.hover();
  }
  const target = input === "touch" ? null : await link.evaluate(node => {
    const rect = node.getBoundingClientRect();
    const hit = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
    return { width: rect.width, height: rect.height, owned: hit === node || node.contains(hit),
      fit: rect.left >= 0 && rect.right <= innerWidth + 1 && rect.top >= 0 && rect.bottom <= innerHeight + 1,
      labelFit: node.scrollWidth <= node.clientWidth && node.scrollHeight <= node.clientHeight };
  });
  if (target) assertRegistryTarget(target);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  const touches = [];
  let touchObservation;
  if (input === "touch") {
    const callback = `bijuxRegistryTouch${registryTouchSequence++}`;
    await page.exposeFunction(callback, observation => touches.push(observation));
    touchObservation = await link.evaluateHandle((node, name) => {
      const listener = event => {
        const rect = node.getBoundingClientRect();
        const hit = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
        const owners = [];
        for (let ancestor = node.parentElement; ancestor; ancestor = ancestor.parentElement) {
          const style = getComputedStyle(ancestor);
          if (["auto", "scroll"].includes(style.overflowY) && ancestor.scrollHeight > ancestor.clientHeight + 1)
            owners.push({ primary: ancestor.matches(".md-sidebar--primary"), offset: ancestor.scrollTop });
          if (ancestor.matches(".md-sidebar--primary")) break;
        }
        window[name]({ trusted: event.isTrusted, count: event.touches.length, owners,
          target: { width: rect.width, height: rect.height, owned: hit === node || node.contains(hit),
            fit: rect.left >= 0 && rect.right <= innerWidth + 1 && rect.top >= 0 && rect.bottom <= innerHeight + 1,
            labelFit: node.scrollWidth <= node.clientWidth && node.scrollHeight <= node.clientHeight } });
      };
      node.addEventListener("touchstart", listener, { capture: true, once: true });
      return { dispose() { node.removeEventListener("touchstart", listener, true); } };
    }, callback);
  }
  const previousDocument = await page.evaluateHandle(() => document);
  const documentRequests = [];
  let retainedDocument;
  const observeDocument = request => {
    if (request.isNavigationRequest() && request.frame() === page.mainFrame()) documentRequests.push(request.url());
  };
  page.on("request", observeDocument);
  try {
    if (input === "keyboard") await page.keyboard.press("Enter");
    else if (input === "touch") {
      await link.tap();
      await expect.poll(() => touches.length).toBe(1);
      expect(touches[0].trusted).toBe(true);
      expect(touches[0].count).toBe(1);
      expect(touches[0].owners).toHaveLength(1);
      expect(touches[0].owners[0].primary).toBe(true);
      assertRegistryTarget(touches[0].target);
    }
    else await link.click();
    await expect(page).toHaveURL(expected.url);
    await expect(page.locator("main h1")).toHaveText(expected.heading);
    try {
      retainedDocument = await previousDocument.evaluate(original => original === document);
    } catch (error) {
      // Only a destroyed former context and a genuine completed document load
      // establish native navigation; an attempted or aborted request does not.
      if (!documentRequests.length || !/Execution context was destroyed|JSHandles can be evaluated only in the context|Execution context is not available|Cannot find context/.test(error.message)) throw error;
      await page.waitForLoadState("domcontentloaded");
      retainedDocument = false;
    }
  } finally {
    page.off("request", observeDocument);
    await previousDocument.dispose();
    if (touchObservation) {
      try { await touchObservation.evaluate(observation => observation.dispose()); }
      catch (error) { if (!/Execution context was destroyed|JSHandles can be evaluated only in the context|Execution context is not available|Cannot find context/.test(error.message)) throw error; }
      await touchObservation.dispose();
    }
  }
  await expect(page.locator("main h1")).toHaveText(expected.heading);
  // Cross-site registry links may use a native document navigation. Retained
  // document reading journeys own H1 focus; native navigation owns page context.
  if (retainedDocument) await expect(page.locator("main h1")).toBeFocused();
  await expect(page).toHaveTitle(expected.title);
  expect(await page.evaluate(() => document.activeElement.isConnected)).toBe(true);
  await expect(page.locator("#__drawer")).not.toBeChecked();
  await expect(page.locator(".md-content")).toHaveJSProperty("inert", false);
  await openDrawer(page);
  const current = drawer(page).locator(".bijux-mobile-hub__link[aria-current='location']");
  await expect(current).toHaveCount(1);
  expect(await current.evaluate(node => node.href)).toBe(expected.currentURL || expected.url);
  const incorrect = await drawer(page).locator("a[aria-current='page']").evaluateAll(nodes =>
    nodes.filter(node => node.getClientRects().length && new URL(node.href).pathname !== location.pathname)
      .map(node => ({ name: node.textContent.trim(), href: node.href })));
  expect(incorrect).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(control(page, "drawer")).toBeFocused();
}

async function touchJourney(browser, info, journey) {
  const context = await browser.newContext({ hasTouch: true, viewport: { width: 390, height: 844 }, baseURL: info.project.use.baseURL });
  const errors = [];
  try {
    const page = await context.newPage();
    page.on("pageerror", error => errors.push(error.message));
    const reportedTouchPoints = await page.evaluate(() => navigator.maxTouchPoints);
    await info.attach("touch-context.json", { body: Buffer.from(JSON.stringify({ hasTouch: true, reportedTouchPoints, physicalDeviceQualified: false })), contentType: "application/json" });
    await journey(page);
    expect(errors, "Touch context has no uncaught runtime errors").toEqual([]);
  } finally {
    await context.close();
  }
}
async function drawerActivationOnce(page, input, info) {
  const opener = control(page, "drawer"), checkbox = page.locator("#__drawer");
  await expect(checkbox).not.toBeChecked();
  await expect(opener).toHaveAttribute("aria-expanded", "false");
  const observed = await opener.evaluateHandle(node => {
    const toggle = document.getElementById("__drawer");
    const record = { initial: toggle.checked, changes: [], clicks: [], touches: [] };
    const change = () => record.changes.push({ checked: toggle.checked, expanded: node.getAttribute("aria-expanded") });
    const click = event => record.clicks.push({ trusted: event.isTrusted, detail: event.detail });
    const touch = event => record.touches.push({ trusted: event.isTrusted, count: event.touches.length });
    toggle.addEventListener("change", change);
    node.addEventListener("click", click, true);
    node.addEventListener("touchstart", touch, true);
    return { record, dispose() { toggle.removeEventListener("change", change); node.removeEventListener("click", click, true); node.removeEventListener("touchstart", touch, true); } };
  });
  try {
    if (input === "Space" || input === "Enter") {
      await tabTo(page, opener, info.project.use.browserName, 160);
      await expect(opener).toBeFocused();
      await page.keyboard.press(input);
    } else if (input === "touch") await opener.tap();
    else await opener.click();
    await expect(checkbox).toBeChecked();
    await expect(opener).toHaveAttribute("aria-expanded", "true");
    await expect(exposedLinks(page).first()).toBeInViewport();
    const opened = await observed.evaluate(value => value.record);
    expect(opened.initial).toBe(false);
    expect(opened.changes).toEqual([{ checked: true, expanded: "true" }]);
    expect(opened.clicks).toHaveLength(1);
    expect(opened.clicks[0].trusted).toBe(true);
    if (input === "touch") expect(opened.touches).toEqual([{ trusted: true, count: 1 }]);
    await page.keyboard.press("Escape");
    await expect(checkbox).not.toBeChecked();
    await expect(opener).toHaveAttribute("aria-expanded", "false");
    await expect(opener).toBeFocused();
    const completed = await observed.evaluate(value => value.record);
    expect(completed.changes).toEqual([{ checked: true, expanded: "true" }, { checked: false, expanded: "false" }]);
    await info.attach(`drawer-${input}-transitions.json`, { body: Buffer.from(JSON.stringify(completed, null, 2)), contentType: "application/json" });
  } finally {
    await observed.evaluate(value => value.dispose());
    await observed.dispose();
  }
}
async function lastAndCurrentRegistry(page, info, entries, route, input) {
  const root = process.env.BIJUX_GENERATED_ROOT || path.resolve(__dirname, "../../../../artifacts/bijux-docs/generated");
  const manifest = JSON.parse(fs.readFileSync(path.join(root, "manifest.json")));
  const scenario = manifest.scenarios.find(entry => entry.route === route);
  expect(scenario, "The actual served route has a declared producer identity").toBeTruthy();
  const currentURL = new URL(scenario.identity === "bijux" ? "/" : `/${scenario.identity}/`, info.project.use.baseURL).href;
  const currentEntry = entries.find(entry => entry.url === currentURL);
  expect(currentEntry, "Current registry destination belongs to the declared route identity").toBeTruthy();
  for (const entry of [currentEntry, entries.at(-1)]) {
    await phone(page, route);
    await expect(page.locator("[data-bijux-active-repository]")).toHaveAttribute("data-bijux-active-repository", scenario.identity);
    const opener = control(page, "drawer");
    await expect(opener).toBeVisible();
    await expect(opener).toHaveAccessibleName("Open navigation drawer");
    await expect(page.locator("#__drawer")).not.toBeChecked();
    if (input === "keyboard") {
      await tabTo(page, opener, info.project.use.browserName, 160);
      await page.keyboard.press("Space");
    } else await opener.tap();
    await expect(page.locator("#__drawer")).toBeChecked();
    await expect(opener).toHaveAttribute("aria-expanded", "true");
    const links = drawer(page).locator(".bijux-site-registry");
    const current = links.locator("[aria-current='location']");
    await expect(current).toHaveCount(1);
    await expect(current).toHaveAccessibleName(currentEntry.label);
    expect(await current.evaluate(node => node.href)).toBe(currentURL);
    const target = links.getByRole("link", { name: entry.label, exact: true });
    await registryDestination(page, target, entry, input);
  }
}

async function mastheadGeometry(page, firstContent = false) {
  await page.evaluate(() => document.fonts.ready);
  const observed = await page.locator("header").first().evaluate(header => {
    const box = node => { const r = node.getBoundingClientRect(); return { left:r.left, right:r.right, top:r.top, bottom:r.bottom, width:r.width, height:r.height }; };
    const exposed = node => { const r = node.getBoundingClientRect(), s = getComputedStyle(node); return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && !node.closest("[hidden]"); };
    const controls = [...header.querySelectorAll("[data-bijux-header-control], [data-bijux-theme-toggle]")].filter(exposed).map(node => {
      const rect = box(node), hit = document.elementFromPoint((rect.left + rect.right) / 2, (rect.top + rect.bottom) / 2);
      return { kind:node.getAttribute("data-bijux-header-control") || "theme-toggle", name:node.getAttribute("aria-label"), rect, hit:hit === node || node.contains(hit) };
    });
    const helpers = [...header.querySelectorAll("[data-bijux-header-control] .md-visually-hidden")].map(box);
    const titles = [...header.querySelectorAll("[data-bijux-header-topic]")].filter(exposed).map(node => {
      const text = node.querySelector(".md-ellipsis"), glyphs = [], clips = [];
      const walker = document.createTreeWalker(text, NodeFilter.SHOW_TEXT);
      for (let leaf = walker.nextNode(); leaf; leaf = walker.nextNode()) {
        const start = leaf.textContent.search(/\S/), end = leaf.textContent.search(/\s*$/);
        if (start < 0) continue;
        const range = document.createRange(); range.setStart(leaf, start); range.setEnd(leaf, end);
        for (const rect of range.getClientRects()) glyphs.push({ left:rect.left, right:rect.right, top:rect.top, bottom:rect.bottom });
      }
      for (let ancestor = text; ancestor; ancestor = ancestor.parentElement) {
        const style = getComputedStyle(ancestor);
        if (["hidden","clip","auto","scroll"].includes(style.overflowX) || ["hidden","clip","auto","scroll"].includes(style.overflowY))
          clips.push({ rect:box(ancestor), x:style.overflowX !== "visible", y:style.overflowY !== "visible" });
      }
      return { kind:node.getAttribute("data-bijux-header-topic"), text:text.textContent.trim(), rect:box(text),
        scrollWidth:text.scrollWidth, clientWidth:text.clientWidth, glyphs, clips };
    });
    const content = [document.querySelector("main h1"), document.querySelector("main .md-typeset > p")].map(node => {
      if (!node) return null;
      const rect = box(node), hit = document.elementFromPoint((rect.left + rect.right) / 2, (rect.top + rect.bottom) / 2);
      return { text:node.textContent.trim(), rect, hit:hit === node || node.contains(hit) };
    });
    return { header:box(header), controls, helpers, titles, content, viewport:{width:innerWidth,height:innerHeight} };
  });
  await test.info().attach(`masthead-${observed.viewport.width}x${observed.viewport.height}-${observed.titles[0]?.clientWidth || 0}.json`,
    { body:Buffer.from(JSON.stringify(observed, null, 2)), contentType:"application/json" });
  const expectedControls = observed.viewport.width < 1220 ? ["drawer-toggle", "search-toggle", "theme-toggle"] : ["search-toggle", "theme-toggle"];
  expect(observed.controls.map(entry => entry.kind).sort(), "Required utilities survive the actual width and text sizing; an empty census cannot pass").toEqual(expectedControls);
  expect(observed.titles.length, "Only one title layer may be exposed").toBe(observed.viewport.width < 1220 ? 1 : 0);
  for (const title of observed.titles) {
    expect(title.kind).toBe("site");
    expect(title.text).toBe("Bijux");
    expect(title.glyphs.length, "The visible identity has actual rendered text glyphs").toBeGreaterThan(0);
    expect(title.scrollWidth, "The complete visible identity is not ellipsized").toBeLessThanOrEqual(title.clientWidth + 1);
    for (const glyph of title.glyphs) {
      expect(glyph.left).toBeGreaterThanOrEqual(0);
      expect(glyph.right).toBeLessThanOrEqual(observed.viewport.width + 1);
      for (const clip of title.clips) {
        if (clip.x) { expect(glyph.left).toBeGreaterThanOrEqual(clip.rect.left - 1); expect(glyph.right).toBeLessThanOrEqual(clip.rect.right + 1); }
        if (clip.y) { expect(glyph.top).toBeGreaterThanOrEqual(clip.rect.top - 1); expect(glyph.bottom).toBeLessThanOrEqual(clip.rect.bottom + 1); }
      }
      for (const utility of observed.controls) {
        const rect = utility.rect;
        expect(glyph.right <= rect.left + 1 || rect.right <= glyph.left + 1 || glyph.bottom <= rect.top + 1 || rect.bottom <= glyph.top + 1,
          "Identity glyphs do not compete with utility targets").toBe(true);
      }
    }
  }
  for (const entry of observed.controls) {
    expect(entry.name, "Every exposed utility retains an accessible name").toMatch(/\S/);
    expect(entry.rect.width).toBeGreaterThanOrEqual(44);
    expect(entry.rect.height).toBeGreaterThanOrEqual(44);
    expect(entry.rect.left).toBeGreaterThanOrEqual(0);
    expect(entry.rect.right).toBeLessThanOrEqual(observed.viewport.width + 1);
    expect(entry.rect.top).toBeGreaterThanOrEqual(observed.header.top - 1);
    expect(entry.rect.bottom).toBeLessThanOrEqual(observed.header.bottom + 1);
    expect(entry.hit, `${entry.name} owns an ordinary visible pointer target`).toBe(true);
  }
  for (let a = 0; a < observed.controls.length; a++) for (let b = a + 1; b < observed.controls.length; b++) {
    const one = observed.controls[a].rect, two = observed.controls[b].rect;
    expect(one.right <= two.left + 1 || two.right <= one.left + 1 || one.bottom <= two.top + 1 || two.bottom <= one.top + 1, "Utility controls do not overlap").toBe(true);
  }
  for (const helper of observed.helpers) {
    expect(helper.width, "Helper text remains visually hidden").toBeLessThanOrEqual(1);
    expect(helper.height).toBeLessThanOrEqual(1);
  }
  if (firstContent) for (const entry of observed.content) {
    expect(entry, "The initial viewport contains the heading and authored reading text").not.toBeNull();
    expect(entry.text).toMatch(/\S/);
    expect(entry.rect.top).toBeGreaterThanOrEqual(observed.header.bottom - 1);
    expect(entry.rect.bottom).toBeLessThanOrEqual(observed.viewport.height + 1);
    expect(entry.hit, "Visible reading content is not covered by navigation").toBe(true);
  }
}
async function drawerBrandGeometry(page) {
  await settle(drawer(page));
  const observed = await drawer(page).locator(".bijux-nav__title").evaluate(title => {
    const box = node => { const r = node.getBoundingClientRect(); return { left:r.left, right:r.right, top:r.top, bottom:r.bottom }; };
    const nodes = [title.querySelector("img"), title.querySelector(".bijux-nav__site-name"), title.querySelector("[data-bijux-control-close]")];
    const parts = nodes.map(node => ({ rect:box(node), text:node.textContent.trim() }));
    const name = nodes[1], range = document.createRange(); range.selectNodeContents(name);
    const glyphs = [...range.getClientRects()].map(r => ({ left:r.left, right:r.right, top:r.top, bottom:r.bottom }));
    const clips = [];
    for (let node = name; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (["hidden","clip","auto","scroll"].includes(style.overflowX) || ["hidden","clip","auto","scroll"].includes(style.overflowY)) clips.push({ rect:box(node), x:style.overflowX !== "visible", y:style.overflowY !== "visible" });
    }
    return { rect:box(title), parts, glyphs, clips, width:innerWidth, height:innerHeight };
  });
  expect(observed.parts[1].text).toBe("Bijux");
  for (const part of observed.parts) {
    expect(part.rect.left).toBeGreaterThanOrEqual(observed.rect.left - 1);
    expect(part.rect.right).toBeLessThanOrEqual(Math.min(observed.rect.right, observed.width) + 1);
    expect(part.rect.top).toBeGreaterThanOrEqual(observed.rect.top - 1);
    expect(part.rect.bottom).toBeLessThanOrEqual(Math.min(observed.rect.bottom, observed.height) + 1);
  }
  for (let index = 1; index < observed.parts.length; index++) expect(observed.parts[index - 1].rect.right).toBeLessThanOrEqual(observed.parts[index].rect.left + 1);
  for (const glyph of observed.glyphs) for (const clip of observed.clips) {
    if (clip.x) { expect(glyph.left).toBeGreaterThanOrEqual(clip.rect.left - 1); expect(glyph.right).toBeLessThanOrEqual(clip.rect.right + 1); }
    if (clip.y) { expect(glyph.top).toBeGreaterThanOrEqual(clip.rect.top - 1); expect(glyph.bottom).toBeLessThanOrEqual(clip.rect.bottom + 1); }
  }
}

test("inactive navigation strips remain absent at every responsive boundary", async ({ page }, info) => {
  // Each engine's phone assignment owns the supplemental matrix once; existing
  // phone/compact/desktop journeys retain their original boundary assertions.
  const supplemental = info.project.name.endsWith("-phone") ? [360, 412, 769, 1100, 1221, 1280, 1920] : [];
  for (const width of [320, 767, 768, 820, 1024, 1219, 1220, 1440, ...supplemental]) {
    await page.setViewportSize({ width, height: 900 });
    await ready(page);
    const hidden = page.locator("[data-bijux-detail-strip][hidden], [data-bijux-course-strip][hidden]");
    expect(await hidden.count()).toBeGreaterThan(0);
    const painted = await hidden.evaluateAll((nodes) => nodes.filter((node) => node.getClientRects().length && getComputedStyle(node).visibility !== "hidden").length);
    expect(painted, `Hidden navigation painted at ${width}px`).toBe(0);
    const height = await page.locator("header").first().evaluate((node) => node.getBoundingClientRect().height);
    expect(height, `Masthead height at ${width}px`).toBeLessThanOrEqual(width < 768 ? 72 : width < 1220 ? 112 : 160);
    await mastheadGeometry(page, true);
    if (width >= 1220) {
      await expect(page.locator("header .bijux-hub-strip")).toBeVisible();
      await expect(page.locator(".md-sidebar--primary .bijux-site-registry")).toBeHidden();
    } else {
      await openDrawer(page);
      const tabs = page.locator("header .bijux-site-tabs");
      await expect(tabs).toHaveJSProperty("inert", true);
      await page.keyboard.press("Escape");
      await expect(tabs).toHaveJSProperty("inert", false);
      await expect(control(page, "drawer")).toBeFocused();
    }
  }
  await page.setViewportSize({ width:568, height:320 });
  await ready(page);
  expect(await page.locator("header").first().evaluate(node => node.getBoundingClientRect().height)).toBeLessThanOrEqual(64);
  await mastheadGeometry(page, true);
  if (info.project.name.endsWith("-phone")) {
    await page.setViewportSize({ width:667, height:320 });
    await ready(page, "/platform/");
    expect(await page.locator("header").first().evaluate(node => node.getBoundingClientRect().height)).toBeLessThanOrEqual(64);
    await mastheadGeometry(page, true);
  }
});
test("phone brand and visually hidden helper text preserve useful space", async ({ page }, info) => {
  await page.setViewportSize({ width: 320, height: 700 });
  const logoResponse = page.waitForResponse(response => new URL(response.url()).pathname.endsWith("/assets/bijux_logo.png"));
  await ready(page);
  const imageResponse = await logoResponse;
  expect(imageResponse.ok()).toBe(true);
  expect((await imageResponse.body()).length).toBeLessThanOrEqual(32 * 1024);
  const helper = control(page, "drawer").locator(".md-visually-hidden");
  if (await helper.count()) {
    const box = await helper.boundingBox();
    expect(box?.width || 0).toBeLessThanOrEqual(1);
    expect(box?.height || 0).toBeLessThanOrEqual(1);
  }
  const title = page.locator("[data-bijux-header-topic='site'] .md-ellipsis");
  expect(await title.evaluate((node) => node.clientWidth)).toBeGreaterThanOrEqual(40);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  await openDrawer(page);
  const brand = drawer(page).locator(".bijux-nav__title > a.md-logo");
  await expect(brand).toHaveAccessibleName(/\S/);
  const logo = brand.locator("img");
  await expect(logo).toHaveAttribute("alt", "");
  await expect(logo).toHaveAttribute("width", "48");
  await expect(logo).toHaveAttribute("height", "48");
  await expect.poll(() => logo.evaluate(image => image.complete && image.naturalWidth === 128 && image.naturalHeight === 128)).toBe(true);
  await drawerBrandGeometry(page);
  await page.keyboard.press("Escape");
  const supplementaryWidths = info.project.name.endsWith("-phone") ? [360,412,767,768,769,820,1024,1100,1219,1220,1221,1280,1440,1920] : [];
  for (const width of [320,390,...supplementaryWidths]) {
    for (const enlarged of [false,true]) {
      await page.setViewportSize({ width, height:844 });
      await ready(page, "/platform/");
      if (enlarged) {
        const size = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize));
        await page.addStyleTag({ content:`html { font-size:${size * 2}px !important; } * { line-height:1.5 !important; letter-spacing:.12em !important; word-spacing:.16em !important; } p { margin-block-end:2em !important; }` });
      } else {
        await expect(title).toHaveText("Bijux");
        const text = await title.evaluate(node => ({ client:node.clientWidth, scroll:node.scrollWidth }));
        expect(text.scroll, "Ordinary 320px identity is not ellipsized").toBeLessThanOrEqual(text.client + 1);
      }
      await mastheadGeometry(page);
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      // The existing 320/390 input journeys own every activation assertion;
      // supplemental widths qualify the same controls' geometry and names.
      if (width === 320 || width === 390) {
        if (width < 1220) {
          await openDrawer(page);
          await drawerBrandGeometry(page);
          await drawer(page).getByRole("button", { name:"Close navigation", exact:true }).click();
          await expect(page.locator("#__drawer")).not.toBeChecked();
          await expect(control(page,"drawer")).toBeFocused();
        }
        await control(page,"search").click();
        await expect(page.locator("#__search")).toBeChecked();
        await expect(page.locator("[data-md-component='search-query']")).toBeFocused();
        await page.keyboard.press("Escape");
        await expect(control(page,"search")).toBeFocused();
      }
    }
  }
  if (info.project.name.endsWith("-phone")) for (const width of [568,667]) {
    await page.setViewportSize({ width, height:320 });
    await ready(page, "/platform/");
    const size = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize));
    await page.addStyleTag({ content:`html { font-size:${size * 2}px !important; } * { line-height:1.5 !important; letter-spacing:.12em !important; word-spacing:.16em !important; } p { margin-block-end:2em !important; }` });
    await mastheadGeometry(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  }
});
test("tablet drawer exposes real destinations through ordinary pointer input", async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 900 });
  await ready(page);
  await openDrawer(page);
  expect(await exposedLinks(page).count()).toBeGreaterThan(1);
});
test("drawer opens on Space from a known closed state", async ({ page, browser }, info) => {
  for (const input of ["Space", "pointer"]) {
    await phone(page);
    await drawerActivationOnce(page, input, info);
  }
  if (info.project.name.endsWith("-phone")) await touchJourney(browser, info, async touchPage => {
    await phone(touchPage);
    await drawerActivationOnce(touchPage, "touch", info);
  });
});
test("drawer opens on Enter from a known closed state", async ({ page }, info) => {
  await phone(page);
  await drawerActivationOnce(page, "Enter", info);
});
test("Escape dismisses drawer and restores its trigger", async ({ page }) => {
  await phone(page);
  await openDrawer(page);
  await page.keyboard.press("Escape");
  await expect(page.locator("#__drawer")).not.toBeChecked();
  await expect(control(page, "drawer")).toBeFocused();
});
test("parent overview remains a real navigation destination", async ({ page }) => {
  await phone(page);
  await openDrawer(page);
  await drawer(page).locator("summary").filter({ hasText: /^Platform$/ }).click();
  const destination = drawer(page).locator("a[href='platform/'], a[href$='/platform/']").filter({ hasText: /^\s*Overview\s*$/ }).first();
  await destination.click();
  await expect(page).toHaveURL(/\/platform\/$/);
  await expect(page.locator("h1")).toHaveText(/^Platform overview(?:¶)?$/);
});
test("all nine shared site destinations are reachable from phone drawer", async ({ page, browser }, info) => {
  expect(registry).toHaveLength(9);
  for (const destination of registry) {
    await phone(page);
    await openDrawer(page);
    await expect(drawer(page).locator(".bijux-mobile-hub__link:visible")).toHaveCount(9);
    const route = destination.key === "bijux" ? "/" : `/${destination.key}/`;
    await registryDestination(page, drawer(page).locator(".bijux-site-registry").getByRole("link", { name: destination.label, exact: true }), {
      label: destination.label,
      url: new URL(route, info.project.use.baseURL).href,
      heading: destination.key === "bijux" ? /^Bijux reference(?:¶)?$/ : /^Product overview(?:¶)?$/,
      title: destination.key === "bijux" ? "Bijux" : destination.key,
    });
  }
  const entries = registry.map(entry => ({ label: entry.label, url: new URL(entry.key === "bijux" ? "/" : `/${entry.key}/`, info.project.use.baseURL).href,
    heading: entry.key === "bijux" ? /^Bijux reference(?:¶)?$/ : /^Product overview(?:¶)?$/, title: entry.key === "bijux" ? "Bijux" : entry.key }));
  if (info.project.name.endsWith("-phone")) {
    await lastAndCurrentRegistry(page, info, entries, "/", "keyboard");
    await touchJourney(browser, info, touchPage => lastAndCurrentRegistry(touchPage, info, entries, "/", "touch"));
  }
});
test("deep documents have truthful current page state", async ({ page }) => {
  await ready(page, "/bijux-core/platform/details/leaf/");
  const incorrect = await page.locator("a[aria-current='page']").evaluateAll((links) => links.filter((link) => {
    const rect = link.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && new URL(link.href).pathname.replace(/\/+$/, "") !== location.pathname.replace(/\/+$/, "");
  }).map((link) => ({ name: link.textContent.trim(), href: link.href })));
  expect(incorrect).toEqual([]);
  if (page.viewportSize().width >= 1220) {
    await expect(drawer(page).locator("a[aria-current='page']")).toBeVisible();
    const alternatives = page.locator("header .bijux-site-tabs a, header .bijux-detail-tabs a, header .bijux-course-tabs a, header .bijux-detail-select");
    expect(await alternatives.evaluateAll(nodes => nodes.filter(node => node.getClientRects().length).length)).toBe(0);
    expect(await alternatives.evaluateAll(nodes => nodes.every(node => {
      node.focus();
      return document.activeElement !== node;
    }))).toBe(true);
    const reading = drawer(page).locator("a").filter({ hasText: /^\s*Reading reference\s*$/ });
    await tabTo(page, reading, test.info().project.use.browserName, 160);
    await expect(reading).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/bijux-core\/reading\/$/);
    await page.goBack();
    await expect(page).toHaveURL(/\/bijux-core\/platform\/details\/leaf\/$/);
    await expect(drawer(page).locator("a[aria-current='page']")).toBeVisible();
  }
});
test("resize and history preserve shell without uncaught errors", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await ready(page, "/platform/");
  for (const width of [1440, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.locator("main")).toBeVisible();
  }
  await page.locator("main a[href]").filter({ hasText: "Getting started" }).first().click();
  await expect(page).toHaveURL(/\/platform\/start\/$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/platform\/$/);
  expect(errors).toEqual([]);
});
test("search initialization yields a real known-answer result", async ({ page }) => {
  await phone(page, "/bijux-core/");
  await control(page, "search").click();
  await page.locator("[data-md-component='search-query']").pressSequentially("resilient navigation");
  await expect(page.locator(".md-search-result__link").first()).toBeVisible();
  await page.locator(".md-search-result__link").first().click();
  await expect(page).toHaveURL(/\/bijux-core\//);
  await expect(page.locator("main")).toContainText("resilient navigation");
});
test("rich content renders actual Material enhancements", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await ready(page, "/reading/");
  await expect(page.locator(".mermaid svg")).toBeVisible();
  await page.getByText("Reader disclosure", { exact: true }).click();
  await expect(page.getByText("Important nested reading content remains available.")).toBeVisible();
  await expect(page.locator("table")).toContainText("Measurement");
  expect(errors).toEqual([]);
});
test("empty and expanded-registry fixtures retain useful navigation", async ({ page, browser }, info) => {
  for (const route of ["/fixtures/empty/", "/fixtures/long-registry/"]) {
    await phone(page, route);
    await openDrawer(page);
    expect(await exposedLinks(page).count()).toBeGreaterThan(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  }
  const expected = registry.map(entry => {
    const route = entry.key === "bijux" ? "/" : `/${entry.key}/`;
    const label = entry.label + " scientific platform";
    expect(label.length).toBeGreaterThanOrEqual(entry.label.length * 1.5);
    return { label, url: new URL(route, info.project.use.baseURL).href, title: entry.key === "bijux" ? "Bijux" : entry.key,
      heading: entry.key === "bijux" ? /^Bijux reference(?:¶)?$/ : /^Product overview(?:¶)?$/ };
  }).concat([
    { label: "Reference extension", url: new URL("/fixtures/empty/", info.project.use.baseURL).href,
      currentURL: new URL("/bijux-core/", info.project.use.baseURL).href, title: "bijux-core", heading: /^Product overview(?:¶)?$/ },
    { label: "Research extension", url: new URL("/reading/", info.project.use.baseURL).href,
      currentURL: new URL("/", info.project.use.baseURL).href, title: "Reading reference - Bijux", heading: /^Rich reading reference(?:¶)?$/ },
  ]);
  for (const entry of expected) {
    await phone(page, "/fixtures/long-registry/");
    await openDrawer(page);
    await expect(drawer(page).locator(".bijux-mobile-hub__link:visible")).toHaveCount(11);
    await registryDestination(page, drawer(page).locator(".bijux-site-registry").getByRole("link", { name: entry.label, exact: true }), entry);
  }
  if (info.project.name.endsWith("-phone")) {
    await lastAndCurrentRegistry(page, info, expected, "/fixtures/long-registry/", "keyboard");
    await touchJourney(browser, info, touchPage => lastAndCurrentRegistry(touchPage, info, expected, "/fixtures/long-registry/", "touch"));
  }
});
async function nativeHeaderGeometry(page, expectedTitle, info) {
  const observed = await page.locator("header").evaluate(header => {
    const bounds = node => { const r = node.getBoundingClientRect(); return { left:r.left, right:r.right, top:r.top, bottom:r.bottom }; };
    const glyphs = node => {
      const walk = document.createTreeWalker(node, NodeFilter.SHOW_TEXT), rectangles = [];
      for (let text = walk.nextNode(); text; text = walk.nextNode()) {
        if (!text.textContent.trim()) continue;
        const range = document.createRange(); range.selectNodeContents(text);
        for (const r of range.getClientRects()) rectangles.push({ left:r.left, right:r.right, top:r.top, bottom:r.bottom });
      }
      return rectangles;
    };
    const title = header.querySelector("[data-bijux-header-topic='site'] .md-ellipsis");
    const label = header.querySelector("label[for='__drawer'].bijux-native-drawer-label");
    const clipping = [];
    for (let ancestor = title; ancestor; ancestor = ancestor.parentElement) {
      const style = getComputedStyle(ancestor);
      if (["hidden","clip","auto","scroll"].includes(style.overflowX) || ["hidden","clip","auto","scroll"].includes(style.overflowY))
        clipping.push({ rect:bounds(ancestor), x:style.overflowX !== "visible", y:style.overflowY !== "visible" });
    }
    return { title:title.textContent.trim(), titleGlyphs:glyphs(title), labelGlyphs:glyphs(label),
      label:label.textContent.trim(), labelFor:label.htmlFor, header:bounds(header),
      rootFont:parseFloat(getComputedStyle(document.documentElement).fontSize),
      checkbox:bounds(document.querySelector("#__drawer")), clipping, width:innerWidth,
      documentWidth:document.documentElement.scrollWidth };
  });
  await info.attach(`native-enlarged-${page.viewportSize().width}-${expectedTitle}.json`,
    { body:Buffer.from(JSON.stringify(observed, null, 2)), contentType:"application/json" });
  await info.attach(`native-enlarged-${page.viewportSize().width}-${expectedTitle}.png`,
    { body:await page.screenshot(), contentType:"image/png" });
  expect(observed.title).toBe(expectedTitle);
  expect(observed.label).toBe("Navigation");
  expect(observed.labelFor).toBe("__drawer");
  expect(observed.labelGlyphs.length).toBeGreaterThan(0);
  expect(observed.titleGlyphs.length).toBeGreaterThan(0);
  for (const glyph of observed.labelGlyphs) {
    expect(glyph.top, "Navigation text stays beside its native checkbox").toBeGreaterThanOrEqual(observed.checkbox.top);
    expect(glyph.bottom, "Navigation text stays beside its native checkbox").toBeLessThanOrEqual(observed.checkbox.bottom);
  }
  for (const glyph of observed.titleGlyphs) {
    expect(glyph.left).toBeGreaterThanOrEqual(0);
    expect(glyph.right).toBeLessThanOrEqual(observed.width);
    for (const clip of observed.clipping) {
      if (clip.x) { expect(glyph.left).toBeGreaterThanOrEqual(clip.rect.left); expect(glyph.right).toBeLessThanOrEqual(clip.rect.right); }
      if (clip.y) { expect(glyph.top).toBeGreaterThanOrEqual(clip.rect.top); expect(glyph.bottom).toBeLessThanOrEqual(clip.rect.bottom); }
    }
    const target = observed.checkbox;
    expect(glyph.right <= target.left || target.right <= glyph.left || glyph.bottom <= target.top || target.bottom <= glyph.top,
      "Complete identity does not compete with the native navigation target").toBe(true);
  }
  expect(observed.documentWidth).toBeLessThanOrEqual(observed.width);
}

test("no-script generated document retains ordinary destination links", async ({ browser }, info) => {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 844 } });
  try {
    const page = await context.newPage();
    await page.goto(new URL("/", info.project.use.baseURL).href);
    const toggle = page.getByRole("checkbox", { name: "Navigation", exact: true });
    await expect(toggle).toBeVisible();
    await toggle.click();
    await expect(toggle).toBeChecked();
    await expect(exposedLinks(page).first()).toBeInViewport();
    expect(await exposedLinks(page).count()).toBeGreaterThan(1);
    const geometry = await drawer(page).evaluate(node => {
      const bounds = node.getBoundingClientRect();
      return { position: getComputedStyle(node).position, left: bounds.left, right: bounds.right,
        width: innerWidth, documentWidth: document.documentElement.scrollWidth };
    });
    expect(geometry.position).toBe("static");
    expect(geometry.left).toBeGreaterThanOrEqual(-1);
    expect(geometry.right).toBeLessThanOrEqual(geometry.width + 1);
    expect(geometry.documentWidth).toBeLessThanOrEqual(geometry.width + 1);
    for (const width of [768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(new URL("/", info.project.use.baseURL).href);
      const localRows = page.locator("header .bijux-site-tabs, header .bijux-detail-tabs, header .bijux-course-tabs");
      if (width === 768) {
        const toggle = page.getByRole("checkbox", { name: "Navigation", exact: true });
        expect(await localRows.evaluateAll(nodes => nodes.filter(node => node.getClientRects().length).length)).toBe(1);
        await toggle.click();
        expect(await localRows.evaluateAll(nodes => nodes.filter(node => node.getClientRects().length).length)).toBe(0);
        await toggle.click();
        expect(await localRows.evaluateAll(nodes => nodes.filter(node => node.getClientRects().length).length)).toBe(1);
        await toggle.click();
      }
      await expect(drawer(page)).toBeVisible();
      expect(await localRows.evaluateAll(nodes => nodes.filter(node => node.getClientRects().length).length)).toBe(0);
      const reading = drawer(page).locator("a").filter({ hasText: /^\s*Reading reference\s*$/ });
      await reading.click();
      await expect(page).toHaveURL(/\/reading\/$/);
      await expect(page.locator("h1")).toBeVisible();
    }
    // Qualify enlargement once per engine; the other viewport profiles retain
    // the unchanged ordinary fallback journey above.
    if (info.project.name.endsWith("-phone")) for (const width of [320,390]) {
      for (const [route, title] of [["/", "Bijux"], ["/bijux-pollenomics/", "bijux-pollenomics"]]) {
        const preferenceContext = await browser.newContext({ javaScriptEnabled:false, viewport:{ width, height:844 } });
        const preferencePage = await preferenceContext.newPage();
        try {
          await preferencePage.goto(new URL(route, info.project.use.baseURL).href);
          const font = await preferencePage.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize));
          const preference = `html { font-size:${font * 2}px !important; } * { line-height:1.5 !important; letter-spacing:.12em !important; word-spacing:.16em !important; } p { margin-block-end:2em !important; }`;
          // Deliver user CSS without relying on no-script DOM insertion events.
          const style = async request => {
            const response = await request.fetch();
            await request.fulfill({ response, body:await response.text() + "\n" + preference });
          };
          await preferencePage.route("**/assets/styles/08-responsive.css", style);
          try {
            await preferencePage.reload();
            expect(await preferencePage.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize))).toBe(font * 2);
            await nativeHeaderGeometry(preferencePage, title, info);
            const native = preferencePage.getByRole("checkbox", { name:"Navigation", exact:true });
            await tabTo(preferencePage, native, browser.browserType().name());
            const focus = await measureFocus(preferencePage, native);
            expect(focus.focusVisible).toBe(true);
            expect(focus.ratio).toBeGreaterThanOrEqual(3);
            expect(focus.rectangle.width).toBeGreaterThanOrEqual(44);
            expect(focus.rectangle.height).toBeGreaterThanOrEqual(44);
            expect(focus.centerOwned).toBe(true);
            await preferencePage.keyboard.press("Space");
            await expect(native).toBeChecked();
            await expect(drawer(preferencePage)).toBeVisible();
            await preferencePage.keyboard.press("Space");
            await expect(native).not.toBeChecked();
            await expect(native).toBeFocused();
          } finally { await preferencePage.unroute("**/assets/styles/08-responsive.css", style); }
        } finally { await preferenceContext.close(); }
      }
    }
  } finally {
    await context.close();
  }
});

test("disclosure keyboard changes expansion without swallowing overview navigation", async ({ page }) => {
  await phone(page);
  await openDrawer(page);
  const summary = drawer(page).locator("summary").filter({ hasText: /^Platform$/ });
  const group = summary.locator("..");
  await summary.focus();
  await page.keyboard.press("Space");
  await expect(group).toHaveAttribute("open", "");
  await page.keyboard.press("Enter");
  await expect(group).not.toHaveAttribute("open", "");
  await expect(summary).toBeFocused();
});

test("all declared consumer roots serve admitted shell and search data", async ({ page }) => {
  const fs = require("fs"), path = require("path");
  const root = process.env.BIJUX_GENERATED_ROOT || path.resolve(__dirname, "../../../../artifacts/bijux-docs/generated");
  const manifest = JSON.parse(fs.readFileSync(path.join(root, "manifest.json")));
  const consumers = manifest.scenarios.filter((entry) => ["hub", "project"].includes(entry.kind));
  expect(consumers).toHaveLength(9);
  for (const entry of consumers) {
    await ready(page, entry.route);
    await expect(page.locator("[data-bijux-active-repository]")).toHaveAttribute("data-bijux-active-repository", entry.identity);
    const response = await page.request.get(`${entry.route}search/search_index.json`);
    expect(response.status()).toBe(200);
    expect((await response.json()).docs.length).toBeGreaterThan(0);
  }
});
