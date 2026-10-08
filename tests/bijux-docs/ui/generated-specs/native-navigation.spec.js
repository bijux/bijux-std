const fs = require("node:fs"), path = require("node:path");
const { test, expect } = require("@playwright/test");
const qualify = require("./native-navigation/qualification");
const root = path.resolve(process.env.BIJUX_GENERATED_ROOT || path.join(__dirname, "../../../../artifacts/bijux-docs/generated"));
const definitions = [
  { kind: "no-js-native", route: "/", width: 320 },
  { kind: "no-js-native", route: "/bijux-core/platform/details/leaf/", width: 768 },
  ...[320, 768, 1220].map(width => ({ kind: "js-preservation", route: "/", width })),
  { kind: "no-js-resize", route: "/", width: 767 },
  { kind: "no-js-pointer", route: "/", width: 320 },
  { kind: "no-js-desktop", route: "/", width: 1220 },
  { kind: "no-js-rtl", route: "/fixtures/rtl/", width: 320 },
  ...["delayed-native", "throw-before-native", "throw-mounted-native"].map(kind => ({ kind, route: "/", width: 320 })),
];
for (const definition of definitions) {
  test(`${definition.kind} at ${definition.width}px on ${definition.route}`, async ({ browser, browserName }, info) => {
    info.annotations.push({ type: "browser-version", description: browser.version() });
    const manifest = JSON.parse(fs.readFileSync(path.join(root, "manifest.json")));
    await qualify(browser, browserName, definition, info, expect, manifest);
  });
}

// The native Material header retains its sidebar, backdrop and checkbox ownership.
test("native-header Close navigation restores its real opener across compact widths", async ({ page, browser }, info) => {
  test.setTimeout(90_000);
  info.annotations.push({ type: "browser-version", description: browser.version() });
  const observations = [], keys = [], manifest = JSON.parse(fs.readFileSync(path.join(root, "manifest.json")));
  const evidence = { engine: info.project.use.browserName, version: browser.version(), source_sha: manifest.source_sha,
    source_files: manifest.source_files, widths: [320, 390, 767, 768, 959, 960, 1219], observations, keys,
    keyboard_protocol: info.project.use.browserName === "webkit" ? "Option-Tab / Option-Shift-Tab" : "Tab / Shift-Tab" };
  const tab = reverse => `${info.project.use.browserName === "webkit" ? "Alt+" : ""}${reverse ? "Shift+" : ""}Tab`;
  async function tabTo(control, reverse = false) {
    for (let index = 0; index < 128; index++) {
      if (await control.evaluate(node => node === document.activeElement)) return;
      if (await page.locator("#__search").isChecked()) {
        keys.push("Escape"); await page.keyboard.press("Escape");
        await expect(page.locator("#__search")).not.toBeChecked();
      } else {
        keys.push(tab(reverse)); await page.keyboard.press(tab(reverse));
      }
    }
    throw new Error("Ordinary keyboard traversal did not reach the native drawer control");
  }
  async function snapshot(stage) {
    observations.push({ stage, ...await page.evaluate(() => ({ width: innerWidth, checked: document.querySelector("#__drawer").checked,
      ready: document.body.dataset.bijuxDrawerReady || null, openMarker: document.body.dataset.bijuxDrawerOpen || null,
      focusedName: document.activeElement.getAttribute("aria-label"), focusedTag: document.activeElement.tagName,
      openerCount: document.querySelectorAll('.md-header__button[data-bijux-control-target="__drawer"]').length,
      sidebarRole: document.querySelector(".md-sidebar--primary").getAttribute("role"),
      sidebarModal: document.querySelector(".md-sidebar--primary").getAttribute("aria-modal") })) });
  }
  try {
    await page.goto("/fixtures/native-header/");
    const opener = page.getByRole("button", { name: "Navigation", exact: true });
    const close = page.getByRole("button", { name: "Close navigation", exact: true });
    const checkbox = page.locator("#__drawer");
    await expect(opener).toBeVisible();
    for (const width of evidence.widths) {
      await page.setViewportSize({ width, height: 900 });
      await opener.click(); await expect(checkbox).toBeChecked(); await expect(opener).toHaveAttribute("aria-expanded", "true");
      await close.click(); await expect(checkbox).not.toBeChecked(); await expect(opener).toHaveAttribute("aria-expanded", "false"); await expect(opener).toBeFocused();
      await snapshot("pointer-dismissal");
      if ([320, 768, 1219].includes(width)) {
        keys.push("Space"); await page.keyboard.press("Space"); await expect(checkbox).toBeChecked();
        await tabTo(close); keys.push("Space"); await page.keyboard.press("Space");
        await expect(checkbox).not.toBeChecked(); await expect(opener).toHaveAttribute("aria-expanded", "false"); await expect(opener).toBeFocused();
        await page.keyboard.press(tab()); await tabTo(opener, true); await expect(opener).toBeFocused();
        keys.push("Enter"); await page.keyboard.press("Enter"); await expect(checkbox).toBeChecked();
        await close.click(); await expect(checkbox).not.toBeChecked(); await expect(opener).toHaveAttribute("aria-expanded", "false"); await expect(opener).toBeFocused();
        await snapshot("keyboard-dismissal-and-return");
      }
    }
    await page.setViewportSize({ width: 320, height: 900 });
    await opener.click(); await expect(checkbox).toBeChecked(); await expect(opener).toHaveAttribute("aria-expanded", "true");
    const group = page.locator("#bijux-navigation summary").filter({ hasText: /^\s*Platform\s*$/ });
    await expect(group).toHaveCount(1);
    if (!await group.evaluate(node => node.parentElement.open)) await group.click();
    const link = page.locator("#bijux-navigation .bijux-tree a[href]").filter({ hasText: /^\s*Getting started\s*$/ }).first();
    const target = await link.evaluate(node => node.href);
    await link.click(); await expect(page).toHaveURL(target); await expect(page.locator("h1")).toBeVisible();
    await page.goBack(); await expect(page).toHaveURL(/\/fixtures\/native-header\/$/);
    await expect(opener).toHaveCount(1); await expect(checkbox).not.toBeChecked();
    await opener.click(); await expect(checkbox).toBeChecked(); await expect(opener).toHaveAttribute("aria-expanded", "true"); await close.click();
    await expect(checkbox).not.toBeChecked(); await expect(opener).toHaveAttribute("aria-expanded", "false"); await expect(opener).toBeFocused(); await snapshot("route-and-Back-dismissal");
    expect(observations.every(row => row.ready === null && row.openMarker === null && row.sidebarModal === null && row.openerCount === 1)).toBe(true);
    const faultContext = await browser.newContext({ viewport: { width: 320, height: 900 } });
    try {
      const crypto = require("node:crypto"), errors = [];
      await faultContext.route("**/shell/bootstrap.js", async route => {
        const response = await route.fetch(), body = await response.text();
        const digest = value => crypto.createHash("sha256").update(value).digest("hex");
        expect(digest(body)).toBe(manifest.source_files["scripts/bootstrap.js"]);
        const injected = body.replace("      shell.detailTabs?.runDetailTabsSync?.();", '      throw new Error("bijux native drawer qualification mount failure");');
        expect(injected).not.toBe(body);
        evidence.failed_mount_source = { original_sha256: digest(body), injected_sha256: digest(injected) };
        await route.fulfill({ response, body: injected });
      });
      const faultPage = await faultContext.newPage(); faultPage.on("pageerror", error => errors.push(error.message));
      await faultPage.goto(`${info.project.use.baseURL}/fixtures/native-header/`);
      await expect.poll(() => errors).toContain("bijux native drawer qualification mount failure");
      const restoredLabel = faultPage.locator('.md-header__button[for="__drawer"]');
      await expect(restoredLabel).toHaveJSProperty("tagName", "LABEL");
      await expect(faultPage.locator('[data-bijux-control-close]')).toHaveJSProperty("tagName", "LABEL");
      await restoredLabel.click(); await expect(faultPage.locator("#__drawer")).toBeChecked();
      const faultBackdrop = faultPage.locator('.md-overlay[for="__drawer"]');
      const faultBounds = await faultBackdrop.boundingBox(); expect(faultBounds).not.toBeNull();
      await faultBackdrop.click({ position: { x: faultBounds.width - 8, y: faultBounds.height / 2 }, timeout: 5000 });
      await expect(faultPage.locator("#__drawer")).not.toBeChecked();
      expect(errors).toEqual(["bijux native drawer qualification mount failure"]);
      evidence.failed_mount = { originalLabelsRestored: true, ordinaryMaterialOpenerAndBackdrop: true, errors };
    } finally { await faultContext.close(); }
    const nativeContext = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 320, height: 900 } });
    try {
      const nativePage = await nativeContext.newPage();
      await nativePage.goto(`${info.project.use.baseURL}/fixtures/native-header/`);
      const nativeLabel = nativePage.locator('.md-header__button[for="__drawer"]');
      await expect(nativePage.locator('label.md-header__button[for="__drawer"]')).toHaveCount(1);
      await expect(nativePage.locator('button.md-header__button[for="__drawer"]')).toHaveCount(0);
      await expect(nativePage.locator('label[data-bijux-control-close]')).toHaveCount(1);
      await nativeLabel.click(); await expect(nativePage.locator("#__drawer")).toBeChecked();
      const nativeBackdrop = nativePage.locator('.md-overlay[for="__drawer"]');
      const nativeBounds = await nativeBackdrop.boundingBox(); expect(nativeBounds).not.toBeNull();
      await nativeBackdrop.click({ position: { x: nativeBounds.width - 8, y: nativeBounds.height / 2 }, timeout: 5000 });
      await expect(nativePage.locator("#__drawer")).not.toBeChecked();
      evidence.no_js = { originalMaterialLabelPreserved: true, originalCloseLabelPreserved: true, ordinaryMaterialOpenerAndBackdrop: true };
    } finally { await nativeContext.close(); }
    evidence.result = "pass";
  } catch (error) { evidence.result = "fail"; evidence.failure = error.stack; throw error; }
  finally { await info.attach("native-drawer-dismissal", { body: Buffer.from(JSON.stringify(evidence, null, 2)), contentType: "application/json" }); }
});
