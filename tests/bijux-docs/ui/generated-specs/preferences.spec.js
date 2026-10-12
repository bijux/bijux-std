const { test, expect, control, phone, openDrawer, navigation } = require("./helpers/document");

test("denied browser storage preserves palette, search and drawer behavior", async ({ page }) => {
  await page.addInitScript(() => {
    for (const name of ["getItem", "setItem", "removeItem"]) Object.defineProperty(Storage.prototype, name, { value() { throw new DOMException("Storage denied", "SecurityError"); } });
  });
  await phone(page);
  await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", /default|slate/);
  await page.locator("[data-bijux-theme-toggle]").click();
  await openDrawer(page);
  await page.keyboard.press("Escape");
  await control(page, "search").click();
  await page.locator("[data-md-component='search-query']").pressSequentially("resilient navigation");
  await expect(page.locator(".md-search-result__link").first()).toBeVisible();
});

test("malformed and incompatible palette data retain a usable default", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("bijux:theme", "{broken");
    localStorage.setItem("/.__palette", JSON.stringify({ index: 999, color: null }));
  });
  await phone(page);
  await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", /default|slate/);
  await openDrawer(page);
  await page.keyboard.press("Escape");
  await page.locator("[data-bijux-theme-toggle]").click();
  await expect(page.locator("[data-bijux-theme-toggle]")).toHaveAttribute("aria-label", /Theme mode/);
});

test("explicit dark preference applies across initial load and reload", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("bijux:theme", JSON.stringify({ version: 2, mode: "dark" })));
  await phone(page);
  await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", "slate");
  await page.reload();
  await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", "slate");
});

for (const denial of ["getter", "read", "write"]) {
  test(`independent storage ${denial} denial retains instant and cross-site reading`, async ({ page }, info) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.addInitScript(mode => {
      const observations = window.bijuxStorageDenialObservations = { getter: 0, read: 0, write: 0, errors: [] };
      window.bijuxStorageDenialErrorName = "SecurityError";
      const reject = kind => () => {
        observations[kind] += 1;
        observations.errors.push(window.bijuxStorageDenialErrorName);
        throw new DOMException("Storage denied", window.bijuxStorageDenialErrorName);
      };
      if (mode === "getter") Object.defineProperty(window, "localStorage", { configurable: true, get: reject("getter") });
      if (mode === "read") Object.defineProperty(Storage.prototype, "getItem", { configurable: true, value: reject("read") });
      if (mode === "write") Object.defineProperty(Storage.prototype, "setItem", { configurable: true, value: reject("write") });
    }, denial);
    const observations = [];
    const record = async label => observations.push({ label, ...await page.evaluate(() => ({
      url: location.href,
      scheme: document.body.getAttribute("data-md-color-scheme"),
      denied: window.bijuxStorageDenialObservations,
    })) });
    try {
      await phone(page);
      await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", "default");
      await record("initial automatic theme");
      const toggle = page.locator("[data-bijux-theme-toggle]");
      await toggle.click();
      await toggle.click();
      await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", "slate");
      await page.evaluate(() => { window.bijuxPreferenceObservedDocument = document; });
      await record("explicit session theme");
      await openDrawer(page);
      await navigation(page).locator("summary").filter({ hasText: /^Handbook$/ }).click();
      await navigation(page).locator("a[href='handbook/'], a[href$='/handbook/']").filter({ hasText: /^\s*Overview\s*$/ }).click();
      await expect(page).toHaveURL(`${info.project.use.baseURL}/handbook/`);
      await expect(page.locator(".md-content article h1")).toHaveText(/^Handbook overview(?:¶)?$/);
      expect(await page.evaluate(() => window.bijuxPreferenceObservedDocument === document), "Ordinary instant navigation retains the actual Document").toBe(true);
      await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", "slate");
      await record("instant reader theme");
      await openDrawer(page);
      await navigation(page).locator(`a[href="${info.project.use.baseURL}/bijux-atlas/"]`).click();
      await expect(page).toHaveURL(`${info.project.use.baseURL}/bijux-atlas/`);
      await expect(page.locator(".md-content article h1")).toHaveText(/^Product overview(?:¶)?$/);
      await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", /default|slate/);
      await record("cross-site readable fallback");
      await expect.poll(() => page.evaluate(mode => window.bijuxStorageDenialObservations[mode], denial)).toBeGreaterThan(0);
      await openDrawer(page);
      await page.keyboard.press("Escape");
      await expect(page.locator("#__drawer")).not.toBeChecked();
      if (denial === "write") {
        // A writable getter/read path with exhausted storage is distinct from denial.
        await page.evaluate(() => { window.bijuxStorageDenialErrorName = "QuotaExceededError"; });
        await choose(page, "dark");
        await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", "slate");
        await expect.poll(() => page.evaluate(() => window.bijuxStorageDenialObservations.errors.includes("QuotaExceededError"))).toBe(true);
        expect(await page.evaluate(() => localStorage.getItem("bijux:theme")), "Quota failure does not claim durable persistence").toBeNull();
        await record("quota-exhausted session theme");
        await page.reload();
        await expect(page.locator("[data-bijux-theme-toggle]")).toHaveAttribute("data-bijux-theme-mode", "auto");
        await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", "default");
        await openDrawer(page);
        await page.keyboard.press("Escape");
        await expect(control(page, "drawer")).toBeFocused();
        await record("quota failure reload has no persisted choice");
      }
    } finally {
      await info.attach("independent-storage-denial-observations", {
        body: Buffer.from(JSON.stringify({ denial, observations }, null, 2)), contentType: "application/json",
      });
    }
  });
}

async function preference(page, mode, scheme) {
  await expect(page.locator("[data-bijux-theme-toggle]")).toHaveAttribute("data-bijux-theme-mode", mode);
  await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", scheme);
  const selected = await page.locator("input[name='__palette']:checked").evaluate(node => ({
    index: [...document.querySelectorAll("input[name='__palette']")].indexOf(node),
    media: node.getAttribute("data-md-color-media"),
    stored: JSON.parse(localStorage.getItem("bijux:theme")),
    material: window.__md_get("__palette"),
  }));
  expect(selected.stored.mode).toBe(mode);
  expect(selected.material.index).toBe(selected.index);
  expect(selected.media).toBe(mode === "auto" ? "(prefers-color-scheme)" : `(prefers-color-scheme: ${mode})`);
}

async function choose(page, mode) {
  const toggle = page.locator("[data-bijux-theme-toggle]");
  for (let attempt = 0; attempt < 3 && await toggle.getAttribute("data-bijux-theme-mode") !== mode; attempt++) {
    const before = await toggle.getAttribute("data-bijux-theme-mode");
    await toggle.click();
    await expect(toggle).toHaveAttribute("data-bijux-theme-mode", { auto: "light", light: "dark", dark: "auto" }[before]);
  }
  await expect(toggle).toHaveAttribute("data-bijux-theme-mode", mode);
}

test("writable theme choice survives reload, instant reading and native product navigation", async ({ page }, info) => {
  await page.emulateMedia({ colorScheme: "light" });
  await phone(page);
  await choose(page, "dark");
  await preference(page, "dark", "slate");
  await page.reload();
  await preference(page, "dark", "slate");
  const previous = await page.evaluateHandle(() => document);
  try {
    await openDrawer(page);
    await navigation(page).locator("summary").filter({ hasText: /^Handbook$/ }).click();
    await navigation(page).locator("a[href='handbook/'], a[href$='/handbook/']").filter({ hasText: /^\s*Overview\s*$/ }).click();
    await expect(page).toHaveURL(`${info.project.use.baseURL}/handbook/`);
    await expect(page.locator("main h1")).toHaveText(/^Handbook overview(?:¶)?$/);
    expect(await page.evaluate(old => old === document, previous)).toBe(true);
    await preference(page, "dark", "slate");
    await openDrawer(page);
    await navigation(page).locator(`a[href="${info.project.use.baseURL}/bijux-atlas/"]`).click();
    await expect(page).toHaveURL(`${info.project.use.baseURL}/bijux-atlas/`);
    await expect(page.locator("main h1")).toHaveText(/^Product overview(?:¶)?$/);
    // A full product navigation creates a new global; the local handle remains
    // evidence for the preceding same-document journey, not a cross-page claim.
    await preference(page, "dark", "slate");
    await choose(page, "light");
    await preference(page, "light", "default");
    await page.reload();
    await preference(page, "light", "default");
  } finally { await previous.dispose(); }
});

test("automatic palette follows live system changes while explicit choices retain ownership", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await phone(page);
  // Exercise the actual user cycle to persist Auto rather than inject storage.
  await choose(page, "dark");
  await choose(page, "auto");
  await preference(page, "auto", "default");
  for (const system of ["dark", "light", "dark"]) {
    await page.emulateMedia({ colorScheme: system });
    await preference(page, "auto", system === "dark" ? "slate" : "default");
  }
  await choose(page, "light");
  for (const system of ["light", "dark"]) {
    await page.emulateMedia({ colorScheme: system });
    await preference(page, "light", "default");
  }
  await choose(page, "dark");
  for (const system of ["dark", "light"]) {
    await page.emulateMedia({ colorScheme: system });
    await preference(page, "dark", "slate");
  }
  await page.reload();
  await preference(page, "dark", "slate");
});
