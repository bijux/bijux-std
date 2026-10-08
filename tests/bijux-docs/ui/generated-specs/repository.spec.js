const { test, expect, control, ready, phone } = require("./helpers/document");

async function observeFacts(page) {
  const requests = [];
  page.on("request", request => {
    if (new URL(request.url()).hostname === "api.github.com") requests.push(request.url());
  });
  await page.addInitScript(() => {
    window.bijuxPolicyViolations = [];
    document.addEventListener("securitypolicyviolation", event => window.bijuxPolicyViolations.push({ uri: event.blockedURI, directive: event.effectiveDirective }));
  });
  return requests;
}

async function noFacts(page, requests) {
  await expect(page.locator('[data-md-component="source"]')).toHaveCount(0);
  expect(requests).toEqual([]);
  expect(await page.evaluate(() => window.bijuxPolicyViolations.filter(event => event.uri.includes("api.github.com")))).toEqual([]);
  expect(await page.evaluate(() => Object.keys(sessionStorage).filter(key => key.endsWith(".__source")))).toEqual([]);
}

test("default cold repository link and instant destinations preserve navigation without facts", async ({ page }) => {
  const requests = await observeFacts(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await ready(page, "/bijux-core/platform/");
  await noFacts(page, requests);
  const documentIdentity = await page.evaluate(() => window.bijuxDocumentIdentity = crypto.randomUUID());
  await page.locator("main a[href]").filter({ hasText: "Getting started" }).first().click();
  await expect(page).toHaveURL(/\/bijux-core\/platform\/start\/$/);
  await expect(page.locator("h1")).toHaveText(/^Platform getting started(?:¶)?$/);
  expect(await page.evaluate(() => window.bijuxDocumentIdentity)).toBe(documentIdentity);
  await noFacts(page, requests);
  const repository = page.locator(".md-header__source > a.md-source");
  await expect(repository).toBeVisible();
  await expect(repository).toHaveAttribute("href", "https://github.com/bijux/bijux-core");
  await expect(repository).toHaveAccessibleName(/bijux\/bijux-core/);
  await page.context().route("https://github.com/bijux/bijux-core", route => route.fulfill({ contentType: "text/html", body: "<title>Repository destination fixture</title><h1>Bijux Core repository destination</h1>" }));
  const [destination] = await Promise.all([page.waitForEvent("popup"), repository.click()]);
  try {
    await expect(destination).toHaveURL("https://github.com/bijux/bijux-core");
    await expect(destination.locator("h1")).toHaveText("Bijux Core repository destination");
  } finally {
    await destination.close();
  }
  expect(requests).toEqual([]);
});

test("default cold phone search retains native results and a real reader destination", async ({ page }) => {
  const requests = await observeFacts(page);
  await phone(page, "/bijux-core/");
  await control(page, "search").click();
  await page.locator('[data-md-component="search-query"]').pressSequentially("resilient navigation");
  const answer = page.locator(".md-search-result__link").first();
  await expect(answer).toBeVisible();
  await answer.click();
  await expect(page).toHaveURL(/\/bijux-core\//);
  await expect(page.locator("main")).toContainText("resilient navigation");
  await noFacts(page, requests);
});
