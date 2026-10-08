const fs = require("node:fs");
const { test, expect, ready } = require("./helpers/document");
const query = page => page.locator("[data-md-component='search-query']");
const toggle = page => page.locator("#__search");
const control = page => page.locator("[data-bijux-header-control='search-toggle']");
const tab = (info, reverse = false) => `${info.project.use.browserName === "webkit" ? "Alt+" : ""}${reverse ? "Shift+" : ""}Tab`;
const definitions = [
  { kind: "owned", route: "/bijux-core/", width: 390 },
  { kind: "owned", route: "/bijux-core/", width: 1440 },
  { kind: "native", route: "/fixtures/native-header/", width: 390 },
  { kind: "native", route: "/fixtures/native-header/", width: 1440 },
];
async function record(info, observations) {
  const file = info.outputPath("shortcut-modality.json");
  fs.writeFileSync(file, JSON.stringify({ observations }, null, 2) + "\n");
  await info.attach("shortcut-modality", { path: file, contentType: "application/json" });
}
async function keyboardSearch(page, info) {
  const invoker = await control(page).isVisible() ? control(page) : query(page);
  for (let step = 0; step < 160 && !await invoker.evaluate(node => node === document.activeElement); step++)
    await page.keyboard.press(tab(info, true));
  await expect(invoker).toBeFocused();
  if (await control(page).isVisible()) await page.keyboard.press("Space");
  await expect(query(page)).toBeFocused();
  await expect(toggle(page)).toBeChecked();
  return invoker;
}

for (const definition of definitions) {
  test(`${definition.kind} at ${definition.width}px keeps character and modifier shortcuts outside global search`, async ({ page }, info) => {
    const observations = [];
    await page.setViewportSize({ width: definition.width, height: 900 });
    await ready(page, definition.route);
    const document = await page.evaluateHandle(() => window.document);
    try {
      for (const key of ["/", "f", "s", "Control+f", "Meta+f", "Alt+s", "ControlOrMeta+k"]) {
        await page.locator("main h1").click();
        await expect(toggle(page)).not.toBeChecked();
        await page.keyboard.press(key);
        const state = await page.evaluate(() => ({ open: document.getElementById("__search").checked,
          searchFocused: document.activeElement === document.querySelector("[data-md-component=search-query]") }));
        observations.push({ ...definition, key, ...state });
        await expect(toggle(page)).not.toBeChecked();
        await expect(query(page)).not.toBeFocused();
        expect(await document.evaluate(node => node === window.document)).toBe(true);
      }
      const advertised = await page.locator("[aria-keyshortcuts]").evaluateAll(nodes => nodes.map(node => node.getAttribute("aria-keyshortcuts")));
      expect(advertised.flatMap(value => value.split(/\s+/)).filter(value => ["/", "f", "s"].includes(value.toLowerCase()))).toEqual([]);
    } finally {
      await document.dispose();
      await record(info, observations);
    }
  });
}

for (const definition of definitions.filter(item => item.width === 390)) {
  test(`${definition.kind} focused author fields and native search retain typing keyboard results and history`, async ({ page }, info) => {
    const observations = [];
    for (const width of [390, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      const route = definition.route + "search-modality/";
      await ready(page, route);
      for (const name of ["Reader notes", "Editable reader notes"]) {
        const editor = page.getByRole("textbox", { name, exact: true });
        await editor.click();
        await page.keyboard.type("f/s");
        if (name === "Reader notes") await expect(editor).toHaveValue("f/s");
        else await expect(editor).toHaveText("f/s");
        await expect(editor).toBeFocused();
        await expect(toggle(page)).not.toBeChecked();
        observations.push({ width, editor: name, value: "f/s" });
      }
      await page.locator("main h1").click();
      const invoker = await keyboardSearch(page, info);
      await page.keyboard.press("ControlOrMeta+A");
      await page.keyboard.press("Backspace");
      await page.keyboard.type("f/s");
      await expect(query(page)).toHaveValue("f/s");
      await page.keyboard.press("ControlOrMeta+A");
      await page.keyboard.type("resilient navigation");
      const result = page.locator(".md-search-result__link").first();
      await expect(result).toBeVisible();
      const destination = await result.evaluate(node => node.href), original = page.url();
      const document = await page.evaluateHandle(() => window.document);
      try {
        await page.keyboard.press("ArrowDown");
        await expect(result).toBeFocused();
        await page.keyboard.press("Enter");
        await expect(page).toHaveURL(destination);
        await expect(page.locator("main")).toContainText("resilient navigation");
        expect(await document.evaluate(node => node === window.document)).toBe(true);
        await page.goBack();
        await expect(page).toHaveURL(original);
        expect(await document.evaluate(node => node === window.document)).toBe(true);
        await page.locator("main h1").click();
        const restored = await keyboardSearch(page, info);
        await page.keyboard.press("Escape");
        await expect(toggle(page)).not.toBeChecked();
        await expect(restored).toBeFocused();
        observations.push({ width, destination, sameDocument: true, keyboard: "Tab/Space, ArrowDown/Enter, Back, Escape" });
      } finally { await document.dispose(); }
    }
    await record(info, observations);
  });
}
