const { test, expect, control, ready, phone, openDrawer } = require("./helpers/document");
const AxeBuilder = require("@axe-core/playwright").default;
const fs = require("node:fs");

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.bijuxAccessibilityInputEvidence = [];
    for (const type of ["pointerdown", "click", "keydown", "input"]) {
      document.addEventListener(type, event => {
        const target = event.target;
        window.bijuxAccessibilityInputEvidence.push({
          type, trusted: event.isTrusted, key: event.key,
          tag: target.tagName, id: target.id,
          label: target.getAttribute?.("aria-label"),
          component: target.getAttribute?.("data-md-component"),
        });
      }, true);
    }
  });
});

async function theme(page, wanted) {
  for (let index = 0; index < 3 && await page.locator("body").getAttribute("data-md-color-scheme") !== wanted; index++)
    await page.locator("[data-bijux-theme-toggle]").click();
  await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", wanted);
}

async function scan(page, info, name, scans) {
  const offOrigin = [], origin = new URL(info.project.use.baseURL).origin;
  const observe = request => { if (new URL(request.url()).origin !== origin) offOrigin.push(request.url()); };
  page.on("request", observe);
  try {
    const before = await page.evaluate(() => ({
      url: location.href, theme: document.body.getAttribute("data-md-color-scheme"),
      themeControl: document.querySelector("[data-bijux-theme-toggle]")?.getAttribute("aria-label"),
      requestedSystemDark: matchMedia("(prefers-color-scheme: dark)").matches,
      width: innerWidth, height: innerHeight,
      drawerOpen: document.querySelector("#__drawer")?.checked,
      searchOpen: document.querySelector("#__search")?.checked,
      query: document.querySelector("[data-md-component='search-query']")?.value,
      active: { tag: document.activeElement.tagName, id: document.activeElement.id, label: document.activeElement.getAttribute("aria-label") },
      input: window.bijuxAccessibilityInputEvidence,
      searchMetadata: [...document.querySelectorAll(".md-search-result__meta")].map(node => {
        const style = getComputedStyle(node), backgrounds = [];
        for (let parent = node; parent; parent = parent.parentElement) {
          const computed = getComputedStyle(parent);
          backgrounds.push({ tag: parent.tagName, class: parent.className, background: computed.backgroundColor, image: computed.backgroundImage, opacity: computed.opacity });
        }
        return { text: node.textContent, foreground: style.color, fontSize: style.fontSize, fontWeight: style.fontWeight, backgrounds };
      }),
    }));
    const started = Date.now();
    // CSSOM/resource preloading adds requests rather than testing the reader's rendered state.
    // Run all default rules, including WCAG and best practice, with no exclusions.
    // Retain every incomplete result for owned review rather than treating it as a pass.
    const result = await new AxeBuilder({ page }).options({ preload: false }).analyze();
    const record = { name, before, duration_ms: Date.now() - started, offOriginRequests: offOrigin, result };
    scans.push(record);
    const file = info.outputPath(`${name}-axe.json`);
    fs.writeFileSync(file, JSON.stringify(record, null, 2) + "\n");
    await info.attach(name, { path: file, contentType: "application/json" });
    expect(offOrigin, "The automated scan adds no off-origin network requests").toEqual([]);
  } finally { page.off("request", observe); }
}

function clean(scans) {
  expect(scans.flatMap(scan => scan.result.violations.map(rule => ({
    state: scan.name, rule: rule.id, impact: rule.impact,
    nodes: rule.nodes.map(node => ({ target: node.target, summary: node.failureSummary })),
  }))), "Confirmed automated accessibility violations remain release failures").toEqual([]);
}

test("root and deep desktop documents retain complete automated scan evidence in light and dark", async ({ page }, info) => {
  const scans = [];
  await ready(page, "/"); await theme(page, "default");
  await expect(page.locator("main h1")).toContainText("Bijux reference");
  await scan(page, info, "root-desktop-light", scans);
  await ready(page, "/bijux-core/platform/details/leaf/"); await theme(page, "default");
  await expect(page.locator("main h1")).toContainText("Platform leaf destination");
  await expect(page.getByRole("navigation", { name: "bijux-core documentation navigation", exact: true })).toHaveCount(1);
  await expect(page.locator(".md-path")).toHaveAccessibleName("Navigation");
  await scan(page, info, "deep-desktop-light", scans);
  await theme(page, "slate");
  await scan(page, info, "deep-desktop-dark", scans);
  clean(scans);
});

test("ordinary root and deep phone drawer states retain modal focus and automated scan evidence", async ({ page }, info) => {
  const scans = [];
  await phone(page, "/"); await theme(page, "default"); await openDrawer(page);
  await expect(page.locator(".md-sidebar--primary")).toHaveAttribute("role", "dialog");
  await expect(page.locator(".md-sidebar--primary")).toHaveAttribute("aria-modal", "true");
  await expect(page.getByRole("dialog", { name: "Site navigation", exact: true })).toHaveCount(1);
  await expect(page.locator("#bijux-navigation :focus")).toHaveCount(1);
  await scan(page, info, "root-phone-drawer-light", scans);
  await page.keyboard.press("Escape"); await expect(control(page, "drawer")).toBeFocused();
  await phone(page, "/bijux-core/platform/details/leaf/"); await theme(page, "default"); await openDrawer(page);
  await expect(page.locator("#bijux-navigation :focus")).toHaveCount(1);
  await scan(page, info, "deep-phone-drawer-light", scans);
  await page.keyboard.press("Escape"); await expect(control(page, "drawer")).toBeFocused();
  await theme(page, "slate"); await openDrawer(page);
  await expect(page.locator("#bijux-navigation :focus")).toHaveCount(1);
  await scan(page, info, "deep-phone-drawer-dark", scans);
  await page.keyboard.press("Escape"); await expect(control(page, "drawer")).toBeFocused();
  clean(scans);
});

test("ordinary scoped search empty and known-answer states retain focused query and automated scan evidence", async ({ page }, info) => {
  const scans = [], query = page.locator("[data-md-component='search-query']");
  await phone(page, "/bijux-core/platform/details/leaf/"); await theme(page, "default");
  await control(page, "search").click(); await expect(query).toBeFocused();
  await expect(query).toHaveAccessibleName("Search bijux-core");
  await expect(query).toHaveValue("");
  await scan(page, info, "deep-phone-search-empty-light", scans);
  await page.keyboard.insertText("resilient navigation");
  await expect(query).toHaveValue("resilient navigation");
  const answer = page.locator(".md-search-result__link:visible").filter({ hasText: "Reading reference" }).first();
  await expect(answer).toBeVisible({ timeout: 15_000 });
  expect(await answer.getAttribute("href")).toContain("/bijux-core/reading/");
  await scan(page, info, "deep-phone-search-answer-light", scans);
  await page.keyboard.press("Escape"); await expect(control(page, "search")).toBeFocused();
  await theme(page, "slate");
  // Engineering emulation of the system preference, with an ordinary Auto request.
  await page.emulateMedia({ colorScheme: "dark" });
  await page.locator("[data-bijux-theme-toggle]").click();
  await expect(page.locator("[data-bijux-theme-toggle]")).toHaveAccessibleName("Theme mode: Auto. Switch to Light.");
  await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", "slate");
  await control(page, "search").click();
  await expect(query).toBeFocused(); await expect(query).toHaveValue("resilient navigation");
  await expect(answer).toBeVisible();
  await scan(page, info, "deep-phone-search-answer-auto-dark", scans);
  await page.keyboard.press("Escape"); await expect(control(page, "search")).toBeFocused();
  clean(scans);
});
