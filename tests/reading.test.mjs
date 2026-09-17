import assert from "node:assert/strict";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import { chooseReadingPlan, isCommunityArticle, readingTask,
  performCommunityReading, combineDailyResults, solveCaptcha, dragSlider,
  previewCheckin, performDryRun } from "../checkin.mjs";

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
  const reloads = [];
  const calls = { browse: 0, claim: 0, solve: 0 };
  const options = { timeoutMs: 1500, date: "2026-09-17", now: () => time,
    pause: async (ms) => { time += ms; },
    snapshot: async (_cdp, reload = false) => {
      reloads.push(reload);
      return states[Math.min(reads++, states.length - 1)];
    },
    browse: async () => { calls.browse += 1; return { articleTitle: "random", dwellMs: 60000 }; },
    claim: async () => { calls.claim += 1; return true; },
    solve: async () => { calls.solve += 1; }, ...overrides };
  return { options, calls, reloads, reads: () => reads };
}
const state = (status, total = 52, extra = {}) => ({ task: { status, reward: 1 },
  pointsAvailable: total, pointsTotal: total, captcha: false, ...extra });

test("reading dry-run browses when needed, opens the CAPTCHA, and performs one wrong drag", async () => {
  for (const needsVisit of [false, true]) {
    const events = [];
    let solves = 0;
    const cdp = { send: async (method, event) => events.push({ method, ...event }) };
    const states = [state("claimable"), state("unknown"), state("claimable", 52, { captcha: true })];
    if (needsVisit) states.unshift(state("available"));
    const s = scenario(states, { dryRun: true, solve: async (client, options) => {
      solves += 1;
      assert.deepEqual(options, { move: false });
      return solveCaptcha(client, options, {
        capture: async () => ({}), solve: () => 120,
        drag: (page, gap, dragOptions) => dragSlider(page, {
          track: { left: 10, top: 20, width: 340, height: 40 },
          handle: { left: 10, top: 20, width: 40, height: 40 },
        }, gap, { ...dragOptions, pause: async () => {} }),
        wait: async () => assert.fail("preview must not enter successful verification"),
      });
    } });
    const result = await performCommunityReading(cdp, s.options);
    assert.equal(result.status, "dry-run-captcha-parsed");
    assert.equal(result.captchaStage, "reading");
    assert.equal(result.pointsAwarded, null);
    assert.equal(result.gapX, 120);
    assert.equal(result.previewOffset, 292);
    assert.ok(Math.abs(result.previewOffset - result.gapX) >= 64);
    assert.equal(s.calls.browse, Number(needsVisit));
    assert.equal(s.calls.claim, 1);
    assert.equal(solves, 1);
    assert.equal(s.reads(), states.length, "return immediately after the wrong drag");
    assert.deepEqual(s.reloads, needsVisit ? [true, true, false, false] : [true, false, false],
      "never reload a pending CAPTCHA when the claim button is temporarily disabled");
    assert.equal(events.filter((event) => event.type === "mouseReleased").length, 1);
    assert.equal(events.at(-1).x, 322);
  }
});

test("reading preview refuses silent awards, missing CAPTCHA, and rejected requests", async () => {
  for (const [response, message] of [
    [state("available", 53), /站点可能已发奖/],
    [state("claimable", 53, { captcha: true }), /站点可能已发奖/],
    [state("completed"), /站点可能已发奖/],
    [state("claimable"), /拼图超时/],
    [state("claimable", 52, { failure: "rate-limit" }), /拒绝/],
    [state("claimable", 52, { isLoginPage: true }), /登录失效/],
  ]) {
    const s = scenario([state("claimable"), response], { dryRun: true });
    await assert.rejects(performCommunityReading({}, s.options), message);
    assert.deepEqual(s.calls, { browse: 0, claim: 1, solve: 0 });
  }
});

test("reading preview does not retry a failed solve or open another article", async () => {
  let attempts = 0;
  const s = scenario([state("claimable"), state("claimable", 52, { captcha: true })], {
    dryRun: true,
    solve: async (_cdp, options) => {
      attempts += 1;
      assert.equal(options.move, false);
      throw new Error("track shorter than 64px");
    },
  });
  await assert.rejects(performCommunityReading({}, s.options), /64px/);
  assert.equal(attempts, 1);
  assert.equal(s.calls.claim, 1);
  assert.equal(s.calls.browse, 0);
});

test("reading preview reports unavailable tasks rather than claiming it parsed a puzzle", async () => {
  const unavailable = scenario([state("available")], { dryRun: true });
  await assert.rejects(performCommunityReading({}, unavailable.options), /未发现待领奖励/);
  assert.deepEqual(unavailable.calls, { browse: 1, claim: 0, solve: 0 });
  const missingReward = scenario([state("claimable", 52, { task: { status: "claimable" } })], { dryRun: true });
  await assert.rejects(performCommunityReading({}, missingReward.options), /无法识别待领奖励积分/);
  assert.equal(missingReward.calls.claim, 0);
  for (const status of ["completed", "monthly-limit"]) {
    const s = scenario([state(status)], { dryRun: true });
    const result = await performCommunityReading({}, s.options);
    assert.notEqual(result.status, "dry-run-captcha-parsed");
    assert.deepEqual(s.calls, { browse: 0, claim: 0, solve: 0 });
  }
});

test("logged-in dry-run previews check-in then reading; already checked in skips only that drag", async () => {
  for (const alreadyCheckedIn of [false, true]) {
    const calls = [];
    const previous = { articleTitle: "last" };
    const result = await performDryRun({}, { alreadyCheckedIn, signButton: {} }, {
      previous,
      checkinPreview: (cdp, current) => previewCheckin(cdp, current, {
        click: async () => { calls.push("checkin-click"); return true; },
        wait: async () => ({ captcha: true }),
        solve: async (_cdp, options) => {
          assert.equal(options.move, false);
          calls.push("checkin-wrong-drag");
          return { gapX: 120, previewOffset: 292 };
        },
      }),
      readingPreview: async (_cdp, options) => {
        assert.deepEqual(options, { dryRun: true, previous });
        calls.push("reading-preview");
        return { status: "dry-run-captcha-parsed", captchaStage: "reading", captchaParsed: true,
          pointsAvailable: 52, pointsTotal: 52 };
      },
    });
    assert.deepEqual(calls, alreadyCheckedIn ? ["reading-preview"]
      : ["checkin-click", "checkin-wrong-drag", "reading-preview"]);
    assert.equal(result.captchaStage, "reading");
    assert.equal(result.pointsAwarded, null);
    assert.equal(result.pointsTotal, 52);
    assert.equal(result.checkin.status, alreadyCheckedIn ? "already-checked-in" : "dry-run-captcha-parsed");
  }
});

test("check-in preview failures or blocked login prevent the reading stage", async () => {
  for (const current of [{ isLoginPage: true }, {}, { signButton: {} }]) {
    let reads = 0;
    await assert.rejects(performDryRun({}, current, {
      checkinPreview: (cdp, state) => previewCheckin(cdp, state, {
        click: async () => true,
        wait: async () => ({ alreadyCheckedIn: true, captcha: false }),
        solve: async () => assert.fail("must not drag without a CAPTCHA"),
      }),
      readingPreview: async () => { reads += 1; },
    }));
    assert.equal(reads, 0);
  }
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
