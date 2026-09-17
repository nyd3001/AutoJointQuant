#!/usr/bin/env node

import { execFileSync, spawn } from "node:child_process";
import {
  accessSync,
  closeSync,
  constants as fsConstants,
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  readlinkSync,
  realpathSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { homedir, hostname, tmpdir } from "node:os";
import { delimiter, dirname, isAbsolute, join, resolve, sep } from "node:path";
import { loadEnvFile } from "node:process";
import { fileURLToPath } from "node:url";
import { setTimeout as sleep } from "node:timers/promises";

const HERE = dirname(fileURLToPath(import.meta.url));
const FLOOR_URL = "https://www.joinquant.com/view/user/floor?type=mainFloor";
const CREDITS_URL = "https://www.joinquant.com/view/user/floor?type=creditsdesc";

class AppError extends Error {
  constructor(message, exitCode = 1) {
    super(message);
    this.exitCode = exitCode;
  }
}

function expandPath(value, base = HERE) {
  if (value === "~") return homedir();
  if (value.startsWith("~/") || value.startsWith("~\\")) return join(homedir(), value.slice(2));
  return isAbsolute(value) ? value : resolve(base, value);
}

function loadConfigurationFile() {
  const configured = process.env.JOINQUANT_ENV_FILE;
  if (!configured || configured === "-") return null;
  const path = expandPath(configured);
  if (!existsSync(path)) {
    throw new AppError(`环境变量文件不存在：${path}`);
  }
  if (process.platform !== "win32" && (statSync(path).mode & 0o077) !== 0) {
    throw new AppError(`环境变量文件权限过宽：${path}；请执行 chmod 600 '${path}'`);
  }
  // Explicit process variables must win over values from the file.
  const inherited = { ...process.env };
  loadEnvFile(path);
  Object.assign(process.env, inherited);
  return path;
}

function resolveExecutable(value) {
  if (!value) return null;
  if (value.includes("/") || value.includes("\\")) {
    const candidate = expandPath(value);
    try {
      accessSync(candidate, fsConstants.X_OK);
      return candidate;
    } catch {
      return null;
    }
  }
  for (const directory of (process.env.PATH || "").split(delimiter).filter(Boolean)) {
    const candidate = join(directory, value);
    try {
      accessSync(candidate, fsConstants.X_OK);
      return candidate;
    } catch {}
  }
  return null;
}

function discoverChrome() {
  const configured = process.env.JOINQUANT_CHROME_BIN;
  if (configured) return resolveExecutable(configured) || configured;
  const candidates = process.platform === "darwin"
    ? [
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
      join(homedir(), "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
      "/Applications/Chromium.app/Contents/MacOS/Chromium",
      "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
      "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
      "google-chrome",
      "chromium",
      "chromium-browser",
    ]
    : process.platform === "win32"
      ? ["chrome.exe", "msedge.exe", "chromium.exe"]
      : [
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
        "ungoogled-chromium",
      ];
  return candidates.map(resolveExecutable).find(Boolean) || null;
}

function browserInstallHint() {
  if (process.platform === "linux") {
    return "请安装 Chromium/Chrome；NixOS 可在 environment.systemPackages 中加入 pkgs.chromium，或进入 nix develop；也可设置 JOINQUANT_CHROME_BIN 指向浏览器可执行文件";
  }
  if (process.platform === "darwin") {
    return "请安装 Google Chrome/Chromium，或设置 JOINQUANT_CHROME_BIN 指向浏览器可执行文件";
  }
  return "请安装 Chrome/Chromium，或设置 JOINQUANT_CHROME_BIN 指向浏览器可执行文件";
}

function parseFlag(value) {
  return /^(1|true|yes|on)$/i.test(value || "");
}

function positiveInteger(value, name, fallback) {
  if (value === undefined || value === "") return fallback;
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number <= 0) {
    throw new AppError(`${name} 必须是正整数`);
  }
  return number;
}

function validateDedicatedProfile(profile) {
  const normalProfiles = process.platform === "darwin"
    ? [
      "~/Library/Application Support/Google/Chrome",
      "~/Library/Application Support/Chromium",
    ]
    : process.platform === "linux"
      ? ["~/.config/google-chrome", "~/.config/chromium"]
      : [];
  const unsafe = normalProfiles
    .map((value) => expandPath(value))
    .some((value) => profile === value || profile.startsWith(`${value}${sep}`));
  if (unsafe) {
    throw new AppError("JOINQUANT_PROFILE_DIR 必须是独立目录，不能指向日常浏览器 profile");
  }
  return profile;
}

function buildConfig(envFile) {
  const debugPort = process.env.JOINQUANT_DEBUG_PORT || "auto";
  if (debugPort !== "auto") {
    const port = Number(debugPort);
    if (!Number.isSafeInteger(port) || port < 1 || port > 65535) {
      throw new AppError("JOINQUANT_DEBUG_PORT 必须是 auto 或 1-65535 的端口号");
    }
  }
  const timeoutMs = positiveInteger(process.env.JOINQUANT_TIMEOUT_MS, "JOINQUANT_TIMEOUT_MS", 15000);
  return {
    chrome: discoverChrome(),
    debugPort,
    envFile,
    execute: process.argv.includes("--execute"),
    headless: process.env.JOINQUANT_HEADLESS === undefined
      ? process.platform === "linux" && !process.env.DISPLAY && !process.env.WAYLAND_DISPLAY
      : parseFlag(process.env.JOINQUANT_HEADLESS),
    password: process.env.JOINQUANT_PASSWORD || "",
    profile: validateDedicatedProfile(
      expandPath(process.env.JOINQUANT_PROFILE_DIR || join(HERE, ".chrome-profile")),
    ),
    timeoutMs,
    actionDelayMs: positiveInteger(
      process.env.JOINQUANT_ACTION_DELAY_MS, "JOINQUANT_ACTION_DELAY_MS", 1000,
    ),
    pageReadyTimeoutMs: positiveInteger(
      process.env.JOINQUANT_PAGE_READY_TIMEOUT_MS,
      "JOINQUANT_PAGE_READY_TIMEOUT_MS",
      Math.max(timeoutMs, 60000),
    ),
    username: process.env.JOINQUANT_USERNAME || "",
  };
}

let CONFIG;
let ACTIVE_PORT;
let BROWSER_CHILD = null;
let OWNS_BROWSER = false;
let LOCK_PATH = null;

function info(message) {
  process.stdout.write(`[joinquant] ${message}\n`);
}

function fail(message, code = 1) {
  process.stderr.write(`[joinquant] ${message}\n`);
  process.exitCode = code;
}

async function jsonFetch(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    signal: options.signal || AbortSignal.timeout(CONFIG?.timeoutMs || 15000),
  });
  if (!response.ok) throw new AppError(`HTTP ${response.status} from ${url}`);
  return response.json();
}

class CdpClient {
  constructor(url) {
    this.closed = false;
    this.socket = new WebSocket(url);
    this.nextId = 1;
    this.pending = new Map();
    this.ready = new Promise((resolve, reject) => {
      this.socket.addEventListener("open", resolve, { once: true });
      this.socket.addEventListener("error", reject, { once: true });
      this.socket.addEventListener("close", () => reject(new AppError("CDP connection closed before it was ready")), { once: true });
    });
    this.socket.addEventListener("message", (event) => {
      let message;
      try {
        message = JSON.parse(String(event.data));
      } catch {
        return;
      }
      if (!message.id) return;
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      clearTimeout(pending.timer);
      if (message.error) pending.reject(new AppError(message.error.message));
      else pending.resolve(message.result);
    });
    this.socket.addEventListener("close", () => {
      this.closed = true;
      for (const pending of this.pending.values()) {
        clearTimeout(pending.timer);
        pending.reject(new AppError("CDP connection closed"));
      }
      this.pending.clear();
    });
  }

  async send(method, params = {}) {
    await this.ready;
    if (this.closed) throw new AppError("CDP connection is closed");
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new AppError(`CDP command timed out: ${method}`));
      }, CONFIG?.timeoutMs || 15000);
      this.pending.set(id, { resolve, reject, timer });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  close() {
    if (!this.closed) this.socket.close();
  }
}

async function endpointReady(port) {
  try {
    await jsonFetch(`http://127.0.0.1:${port}/json/version`, {
      signal: AbortSignal.timeout(750),
    });
    return true;
  } catch {
    return false;
  }
}

function activePortFromProfile() {
  const path = join(CONFIG.profile, "DevToolsActivePort");
  if (!existsSync(path)) return null;
  try {
    const port = Number(readFileSync(path, "utf8").split(/\r?\n/, 1)[0]);
    return Number.isSafeInteger(port) && port >= 1 && port <= 65535 ? port : null;
  } catch {
    return null;
  }
}

function acquireLock() {
  mkdirSync(CONFIG.profile, { recursive: true, mode: 0o700 });
  LOCK_PATH = join(CONFIG.profile, ".autojoinquant.lock");
  const create = () => {
    const descriptor = openSync(LOCK_PATH, "wx", 0o600);
    try {
      writeFileSync(descriptor, JSON.stringify({ pid: process.pid, startedAt: new Date().toISOString() }));
    } finally {
      closeSync(descriptor);
    }
  };
  try {
    create();
    return;
  } catch (error) {
    if (error.code !== "EEXIST") throw error;
  }

  let active = false;
  try {
    const lock = JSON.parse(readFileSync(LOCK_PATH, "utf8"));
    if (Number.isSafeInteger(lock.pid) && lock.pid > 0) {
      try {
        process.kill(lock.pid, 0);
        active = true;
      } catch (error) {
        active = error.code === "EPERM";
      }
    }
  } catch {}
  if (active) throw new AppError(`已有签到进程在运行（锁文件：${LOCK_PATH}）`);
  try {
    unlinkSync(LOCK_PATH);
    create();
  } catch (error) {
    throw new AppError(`无法获取运行锁：${error.message}`);
  }
}

function releaseLock() {
  if (!LOCK_PATH) return;
  try {
    const lock = JSON.parse(readFileSync(LOCK_PATH, "utf8"));
    if (lock.pid === process.pid) unlinkSync(LOCK_PATH);
  } catch {}
  LOCK_PATH = null;
}

function cleanStaleChromeLocks() {
  const lockPath = join(CONFIG.profile, "SingletonLock");
  let target;
  try {
    target = readlinkSync(lockPath);
  } catch {
    return;
  }
  const match = target.match(/^(.*)-(\d+)$/);
  if (!match) {
    throw new AppError(`Chrome profile 存在无法识别的锁：${lockPath} -> ${target}`);
  }
  // macOS host names commonly change between networks; the profile is on a local filesystem.
  if (match[1] !== hostname() && process.platform !== "darwin") {
    throw new AppError(`Chrome profile 被另一台主机锁定：${target}`);
  }
  const pid = Number(match[2]);
  try {
    process.kill(pid, 0);
    throw new AppError(`Chrome profile 正由 PID ${pid} 使用`);
  } catch (error) {
    if (error instanceof AppError || error.code === "EPERM") throw error;
    if (error.code !== "ESRCH") throw error;
  }
  for (const name of ["SingletonLock", "SingletonCookie", "SingletonSocket"]) {
    try { unlinkSync(join(CONFIG.profile, name)); } catch {}
  }
  info(`已清理独立 Chrome profile 的失效锁（旧 PID ${pid}）`);
}

async function ensureChrome() {
  if (CONFIG.debugPort === "auto") {
    const profilePort = activePortFromProfile();
    if (profilePort && await endpointReady(profilePort)) {
      ACTIVE_PORT = profilePort;
      return;
    }
    // Compatibility with releases that used a fixed port and did not create
    // DevToolsActivePort. Only probe it when this dedicated profile is locked.
    try {
      readlinkSync(join(CONFIG.profile, "SingletonLock"));
      if (await endpointReady(9223)) {
        ACTIVE_PORT = 9223;
        info("复用旧版独立 Chrome profile 的 CDP 端口 9223");
        return;
      }
    } catch {}
  } else {
    const configuredPort = Number(CONFIG.debugPort);
    if (await endpointReady(configuredPort)) {
      ACTIVE_PORT = configuredPort;
      return;
    }
  }
  if (!CONFIG.chrome || !resolveExecutable(CONFIG.chrome)) {
    const candidate = CONFIG.chrome ? `（配置值：${CONFIG.chrome}）` : "";
    throw new AppError(`未发现 Chrome/Chromium 可执行文件${candidate}。${browserInstallHint()}`);
  }
  mkdirSync(CONFIG.profile, { recursive: true, mode: 0o700 });
  cleanStaleChromeLocks();
  if (CONFIG.debugPort === "auto") {
    try { unlinkSync(join(CONFIG.profile, "DevToolsActivePort")); } catch {}
  }
  const requestedPort = CONFIG.debugPort === "auto" ? 0 : Number(CONFIG.debugPort);
  const chromeArgs = [
    "--remote-debugging-address=127.0.0.1",
    `--remote-debugging-port=${requestedPort}`,
    `--user-data-dir=${CONFIG.profile}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--lang=zh-CN",
    "about:blank",
  ];
  if (CONFIG.headless) {
    chromeArgs.unshift("--headless=new", "--window-size=1280,900");
    info("使用 Chromium headless 模式（未检测到桌面或已显式启用）");
  }
  if (process.platform === "linux" && typeof process.getuid === "function" && process.getuid() === 0) {
    if (!parseFlag(process.env.JOINQUANT_ALLOW_NO_SANDBOX)) {
      throw new AppError("不建议以 root 运行 Chromium；请改用普通用户，或显式设置 JOINQUANT_ALLOW_NO_SANDBOX=1 承担风险");
    }
    chromeArgs.unshift("--no-sandbox");
  }
  BROWSER_CHILD = spawn(CONFIG.chrome, chromeArgs, { stdio: "ignore" });
  OWNS_BROWSER = true;
  let launchError = null;
  BROWSER_CHILD.once("error", (error) => { launchError = error; });
  const attempts = Math.max(30, Math.ceil(CONFIG.timeoutMs / 250));
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (launchError) throw new AppError(`浏览器启动失败：${launchError.message}`);
    const port = CONFIG.debugPort === "auto" ? activePortFromProfile() : requestedPort;
    if (port && await endpointReady(port)) {
      ACTIVE_PORT = port;
      return;
    }
    if (BROWSER_CHILD.exitCode !== null) {
      throw new AppError(`浏览器在 CDP 就绪前退出（exit=${BROWSER_CHILD.exitCode}）`);
    }
    await sleep(250);
  }
  throw new AppError(`Chrome CDP endpoint 未在 ${CONFIG.timeoutMs}ms 内就绪`);
}

async function openPage() {
  const targets = await jsonFetch(`http://127.0.0.1:${ACTIVE_PORT}/json/list`);
  let target = targets.find((item) => item.type === "page"
    && item.webSocketDebuggerUrl
    && /^https:\/\/([^.]+\.)?joinquant\.com\//i.test(item.url || ""));
  if (!target) {
    const response = await fetch(
      `http://127.0.0.1:${ACTIVE_PORT}/json/new?${encodeURIComponent(FLOOR_URL)}`,
      { method: "PUT", signal: AbortSignal.timeout(CONFIG.timeoutMs) },
    );
    if (!response.ok) throw new AppError("unable to create a Chrome page target");
    target = await response.json();
  }
  const cdp = new CdpClient(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  return cdp;
}

async function closeOwnedBrowser() {
  if (!OWNS_BROWSER) return;
  try {
    const version = await jsonFetch(`http://127.0.0.1:${ACTIVE_PORT}/json/version`, {
      signal: AbortSignal.timeout(1000),
    });
    if (version.webSocketDebuggerUrl) {
      const browser = new CdpClient(version.webSocketDebuggerUrl);
      await Promise.race([
        browser.send("Browser.close").catch(() => {}),
        sleep(1000),
      ]);
      browser.close();
    }
  } catch {}
  if (BROWSER_CHILD?.exitCode === null) {
    await Promise.race([
      new Promise((resolveExit) => BROWSER_CHILD.once("exit", resolveExit)),
      sleep(2000),
    ]);
  }
  if (BROWSER_CHILD?.exitCode === null) BROWSER_CHILD.kill("SIGTERM");
  BROWSER_CHILD = null;
  OWNS_BROWSER = false;
}

function evaluationDetail(details) {
  return details?.exception?.description
    || details?.exception?.value
    || details?.text
    || "unknown page exception";
}

async function evaluate(cdp, expression, retries = 3) {
  for (let attempt = 1; attempt <= retries; attempt += 1) {
    try {
      const result = await cdp.send("Runtime.evaluate", {
        expression,
        awaitPromise: true,
        returnByValue: true,
        userGesture: true,
      });
      if (!result.exceptionDetails) return result.result?.value;
      const detail = evaluationDetail(result.exceptionDetails);
      if (attempt < retries && /execution context|cannot find context|no execution context/i.test(detail)) {
        await sleep(250);
        continue;
      }
      throw new Error(`page evaluation failed: ${detail}`);
    } catch (error) {
      if (attempt < retries && /execution context|cannot find context|no execution context/i.test(error.message)) {
        await sleep(250);
        continue;
      }
      throw error;
    }
  }
  throw new Error("page evaluation failed after retries");
}

async function navigate(cdp, url) {
  const result = await cdp.send("Page.navigate", { url });
  if (result.errorText) throw new AppError(`页面导航失败：${result.errorText}`);
  const ready = await waitFor(
    cdp,
    `document.readyState === "interactive" || document.readyState === "complete"`,
    pageReadyTimeoutMs(),
  );
  if (!ready) throw new AppError("页面加载超时；请检查网络，或增大 JOINQUANT_PAGE_READY_TIMEOUT_MS", 3);
}

async function pageState(cdp) {
  return evaluate(cdp, `(() => {
    const text = document.body?.innerText || "";
    const numberFrom = (value) => {
      const match = String(value || "").match(/[0-9][0-9,]*/);
      return match ? Number(match[0].replaceAll(",", "")) : null;
    };
    const availableElement = [...document.querySelectorAll("span")]
      .find((item) => item.previousSibling?.textContent?.includes("可用积分"));
    const totalElement = [...document.querySelectorAll("p")]
      .find((item) => /累计获得[\\s\\S]*积分/.test(item.textContent || ""));
    const awardMatch = text.match(/(?:获得|奖励|领取)\\s*([0-9][0-9,]*)\\s*积分/);
    return {
      url: location.href,
      title: document.title,
      ...(${readPageSignals.toString()})(),
      loggedIn: text.includes("积分中心") || text.includes("签到领积分"),
      pointsVisible: /积分/.test(text),
      pointsAvailable: numberFrom(availableElement?.textContent),
      pointsTotal: numberFrom(totalElement?.textContent),
      pointsAwarded: awardMatch ? numberFrom(awardMatch[1]) : null,
    };
  })()`);
}

async function readPoints(cdp, state = null) {
  let current = state || await pageState(cdp);
  if (Number.isFinite(current.pointsAvailable) && Number.isFinite(current.pointsTotal)) {
    return current;
  }
  await navigate(cdp, CREDITS_URL);
  await waitFor(
    cdp,
    `document.body?.innerText?.includes("可用积分") && document.body?.innerText?.includes("累计获得")`,
    pageReadyTimeoutMs(),
  );
  // Vue initially renders zero-valued placeholders after document.readyState is complete.
  await sleep(2000);
  current = await pageState(cdp);
  return current;
}

async function waitFor(cdp, predicate, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const value = await evaluate(cdp, predicate);
    if (value) return value;
    await sleep(300);
  }
  return null;
}

function pageReadyTimeoutMs() {
  return CONFIG.pageReadyTimeoutMs;
}

export function jitterDelay(baseMs, random = Math.random) {
  return Math.max(1, Math.round(baseMs * (0.7 + 0.6 * random())));
}

async function pauseBeforeAction() {
  await sleep(jitterDelay(CONFIG.actionDelayMs));
}

export function planDragTiming(random = Math.random) {
  const durationMs = jitterDelay(1000, random);
  const weights = Array.from({ length: 48 }, () => jitterDelay(100, random));
  const total = weights.reduce((sum, weight) => sum + weight, 0);
  return weights.map((weight) => durationMs * weight / total);
}

// Executed in the page. Return categories only, never raw account/error text.
export function readPageSignals() {
  const visible = (element) => {
    if (!element) return false;
    const style = getComputedStyle(element);
    const box = element.getBoundingClientRect();
    return style.visibility !== "hidden" && style.display !== "none"
      && box.width > 0 && box.height > 0;
  };
  const buttons = [...document.querySelectorAll("button, [role=button], a")].filter(visible);
  const action = buttons.find((item) => /签到/.test(item.innerText || "")
    && !/已签到/.test(item.innerText || "") && !item.disabled
    && item.getAttribute("aria-disabled") !== "true");
  const messages = [...document.querySelectorAll(
    '#yth_captchar, [role=alert], .error, .error-msg, .el-message, .ant-message-notice',
  )].filter(visible).map((item) => item.innerText || "").join(" ");
  const failure = /操作频繁|请求频繁|尝试次数/.test(messages) ? "rate-limit"
    : /(?:账号|用户名|账户)(?:或密码)?(?:错误|不正确|不存在)|密码(?:错误|不正确)/.test(messages) ? "credentials"
    : /验证失败|校验失败|验证不通过|滑动失败|验证错误/.test(messages) ? "verification"
    : /网络异常|网络错误|请求超时|连接超时|服务繁忙|系统繁忙|稍后再试/.test(messages) ? "network"
    : null;
  return {
    isLoginPage: location.pathname.includes("/user/login")
      || visible(document.querySelector('input[type="password"]')),
    captcha: visible(document.querySelector("#yth_captchar")),
    alreadyCheckedIn: buttons.some((item) => /已签到/.test(item.innerText || "")),
    signButton: action ? { text: action.innerText.trim(), disabled: false } : null,
    failure,
  };
}

export async function waitForPageOutcome(cdp, stage, {
  timeoutMs = pageReadyTimeoutMs(), settleMs = CONFIG.actionDelayMs,
  pause = sleep, now = Date.now,
} = {}) {
  const labels = { page: "页面加载", login: "登录结果", checkin: "签到响应",
    verification: "验证码校验", success: "签到成功确认" };
  const failures = { "rate-limit": "站点提示操作频繁或稍后再试",
    credentials: "站点提示账号或密码错误", verification: "站点明确提示验证码校验失败",
    network: "站点提示网络或服务异常" };
  const deadline = now() + timeoutMs;
  let absentSince = null;
  let state = null;
  while (now() < deadline) {
    try {
      state = await evaluate(cdp, `(${readPageSignals.toString()})()`);
    } catch (error) {
      if (!/execution context|cannot find context|no execution context/i.test(error.message)) throw error;
      absentSince = null;
      await pause(300);
      continue;
    }
    if (state.failure) throw new AppError(`${labels[stage]}失败：${failures[state.failure]}；已停止，不自动重试`, 3);
    const floorReady = !state.isLoginPage && (state.signButton || state.alreadyCheckedIn);
    if (stage === "page" && (state.isLoginPage || state.captcha || floorReady)) return state;
    if (stage === "login" && (state.captcha || floorReady)) return state;
    if (stage === "checkin" && (state.captcha || state.alreadyCheckedIn)) return state;
    if (stage === "success" && state.alreadyCheckedIn) return state;
    if (stage === "verification") {
      absentSince = state.captcha ? null : (absentSince ?? now());
      if (absentSince !== null && now() - absentSince >= settleMs) return state;
    }
    await pause(300);
  }
  const detail = state?.captcha ? "验证码仍可见，但未识别到明确拒绝提示" : "未观察到所需页面状态";
  throw new AppError(
    `${labels[stage]}超时（${Math.ceil(timeoutMs / 1000)} 秒）：${detail}；可能是网络较慢、响应未完成或页面结构变化。可增大 JOINQUANT_PAGE_READY_TIMEOUT_MS；已停止，不自动重试`,
    3,
  );
}

async function waitForRelevantPage(cdp) {
  await waitForPageOutcome(cdp, "page");
  return pageState(cdp);
}

async function fillLogin(cdp, { moveCaptcha = true } = {}) {
  if (!CONFIG.username || !CONFIG.password) {
    throw new AppError(
      "当前未登录；请设置 JOINQUANT_USERNAME 和 JOINQUANT_PASSWORD，或使用受保护的环境变量文件",
      2,
    );
  }
  const username = JSON.stringify(CONFIG.username);
  const password = JSON.stringify(CONFIG.password);
  const controlsReady = await waitFor(cdp, `(() => {
    const inputs = [...document.querySelectorAll("input")];
    const hasPassword = inputs.some((input) => input.type === "password" || /密码/.test(input.placeholder || ""));
    const hasUser = inputs.some((input) => input.type === "tel" || /手机号|账号|用户名/.test(input.placeholder || "") || /username|account|mobile/.test(input.name || ""));
    const hasButton = Boolean(document.querySelector("button.btnPwdSubmit, button[type=submit], input[type=submit]"))
      || [...document.querySelectorAll("button, a")].some((item) => /登\\s*录/.test(item.innerText || ""));
    return hasUser && hasPassword && hasButton;
  })()`, pageReadyTimeoutMs());
  if (!controlsReady) throw new AppError("等待后仍未找到登录控件", 3);
  const result = await evaluate(cdp, `(() => {
    const find = (selectors) => selectors.map((selector) => document.querySelector(selector)).find(Boolean);
    const user = find(["input[name=username]", "input[name=account]", "input[name=mobile]", "input[type=tel]", "input[placeholder='手机号']", "input[placeholder='请输入手机号']"]);
    const pwd = find(["input[name=pwd]", "input[name=password]", "input[type=password]", "input[placeholder='请输入密码']"]);
    const agree = document.querySelector("#agreementBox, input[type=checkbox]");
    const button = find(["button.btnPwdSubmit", "button[type=submit]", "input[type=submit]"])
      || [...document.querySelectorAll("button, a")].find((item) => /登\\s*录/.test(item.innerText || ""));
    if (!user || !pwd || !button) return { ok: false, reason: "login controls not found" };
    const setValue = (element, value) => {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
      setter.call(element, value);
      element.dispatchEvent(new Event("input", { bubbles: true }));
      element.dispatchEvent(new Event("change", { bubbles: true }));
    };
    setValue(user, ${username});
    setValue(pwd, ${password});
    if (agree && !agree.checked) agree.click();
    return { ok: true };
  })()`);
  if (!result?.ok) throw new AppError(result?.reason || "无法填写登录表单", 3);
  // Allow input/change handlers to update button validity before submitting once.
  await pauseBeforeAction();
  const submitted = await waitFor(cdp, `(() => {
    const button = document.querySelector("button.btnPwdSubmit, button[type=submit], input[type=submit]")
      || [...document.querySelectorAll("button, a")].find((item) => /登\\s*录/.test(item.innerText || ""));
    if (!button || button.disabled || button.getAttribute("aria-disabled") === "true"
      || button.getBoundingClientRect().width <= 0) return false;
    setTimeout(() => button.click(), 0);
    return true;
  })()`, pageReadyTimeoutMs());
  if (!submitted) throw new AppError("等待登录按钮可用超时；未提交登录，请检查表单或页面加载", 3);
  let outcome = await waitForPageOutcome(cdp, "login");
  const captchaParsed = outcome.captcha;
  if (captchaParsed) {
    await solveCaptcha(cdp, { move: moveCaptcha });
    if (!moveCaptcha) return { captchaParsed: true, loginCompleted: false };
    outcome = await waitForPageOutcome(cdp, "login");
    if (outcome.captcha) throw new AppError("登录后再次出现验证码；已停止，不自动重试", 3);
  }
  return {
    captchaParsed,
    loginCompleted: !outcome.isLoginPage,
  };
}

async function captureCaptcha(cdp) {
  await pauseBeforeAction();
  const responseText = await evaluate(cdp, `fetch("/common/verifyCode/captchar", {
    method: "POST",
    headers: { "X-Requested-With": "XMLHttpRequest" }
  }).then((response) => response.text())`);
  const jsonStart = responseText.indexOf("{");
  if (jsonStart < 0) throw new AppError("验证码响应不是 JSON", 3);
  let payload;
  try {
    payload = JSON.parse(responseText.slice(jsonStart));
  } catch (error) {
    throw new AppError(`验证码响应 JSON 解析失败：${error.message}`, 3);
  }
  const responsePiece = payload?.data?.hqImg;
  if (typeof responsePiece === "string" && responsePiece.includes(",")) {
    return { response: responseText.slice(jsonStart), piece: responsePiece.split(",", 2)[1] };
  }
  const image = await evaluate(cdp, `(() => {
    const element = document.querySelector("#xy_img");
    if (!element) return null;
    const value = getComputedStyle(element).backgroundImage;
    const match = value.match(/url\\(["']?(data:image\\/[^;]+;base64,[^"')]+)["']?\\)/);
    return match ? match[1] : null;
  })()`);
  if (!image) throw new AppError("未找到验证码拼图图片", 3);
  return { response: responseText.slice(jsonStart), piece: image.split(",", 2)[1] };
}

function runSolver(captcha) {
  const prefix = join(tmpdir(), `joinquant-captcha-${process.pid}`);
  const responsePath = `${prefix}.json`;
  const piecePath = `${prefix}.png`;
  try {
    writeFileSync(responsePath, captcha.response, { mode: 0o600 });
    writeFileSync(piecePath, Buffer.from(captcha.piece, "base64"), { mode: 0o600 });
    const solver = join(HERE, "captcha_solver.py");
    const python = process.env.JOINQUANT_PYTHON;
    const command = python
      ? { bin: python, args: [] }
      : { bin: process.env.JOINQUANT_UV || "uv", args: ["run", "--project", HERE, "python"] };
    const output = execFileSync(command.bin, [
      ...command.args, solver, "--response", responsePath, "--piece", piecePath,
    ], {
      encoding: "utf8",
      timeout: Math.max(CONFIG.timeoutMs, CONFIG.pageReadyTimeoutMs),
      maxBuffer: 1024 * 1024,
    });
    const match = output.match(/GAP_X=(\d+)/);
    if (!match) throw new AppError("验证码求解器未返回 GAP_X", 3);
    return Number(match[1]);
  } catch (error) {
    if (error instanceof AppError) throw error;
    throw new AppError(`验证码求解器执行失败：${error.message}`, 3);
  } finally {
    for (const file of [responsePath, piecePath]) {
      try { unlinkSync(file); } catch {}
    }
  }
}

async function dragCaptcha(cdp, gapX, { intentionallyWrong = false } = {}) {
  // Read geometry after the pause so a moving dialog cannot leave stale coordinates.
  await pauseBeforeAction();
  const geometry = await waitFor(cdp, `(() => {
    const track = document.querySelector("#slideVerifyDragControl, #drag, .valid-code__drag");
    const handle = track?.querySelector(".valid-code__drag-handle, .handler")
      || document.querySelector(".valid-code__drag-handle.handler, #drag .handler");
    if (!track || !handle) return null;
    const t = track.getBoundingClientRect();
    const h = handle.getBoundingClientRect();
    if (t.width <= 0 || t.height <= 0 || h.width <= 0 || h.height <= 0) return null;
    return { track: { left: t.left, top: t.top, width: t.width, height: t.height }, handle: { left: h.left, top: h.top, width: h.width, height: h.height } };
  })()`, pageReadyTimeoutMs());
  if (!geometry) {
    const seconds = Math.ceil(CONFIG.pageReadyTimeoutMs / 1000);
    throw new AppError(
      `等待验证码滑块加载超时（${seconds} 秒）；可能是网络较慢或页面仍在渲染。可设置 JOINQUANT_PAGE_READY_TIMEOUT_MS=90000 后重试`,
      3,
    );
  }
  return dragSlider(cdp, geometry, gapX, { intentionallyWrong });
}

export function choosePreviewOffset(solvedOffset, maxOffset) {
  if (![solvedOffset, maxOffset].every(Number.isFinite)
      || maxOffset < 0 || solvedOffset < 0 || solvedOffset > maxOffset) {
    throw new AppError("验证码滑块位置无效", 3);
  }
  const candidates = [Math.min(8, maxOffset), Math.max(0, maxOffset - 8)];
  const offset = candidates.reduce((farthest, candidate) => (
    Math.abs(candidate - solvedOffset) > Math.abs(farthest - solvedOffset) ? candidate : farthest
  ));
  if (Math.abs(offset - solvedOffset) < 64) {
    throw new AppError("验证码滑轨过短，无法安全选择与求解位置相差至少 64px 的预演位置", 3);
  }
  return offset;
}

export async function dragSlider(cdp, geometry, gapX, {
  intentionallyWrong = false, pause = sleep, random = Math.random,
} = {}) {
  const maxOffset = Math.max(0, geometry.track.width - geometry.handle.width);
  const solvedOffset = Math.min(Math.max(gapX, 0), maxOffset);
  const offset = intentionallyWrong ? choosePreviewOffset(solvedOffset, maxOffset) : solvedOffset;
  const startX = geometry.handle.left + geometry.handle.width / 2;
  const startY = geometry.handle.top + geometry.handle.height / 2;
  const timings = planDragTiming(random);
  const steps = timings.length;
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: startX, y: startY, buttons: 0 });
  await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: startX, y: startY, button: "left", buttons: 1, clickCount: 1 });
  for (let index = 1; index <= steps; index += 1) {
    const progress = index / steps;
    const eased = progress < 0.5 ? 2 * progress * progress : 1 - ((-2 * progress + 2) ** 2) / 2;
    await cdp.send("Input.dispatchMouseEvent", {
      type: "mouseMoved", x: startX + offset * eased, y: startY + Math.sin(progress * Math.PI) * 0.4,
      button: "left", buttons: 1,
    });
    await pause(timings[index - 1]);
  }
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: startX + offset, y: startY, button: "left", buttons: 0, clickCount: 1 });
  return offset;
}

export async function solveCaptcha(cdp, { move = true } = {}, {
  capture = captureCaptcha, solve = runSolver, drag = dragCaptcha, wait = waitForPageOutcome,
} = {}) {
  const captcha = await capture(cdp);
  const gapX = solve(captcha);
  if (!move) {
    info(`验证码缺口已由脚本计算（x=${gapX}）`);
    const previewOffset = await drag(cdp, gapX, { intentionallyWrong: true });
    info(`预演已拖动到刻意错误的位置（x=${Math.round(previewOffset)}），与求解位置相差 ${Math.round(Math.abs(previewOffset - gapX))}px`);
    return { parsed: true, gapX, previewOffset };
  }
  info(`验证码缺口已由脚本计算（x=${gapX}），开始自动拖动验证`);
  await drag(cdp, gapX);
  await wait(cdp, "verification");
  return { parsed: true };
}

async function clickSignButton(cdp) {
  await pauseBeforeAction();
  return evaluate(cdp, `(() => {
    const visible = (element) => {
      const style = getComputedStyle(element);
      const box = element.getBoundingClientRect();
      return style.visibility !== "hidden" && style.display !== "none" && box.width > 0 && box.height > 0;
    };
    const button = [...document.querySelectorAll("button, [role=button], a")].find((item) => {
      const label = (item.innerText || "").trim();
      return visible(item) && /签到/.test(label) && !/今日已签到|已签到/.test(label)
        && !item.disabled && item.getAttribute("aria-disabled") !== "true";
    });
    if (!button) return false;
    button.click();
    return true;
  })()`);
}

async function performCheckin(cdp) {
  let before = await pageState(cdp);
  if (before.alreadyCheckedIn) {
    const balances = await readPoints(cdp, before);
    info("页面确认今日已经签到，无需重复操作");
    return {
      status: "already-checked-in",
      pointsAwarded: 0,
      pointsAvailable: balances.pointsAvailable,
      pointsTotal: balances.pointsTotal,
    };
  }
  if (!before.signButton) {
    throw new AppError("未发现可用的签到按钮，也没有观察到今日已签到证据", 3);
  }
  const baseline = await readPoints(cdp, before);
  await navigate(cdp, FLOOR_URL);
  before = await waitForRelevantPage(cdp);
  if (before.alreadyCheckedIn) {
    return {
      status: "already-checked-in",
      pointsAwarded: 0,
      pointsAvailable: baseline.pointsAvailable,
      pointsTotal: baseline.pointsTotal,
    };
  }
  if (!before.signButton) {
    throw new AppError("返回签到页后未发现可用签到按钮", 3);
  }
  const clicked = await clickSignButton(cdp);
  if (!clicked) throw new AppError("签到按钮在点击前消失或不可用", 3);
  const response = await waitForPageOutcome(cdp, "checkin");
  if (response.captcha) await solveCaptcha(cdp);
  await waitForPageOutcome(cdp, "success");
  const successState = await pageState(cdp);
  await cdp.send("Page.reload");
  await sleep(CONFIG.actionDelayMs);
  await waitFor(
    cdp,
    `document.readyState === "interactive" || document.readyState === "complete"`,
    pageReadyTimeoutMs(),
  );
  const after = await waitForRelevantPage(cdp);
  const balances = await readPoints(cdp, after);
  const availableDelta = Number.isFinite(baseline.pointsAvailable)
    && Number.isFinite(balances.pointsAvailable)
    ? balances.pointsAvailable - baseline.pointsAvailable
    : null;
  return {
    status: "checked-in",
    pointsAwarded: successState.pointsAwarded ?? availableDelta,
    pointsAvailable: balances.pointsAvailable,
    pointsTotal: balances.pointsTotal,
  };
}

function emitResult(result) {
  if (result.status === "dry-run-captcha-parsed") {
    const stage = result.captchaStage === "login" ? "登录拼图（尚未进入签到阶段）" : "签到拼图";
    info(`预演阶段：${stage}；已按偏离求解位置的方式拖动，流程已停止`);
  } else {
    const display = (value) => Number.isFinite(value) ? String(value) : "未识别";
    info(
      `积分结果：本次=${display(result.pointsAwarded)}，可用=${display(result.pointsAvailable)}，累计=${display(result.pointsTotal)}`,
    );
  }
  process.stdout.write(`AUTOJOINQUANT_RESULT=${JSON.stringify(result)}\n`);
}

function printHelp() {
  process.stdout.write(`AutoJointQuant

Usage:
  node checkin.mjs [--dry-run]
  node checkin.mjs --execute
  node checkin.mjs --diagnose

Options:
  --dry-run   Parse CAPTCHA, drag to an intentionally wrong position, and stop
  --execute   Log in if needed and perform today's check-in
  --diagnose  Validate local configuration without opening a browser
  --help      Show this help
`);
}

function validateArguments() {
  const argumentsList = process.argv.slice(2);
  const allowed = new Set(["--diagnose", "--dry-run", "--execute", "--help"]);
  const unknown = argumentsList.filter((argument) => !allowed.has(argument));
  if (unknown.length) throw new AppError(`未知参数：${unknown.join(", ")}`);
  if (argumentsList.includes("--execute") && argumentsList.includes("--dry-run")) {
    throw new AppError("--execute 与 --dry-run 不能同时使用");
  }
  return {
    diagnose: argumentsList.includes("--diagnose"),
    help: argumentsList.includes("--help"),
  };
}

function diagnose() {
  const credentials = CONFIG.username && CONFIG.password ? "已配置" : "不完整";
  const browser = CONFIG.chrome && resolveExecutable(CONFIG.chrome) ? CONFIG.chrome : "未发现";
  const pythonRunner = process.env.JOINQUANT_PYTHON
    ? `Python: ${process.env.JOINQUANT_PYTHON}`
    : `uv: ${resolveExecutable(process.env.JOINQUANT_UV || "uv") || "未发现"}`;
  info(`平台=${process.platform}/${process.arch}，Node=${process.versions.node}`);
  info(`浏览器=${browser}`);
  info(`profile=${CONFIG.profile}，调试端口=${CONFIG.debugPort}，headless=${CONFIG.headless}，页面等待=${CONFIG.pageReadyTimeoutMs}ms，操作间隔基准=${CONFIG.actionDelayMs}ms（±30%）`);
  info(`环境变量文件=${CONFIG.envFile || "未加载"}，登录凭据=${credentials}，求解器运行时=${pythonRunner}`);
  if (browser === "未发现") throw new AppError(browserInstallHint());
  if (pythonRunner.endsWith("未发现")) {
    throw new AppError("未发现 uv；请安装 uv，或用 JOINQUANT_PYTHON 指向已安装求解器依赖的 Python");
  }
  info("本地配置诊断通过（未打开浏览器、未访问 JoinQuant）");
}

async function main() {
  acquireLock();
  let cdp = null;
  try {
    await ensureChrome();
    cdp = await openPage();
    await navigate(cdp, FLOOR_URL);
    let state = await waitForRelevantPage(cdp);
    info(`页面已打开：${state.isLoginPage ? "需要登录" : "已登录"}`);
    if (state.isLoginPage) {
      const login = await fillLogin(cdp, { moveCaptcha: CONFIG.execute });
      if (!CONFIG.execute && login.captchaParsed) {
        emitResult({
          status: "dry-run-captcha-parsed",
          captchaStage: "login",
          captchaParsed: true,
          pointsAwarded: null,
          pointsAvailable: null,
          pointsTotal: null,
        });
        return;
      }
      state = await waitForRelevantPage(cdp);
      if (state.isLoginPage) throw new AppError("登录未完成", 3);
    }
    if (!CONFIG.execute) {
      // A logged-in session shows the puzzle only after the sign-in button is
      // clicked. Dry-run starts that flow and deliberately misses the solved
      // position so the drag path is tested without completing the check-in.
      if (!state.alreadyCheckedIn && state.signButton) {
        if (!state.captcha) {
          info("预演：点击签到按钮以打开拼图验证；仅拖到刻意错误的位置，不提交签到");
          if (!await clickSignButton(cdp)) {
            throw new AppError("预演时未能点击签到按钮", 3);
          }
          const outcome = await waitForPageOutcome(cdp, "checkin");
          if (!outcome.captcha) {
            throw new AppError("预演点击后页面已显示已签到，未出现拼图；站点状态可能已改变，请检查账号", 3);
          }
        }
        await solveCaptcha(cdp, { move: false });
        emitResult({
          status: "dry-run-captcha-parsed",
          captchaStage: "checkin",
          captchaParsed: true,
          pointsAwarded: null,
          pointsAvailable: state.pointsAvailable,
          pointsTotal: state.pointsTotal,
        });
        return;
      }
      const checkin = state.alreadyCheckedIn ? "今日已签到" : state.signButton ? "可签到" : "未识别";
      info(`预演结果：签到状态=${checkin}，验证码=${state.captcha ? "出现" : "未出现"}`);
      const balances = state.isLoginPage ? state : await readPoints(cdp, state);
      emitResult({
        status: "dry-run",
        pointsAwarded: null,
        pointsAvailable: balances.pointsAvailable,
        pointsTotal: balances.pointsTotal,
      });
      return;
    }
    const result = await performCheckin(cdp);
    if (result.status === "checked-in") info("签到成功证据已确认");
    emitResult(result);
    if (![result.pointsAwarded, result.pointsAvailable, result.pointsTotal].every(Number.isFinite)) {
      throw new AppError("签到状态已确认，但积分数量读取不完整；请检查页面变化后再决定是否重试", 4);
    }
  } finally {
    cdp?.close();
    await closeOwnedBrowser();
    releaseLock();
  }
}

async function bootstrap() {
  const nodeMajor = Number(process.versions.node.split(".", 1)[0]);
  if (nodeMajor < 22) throw new AppError(`需要 Node.js 22+，当前为 ${process.versions.node}`);
  const argumentsState = validateArguments();
  if (argumentsState.help) {
    printHelp();
    return;
  }
  const envFile = loadConfigurationFile();
  CONFIG = buildConfig(envFile);
  if (argumentsState.diagnose) {
    diagnose();
    return;
  }
  await main();
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
  bootstrap().catch((error) => fail(error.message || String(error), error.exitCode || 1));
}
