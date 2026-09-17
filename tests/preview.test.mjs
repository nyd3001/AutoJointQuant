import assert from "node:assert/strict";
import { test } from "node:test";
import { choosePreviewOffset, dragSlider, solveCaptcha, jitterDelay, planDragTiming } from "../checkin.mjs";

const geometry = (maxOffset) => ({
  track: { left: 10, top: 20, width: maxOffset + 40, height: 40 },
  handle: { left: 10, top: 20, width: 40, height: 40 },
});

test("preview offsets stay in bounds and at least 64px from the solved offset", () => {
  for (const maxOffset of [144, 300, 600]) {
    for (const solved of [0, maxOffset / 4, maxOffset / 2, maxOffset]) {
      const offset = choosePreviewOffset(solved, maxOffset);
      assert.ok(offset >= 0 && offset <= maxOffset);
      assert.ok(Math.abs(offset - solved) >= 64);
      assert.notEqual(offset, solved);
    }
  }
  assert.equal(choosePreviewOffset(0, 72), 64);
  for (const pair of [[0, 0], [0, 8], [0, 63], [0, 64], [0, 71], [64, 128]]) {
    assert.throws(() => choosePreviewOffset(...pair), /64px/);
  }
  for (const pair of [[NaN, 300], [Infinity, 300], [0, Infinity], [-1, 300], [301, 300]]) {
    assert.throws(() => choosePreviewOffset(...pair), /无效/);
  }
});

test("an unsafe preview aborts before any CDP input", async () => {
  const events = [];
  const cdp = { send: async (...args) => events.push(args) };
  await assert.rejects(
    dragSlider(cdp, geometry(100), 50, { intentionallyWrong: true }), /64px/,
  );
  assert.deepEqual(events, []);
});

test("dry-run uses the real event path once and releases at the preview offset", async () => {
  const events = [];
  const cdp = { send: async (method, event) => events.push({ method, ...event }) };
  let attempts = 0;
  const result = await solveCaptcha(cdp, { move: false }, {
    capture: async () => ({}),
    solve: () => 120,
    drag: async (client, gap, options) => {
      attempts += 1;
      assert.deepEqual(options, { intentionallyWrong: true });
      return dragSlider(client, geometry(300), gap, options);
    },
  });
  assert.equal(attempts, 1);
  assert.equal(result.previewOffset, 292);
  assert.ok(Math.abs(result.previewOffset - result.gapX) >= 64);
  assert.equal(events.length, 51);
  assert.ok(events.every((event) => event.method === "Input.dispatchMouseEvent"));
  assert.equal(events.filter((event) => event.type === "mousePressed").length, 1);
  assert.equal(events.filter((event) => event.type === "mouseReleased").length, 1);
  assert.equal(events[0].type, "mouseMoved");
  assert.equal(events[1].type, "mousePressed");
  assert.ok(events.slice(2, -1).every((event) => event.buttons === 1));
  assert.equal(events.at(-1).type, "mouseReleased");
  assert.equal(events.at(-1).x, 30 + result.previewOffset);
});

test("preview failure propagates without retry or correct-drag fallback", async () => {
  for (const error of [new Error("short track"), new Error("CDP failed")]) {
    let attempts = 0;
    await assert.rejects(solveCaptcha({}, { move: false }, {
      capture: async () => ({}),
      solve: () => 120,
      drag: async (_cdp, _gap, options) => {
        attempts += 1;
        assert.deepEqual(options, { intentionallyWrong: true });
        throw error;
      },
    }), (actual) => actual === error);
    assert.equal(attempts, 1);
  }
});

test("the ordinary drag still releases at the solved offset", async () => {
  const events = [];
  const offset = await dragSlider({ send: async (_method, event) => events.push(event) },
    geometry(300), 120);
  assert.equal(offset, 120);
  assert.equal(events.at(-1).x, 150);
});

test("action timing stays within the documented bounds and scales with configuration", () => {
  for (const base of [1000, 2000]) {
    assert.equal(jitterDelay(base, () => 0), base * 0.7);
    assert.equal(jitterDelay(base, () => 0.5), base);
    assert.equal(jitterDelay(base, () => 1), base * 1.3);
  }
});

test("drag timing varies both the total duration and individual intervals", () => {
  for (const totalSample of [0, 0.5, 1]) {
    let index = 0;
    const timings = planDragTiming(() => index++ === 0 ? totalSample : (index % 2));
    assert.equal(timings.length, 48);
    assert.ok(timings.every((ms) => ms > 0));
    assert.ok(new Set(timings).size > 1);
    assert.ok(Math.abs(timings.reduce((sum, ms) => sum + ms, 0)
      - (700 + 600 * totalSample)) < 0.001);
  }
});

test("timing variation does not change preview offset or release count", async () => {
  for (const sample of [0, 1]) {
    const events = [];
    const waits = [];
    const offset = await dragSlider({ send: async (_method, event) => events.push(event) },
      geometry(300), 120, {
        intentionallyWrong: true, random: () => sample,
        pause: async (ms) => waits.push(ms),
      });
    assert.equal(offset, 292);
    assert.ok(Math.abs(offset - 120) >= 64);
    assert.equal(waits.length, 48);
    assert.ok(Math.abs(waits.reduce((sum, ms) => sum + ms, 0) - (700 + sample * 600)) < 0.001);
    assert.equal(events.filter((event) => event.type === "mouseReleased").length, 1);
    assert.equal(events.at(-1).x, 322);
  }
});
