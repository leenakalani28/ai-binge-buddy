// Optional Node check of the actual bundled JavaScript without a browser.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const html = fs.readFileSync('src/wheel/index.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
for (let selected = 0; selected < 3; selected++) {
  const messages = [];
  const button = {};
  const result = {};
  const context = new Proxy({}, { get: () => () => {} , set: () => true });
  let handler;
  let randomCalls = 0;
  const sandbox = {
    document: {getElementById: id => id === 'spin' ? button : id === 'result' ? result : {getContext: () => context}},
    parent: {postMessage: msg => messages.push(msg)},
    window: {innerWidth: 1000, addEventListener: (type, fn) => {if (type === 'message') handler = fn;}},
    crypto: {getRandomValues: array => {array[0] = randomCalls++ === 0 ? 4294967295 : selected;}, randomUUID: () => 'test-event'},
    performance: {now: () => 0}, requestAnimationFrame: fn => fn(4000), Uint32Array, Math
  };
  vm.runInNewContext(script, sandbox);
  handler({data: {type: 'streamlit:render', args: {titles: ['One', 'Two', 'Three'], batch_id: 7}}});
  button.onclick();
  const message = messages.find(msg => msg.type === 'streamlit:setComponentValue');
  assert.equal(message.value.index, selected);
  assert.equal(message.value.batch_id, 7);
  assert.equal(result.textContent, ['One', 'Two', 'Three'][selected]);
  assert.equal(button.disabled, false);
  assert.equal(randomCalls, 2); // Excess random value was rejected.
}
console.log('Wheel JavaScript: all three stopping sectors and Python messages verified.');
