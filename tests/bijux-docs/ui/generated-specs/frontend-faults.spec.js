const crypto = require("node:crypto");
const { test, expect } = require("./helpers/document");
const digest = bytes => crypto.createHash("sha256").update(bytes).digest("hex");
async function ready(page) {
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-bijux-viewport", "phone");
  await expect(page.locator("main")).toBeVisible();
}
async function hiddenStrips(page) {
  const count = await page.locator("[data-bijux-detail-strip][hidden], [data-bijux-course-strip][hidden]").count();
  expect(count).toBeGreaterThan(0);
  const painted = await page.locator("[data-bijux-detail-strip][hidden], [data-bijux-course-strip][hidden]").evaluateAll(nodes => nodes.filter(node => node.getClientRects().length && getComputedStyle(node).visibility !== "hidden").length);
  expect(painted, "Hidden navigation must not paint").toBe(0);
}
async function ordinaryOpen(page) {
  await page.locator("[data-bijux-header-control='drawer-toggle']").click();
  await expect(page.locator("#__drawer"), "Ordinary navigation toggle must actually open").toBeChecked();
  await expect(page.locator(".md-sidebar--primary a:visible").first()).toBeInViewport();
}
async function mutatedAsset(page, selector, extra, observed) {
  if (process.env.BIJUX_FRONTEND_FAULT_MODE === "clean") return;
  if (process.env.BIJUX_FRONTEND_FAULT_MODE !== "fault") throw new Error("Explicit clean/fault mode required");
  await page.route(selector, async route => {
    const original = await route.fetch();
    const bytes = await original.body();
    const output = Buffer.concat([bytes, Buffer.from("\n" + extra + "\n")]);
    observed.push({ url:route.request().url(), original_sha256:digest(bytes), output_sha256:digest(output), additional_bytes_sha256:digest(Buffer.from(extra)), original_bytes:bytes.length, output_bytes:output.length });
    await route.fulfill({ response:original, body:output });
  });
}
async function record(info, name, data) {
  await info.attach(name, { body:Buffer.from(JSON.stringify(data, null, 2)), contentType:"application/json" });
}
test("unmodified production ribbons and ordinary drawer input qualify", async ({ page }) => {
  await ready(page); await hiddenStrips(page); await ordinaryOpen(page);
  await page.keyboard.press("Escape");
  await expect(page.locator("[data-bijux-header-control='drawer-toggle']")).toBeFocused();
});
test("painted hidden ribbons fail the real navigation assertion", async ({ page }, info) => {
  const mutations=[];
  await mutatedAsset(page, "**/*.css", "html body header [data-bijux-detail-strip][hidden], html body header [data-bijux-course-strip][hidden] { display:block !important; visibility:visible !important; }", mutations);
  await ready(page);
  try { await hiddenStrips(page); } finally { await record(info,"hidden-ribbon-asset-procedure",{mutations,observed:await page.locator("[data-bijux-detail-strip][hidden], [data-bijux-course-strip][hidden]").evaluateAll(nodes=>nodes.map(node=>({text:node.textContent.trim(),width:node.getBoundingClientRect().width,height:node.getBoundingClientRect().height,display:getComputedStyle(node).display}))) }); }
});
test("blocked ordinary toggle fails actual opened-state acceptance", async ({ page }, info) => {
  const mutations=[];
  await mutatedAsset(page, "**/bootstrap.js", 'window.addEventListener("click", event => { const control = event.target.closest && event.target.closest("[data-bijux-header-control=drawer-toggle]"); if (control) { event.preventDefault(); event.stopImmediatePropagation(); } }, true);', mutations);
  await ready(page);
  try { await ordinaryOpen(page); } finally { await record(info,"blocked-toggle-asset-procedure",{mutations,observed:await page.locator("#__drawer").isChecked(),control:await page.locator("[data-bijux-header-control='drawer-toggle']").evaluate(node=>({tag:node.tagName,name:node.getAttribute("aria-label"),width:node.getBoundingClientRect().width,height:node.getBoundingClientRect().height}))}); }
});

test("trusted palette activation rejects uncaught runtime failure", async ({ page }, info) => {
  const mutations=[];
  await mutatedAsset(page, "**/bootstrap.js", 'window.addEventListener("click", event => { if (event.isTrusted && event.target.closest("[data-bijux-theme-toggle]")) throw new Error("bijux frontend runtime fault witness"); });', mutations);
  await ready(page);
  await page.locator("[data-bijux-theme-toggle]").click();
  await record(info,"runtime-error-asset-procedure",{mutations});
});
