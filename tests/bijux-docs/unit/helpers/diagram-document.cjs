const vm = require('node:vm');
const turn = () => new Promise(resolve => setImmediate(resolve));

function documentFixture(source, {empty = false, vendor = true} = {}) {
  const events = new Map(), runs = [], configurations = [], scripts = [];
  let scheme = 'default', active = 0, maximum = 0, subscription;
  let nodes = [];
  class Element {
    constructor(tag) { this.localName = tag; this.namespaceURI = tag === 'svg' ? 'http://www.w3.org/2000/svg' : null; this.children = []; this.attributes = new Map(); this.listeners = new Map(); this.isConnected = true; this.hidden = false; this.text = ''; }
    get textContent() { return this.text + this.children.map(child => child.textContent).join(''); }
    set textContent(value) { this.text = String(value); this.children = []; }
    setAttribute(name, value) { this.attributes.set(name, String(value)); }
    append(...children) { this.children.push(...children); }
    appendChild(child) { this.append(child); return child; }
    querySelector(tag) { return this.children.flatMap(child => [child, ...child.descendants()]).find(child => child.localName === tag) || null; }
    querySelectorAll() { return this.descendants(); }
    descendants() { return this.children.flatMap(child => [child, ...child.descendants()]); }
    addEventListener(name, handler) { this.listeners.set(name, handler); }
    replaceWith(next) { nodes = nodes.map(node => node === this ? next : node); this.isConnected = false; }
    replaceChildren(...children) { this.children = children; this.text = ''; }
    remove() { this.isConnected = false; }
    click() { this.listeners.get('click')?.(); }
  }
  const authored = new Element('pre');
  const code = new Element('code'); code.textContent = 'graph TD; A-->B'; authored.append(code);
  nodes = empty ? [] : [authored];
  const api = {
    initialize(config) { configurations.push(config); },
    render(id, text) {
      active += 1; maximum = Math.max(maximum, active);
      let resolve, reject;
      const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
      runs.push({id, source: text, resolve(svg = '<svg/>') { active -= 1; resolve({svg}); }, reject(error = new Error('Invalid diagram')) { active -= 1; reject(error); }});
      return promise;
    },
  };
  const window = {
    document$: { subscribe(handler) { subscription = handler; } },
    addEventListener(name, handler) { events.set(name, handler); },
  };
  const document = {
    currentScript: {src: 'https://example.invalid/assets/javascripts/mermaid-init.js'},
    body: {getAttribute() { return scheme; }},
    createElement(tag) { return new Element(tag); },
    querySelectorAll() { return nodes.filter(node => node.isConnected); },
    importNode(node) { return node; },
    head: {appendChild(script) { scripts.push(script); queueMicrotask(() => { if (vendor) { window.mermaid = api; script.onload(); } else script.onerror(); }); }},
  };
  const context = { window, document, URL, setTimeout() { return 1; }, clearTimeout() {},
    DOMParser: class { parseFromString(svg) { const root = new Element('svg'); root.textContent = svg; return {body: {firstElementChild: root, children: [root]}}; } },
  };
  vm.runInNewContext(source, context, {timeout: 1000});
  return {
    runs, configurations, scripts, maximum: () => maximum,
    publish: () => subscription(),
    theme(value) { scheme = value; events.get('bijux:theme-change')(); },
    replaceDocument(text = 'graph TD; C-->D') { nodes.forEach(node => { node.isConnected = false; }); const next = new Element('pre'); const code = new Element('code'); code.textContent = text; next.append(code); nodes = [next]; },
    pagehide: () => events.get('pagehide')(),
    get figure() { return nodes[0]; },
    set vendorAvailable(value) { vendor = value; },
  };
}
module.exports = { documentFixture, turn };
