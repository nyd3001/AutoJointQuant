import assert from "node:assert/strict";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import { chooseReadingPlan, isCommunityArticle, readingTask,
  performCommunityReading, combineDailyResults } from "../checkin.mjs";

test("article choice is random, de-duplicated, and avoids the previous title when possible", () => {
  const titles = ["last", "first", "second", "first", ""];
  assert.deepEqual(chooseReadingPlan(titles, "last", 45000, 90000, () => 0),
    { articleTitle: "first", dwellMs: 45000 });
  assert.deepEqual(chooseReadingPlan(titles, "last", 45000, 90000, () => 1),
    { articleTitle: "second", dwellMs: 90000 });
  assert.equal(chooseReadingPlan(["only"], "only", 45000, 45000).articleTitle, "only");
  assert.throws(() => chooseReadingPlan([], "", 45, 90), /没有可用文章/);
  for (const range of [[0, 1], [90, 45], [NaN, 90], [1, Infinity]]) {
    assert.throws(() => chooseReadingPlan(titles, "", ...range), /正整数区间/);
  }
});

test("only same-site community article URLs are accepted", () => {
  for (const path of ["post/4589", "view/community/detail/a123"]) {
    assert.equal(isCommunityArticle(`https://www.joinquant.com/${path}`), true);
  }
  for (const url of ["https://evil.test/post/123", "javascript:alert(1)",
    "https://www.joinquant.com.evil.test/post/123", "https://www.joinquant.com/algorithm/index",
    "https://www.joinquant.com/view/community/list", "http://www.joinquant.com/post/123"]) {
    assert.equal(isCommunityArticle(url), false);
  }
});

test("reading claims are scoped to the named card and never click other rewards", () => {
  let unrelated = 0;
  let clicked = 0;
  const button = { textContent: "立即领取", disabled: false, getAttribute: () => null,
    click: () => { clicked += 1; } };
  const card = { textContent: "浏览社区文章 浏览1篇文章可以获得1积分，每月最多可得30分",
    querySelector: (selector) => ({ textContent: selector === ".header-title" ? "浏览社区文章" : "浏览社区文章 +1" }),
    querySelectorAll: () => [button] };
  const other = { querySelector: () => ({ textContent: "新人注册有奖励" }),
    querySelectorAll: () => [{ ...button, click: () => { unrelated += 1; } }] };
  const context = { document: { querySelectorAll: () => [other, card] } };
  const read = (action) => runInNewContext(`(${readingTask.toString()})(${action})`, context);
  assert.equal(read(false).status, "claimable");
  assert.equal(clicked, 0);
  assert.equal(read(true).clicked, true);
  assert.equal(clicked, 1);
  assert.equal(unrelated, 0);
  button.disabled = true;
  assert.equal(read(true).clicked, false);
  button.textContent = "已领取";
  assert.equal(read(false).status, "completed");
  button.textContent = "去看看";
  assert.equal(read(false).status, "available");
});

function scenario(states, overrides = {}) {
  let time = 0;
  let reads = 0;
  const calls = { browse: 0, claim: 0, solve: 0 };
  const options = { timeoutMs: 1500, date: "2026-09-17", now: () => time,
    pause: async (ms) => { time += ms; },
    snapshot: async () => states[Math.min(reads++, states.length - 1)],
    browse: async () => { calls.browse += 1; return { articleTitle: "random", dwellMs: 60000 }; },
    claim: async () => { calls.claim += 1; return true; },
    solve: async () => { calls.solve += 1; }, ...overrides };
  return { options, calls, reads: () => reads };
}
const state = (status, total = 52, extra = {}) => ({ task: { status, reward: 1 },
  pointsAvailable: total, pointsTotal: total, captcha: false, ...extra });

test("dry-run never visits, reads, or claims a community task", async () => {
  const s = scenario([], { dryRun: true });
  assert.equal((await performCommunityReading({}, s.options)).status, "skipped-dry-run");
  assert.equal(s.reads(), 0);
  assert.deepEqual(s.calls, { browse: 0, claim: 0, solve: 0 });
});

test("browse once, claim once, solve at most once, and confirm points separately", async () => {
  const s = scenario([state("available"), state("claimable"),
    state("claimable", 52, { captcha: true }), state("available", 53)]);
  const result = await performCommunityReading({}, s.options);
  assert.equal(result.status, "claimed");
  assert.equal(result.pointsAwarded, 1);
  assert.equal(result.dwellMs, 60000);
  assert.equal(result.date, "2026-09-17");
  assert.deepEqual(s.calls, { browse: 1, claim: 1, solve: 1 });
});

test("existing pending reward is claimed without opening another article", async () => {
  const s = scenario([state("claimable"), state("available", 53)]);
  assert.equal((await performCommunityReading({}, s.options)).status, "claimed");
  assert.deepEqual(s.calls, { browse: 0, claim: 1, solve: 0 });
});

test("completed, monthly-limit and today's saved success do not browse or claim", async () => {
  for (const current of ["completed", "monthly-limit", "available"]) {
    const s = scenario([state(current)], { previous: { date: "2026-09-17", status: "claimed" } });
    assert.ok(["already-completed", "monthly-limit"].includes((await performCommunityReading({}, s.options)).status));
    assert.deepEqual(s.calls, { browse: 0, claim: 0, solve: 0 });
  }
});

test("a visit, missing balance, or closed CAPTCHA without matching points is not success", async () => {
  for (const states of [[state("available")], [state("claimable"), state("available")],
    [state("claimable"), state("available", 57)]]) {
    const s = scenario(states);
    assert.equal((await performCommunityReading({}, s.options)).status, "unconfirmed");
    assert.ok(s.calls.browse <= 1);
    assert.ok(s.calls.claim <= 1);
  }
  const s = scenario([state("available", null)]);
  await assert.rejects(performCommunityReading({}, s.options), /无法读取积分/);
  assert.equal(s.calls.browse, 0);
});

test("rejected or unresolved CAPTCHA never causes a second solve/claim", async () => {
  const s = scenario([state("claimable"), state("claimable", 52, { captcha: true })]);
  assert.equal((await performCommunityReading({}, s.options)).status, "unconfirmed");
  assert.deepEqual(s.calls, { browse: 0, claim: 1, solve: 1 });
  const denied = scenario([state("claimable"), state("claimable", 52, { failure: "rate-limit" })]);
  await assert.rejects(performCommunityReading({}, denied.options), /拒绝/);
  assert.equal(denied.calls.claim, 1);
});

test("aggregate result preserves check-in evidence when reading fails", () => {
  const checkin = { status: "already-checked-in", pointsAwarded: 0, pointsAvailable: 52, pointsTotal: 52 };
  const result = combineDailyResults(checkin, { status: "failed", pointsAwarded: null });
  assert.equal(result.status, "partial");
  assert.equal(result.checkin, checkin);
  assert.equal(result.pointsAwarded, null);
  assert.equal(result.pointsTotal, null);
  assert.equal(result.checkin.pointsTotal, 52);
  assert.equal(combineDailyResults(checkin, { status: "claimed", pointsAwarded: 1,
    pointsAvailable: 53, pointsTotal: 53 }).pointsAwarded, 1);
});
