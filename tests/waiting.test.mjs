import assert from "node:assert/strict";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import { readPageSignals, waitForPageOutcome, solveCaptcha } from "../checkin.mjs";

const idle = { isLoginPage: false, captcha: false, alreadyCheckedIn: false,
  signButton: null, failure: null };

function clockedPage(snapshot, timeoutMs = 12000, settleMs = 600) {
  let time = 0;
  let calls = 0;
  return {
    cdp: { send: async (method) => {
      assert.equal(method, "Runtime.evaluate", "waiting must not submit or drag");
      calls += 1;
      return { result: { value: { ...idle, ...snapshot(time) } } };
    } },
    options: { timeoutMs, settleMs, now: () => time, pause: async (ms) => { time += ms; } },
    time: () => time,
    calls: () => calls,
  };
}

test("check-in waits for a CAPTCHA appearing after the old 8s window", async () => {
  const page = clockedPage((time) => ({ captcha: time >= 9000 }));
  const state = await waitForPageOutcome(page.cdp, "checkin", page.options);
  assert.equal(state.captcha, true);
  assert.equal(page.time(), 9000);
});

test("login waits beyond navigation until the account page is ready", async () => {
  const page = clockedPage((time) => ({ isLoginPage: time < 1200,
    signButton: time >= 9000 ? { text: "签到", disabled: false } : null }));
  await waitForPageOutcome(page.cdp, "login", page.options);
  assert.equal(page.time(), 9000);
});

test("verification requires sustained absence, then check-in still needs confirmation", async () => {
  const page = clockedPage((time) => ({ captcha: time === 0 || time === 600 }));
  await waitForPageOutcome(page.cdp, "verification", page.options);
  assert.equal(page.time(), 1500);
  await assert.rejects(waitForPageOutcome(page.cdp, "success", {
    ...page.options, timeoutMs: 900,
  }), /签到成功确认超时/);
});

test("slow check-in confirmation succeeds without another submission", async () => {
  const page = clockedPage((time) => ({ alreadyCheckedIn: time >= 9000 }));
  const state = await waitForPageOutcome(page.cdp, "success", page.options);
  assert.equal(state.alreadyCheckedIn, true);
  assert.equal(page.time(), 9000);
});

test("explicit failures stop immediately and remain distinct from timeouts", async () => {
  for (const [failure, message] of [["verification", /明确提示验证码校验失败/],
    ["rate-limit", /操作频繁/], ["credentials", /账号或密码错误/], ["network", /网络或服务异常/]]) {
    const page = clockedPage(() => ({ failure }));
    await assert.rejects(waitForPageOutcome(page.cdp, "login", page.options), message);
    assert.equal(page.calls(), 1);
  }
  const page = clockedPage(() => ({ captcha: true }), 900);
  await assert.rejects(waitForPageOutcome(page.cdp, "verification", page.options), (error) => {
    assert.equal(error.exitCode, 3);
    assert.match(error.message, /未识别到明确拒绝提示/);
    assert.match(error.message, /JOINQUANT_PAGE_READY_TIMEOUT_MS/);
    return true;
  });
});

test("a real attempt waits for verification once; a rejection is not retried", async () => {
  for (const rejected of [false, true]) {
    let drags = 0;
    let waits = 0;
    const attempt = solveCaptcha({}, {}, {
      capture: async () => ({}), solve: () => 120,
      drag: async () => { drags += 1; },
      wait: async (_cdp, stage) => {
        waits += 1;
        assert.equal(stage, "verification");
        if (rejected) throw new Error("verification rejected");
      },
    });
    if (rejected) await assert.rejects(attempt, /verification rejected/);
    else assert.deepEqual(await attempt, { parsed: true });
    assert.equal(drags, 1);
    assert.equal(waits, 1);
  }
});

function element(text = "", { visible = true, disabled = false } = {}) {
  return { innerText: text, disabled,
    getAttribute: () => null,
    getBoundingClientRect: () => ({ width: visible ? 100 : 0, height: visible ? 40 : 0 }),
  };
}

function domSignals({ captcha = null, buttons = [], messages = [], password = null } = {}) {
  return runInNewContext(`(${readPageSignals.toString()})()`, {
    location: { pathname: "/view/user/floor" },
    getComputedStyle: () => ({ visibility: "visible", display: "block" }),
    document: {
      querySelector: (selector) => selector === "#yth_captchar" ? captcha : password,
      querySelectorAll: (selector) => selector.startsWith("button") ? buttons : messages,
    },
  });
}

test("hidden CAPTCHA nodes and disabled sign-in controls do not imply failure or success", () => {
  const state = domSignals({ captcha: element("", { visible: false }),
    buttons: [element("签到", { disabled: true })],
    password: element("", { visible: false }),
    messages: [element("验证失败", { visible: false })] });
  assert.equal(state.captcha, false);
  assert.equal(state.isLoginPage, false);
  assert.equal(state.alreadyCheckedIn, false);
  assert.equal(state.signButton, null);
  assert.equal(state.failure, null);
  assert.equal(domSignals({ buttons: [element("今日已签到", { disabled: true })] })
    .alreadyCheckedIn, true);
});

test("visible rejection text is classified without returning raw account text", () => {
  const state = domSignals({ messages: [element("账号或密码错误 test-user@example.com")] });
  assert.equal(state.failure, "credentials");
  assert.ok(!JSON.stringify(state).includes("test-user@example.com"));
});
