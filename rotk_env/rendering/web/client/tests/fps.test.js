import {test} from 'node:test';
import assert from 'node:assert/strict';
import {FrameRateCounter, DisplayMetrics} from '../performance.js';

test('FPS counts completed display frames at 30/60/144 Hz, independently of packets', () => {
  for (const hz of [30, 60, 144]) {
    const counter = new FrameRateCounter();
    assert.equal(counter.frame(0), null);
    for (let i = 1; i < hz; i++) assert.equal(counter.frame(i * 1000 / hz), null);
    assert.equal(counter.frame(1000), hz);
    for (let i = 1; i < hz; i++) counter.frame(1000 + i * 1000 / hz);
    assert.equal(counter.frame(2000), hz);
  }
});

test('a foreground stall lowers FPS; reset excludes time in a hidden tab', () => {
  const counter = new FrameRateCounter();
  counter.frame(0); assert.equal(counter.frame(2000), .5);
  counter.reset(); assert.equal(counter.frame(60000), null);
  for (let i = 1; i < 60; i++) counter.frame(60000 + i * 1000 / 60);
  assert.equal(counter.frame(61000), 60);
});

test('FPS is visible by default, writes at most once per second and keeps diagnostics opt-in', t => {
  let writes = 0, removed = false, visibility;
  const attributes = {};
  const panel = {setAttribute(key, value) { attributes[key] = value; }, remove() { removed = true; },
    set textContent(value) { this.text = value; writes++; }, get textContent() { return this.text; }};
  const previous = globalThis.document;
  t.after(() => { if (previous === undefined) delete globalThis.document; else globalThis.document = previous; });
  globalThis.document = {hidden: false, createElement: () => panel,
    addEventListener(_, callback) { visibility = callback; },
    removeEventListener(_, callback) { assert.equal(callback, visibility); }};
  const canvas = {dataset: {}, parentElement: {append: node => assert.equal(node, panel)}};
  const metrics = new DisplayMetrics(canvas);
  assert.equal(attributes['aria-live'], 'off');
  assert.equal(panel.textContent, '— FPS');
  for (let i = 0; i <= 60; i++) { metrics.begin(i * 1000 / 60); metrics.end(i * 1000 / 60, null); }
  assert.equal(panel.textContent, '60 FPS'); assert.equal(writes, 2);
  assert.equal(canvas.dataset.fps, '60'); assert.equal(canvas.dataset.performance, undefined);
  assert.equal(metrics.cpu.length, 0); assert.equal(metrics.intervals.length, 0);
  document.hidden = true; visibility(); metrics.end(30000, null);
  assert.equal(canvas.dataset.fps, undefined);
  document.hidden = false; visibility(); metrics.end(40000, null);
  assert.equal(panel.textContent, '— FPS');
  metrics.close(); assert.ok(removed);
});
