const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync('app.py', 'utf8');
const block = source.slice(source.indexOf('const token ='), source.indexOf('</script>', source.indexOf('const token =')));
let scrolls = 0;
const parent = {document: {querySelector: () => ({scrollTo: () => scrolls++})}, scrollTo: () => scrolls++};
function render(token) {
  const script = block.replace(/const token =[^\n]+/, 'const token = ' + JSON.stringify(token) + ';');
  vm.runInNewContext(script, {window: {parent}, requestAnimationFrame: fn => fn(), setTimeout: fn => fn()});
}
render('navigation-one');
assert.equal(scrolls, 6);
render('navigation-one'); // A wheel result reruns the same page.
assert.equal(scrolls, 6);
render('navigation-two'); // Returning to the shortlist must still scroll up.
assert.equal(scrolls, 12);
render('navigation-two');
assert.equal(scrolls, 12);
console.log('Scroll guard: wheel reruns stay put; new navigations still scroll to top.');
