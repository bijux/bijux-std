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

module.exports = { nativeAnswer };
