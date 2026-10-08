const {test, expect} = require('@playwright/test');
let evidence;
test.beforeEach(async ({page, browser}, info) => {
  evidence = {errors: [], offsite: [], externalScripts: [], vendor: [], documents: []};
  info.annotations.push({type:'browser-version',description:browser.version()});
  page.on('pageerror', e => evidence.errors.push(e.message));
  page.on('request', r => {
    if (r.isNavigationRequest() && r.frame() === page.mainFrame()) evidence.documents.push(r.url());
    if (new URL(r.url()).origin !== 'http://127.0.0.1:4173') evidence.offsite.push(r.url());
    if (r.resourceType()==='script' && new URL(r.url()).origin !== 'http://127.0.0.1:4173') evidence.externalScripts.push(r.url());
    if (/mermaid-[0-9].*\.js/.test(r.url())) evidence.vendor.push(r.url());
  });
});
test.afterEach(async () => {expect(evidence.errors).toEqual([]);expect(evidence.externalScripts).toEqual([]);});
const figure = page => page.locator('main .bijux-diagram');
const source = page => figure(page).locator('.bijux-diagram-source code');
async function rendered(page) {
  await expect(figure(page).locator('.bijux-diagram-preview > svg')).toHaveCount(1);
  await expect(figure(page).locator('details')).not.toHaveAttribute('open');
  expect(await figure(page).evaluate(n => n.shadowRoot)).toBeNull();
  expect(await figure(page).locator('svg').evaluate(n => {const b=n.getBoundingClientRect();return b.width>0&&b.height>0;})).toBe(true);
}
test('ordinary instant navigation and light/dark requests preserve the sole renderer and authored source', async ({page}) => {
  await page.goto('/reading/');await rendered(page);
  const authored=await source(page).textContent();expect(authored).toContain('accTitle: Reader navigation');
  const realm=await page.evaluate(()=>{window.bijuxDiagramJourney={identity:crypto.randomUUID()};return {identity:window.bijuxDiagramJourney.identity,timeOrigin:performance.timeOrigin};});
  const ids=[];
  for(let i=0;i<3;i++) {
    ids.push(await figure(page).locator('svg').getAttribute('id'));
    const prior=await page.locator('body').getAttribute('data-md-color-scheme');
    await page.locator('[data-bijux-theme-toggle]').click();
    const next=await page.locator('body').getAttribute('data-md-color-scheme');
    if(prior!==next) await expect.poll(()=>figure(page).locator('svg').getAttribute('id')).not.toBe(ids.at(-1));
    await rendered(page);expect(await source(page).textContent()).toBe(authored);
  }
  const previous = page.locator('footer .md-footer__link--prev');
  const targetPath = new URL(await previous.getAttribute('href'), page.url()).pathname;
  await previous.click();
  await expect.poll(()=>new URL(page.url()).pathname).toBe(targetPath);
  await expect(page.locator('main h1')).toContainText('Repository leaf destination');
  const afterForward = await page.evaluate(()=>({identity:window.bijuxDiagramJourney?.identity,timeOrigin:performance.timeOrigin}));
  expect(afterForward.identity).toBe(realm.identity);
  await page.goBack();await expect.poll(()=>new URL(page.url()).pathname).toBe('/reading/');await rendered(page);
  const afterBack = await page.evaluate(()=>({identity:window.bijuxDiagramJourney?.identity,timeOrigin:performance.timeOrigin}));
  expect(afterBack.identity).toBe(realm.identity);
  expect(evidence.documents).toEqual(['http://127.0.0.1:4173/reading/']);
  test.info().annotations.push({type:'document-lifecycle',description:JSON.stringify({initial:realm,afterForward,afterBack,navigationRequests:evidence.documents})});
  expect(await source(page).textContent()).toBe(authored);
  expect(evidence.vendor).toHaveLength(1);
  expect(await page.locator('pre.mermaid').count()).toBe(0);
});
test('a document without diagrams does not load the renderer', async ({page}) => {
  await page.goto('/platform/start/');await expect(page.locator('main h1')).toContainText('Platform getting started');
  await page.waitForTimeout(350);
  expect(evidence.vendor).toHaveLength(0);expect(await page.evaluate(()=>typeof window.mermaid)).toBe('undefined');
});
test('a failed owned bundle exposes exact source and keyboard Retry renders the real diagram', async ({page}) => {
  const vendor='**/vendor/mermaid-11.17.2.min.js';await page.route(vendor,route=>route.fulfill({status:503,body:'Renderer unavailable'}));
  await page.goto('/reading/');
  await expect(figure(page).getByRole('status')).toContainText('preview unavailable');
  await expect(figure(page).locator('details')).toHaveAttribute('open','');
  const authored=await source(page).textContent();expect(authored).toContain('Overview --> Detail');
  await page.unroute(vendor);
  const retry=figure(page).getByRole('button',{name:'Retry diagram'});await retry.focus();await page.keyboard.press('Enter');
  await rendered(page);expect(await source(page).textContent()).toBe(authored);expect(evidence.vendor).toHaveLength(2);
});

test('resource labels, escaped resource styles and source directives retain readable fallback in both themes', async ({page}) => {
  const attempted = [];
  await page.route('https://diagram-resource.invalid/**', route => { attempted.push(route.request().url()); return route.abort(); });
  await page.goto('/diagram-safety/');
  const figures = figure(page);
  await expect(figures).toHaveCount(4);
  const authored = await figures.locator('.bijux-diagram-source code').allTextContents();
  expect(authored[0]).toContain('<img');
  expect(authored[1]).toContain(String.raw`\75rl`);
  expect(authored[2]).toContain('securityLevel');
  for (let mode = 0; mode < 2; mode++) {
    for (let index = 0; index < 3; index++) {
      const rejected = figures.nth(index);
      await expect(rejected.getByRole('status')).toContainText('preview unavailable');
      await expect(rejected.locator('details')).toHaveAttribute('open', '');
      await expect(rejected.locator('.bijux-diagram-preview > svg')).toHaveCount(0);
    }
    await expect(figures.nth(3).locator('.bijux-diagram-preview > svg')).toHaveCount(1);
    expect(await figures.locator('.bijux-diagram-source code').allTextContents()).toEqual(authored);
    expect(attempted).toEqual([]);
    expect(evidence.offsite.filter(url => new URL(url).hostname === 'diagram-resource.invalid')).toEqual([]);
    if (mode === 0) {
      const prior = await page.locator('body').getAttribute('data-md-color-scheme');
      await page.locator('[data-bijux-theme-toggle]').click();
      const next = await page.locator('body').getAttribute('data-md-color-scheme');
      if (next === prior) await page.locator('[data-bijux-theme-toggle]').click();
      await expect(page.locator('body')).not.toHaveAttribute('data-md-color-scheme', prior);
    }
  }
  expect(evidence.vendor).toHaveLength(1);
});
