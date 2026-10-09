'use strict';

// Native test-runner events keep user console output outside result accounting.
module.exports = async function* rendererTestEvents(events) {
  for await (const event of events) {
    if (['test:pass', 'test:fail', 'test:plan', 'test:summary'].includes(event.type)) {
      yield `${JSON.stringify(event)}\n`;
    }
  }
};
