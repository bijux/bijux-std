const { expect } = require("./document");

async function nativeAnswer(page, text = "resilient navigation") {
  let href;
  // Native result visibility alone can belong to a partial input. The authored
  // leaf destination and full matched terms must agree with the settled query.
  await expect.poll(async () => {
    href = await page.evaluate(text => {
      const query = document.querySelector("[data-md-component='search-query']");
      if (query?.value !== text || window.bijuxSearchWorker?.state.stage !== "worker-ready") return "";
      for (const link of document.querySelectorAll(".md-search-result__link")) {
        const url = new URL(link.href, location.href);
        if (link.getClientRects().length && /\/details\/leaf\/$/.test(url.pathname) && url.searchParams.get("h") === text) return link.href;
      }
      return "";
    }, text);
    return href;
  }, { message: "The latest native query must return its full known-answer terms and authored route" }).not.toBe("");
  const link = page.locator(`.md-search-result__link[href=${JSON.stringify(href)}]`).first();
  await expect(link).toBeVisible();
  return link;
}

async function observeClearWhileTyping(page, text) {
  await page.evaluate(() => {
    const control = document.querySelector('.md-search__options > button[type="reset"]');
    if (!control) throw new Error("The native Clear control is absent");
    const observation = { active: true, frames: [] };
    window.bijuxSearchClearObservation = observation;
    function read() {
      const style = getComputedStyle(control);
      const rectangle = control.getBoundingClientRect();
      const point = { x: rectangle.x + rectangle.width / 2, y: rectangle.y + rectangle.height / 2 };
      const hit = document.elementFromPoint(point.x, point.y);
      observation.frames.push({
        at: performance.now(), value: control.form.querySelector('[data-md-component="search-query"]').value,
        width: rectangle.width, height: rectangle.height, x: rectangle.x, y: rectangle.y,
        opacity: Number(style.opacity), pointerEvents: style.pointerEvents, transform: style.transform,
        centerOwned: hit === control || control.contains(hit),
        inViewport: rectangle.x >= 0 && rectangle.y >= 0 && rectangle.right <= innerWidth && rectangle.bottom <= innerHeight,
      });
      if (observation.active) requestAnimationFrame(read);
    }
    requestAnimationFrame(read);
  });
  try {
    await page.keyboard.type(text, { delay: 25 });
  } finally {
    await page.evaluate(() => { window.bijuxSearchClearObservation.active = false; });
  }
  return page.evaluate(() => window.bijuxSearchClearObservation.frames);
}

function assertClearTarget(frames) {
  const live = frames.filter(frame => frame.value && frame.opacity > 0 && frame.pointerEvents !== "none");
  expect(live.length, "Observe the real clickable Clear target during ordinary typing").toBeGreaterThan(0);
  for (const frame of live) {
    expect(frame.width, "Clear must not shrink below the applicable 24 CSS-pixel target minimum").toBeGreaterThanOrEqual(24);
    expect(frame.height, "Clear must not shrink below the applicable 24 CSS-pixel target minimum").toBeGreaterThanOrEqual(24);
    expect(frame.centerOwned, "The measured target must own its pointer center").toBe(true);
    expect(frame.inViewport, "The complete Clear target must remain in the viewport").toBe(true);
  }
  return live;
}

async function clearKnownResults(page, text) {
  const query = page.locator('[data-md-component="search-query"]');
  const clear = page.getByRole("button", { name: "Clear", exact: true });
  await expect(query).toHaveValue(text);
  await expect(page.locator(".md-search-result__link:visible").first()).toBeVisible();
  const target = await clear.evaluate(node => {
    const r = node.getBoundingClientRect();
    const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
    return { width: r.width, height: r.height, centerOwned: hit === node || node.contains(hit),
      form: { width: node.form.getBoundingClientRect().width, height: node.form.getBoundingClientRect().height } };
  });
  expect(target.width).toBeGreaterThanOrEqual(24);
  expect(target.height).toBeGreaterThanOrEqual(24);
  expect(target.centerOwned).toBe(true);
  await clear.click({ position: { x: 4, y: 4 } });
  await expect(query).toHaveValue("");
  await expect(query).toBeFocused();
  await expect(page.locator(".md-search-result__meta")).toContainText("Type to start searching");
  await expect(page.locator(".md-search-result__link:visible")).toHaveCount(0);
  return target;
}
module.exports = { nativeAnswer, observeClearWhileTyping, assertClearTarget, clearKnownResults };
