const { test, expect } = require("@playwright/test");
const fs = require("node:fs"), path = require("node:path");
const generated = process.env.BIJUX_GENERATED_ROOT || path.resolve(__dirname, "../../../../artifacts/bijux-docs/generated");
const figures = page => page.locator("main .bijux-diagram");
const sources = page => figures(page).locator(".bijux-diagram-source code");
function authored(name) {
  const markdown = fs.readFileSync(path.join(generated, "inputs/hub/docs", name + ".md"), "utf8");
  return [...markdown.matchAll(/```mermaid\n([\s\S]*?)\n```/g)].map(match => match[1] + "\n");
}
async function rejected(figure) {
  await expect(figure.getByRole("status")).toContainText("preview unavailable");
  await expect(figure.locator("details")).toHaveAttribute("open", "");
  await expect(figure.locator(".bijux-diagram-preview > svg")).toHaveCount(0);
  await expect(figure.getByRole("button", { name: "Retry diagram", exact: true })).toBeVisible();
}
async function admitted(figure, title) {
  const svg = figure.locator(".bijux-diagram-preview > svg");
  await expect(svg).toHaveCount(1);
  await expect(svg).toHaveAttribute("role", "graphics-document document");
  await expect(svg.locator("title")).toHaveText(title);
  await expect(svg.locator("desc")).not.toBeEmpty();
  await expect(figure.locator("details")).not.toHaveAttribute("open");
  expect(await svg.evaluate(node => {
    const bounds = node.getBoundingClientRect();
    return bounds.width > 0 && bounds.height > 0;
  })).toBe(true);
}
async function theme(page) {
  const previous = await page.locator("body").getAttribute("data-md-color-scheme");
  await page.getByRole("button", { name: /^Theme mode:/ }).click();
  if (await page.locator("body").getAttribute("data-md-color-scheme") === previous)
    await page.getByRole("button", { name: /^Theme mode:/ }).click();
  await expect(page.locator("body")).not.toHaveAttribute("data-md-color-scheme", previous);
}
test.beforeEach(async ({ browser }, info) => {
  info.annotations.push({ type: "browser-version", description: browser.version() });
});
async function observe(page, info, journey) {
  const errors = [], requests = [], origin = new URL(info.project.use.baseURL).origin;
  page.on("pageerror", error => errors.push(error.message));
  page.on("request", request => { if (new URL(request.url()).origin !== origin) requests.push(request.url()); });
  // A request is recorded before the offline route can stop its network effect.
  await page.route("https://diagram.example.invalid/**", route => route.abort());
  try {
    await journey();
    expect(errors).toEqual([]);
    expect(requests).toEqual([]);
    expect(await page.evaluate(() => window.diagramAttack)).toBeUndefined();
  } finally {
    await info.attach("diagram-trust-observations", {
      body: Buffer.from(JSON.stringify({ errors, offOriginRequests: requests }, null, 2)), contentType: "application/json",
    });
  }
}
test("scientific comparisons, nested labels and state descriptions retain exact meaning in both themes", async ({ page }, info) => {
  await observe(page, info, async () => {
    await page.goto("/diagram-scientific/");
    await expect(figures(page)).toHaveCount(3);
    const expected = authored("diagram-scientific");
    for (let mode = 0; mode < 2; mode++) {
      await admitted(figures(page).nth(0), "Scientific comparison");
      await admitted(figures(page).nth(1), "Nested scientific reading");
      await admitted(figures(page).nth(2), "Scientific review states");
      await expect(figures(page).nth(0).locator("svg")).toContainText("Comparison x < y; probability α ≤ β");
      await expect(figures(page).nth(1).locator("svg")).toContainText("Nested cohort α ≤ β");
      await expect(figures(page).nth(1).locator("svg")).toContainText("Control x < y");
      await expect(figures(page).nth(2).locator("svg")).toContainText("α ≤ β");
      expect(await sources(page).allTextContents()).toEqual(expected);
      if (mode === 0) await theme(page);
    }
  });
});
test("structured configuration, nested resource markup and image shapes cannot escape the local renderer", async ({ page }, info) => {
  await observe(page, info, async () => {
    await page.goto("/diagram-resources/");
    await expect(figures(page)).toHaveCount(3);
    const expected = authored("diagram-resources");
    for (let mode = 0; mode < 2; mode++) {
      for (let index = 0; index < 3; index++) await rejected(figures(page).nth(index));
      expect(await sources(page).allTextContents()).toEqual(expected);
      if (mode === 0) await theme(page);
    }
    const retry = figures(page).nth(0).getByRole("button", { name: "Retry diagram", exact: true });
    await retry.focus(); await page.keyboard.press("Enter");
    await rejected(figures(page).nth(0));
    expect(await sources(page).allTextContents()).toEqual(expected);
  });
});
test("malformed, excessive text and excessive edge inputs isolate failure while later reader diagrams remain usable", async ({ page }, info) => {
  await observe(page, info, async () => {
    await page.goto("/diagram-limits/");
    await expect(figures(page)).toHaveCount(6);
    const expected = authored("diagram-limits");
    expect(expected[2].length).toBeGreaterThan(50000);
    expect(expected[4].match(/-->/g)).toHaveLength(501);
    for (let mode = 0; mode < 2; mode++) {
      for (let index = 0; index < 6; index += 2) {
        await rejected(figures(page).nth(index));
        await admitted(figures(page).nth(index + 1), "Healthy isolation checkpoint");
        await expect(figures(page).nth(index + 1).locator("svg")).toContainText("Reader continues");
      }
      expect(await sources(page).allTextContents()).toEqual(expected);
      if (mode === 0) await theme(page);
    }
    const realm = await page.evaluate(() => window.bijuxDiagramTrustIdentity = crypto.randomUUID());
    await page.locator(".md-nav--primary a[href$='reading/']").first().click();
    await expect(page.locator("h1")).toContainText("Rich reading reference");
    await expect(figures(page).locator("svg")).toHaveCount(1);
    expect(await page.evaluate(() => window.bijuxDiagramTrustIdentity)).toBe(realm);
    await page.goBack();
    await expect(page).toHaveURL(/\/diagram-limits\/$/);
    await rejected(figures(page).nth(0));
    await admitted(figures(page).nth(5), "Healthy isolation checkpoint");
    expect(await sources(page).allTextContents()).toEqual(expected);
  });
});
