const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { test, expect } = require("@playwright/test");
const { nativeAnswer } = require("./helpers/search");
const generated = path.resolve(
  process.env.BIJUX_GENERATED_ROOT ||
    path.join(__dirname, "../../../../artifacts/bijux-docs/generated"),
);
const manifest = JSON.parse(
  fs.readFileSync(path.join(generated, "manifest.json")),
);
const sha = (data) => crypto.createHash("sha256").update(data).digest("hex");
const query = (page) => page.locator("[data-md-component='search-query']");
const opener = (page) =>
  page.locator("[data-bijux-header-control='search-toggle']");
const toggle = (page) => page.locator("#__search");
const definitions = [
  { name: "owned phone", width: 320 },
  { name: "owned compact", width: 768 },
  { name: "owned desktop", width: 1440 },
  { name: "owned forced-colors desktop", width: 1440, forcedColors: "active" },
  { name: "native phone", width: 320, native: true },
  { name: "native inline desktop", width: 1440, native: true },
  { name: "owned resize and instant history", width: 1440, history: true },
  {
    name: "native resize and instant history",
    width: 1440,
    native: true,
    history: true,
  },
];

const tabKey = (page, reverse = false) =>
  `${page.context().browser().browserType().name() === "webkit" ? "Alt+" : ""}${reverse ? "Shift+" : ""}Tab`;

async function focusThroughTab(page, target, record, reverse = false) {
  for (
    let step = 0;
    step < 80 &&
    !(await target.evaluate((node) => node === document.activeElement));
    step++
  ) {
    await page.keyboard.press(tabKey(page, reverse));
    record.push(
      await page.evaluate(() => ({
        tag: document.activeElement.tagName,
        name: document.activeElement.getAttribute("aria-label"),
        className: document.activeElement.className,
        searchOpen: document.getElementById("__search").checked,
      })),
    );
  }
  await expect(target).toBeFocused();
}

async function transit(page, definition, evidence) {
  const inline = definition.native && (await opener(page).isHidden());
  const invoker = inline ? query(page) : opener(page);
  if (process.env.BIJUX_SEARCH_INVOKER_BASELINE === "1" && !definition.native) {
    await focusThroughTab(page, invoker, evidence.tabStops);
    await page.keyboard.press(tabKey(page));
    await expect(query(page)).toBeFocused();
    await expect(toggle(page)).toBeChecked();
    await page.keyboard.press("Escape");
    await expect(invoker).toBeFocused();
    await expect(toggle(page)).not.toBeChecked();
    await page.keyboard.press(tabKey(page));
    await expect(query(page)).toBeFocused();
    await expect(toggle(page)).toBeChecked();
    evidence.trap =
      "Forward Tab opens inline query; Escape returns visible button; next forward Tab opens the same query again";
    throw new Error(
      "Owned duplicate Search invokers trap forward header traversal",
    );
  }
  if (!inline) {
    await expect(query(page)).toBeHidden();
    await expect(opener(page)).toHaveAccessibleName(
      definition.native ? "Search" : "Open search",
    );
  } else {
    await expect(query(page)).toBeVisible();
    await expect(opener(page)).toBeHidden();
  }
  const readerFocus =
    definition.fromReader ||
    definition.previousSearchFocus ||
    (await page.evaluate(() =>
      Boolean(
        document.activeElement.closest(".md-content, .md-footer, .md-sidebar"),
      ),
    ));
  evidence.initialDirection = readerFocus
    ? "Shift-Tab from restored reader focus"
    : "Tab from document/header focus";
  await focusThroughTab(page, invoker, evidence.tabStops, readerFocus);
  if (inline) {
    await expect(toggle(page)).toBeChecked();
    await page.keyboard.press("Escape");
    await expect(toggle(page)).not.toBeChecked();
    await expect(invoker).toBeFocused();
  }
  const forwardTransit = [];
  for (let step = 0; step < 4; step++) {
    await page.keyboard.press(tabKey(page));
    await expect(toggle(page)).not.toBeChecked();
    forwardTransit.push(
      await page.evaluate(() => ({
        tag: document.activeElement.tagName,
        className: document.activeElement.className,
      })),
    );
    if (!(await page.locator(".md-search :focus").count())) break;
  }
  evidence.forwardTransit = forwardTransit;
  await expect.poll(() => page.locator(".md-search :focus").count()).toBe(0);
  // Observe the complete admitted debounce window without injecting toggle state.
  await page.waitForTimeout(200);
  await expect(toggle(page)).not.toBeChecked();
  evidence.afterForward = await page.evaluate(() => ({
    tag: document.activeElement.tagName,
    name: document.activeElement.getAttribute("aria-label"),
    className: document.activeElement.className,
  }));
  await focusThroughTab(page, invoker, evidence.tabStops, true);
  if (inline) {
    await expect(toggle(page)).toBeChecked();
    await page.keyboard.press("Escape");
    await expect(toggle(page)).not.toBeChecked();
  }
  await page.keyboard.press(tabKey(page, true));
  await expect(toggle(page)).not.toBeChecked();
  await expect.poll(() => page.locator(".md-search :focus").count()).toBe(0);
  evidence.afterBackward = await page.evaluate(() => ({
    tag: document.activeElement.tagName,
    name: document.activeElement.getAttribute("aria-label"),
    className: document.activeElement.className,
  }));
  await focusThroughTab(page, invoker, evidence.tabStops);
  if (!inline) await page.keyboard.press("Space");
  await expect(toggle(page)).toBeChecked();
  await expect(query(page)).toBeFocused();
  await page.keyboard.press("ControlOrMeta+A");
  await page.keyboard.insertText("resilient navigation");
  const answer = await nativeAnswer(page);
  evidence.answer = {
    href: await answer.getAttribute("href"),
    text: await answer.textContent(),
  };
  await page.keyboard.press("Escape");
  await expect(toggle(page)).not.toBeChecked();
  await expect(invoker).toBeFocused();
  if (!inline) await expect(query(page)).toBeHidden();
  for (let step = 0; step < 4; step++) {
    await page.keyboard.press(tabKey(page));
    await expect(toggle(page)).not.toBeChecked();
    if (!(await page.locator(".md-search :focus").count())) break;
  }
  await expect.poll(() => page.locator(".md-search :focus").count()).toBe(0);
  await page.waitForTimeout(200);
  await expect(toggle(page)).not.toBeChecked();
  if (inline) await query(page).click();
  else await opener(page).click();
  await expect(toggle(page)).toBeChecked();
  const close = page.getByRole("button", { name: "Close search", exact: true });
  await expect(close).toBeVisible();
  await close.click();
  await expect(toggle(page)).not.toBeChecked();
  await expect(invoker).toBeFocused();
  await expect(close).toBeHidden();
  evidence.closed = true;
  // Modified selection preserves the closed inline focus and browser default.
  await page.keyboard.press("ControlOrMeta+A");
  await expect(toggle(page)).not.toBeChecked();
  if (inline) await page.keyboard.press(tabKey(page));
  // Retain all three global shortcuts implemented by the admitted Material bundle.
  for (const key of ["/", "f", "s"]) {
    await page.keyboard.press(key);
    await expect(toggle(page)).toBeChecked();
    await expect(query(page)).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(toggle(page)).not.toBeChecked();
    await expect(invoker).toBeFocused();
    if (inline) await page.keyboard.press(tabKey(page));
  }
  evidence.shortcut =
    "Unmodified slash/f/s open; Escape restores; modified select retains closed state";
}

for (const definition of definitions) {
  test(`${definition.name} exposes one search invoker and permits header traversal`, async ({
    browser,
  }, info) => {
    info.annotations.push({
      type: "browser-version",
      description: browser.version(),
    });
    const context = await browser.newContext({
      viewport: { width: definition.width, height: 900 },
      forcedColors: definition.forcedColors || "none",
    });
    const page = await context.newPage();
    const evidence = {
      definition,
      engine: info.project.use.browserName,
      version: browser.version(),
      manifest_sha256: sha(
        fs.readFileSync(path.join(generated, "manifest.json")),
      ),
      keyboard_protocol:
        info.project.use.browserName === "webkit"
          ? "Option-Tab/Option-Shift-Tab for complete native focus traversal"
          : "Tab/Shift-Tab",
      tabStops: [],
      errors: [],
      missing: [],
      started_at: new Date().toISOString(),
    };
    page.on("pageerror", (error) =>
      evidence.errors.push({ name: error.name, message: error.message }),
    );
    page.on("response", (response) => {
      if (
        new URL(response.url()).origin === info.project.use.baseURL &&
        response.status() >= 400
      )
        evidence.missing.push({
          url: response.url(),
          status: response.status(),
        });
    });
    const route = definition.native
      ? "/fixtures/native-header/"
      : "/bijux-core/";
    try {
      await page.goto(info.project.use.baseURL + route);
      if (!definition.native)
        await expect(page.locator("body")).toHaveAttribute(
          "data-bijux-drawer-ready",
          "true",
        );
      await transit(page, definition, evidence);
      if (definition.history) {
        evidence.resize = [];
        for (const width of [768, 320, 1440]) {
          const previousSearchFocus = await page.evaluate(() =>
            Boolean(document.activeElement.closest(".md-search")),
          );
          await page.setViewportSize({ width, height: 900 });
          const resizeEvidence = { width, previousSearchFocus, tabStops: [] };
          evidence.resize.push(resizeEvidence);
          await transit(
            page,
            { ...definition, width, previousSearchFocus },
            resizeEvidence,
          );
        }
        const timeOrigin = await page.evaluate(() => performance.timeOrigin);
        const returnHeading = await page
          .locator(".md-content h1")
          .textContent();
        await page.locator("a.md-footer__link--next").click();
        await expect(page).not.toHaveURL(info.project.use.baseURL + route);
        expect(await page.evaluate(() => performance.timeOrigin)).toBe(
          timeOrigin,
        );
        await page.goBack();
        await expect(page).toHaveURL(info.project.use.baseURL + route);
        await expect(page.locator(".md-content h1")).toHaveText(returnHeading);
        expect(await page.evaluate(() => performance.timeOrigin)).toBe(
          timeOrigin,
        );
        evidence.historyTransit = { tabStops: [] };
        await transit(
          page,
          { ...definition, fromReader: true },
          evidence.historyTransit,
        );
        evidence.history = { timeOrigin, retainedDocument: true };
      }
      const beforeResultOrigin = await page.evaluate(
        () => performance.timeOrigin,
      );
      const beforeResultURL = page.url();
      const beforeResultHeading = await page
        .locator(".md-content h1")
        .textContent();
      const inline = definition.native && (await opener(page).isHidden());
      if (inline) await query(page).click();
      else await opener(page).click();
      await page.keyboard.press("ControlOrMeta+A");
      await page.keyboard.insertText("resilient navigation");
      const answer = await nativeAnswer(page);
      const destination = await answer.getAttribute("href");
      // Sequential modal containment and native result selection are distinct.
      for (const key of ["Tab", "Tab", "Shift+Tab", "Shift+Tab"]) {
        await page.keyboard.press(key);
        await expect(
          page.locator("[data-md-component='search'] :focus"),
        ).toHaveCount(1);
        await expect(toggle(page)).toBeChecked();
      }
      for (
        let step = 0;
        step < 40 &&
        !(await answer.evaluate((node) => node === document.activeElement));
        step++
      ) {
        await page.keyboard.press("ArrowDown");
      }
      await expect(answer).toBeFocused();
      await page.keyboard.press("ArrowUp");
      await expect(answer).not.toBeFocused();
      await page.keyboard.press("ArrowDown");
      await expect(answer).toBeFocused();
      await page.keyboard.press("Enter");
      await expect(page).toHaveURL(destination);
      await expect(page.locator(".md-content h1")).toContainText(
        "leaf destination",
      );
      await expect(toggle(page)).not.toBeChecked();
      expect(await page.evaluate(() => performance.timeOrigin)).toBe(
        beforeResultOrigin,
      );
      await page.goBack();
      await expect(page).toHaveURL(beforeResultURL);
      await expect(page.locator(".md-content h1")).toHaveText(
        beforeResultHeading,
      );
      expect(await page.evaluate(() => performance.timeOrigin)).toBe(
        beforeResultOrigin,
      );
      evidence.returnTransit = { tabStops: [] };
      await transit(
        page,
        { ...definition, fromReader: true },
        evidence.returnTransit,
      );
      evidence.resultNavigation = {
        destination,
        ordinaryKeyboard:
          "Native ArrowDown/ArrowUp/ArrowDown then Enter; separate Tab/Shift-Tab containment",
        retainedDocument: true,
        backRestored: beforeResultURL,
      };
      expect(evidence.errors).toEqual([]);
      expect(evidence.missing).toEqual([]);
      evidence.result = "pass";
    } catch (error) {
      evidence.result = "fail";
      evidence.failure = { message: error.message, stack: error.stack };
      throw error;
    } finally {
      evidence.focus = await page.evaluate(() => ({
        tag: document.activeElement.tagName,
        className: document.activeElement.className,
        searchOpen: document.getElementById("__search").checked,
      }));
      await context.close();
      evidence.closed_at = new Date().toISOString();
      fs.writeFileSync(
        info.outputPath("search-invoker-evidence.json"),
        JSON.stringify(evidence, null, 2) + "\n",
      );
      await info.attach("search-invoker-evidence", {
        body: Buffer.from(JSON.stringify(evidence, null, 2)),
        contentType: "application/json",
      });
    }
  });
}
