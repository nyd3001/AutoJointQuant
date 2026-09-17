<h1 align="center">AutoJointQuant</h1>
<p align="center">聚宽多账号签到与社区浏览积分：支持定时任务、拼图验证和积分回显，不依赖 Computer Use。</p>
<p align="center"><strong>已验证：</strong>macOS · Linux · NixOS · <strong>浏览器：</strong>Chrome/Chromium</p>
<p align="center"><a href="README.en.md">English</a></p>

## 安装

### 方式一：Nix（推荐）

```bash
git clone https://github.com/nyd3001/AutoJointQuant.git
cd AutoJointQuant
nix profile install .
```

Nix package 已包含 Node.js 和拼图求解依赖，Linux/NixOS 下也包含 Chromium。

### 方式二：uv

```bash
git clone https://github.com/nyd3001/AutoJointQuant.git
cd AutoJointQuant
uv tool install .
```

uv 安装需要 Python 3.10+、uv、Node.js 22+ 和 Chrome/Chromium。

## 快速开始

```bash
# 添加账号；按提示输入用户名、确认密码和定时设置
autojoinquant config add main

# 登录后预演签到和浏览奖励拼图，每个阶段只错位拖动一次
autojoinquant run main --dry-run

# 签到、随机浏览一篇文章并领取积分；查看状态
autojoinquant run main
autojoinquant status main

# 管理账号
autojoinquant config list
autojoinquant config edit main
autojoinquant config remove main

# 管理定时任务
autojoinquant schedule start main --time 08:30
autojoinquant schedule status main
autojoinquant schedule remove main
```

首次使用或环境变化后先执行 `--dry-run`：登录成功后依次预演签到和浏览奖励，浏览文章后点击“立即领取”打开拼图，计算缺口并拖到相距至少 64px 的错误位置，不尝试通过验证；已签到则跳过签到阶段。遇到登录拼图仅预演登录后停止；任务已完成则跳过，任何异常均停止且不重试。预演会浏览文章、点击按钮，无法保证站点状态不变，也不会覆盖正式运行记录。完整参数见 `autojoinquant <command> --help`。

`run`（含定时任务）会随机选择社区文章，尽量避开上次文章，正文加载后随机停留 **45–90 秒**，再领取浏览奖励；本机记录当天已完成则跳过，已有待领奖励则不重复浏览。签到与浏览积分分别报告。预演使用相同的随机浏览流程；可用 `JOINQUANT_READING_MIN_MS` / `JOINQUANT_READING_MAX_MS` 调整停留区间。

升级后，已有 systemd 定时任务请重新执行 `schedule start <alias>`，应用延长后的 15 分钟运行上限。

页面较慢时设置 `JOINQUANT_PAGE_READY_TIMEOUT_MS=90000`。登录提交、点击签到、读取拼图及拖动前默认等待 0.7–1.3 秒，可用 `JOINQUANT_ACTION_DELAY_MS=2000` 将范围调为 1.4–2.6 秒；拖动时长及步间隔也有波动。

## 卸载

### Nix

```bash
autojoinquant schedule remove main
nix profile remove autojoinquant
```

### uv

```bash
autojoinquant schedule remove main
uv tool uninstall autojoinquant
```

卸载不会删除账号数据和历史结果。
