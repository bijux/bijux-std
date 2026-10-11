"use strict";
const assert = require("node:assert/strict");
const { createHash } = require("node:crypto");
const hash = bytes => createHash("sha256").update(bytes).digest("hex");

function admitReadingResponse(response, expectedHash, prior, browserName) {
  assert.match(expectedHash, /^[a-f0-9]{64}$/);
  if (response.status === 200) {
    assert.equal(hash(response.body), expectedHash, "The actual response is the owned fixture representation");
    const modified = response.headers["last-modified"];
    if (response.headers["content-type"] === undefined && modified === undefined) {
      // Chromium exposes a revalidated cached body as 200 with the wire 304
      // headers. Exact returned bytes and the exposed native validator bind it
      // to the already observed representation, never to a headerless first load.
      assert.equal(browserName, "chromium");
      assert.ok(prior);
      assert.equal(prior.url, response.url);
      assert.equal(prior.bodyHash, expectedHash);
      assert.ok(Number.isFinite(Date.parse(prior.modified)));
      assert.equal(response.navigation, true);
      assert.equal(response.requestHeaders["if-modified-since"], prior.modified);
      return { ...prior, transportStatus: 200, validatorEvidence: "chromium-revalidated-body" };
    }
    assert.equal(response.headers["content-type"]?.split(";")[0], "text/html");
    assert.equal(typeof modified, "string");
    assert.ok(Number.isFinite(Date.parse(modified)), "A real cache validator accompanies the representation");
    return { url: response.url, bodyHash: expectedHash, modified, transportStatus: 200 };
  }
  assert.equal(response.status, 304, "Only an admitted representation or its validated conditional response is usable");
  assert.ok(prior, "A conditional response cannot establish an unobserved cached representation");
  assert.equal(prior.url, response.url);
  assert.equal(prior.bodyHash, expectedHash);
  assert.ok(Number.isFinite(Date.parse(prior.modified)));
  assert.equal(response.navigation, true, "Only the native document navigation can reuse the representation");
  const validator = response.requestHeaders["if-modified-since"];
  if (validator === undefined) {
    // Firefox hides its internal conditional header from Playwright. Native
    // wire controls establish that boundary; URL, exact prior bytes and the
    // independently asserted rendered destination remain mandatory here.
    assert.equal(browserName, "firefox", "An absent exposed validator is bounded to Firefox document caching");
  } else {
    assert.equal(validator, prior.modified, "An exposed validator must revalidate the admitted representation");
  }
  return { ...prior, transportStatus: 304, validatorEvidence: validator === undefined ? "firefox-internal-header" : "exposed-request-header" };
}
module.exports = { admitReadingResponse, hash };
