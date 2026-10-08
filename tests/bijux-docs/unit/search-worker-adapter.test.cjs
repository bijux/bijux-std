const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const { Subject } = require('rxjs');
const source = fs.readFileSync(path.resolve(__dirname, '../../../shared/bijux-docs/tooling/material/search-worker-adapter.js'), 'utf8');
const setup = () => ({type: 0, data: {config: {lang: ['en']}, docs: [{location: 'platform/', title: 'Platform', text: 'resilient navigation'}], options: {suggest: true}}});
function fixture(options = {}) {
  const workers = [], timers = new Map(), states = [], listeners = new Map();
  let timerId = 0, clock = 0;
  const window = new EventTarget();
  const add = window.addEventListener.bind(window), remove = window.removeEventListener.bind(window);
  window.addEventListener = (name, listener) => { listeners.set(name, listener); add(name, listener); };
  window.removeEventListener = (name, listener) => { listeners.delete(name); remove(name, listener); };
  window.addEventListener('bijux:search-worker-status', event => states.push(event.detail));
  class Worker {
    constructor(url) { if (options.constructionFails) throw new Error('Resource constructor failed'); this.url = url; this.sent = []; this.terminated = false; workers.push(this); }
    postMessage(message) { if (options.postFails) throw new Error('Clone failure'); this.sent.push(JSON.parse(JSON.stringify(message))); this.afterPost?.(message); }
    terminate() { this.terminated = true; }
    receive(message) { this.onmessage?.({data: message}); }
    fail() { let handled = false; this.onerror?.({preventDefault() { handled = true; }}); return handled; }
  }
  vm.runInNewContext(source, {window, Worker, CustomEvent, URL,
    document: {getElementById() { return {textContent: JSON.stringify({base: '.'})}; }},
    location: {href: 'https://example.invalid/bijux-core/', origin: 'https://example.invalid'},
    setTimeout(handler, duration) { assert.ok([150, 8000].includes(duration)); timers.set(++timerId, {handler, duration, due: clock + duration}); return timerId; },
    clearTimeout(id) { timers.delete(id); },
  }, {timeout: 1000});
  const stream = window.bijuxSearchWorker.channel(options.url || 'assets/javascripts/workers/search.native.js', Subject);
  const values = [], errors = [];
  stream.subscribe({next: value => values.push(JSON.parse(JSON.stringify(value))), error: error => errors.push(error)});
  return {window, workers, timers, states, values, errors, listeners, stream,
    retry() { window.dispatchEvent(new Event('bijux:search-worker-retry')); },
    advance(milliseconds) { const until = clock + milliseconds; let count = 0; while (true) { const next = [...timers.entries()].filter(([, timer]) => timer.due <= until).sort((a,b) => a[1].due - b[1].due || a[0] - b[0])[0]; if (!next) break; assert.ok(++count < 100, 'bounded virtual timer loop'); clock = next[1].due; timers.delete(next[0]); next[1].handler(); } clock = until; },
    timeout() { this.advance(8000); },
    ready() { workers.at(-1).receive({type: 1}); },
  };
}

test('owned error retires only its worker and retry forwards unchanged native setup and real readiness', () => {
  const f = fixture(), original = setup();
  f.stream.next(original); assert.equal(f.values.length, 0);
  assert.equal(f.workers[0].fail(), true);
  assert.equal(f.workers[0].terminated, true);
  assert.equal(f.window.bijuxSearchWorker.state.stage, 'worker-unavailable');
  assert.equal(f.window.bijuxSearchWorker.state.attempt, 1);
  assert.equal(f.listeners.has('error'), false); assert.equal(f.window.onerror, undefined);
  f.retry(); assert.equal(f.workers.length, 2);
  assert.deepEqual(f.workers[1].sent, [original]);
  assert.equal(f.window.bijuxSearchWorker.state.stage, 'worker-loading');
  assert.equal(f.window.bijuxSearchWorker.state.attempt, 2);
  f.ready(); assert.deepEqual(f.values, [{type: 1}]);
  assert.equal(f.window.bijuxSearchWorker.state.stage, 'worker-ready'); assert.deepEqual(f.errors, []);
});
test('setup deadline terminates an unresponsive worker and leaves native subscribers available for retry', () => {
  const f = fixture(); f.stream.next(setup()); f.timeout();
  assert.equal(f.workers[0].terminated, true);
  assert.equal(f.window.bijuxSearchWorker.state.reason, 'timeout');
  assert.equal(f.window.bijuxSearchWorker.state.phase, 'setup');
  assert.deepEqual(f.values, []); f.retry(); f.ready(); assert.equal(f.values.length, 1);
});
test('latest native query is replayed after replacement readiness without a duplicate initial query', () => {
  const f = fixture(); f.stream.next(setup());
  f.stream.subscribe(message => { if (message.type === 1 && f.workers.length === 1) f.stream.next({type: 2, data: 'original query'}); });
  f.ready(); f.advance(150); assert.deepEqual(f.workers[0].sent.map(message => message.type), [0, 2]);
  f.workers[0].receive({type: 3, data: {items: []}});
  f.workers[0].fail(); f.stream.next({type: 2, data: 'latest query'});
  f.retry(); assert.deepEqual(f.workers[1].sent.map(message => message.type), [0]);
  f.ready(); f.advance(150); assert.deepEqual(f.workers[1].sent.map(message => message.type), [0, 2]);
  assert.equal(f.workers[1].sent[1].data, 'latest query');
});
test('late messages from a retired generation never reach native results', () => {
  const f = fixture(); f.stream.next(setup()); f.ready();
  const late = f.workers[0].onmessage;
  f.workers[0].fail(); f.retry(); late({data: {type: 3, data: {items: ['stale']}}});
  assert.deepEqual(f.values, [{type: 1}]); assert.deepEqual(f.errors, []);
});
test('native result completion cancels the query deadline; unanswered work fails visibly', () => {
  const f = fixture(); f.stream.next(setup()); f.ready();
  f.stream.next({type: 2, data: 'known answer'}); f.advance(150); assert.equal(f.timers.size, 1);
  const result = {type: 3, data: {items: [{location: 'platform/', title: 'Platform'}]}};
  f.workers[0].receive(result); assert.equal(f.timers.size, 0); assert.deepEqual(f.values.at(-1), result);
  f.stream.next({type: 2, data: 'unanswered query'}); f.advance(150); f.timeout();
  assert.equal(f.window.bijuxSearchWorker.state.phase, 'query'); assert.equal(f.workers[0].terminated, true);
});
test('constructor, post-message, malformed protocol and offscope failures remain typed and contained', () => {
  for (const options of [{constructionFails: true}, {postFails: true}, {url: 'https://other.example.invalid/search.js'}]) {
    const f = fixture(options); f.stream.next(setup());
    assert.equal(f.window.bijuxSearchWorker.state.stage, 'worker-unavailable'); assert.deepEqual(f.errors, []); assert.deepEqual(f.values, []);
  }
  const f = fixture(); f.stream.next(setup()); f.workers[0].receive({type: 3, data: {items: []}});
  assert.equal(f.window.bijuxSearchWorker.state.reason, 'protocol'); assert.deepEqual(f.values, []);
});
test('one channel shares one worker and explicit disposal removes all resource listeners', () => {
  const f = fixture();
  assert.equal(f.window.bijuxSearchWorker.channel('assets/javascripts/workers/search.native.js', Subject), f.stream);
  assert.equal(f.workers.length, 1);
  f.stream.next(setup()); f.window.bijuxSearchWorker.dispose();
  assert.equal(f.workers[0].terminated, true); assert.equal(f.timers.size, 0);
  for (const name of ['bijux:search-worker-retry', 'pagehide', 'pageshow']) assert.equal(f.listeners.has(name), false);
  f.retry(); assert.equal(f.workers.length, 1); assert.equal(f.stream.isStopped, true);
});
test('persisted page suspension retires work and resume creates one replacement with the cached native setup', () => {
  const f = fixture(), original = setup(); f.stream.next(original); f.ready();
  const hide = new Event('pagehide'); Object.defineProperty(hide, 'persisted', {value: true}); f.window.dispatchEvent(hide);
  assert.equal(f.workers[0].terminated, true);
  const show = new Event('pageshow'); Object.defineProperty(show, 'persisted', {value: true}); f.window.dispatchEvent(show);
  assert.equal(f.workers.length, 2); assert.deepEqual(f.workers[1].sent, [original]);
  f.ready(); assert.equal(f.window.bijuxSearchWorker.state.stage, 'worker-ready');
});

function result(title) { return {type: 3, data: {items: [{location: 'platform/', title}]}}; }
function searching() { const f = fixture(); f.stream.next(setup()); f.ready(); return f; }
function queries(worker) { return worker.sent.filter(message => message.type === 2); }

test('500 ordinary query edits settle to one unchanged native final query', () => {
  const f = searching();
  for (let n = 0; n < 500; n += 1) {
    f.stream.next({type: 2, data: 'typed query ' + n}); f.advance(20);
  }
  assert.deepEqual(queries(f.workers[0]), []);
  assert.equal(f.timers.size, 1);
  f.advance(129); assert.deepEqual(queries(f.workers[0]), []);
  f.advance(1); assert.deepEqual(queries(f.workers[0]), [{type: 2, data: 'typed query 499'}]);
  f.workers[0].receive(result('final answer'));
  assert.equal(f.values.at(-1).data.items[0].title, 'final answer'); assert.equal(f.timers.size, 0);
});

test('one in-flight query and one replaceable latest pending query discard obsolete results', () => {
  const f = searching();
  f.stream.next({type: 2, data: 'initial'}); f.advance(150);
  for (let n = 0; n < 500; n += 1) f.stream.next({type: 2, data: 'latest ' + n});
  f.advance(150);
  assert.deepEqual(queries(f.workers[0]), [{type: 2, data: 'initial'}]);
  assert.equal(f.timers.size, 1);
  f.workers[0].receive(result('obsolete answer'));
  assert.deepEqual(queries(f.workers[0]), [{type: 2, data: 'initial'}, {type: 2, data: 'latest 499'}]);
  assert.deepEqual(f.values, [{type: 1}]);
  const answer = result('latest answer'); f.workers[0].receive(answer);
  assert.deepEqual(f.values, [{type: 1}, answer]); assert.equal(f.timers.size, 0);
});

test('obsolete result remains suppressed until unsettled replacement is eligible', () => {
  const f = searching(); f.stream.next({type: 2, data: 'old'}); f.advance(150);
  f.stream.next({type: 2, data: 'new'}); f.advance(149);
  f.workers[0].receive(result('old result'));
  assert.equal(queries(f.workers[0]).length, 1); assert.deepEqual(f.values, [{type: 1}]);
  f.advance(1); assert.equal(queries(f.workers[0]).at(-1).data, 'new');
});

test('backspace and clear remain real native queries and never expose an obsolete nonempty result', () => {
  const f = searching(); f.stream.next({type: 2, data: 'descriptor'}); f.advance(150);
  for (const text of ['descripto', 'descript', 'descr', '']) { f.stream.next({type: 2, data: text}); f.advance(20); }
  f.advance(130); f.workers[0].receive(result('obsolete descriptor answer'));
  assert.deepEqual(queries(f.workers[0]), [{type: 2, data: 'descriptor'}, {type: 2, data: ''}]);
  assert.deepEqual(f.values, [{type: 1}]);
  const cleared = {type: 3, data: {items: []}}; f.workers[0].receive(cleared);
  assert.deepEqual(f.values.at(-1), cleared);
});

test('queued edits never reset the actual eight-second in-flight deadline; retry uses only latest query', () => {
  const f = searching(); f.stream.next({type: 2, data: 'pathological intermediate'}); f.advance(150);
  const actualDeadline = [...f.timers.values()].find(timer => timer.duration === 8000).due;
  for (let n = 0; n < 39; n += 1) { f.advance(200); f.stream.next({type: 2, data: 'refined ' + n}); }
  assert.equal([...f.timers.values()].find(timer => timer.duration === 8000).due, actualDeadline);
  f.advance(199); assert.equal(f.workers[0].terminated, false);
  f.advance(1); assert.equal(f.workers[0].terminated, true);
  assert.equal(f.window.bijuxSearchWorker.state.reason, 'timeout');
  assert.equal(f.window.bijuxSearchWorker.state.phase, 'query'); assert.equal(f.timers.size, 0);
  f.retry(); f.ready(); f.advance(150);
  assert.deepEqual(queries(f.workers[1]), [{type: 2, data: 'refined 38'}]);
  f.workers[1].receive(result('refined answer')); assert.equal(f.values.at(-1).data.items[0].title, 'refined answer');
});

test('RxJS result subscribers may synchronously enqueue without parallel native work', () => {
  const f = searching();
  f.stream.subscribe(message => { if (message.type === 3 && message.data.items[0]?.title === 'first') f.stream.next({type: 2, data: 'subscriber query'}); });
  f.stream.next({type: 2, data: 'first query'}); f.advance(150);
  f.workers[0].receive(result('first'));
  assert.deepEqual(queries(f.workers[0]), [{type: 2, data: 'first query'}]);
  f.advance(150); assert.deepEqual(queries(f.workers[0]).at(-1), {type: 2, data: 'subscriber query'});
  f.workers[0].receive(result('second')); assert.equal(f.values.at(-1).data.items[0].title, 'second');
});

test('synchronous native mock result sees deadline and in-flight ownership established before postMessage', () => {
  const f = searching();
  f.workers[0].afterPost = message => { if (message.type === 2) f.workers[0].receive(result('synchronous')); };
  f.stream.next({type: 2, data: 'query'}); f.advance(150);
  assert.equal(f.values.at(-1).data.items[0].title, 'synchronous');
  assert.equal(f.timers.size, 0); assert.equal(f.window.bijuxSearchWorker.state.stage, 'worker-ready');
});

test('RxJS disposal during READY or RESULT never schedules or leaks a queued query', () => {
  for (const eventType of [1, 3]) {
    const f = fixture(); f.stream.next(setup());
    f.stream.subscribe(message => {
      if (message.type === eventType) {
        f.stream.next({type: 2, data: 'subscriber pending'});
        f.window.bijuxSearchWorker.dispose();
      }
    });
    f.stream.next({type: 2, data: 'cached'}); f.ready();
    if (eventType === 3) { f.advance(150); f.workers[0].receive(result('done')); }
    f.advance(10000);
    assert.equal(f.workers[0].terminated, true); assert.equal(f.timers.size, 0); assert.equal(f.stream.isStopped, true);
    assert.equal(queries(f.workers[0]).length, eventType === 1 ? 0 : 1);
  }
});

test('bfcache suspension cancels pending debounce and active work; resume replays exactly the latest query', () => {
  const f = searching(); f.stream.next({type: 2, data: 'initial'}); f.advance(150);
  f.stream.next({type: 2, data: 'latest cached'});
  const late = f.workers[0].onmessage;
  const hide = new Event('pagehide'); Object.defineProperty(hide, 'persisted', {value: true}); f.window.dispatchEvent(hide);
  assert.equal(f.timers.size, 0); f.advance(10000); assert.equal(queries(f.workers[0]).length, 1);
  const show = new Event('pageshow'); Object.defineProperty(show, 'persisted', {value: true}); f.window.dispatchEvent(show);
  late({data: result('late old generation')}); f.ready(); f.advance(150);
  assert.deepEqual(queries(f.workers[1]), [{type: 2, data: 'latest cached'}]);
  f.workers[1].receive(result('current')); assert.equal(f.values.at(-1).data.items[0].title, 'current');
});

test('extra unsolicited result is a protocol failure rather than an invented current answer', () => {
  const f = searching(); f.workers[0].receive(result('unsolicited'));
  assert.equal(f.window.bijuxSearchWorker.state.reason, 'protocol'); assert.deepEqual(f.values, [{type: 1}]);
});

test('pending and actual query ownership stay searching until the latest native result is delivered', () => {
  const f = searching(), order = [];
  f.window.addEventListener('bijux:search-worker-status', e => order.push(e.detail.stage));
  f.stream.subscribe(message => { if (message.type === 3) order.push('native:' + message.data.items[0].title); });
  f.stream.next({type: 2, data: 'old'});
  assert.equal(f.window.bijuxSearchWorker.state.stage, 'worker-searching');
  assert.equal(f.window.bijuxSearchWorker.state.phase, 'query');
  f.advance(150); f.stream.next({type: 2, data: 'latest'}); f.advance(150);
  f.workers[0].receive(result('obsolete'));
  assert.deepEqual(order, ['worker-searching']);
  assert.equal(f.window.bijuxSearchWorker.state.stage, 'worker-searching');
  f.workers[0].receive(result('latest'));
  assert.deepEqual(order, ['worker-searching', 'native:latest', 'worker-ready']);
  assert.equal(f.window.bijuxSearchWorker.state.stage, 'worker-ready');
});

test('retry READY retains searching and cached-result exclusion until the actual replay answer', () => {
  const f = searching(); f.stream.next({type: 2, data: 'retained'}); f.advance(150);
  f.workers[0].fail(); f.retry(); const statesBeforeReady = f.states.length;
  f.ready(); assert.equal(f.window.bijuxSearchWorker.state.stage, 'worker-searching');
  assert.deepEqual(f.states.slice(statesBeforeReady).map(s => s.stage), ['worker-searching']);
  f.advance(150); f.workers[1].receive(result('actual replay answer'));
  assert.equal(f.values.at(-1).data.items[0].title, 'actual replay answer');
  assert.equal(f.window.bijuxSearchWorker.state.stage, 'worker-ready');
});

test('a native result subscriber that queues another query prevents an intervening ready event', () => {
  const f = searching(); let readyEvents = 0;
  f.window.addEventListener('bijux:search-worker-status', event => { if (event.detail.stage === 'worker-ready') readyEvents += 1; });
  f.stream.subscribe(message => { if (message.type === 3 && message.data.items[0].title === 'first') f.stream.next({type: 2, data: 'next'}); });
  f.stream.next({type: 2, data: 'first'}); f.advance(150); f.workers[0].receive(result('first'));
  assert.equal(readyEvents, 0); assert.equal(f.window.bijuxSearchWorker.state.stage, 'worker-searching');
  f.advance(150); f.workers[0].receive(result('second')); assert.equal(readyEvents, 1);
});

test('synchronous activity-event disposal cancels the assigned settle timer and never posts work', () => {
  const f = searching();
  f.window.addEventListener('bijux:search-worker-status', event => {
    if (event.detail.stage === 'worker-searching') f.window.bijuxSearchWorker.dispose();
  });
  f.stream.next({type: 2, data: 'dispose from status'}); f.advance(10000);
  assert.equal(f.timers.size, 0); assert.equal(f.workers[0].terminated, true);
  assert.deepEqual(queries(f.workers[0]), []); assert.equal(f.stream.isStopped, true);
});

test('reentrant activity-event retry cannot forward the retired generation READY', () => {
  const f = searching(); f.stream.next({type: 2, data: 'cached query'}); f.advance(150);
  f.workers[0].fail(); f.retry(); let retryOnce = true;
  f.window.addEventListener('bijux:search-worker-status', event => {
    if (event.detail.stage === 'worker-searching' && retryOnce) { retryOnce = false; f.retry(); }
  });
  f.ready(); assert.equal(f.workers.length, 3);
  assert.deepEqual(f.values, [{type: 1}]);
  assert.equal(f.window.bijuxSearchWorker.state.stage, 'worker-loading');
  f.ready(); f.advance(150); f.workers[2].receive(result('current answer'));
  assert.deepEqual(f.values, [{type: 1}, {type: 1}, result('current answer')]);
  assert.equal(f.window.bijuxSearchWorker.state.stage, 'worker-ready');
});
