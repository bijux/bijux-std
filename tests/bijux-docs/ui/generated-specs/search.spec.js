const { test, expect, control, phone } = require("./helpers/document");
const { nativeAnswer, observeClearWhileTyping, assertClearTarget, clearKnownResults } = require("./helpers/search");
const query = (page) => page.locator("[data-md-component='search-query']");
async function search(page) {
  await phone(page, "/bijux-core/");
  await control(page, "search").click();
  await expect(query(page)).toBeFocused();
}
async function result(page) {
  await nativeAnswer(page);
}

test("generated hostile index records remain inert in the actual native search renderer", async ({ page }, info) => {
  const token = "bijuxhostilesink", requests = [], corpora = [], observations = [];
  let unsafeLocation = null;
  page.on("request", request => {
    if (new URL(request.url()).origin !== new URL(info.project.use.baseURL).origin) requests.push(request.url());
  });
  await page.addInitScript(() => { window.bijuxSearchAttack = 0; });
  await page.route("**/search/search_index.json", async route => {
    const response = await route.fetch(), index = await response.json();
    const intended = index.docs.find(doc => doc.location.includes("reading/"));
    expect(intended, "Hostile records derive from the generated reader's actual index schema").toBeTruthy();
    index.docs = [{ ...intended,
      title: `<span onclick='window.bijuxSearchAttack++'>${token} intended title</span><img src='https://hostile.invalid/image' onerror='window.bijuxSearchAttack++'>`,
      text: `<p>${token} inert reader text <code>intended_code</code></p><svg onload='window.bijuxSearchAttack++'><foreignObject><p>foreign content</p></foreignObject></svg><math><mtext><img src=x onerror='window.bijuxSearchAttack++'></mtext></math><template><img src=x onerror='window.bijuxSearchAttack++'></template><script>window.bijuxSearchAttack++</script><iframe src='https://hostile.invalid/frame'></iframe>`,
    }];
    if (unsafeLocation) index.docs.push({ ...intended, location: unsafeLocation, title: `${token} unsafe destination`, text: token });
    corpora.push(index);
    await route.fulfill({ response, json: index });
  });
  const opener = page.locator(".md-header__button[for='__search']"), results = page.locator(".md-search-result");
  const open = async () => {
    await phone(page, "/fixtures/native-header/");
    await opener.click();
    await expect(query(page)).toBeFocused();
    await page.keyboard.insertText(token);
  };
  const inertAnswer = async () => {
    const answer = page.locator(".md-search-result__link:visible").filter({ hasText: "inert reader text" });
    await expect(answer).toBeVisible({ timeout: 12_000 });
    await expect(results.locator("img, svg, math, template, script, iframe, [onclick], [onerror], [onload]")).toHaveCount(0);
    const state = await results.evaluate(node => ({ html: node.innerHTML, attack: window.bijuxSearchAttack,
      links: [...node.querySelectorAll("a[href]")].map(link => ({ href: link.href, authored: link.getAttribute("href"), text: link.textContent })) }));
    expect(state.attack).toBe(0);
    expect(state.links.every(link => !/^(?:javascript|data|vbscript):/i.test(link.authored))).toBe(true);
    expect(state.links.some(link => link.text.includes("unsafe destination"))).toBe(false);
    await expect(answer.locator("mark").first()).toHaveText(token);
    await expect(answer.locator("code")).toHaveText("intended_code");
    observations.push(state);
    return answer;
  };
  try {
    await open();
    const answer = await inertAnswer();
    await answer.click();
    await expect(page).toHaveURL(/\/reading\/(?:\?.*)?$/);
    await expect(page.locator("main h1")).toHaveText(/^Rich reading reference/);
    for (const location of ["javascript:window.bijuxSearchAttack++", "data:text/html,<script>parent.bijuxSearchAttack++</script>", "https://hostile.invalid/external", "/bijux-atlas/"]) {
      unsafeLocation = location;
      await open();
      await expect(page.locator(".bijux-search-recovery [role='status']")).toContainText("Search is unavailable", { timeout: 12_000 });
      await expect(page.locator(".md-search-result__link:visible")).toHaveCount(0);
      expect(await page.evaluate(() => window.bijuxSearchAttack)).toBe(0);
      unsafeLocation = null;
      const retry = page.getByRole("button", { name: "Retry search", exact: true });
      for (let attempt = 0; attempt < 12 && !await retry.evaluate(node => node === document.activeElement); attempt++) await page.keyboard.press("Tab");
      await expect(retry).toBeFocused();
      await page.keyboard.press("Enter");
      await inertAnswer();
    }
    expect(requests).toEqual([]);
  } finally {
    await info.attach("hostile-native-search-sink", { body: Buffer.from(JSON.stringify({ corpora, observations, requests, source: "Actual generated index plus source-authored hostile records; shipped native worker and result renderer", refusal: "Whole unsafe corpus with truthful keyboard Retry; no silent record filtering" }, null, 2)), contentType: "application/json" });
  }
});

test("paste-like text insertion produces results and reset clears query", async ({ page }, info) => {
  await search(page);
  await page.keyboard.insertText("resilient navigation");
  await result(page);
  await info.attach("native-search-ranking-and-highlight", { body: Buffer.from(JSON.stringify(await page.locator(".md-search-result__article").evaluateAll(nodes => nodes.map(node => ({ score: node.dataset.mdScore, title: node.querySelector("h1,h2")?.innerHTML, text: node.textContent, href: node.closest("a")?.getAttribute("href") }))), null, 2)), contentType: "application/json" });
  await page.locator("button[type='reset']").click();
  await expect(query(page)).toHaveValue("");
  await expect(page.locator(".md-search-result__meta")).toBeInViewport();
  await expect(page.locator(".md-search-result__meta")).toContainText("Type to start searching");
  await expect(page.locator(".md-search-result__link:visible")).toHaveCount(0);
  await phone(page, "/fixtures/native-header/");
  const nativeOpener = page.locator(".md-header__button[for='__search']");
  await expect(nativeOpener).toHaveCount(1);
  await expect(nativeOpener).toHaveJSProperty("tagName", "BUTTON");
  await expect(nativeOpener).toHaveAttribute("type", "button");
  await nativeOpener.click();
  await expect(query(page)).toBeFocused();
  await page.keyboard.insertText("resilient navigation");
  await result(page);
  await page.locator("button[type='reset']").click();
  await expect(query(page)).toHaveValue("");
  await expect(page.locator(".md-search-result__meta")).toContainText("Type to start searching");
  await page.keyboard.press("Escape");
  await expect(nativeOpener).toBeFocused();
  await page.keyboard.press("Space");
  await expect(query(page)).toBeFocused();
  await page.keyboard.insertText("resilient navigation");
  const answer = await nativeAnswer(page);
  const destination = await answer.getAttribute("href");
  await answer.click();
  await expect(page).toHaveURL(destination);
  await expect(page.locator("#__search")).not.toBeChecked();
  await page.goBack();
  await expect(page).toHaveURL(/\/fixtures\/native-header\/$/);
  await expect(nativeOpener).toHaveCount(1);
  await nativeOpener.click();
  await expect(query(page)).toBeFocused();
  if (await query(page).inputValue()) {
    await query(page).press("ControlOrMeta+A");
    await query(page).press("Backspace");
    await expect(query(page)).toHaveValue("");
  }
  const targets = [];
  for (const enlarged of [false, true]) {
    if (enlarged) {
      await page.setViewportSize({ width: 320, height: 700 });
      const size = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize));
      await page.addStyleTag({ content: `html { font-size: ${size * 2}px !important; }` });
    }
    const frames = await observeClearWhileTyping(page, "resilient navigation");
    assertClearTarget(frames);
    await result(page);
    targets.push({ enlarged, frames, settled: await clearKnownResults(page, "resilient navigation") });
  }
  await info.attach("search-clear-targets", { body: Buffer.from(JSON.stringify(targets, null, 2)), contentType: "application/json" });
});

test("composition completion yields the final input query", async ({ page }) => {
  await search(page);
  // Browser automation has no native IME session; only composition signals are synthetic.
  await query(page).dispatchEvent("compositionstart", { data: "resilient" });
  await page.keyboard.insertText("resilient navigation");
  await query(page).dispatchEvent("compositionend", { data: "resilient navigation" });
  await result(page);
  await expect(query(page)).toHaveValue("resilient navigation");
});

test("Escape dismisses search and returns keyboard context", async ({ page }) => {
  await search(page);
  await page.keyboard.press("Escape");
  await expect(page.locator("#__search")).not.toBeChecked();
  await expect(control(page, "search")).toBeFocused();
});

test("missing search index preserves query and keyboard Retry reaches native results", async ({ page }) => {
  await page.route("**/search/search_index.json", (route) => route.abort("failed"));
  await search(page);
  await page.keyboard.insertText("resilient navigation");
  await expect(query(page)).toHaveValue("resilient navigation");
  await expect(page.locator("[role='status'], [role='alert']").filter({ hasText: /search.*(unavailable|failed|retry)|unable.*search/i }).first()).toBeVisible({ timeout: 12_000 });
  const retry = page.getByRole("button", { name: "Retry search", exact: true });
  await expect(retry).toBeVisible();
  for (let traversal = 0; traversal < 12 && !(await retry.evaluate(node => node === document.activeElement)); traversal += 1) {
    await page.keyboard.press("Tab");
    await expect(page.locator("[data-md-component='search'] :focus")).toHaveCount(1);
  }
  await expect(retry).toBeFocused();
  await page.unroute("**/search/search_index.json");
  await page.keyboard.press("Enter");
  await result(page);
  await expect(query(page)).toHaveValue("resilient navigation");
  await expect(page.locator(".md-search-result__link").first()).toBeInViewport();
  await page.keyboard.press("Escape");
  await expect(page.locator("#__search")).not.toBeChecked();
  await page.route("**/search/search_index.json", route => route.abort("failed"));
  await phone(page, "/fixtures/native-header/");
  await page.locator(".md-header__button[for='__search']").click();
  await page.keyboard.insertText("resilient navigation");
  const nativeRetry = page.getByRole("button", { name: "Retry search", exact: true });
  await expect(nativeRetry).toBeVisible();
  for (let traversal = 0; traversal < 12 && !(await nativeRetry.evaluate(node => node === document.activeElement)); traversal += 1) await page.keyboard.press("Tab");
  await expect(nativeRetry).toBeFocused();
  await page.unroute("**/search/search_index.json");
  await page.keyboard.press("Enter");
  await result(page);
  await expect(query(page)).toHaveValue("resilient navigation");
});

test("search modal contains native Tab traversal and restores background after ordinary close", async ({ page }) => {
  await search(page);
  const dialog = page.locator("[data-md-component='search']");
  await expect(dialog).toHaveAttribute("role", "dialog");
  await expect(dialog).toHaveAttribute("aria-modal", "true");
  await expect(page.locator(".md-content")).toHaveJSProperty("inert", true);
  await page.keyboard.insertText("resilient navigation");
  await result(page);
  for (const key of [...Array(20).fill("Tab"), ...Array(4).fill("Shift+Tab")]) {
    await page.keyboard.press(key);
    await expect(dialog.locator(":focus")).toHaveCount(1);
  }
  await dialog.getByRole("button", { name: "Close search", exact: true }).click();
  await expect(page.locator("#__search")).not.toBeChecked();
  await expect(page.locator(".md-content")).toHaveJSProperty("inert", false);
  await expect(control(page, "search")).toBeFocused();
});


test("native desktop search restores visible inline input after Escape from a result", async ({ page }, info) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  info.annotations.push({ type: "viewport", description: "1440x900 native inline search" });
  await page.goto("/fixtures/native-header/");
  await expect(page.locator("html")).toHaveAttribute("data-bijux-viewport", /desktop|wide/);
  const opener = page.locator(".md-header__button[for='__search']");
  await expect(opener).toBeHidden();
  await query(page).click();
  await page.keyboard.insertText("resilient navigation");
  const answer = await nativeAnswer(page);
  await page.keyboard.press("ArrowDown");
  await expect(answer).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator("#__search")).not.toBeChecked();
  await expect(query(page)).toBeFocused();
  await expect(query(page)).toBeVisible();
  // A rapid return can coalesce in Material's focus stream without a new click.
  // Keep the public closed/focused journey separate from its cancellation witness.
  const closedFrames = await page.evaluate(() => new Promise(resolve => {
    const frames = [];
    const sample = () => {
      frames.push({ closed: !document.getElementById("__search").checked,
        queryFocused: document.activeElement === document.querySelector("[data-md-component='search-query']") });
      if (frames.length === 3) resolve(frames);
      else requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
  }));
  expect(closedFrames.every(frame => frame.closed && frame.queryFocused)).toBe(true);
  await query(page).click();
  await expect(page.locator("#__search")).toBeChecked();
  const settledAnswer = await nativeAnswer(page);
  await page.keyboard.press("ArrowDown");
  await expect(settledAnswer).toBeFocused();
  // Passive rendering turns let the native debounced observer read actual result
  // focus before Escape restores the query. No control state or event is injected.
  const resultFocus = await settledAnswer.evaluate(node => new Promise(resolve => {
    const frames = [];
    const sample = () => {
      frames.push(node === document.activeElement);
      if (frames.length === 3) resolve(frames);
      else requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
  }));
  expect(resultFocus).toEqual([true, true, true]);
  // Observe the actual native debounced focus-open attempt; no UI state is injected.
  await page.evaluate(() => {
    window.bijuxSearchFocusEvidence = [];
    const toggle = document.getElementById("__search");
    toggle.addEventListener("click", event => {
      if (!event.isTrusted) window.bijuxSearchFocusEvidence.push({ wasOpening: toggle.checked, cancelled: event.defaultPrevented });
    });
  });
  await page.keyboard.press("Escape");
  await expect.poll(() => page.evaluate(() => window.bijuxSearchFocusEvidence)).toContainEqual({ wasOpening: true, cancelled: true });
  await expect(page.locator("#__search")).not.toBeChecked();
  await expect(query(page)).toBeFocused();
  await expect(query(page)).toBeVisible();
  await query(page).click();
  await expect(page.locator("#__search")).toBeChecked();
  await nativeAnswer(page);
  await page.keyboard.press("Escape");
  await expect(page.locator("#__search")).not.toBeChecked();
  await page.keyboard.press("Tab");
  await expect(query(page)).not.toBeFocused();
  await page.keyboard.press("/");
  await expect(query(page)).not.toBeFocused();
  await expect(page.locator("#__search")).not.toBeChecked();
  await page.keyboard.press("Shift+Tab");
  await expect(query(page)).toBeFocused();
  const beforeLiteral = await query(page).evaluate(node => ({ value: node.value, start: node.selectionStart, end: node.selectionEnd }));
  await page.keyboard.press("/");
  await expect(query(page)).toHaveValue(beforeLiteral.value.slice(0, beforeLiteral.start) + "/" + beforeLiteral.value.slice(beforeLiteral.end));
  await expect(page.locator("#__search")).toBeChecked();
  await page.keyboard.press("ControlOrMeta+A");
  await page.keyboard.type("resilient navigation");
  await nativeAnswer(page);
  await page.keyboard.press("Escape");
  await expect(page.locator("#__search")).not.toBeChecked();
  await page.keyboard.press("ControlOrMeta+A");
  await expect(page.locator("#__search")).not.toBeChecked();
  await page.keyboard.press("ArrowRight");
  await expect(page.locator("#__search")).not.toBeChecked();
  await page.keyboard.press("Space");
  await expect(page.locator("#__search")).toBeChecked();
  await expect(query(page)).toHaveValue("resilient navigation ");
  await page.keyboard.press("Backspace");
  const reopenedAnswer = await nativeAnswer(page);
  const destination = await reopenedAnswer.getAttribute("href");
  await reopenedAnswer.click();
  await expect(page).toHaveURL(destination);
  await expect(page.locator("#__search")).not.toBeChecked();
});
