# AutoJointQuant

[![CI](https://github.com/nyd3001/AutoJointQuant/actions/workflows/ci.yml/badge.svg)](https://github.com/nyd3001/AutoJointQuant/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.3.0-blue.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[English README](README.en.md)

AutoJointQuant 是一个可全局安装、支持多账号和定时运行的聚宽每日签到 CLI。它为每个账号维护独立的凭据、Chrome/Chromium profile、执行状态和 scheduler，通过 Chrome DevTools Protocol 完成登录、拼图求解、滑块操作与签到，全程不依赖 Computer Use。

项目只执行每日签到：不会领取其他任务、浏览文章、兑换积分或修改账户设置。

```text
config add <alias> ──> 账号 registry ──> 独立凭据和 Chrome profile
       │
       └─> launchd / systemd / cron ──> run <alias>
                                               │
                                    Node.js CDP driver
                                               │
                              Python 拼图求解器 ──> JoinQuant
```

## 功能

- 使用别名管理多个聚宽账号，账号数据彼此隔离。
- 隐藏输入密码，凭据和配置以 `0600` 原子写入。
- `run <alias>` 执行单次签到，`--dry-run` 不修改网站状态。
- 自动寻找 Node.js 22+ 和 Chrome/Chromium。
- macOS 使用 launchd；Linux/NixOS 使用 systemd user，必要时回退到 cron。
- 返回本次获得、当前可用和累计积分，并按账号保存最后结果。
- 提供 uv 全局安装、Nix package、开发环境和 CI。

## 系统要求

使用 uv 安装时需要：

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- Node.js 22+
- Chrome 或 Chromium

Nix package 已包含 Node.js 和 Python 图像依赖；Linux/NixOS package 还包含 Chromium。macOS Nix package 使用系统浏览器。

Firefox 暂不支持，因为当前浏览器后端使用 CDP。

## 安装

从当前 checkout 全局安装：

```bash
git clone https://github.com/nyd3001/AutoJointQuant.git
cd AutoJointQuant
uv tool install .
autojoinquant --version
```

更新已安装版本：

```bash
uv tool install --force .
```

使用 Nix/NixOS：

```bash
nix profile install .
autojoinquant --version
```

不安装、临时运行：

```bash
nix run . -- status
```

定时任务应使用 `uv tool install` 或 `nix profile install` 产生的稳定全局命令，不建议依赖临时 `nix run` 路径。

## 快速开始

```bash
# 1. 添加账号；程序会询问用户名、隐藏密码、是否定时以及执行时间
autojoinquant config add main

# 2. 首次先预演：访问页面，但不登录、不签到、不拖动滑块
autojoinquant run main --dry-run

# 3. 执行一次真实签到
autojoinquant run main

# 4. 查看环境、scheduler 和最后积分
autojoinquant status main
```

`run <alias>` 默认会修改网站状态。升级程序、更换机器或页面行为异常时，应先运行 `--dry-run`。

## 配置

默认 registry 位于 `~/.config/autojoinquant/config.json`。可在所有命令前使用 `--config PATH`，或设置 `AUTOJOINQUANT_CONFIG`。

```bash
autojoinquant --config /path/to/config.json status
```

每个别名会映射为稳定哈希，用于隔离本地文件和 scheduler：

```text
~/.config/autojoinquant/config.json
~/.config/autojoinquant/users/<account-hash>.env
~/.local/share/autojoinquant/profiles/<account-hash>/
~/.local/state/autojoinquant/users/<account-hash>/last-run.json
```

Registry 中只保存路径和调度信息，不保存明文密码：

```json
{
  "version": 2,
  "node_bin": "/path/to/node",
  "users": {
    "main": {
      "env_file": "/home/user/.config/autojoinquant/users/<account-hash>.env",
      "profile_dir": "/home/user/.local/share/autojoinquant/profiles/<account-hash>",
      "schedule_enabled": true,
      "schedule_time": "09:00",
      "schedule_backend": "systemd"
    }
  }
}
```

通常不需要手工编辑此文件。账号命令为：

```bash
autojoinquant config add main
autojoinquant config list
autojoinquant config edit main
autojoinquant config remove main
```

`config list` 和 `status` 只显示脱敏用户名。`config remove` 删除 registry 条目、凭据和对应 timer，但保留浏览器 profile 与历史结果，并输出其位置。

非交互环境可从 stdin 读取一行密码；不提供 `--password` 参数：

```bash
printf '%s\n' "$JOINQUANT_PASSWORD" | \
  autojoinquant config add main \
  --username "$JOINQUANT_USERNAME" \
  --password-stdin --schedule --time 09:00
```

### 从 0.2 升级

0.3 不自动迁移旧版单账号配置。先备份旧 registry，再重新添加账号：

```bash
mv ~/.config/autojoinquant/config.json \
  ~/.config/autojoinquant/config.v1.backup.json
autojoinquant config add main
```

旧的 `~/.config/autojoinquant.env` 不会被新账号自动读取。

## 命令

```text
autojoinquant config add <alias>
autojoinquant config list [--json]
autojoinquant config edit <alias>
autojoinquant config remove <alias> [--yes]

autojoinquant run <alias> [--dry-run]
autojoinquant status [alias] [--json]

autojoinquant schedule start <alias> [--time HH:MM]
autojoinquant schedule status <alias>
autojoinquant schedule remove <alias>
```

完整参数使用 `autojoinquant <command> --help` 查看。

### `run`

`run <alias>` 打开该账号的独立浏览器 profile；需要登录时填写凭据，自动处理拼图，然后只执行每日签到。程序仅选择 JoinQuant 标签页，不会导航普通浏览器标签页。

成功输出保持为人类可读形式：

```text
[joinquant] 页面确认今日已经签到，无需重复操作
[joinquant] 积分结果：本次=0，可用=50，累计=50
```

内部结构化结果不会重复打印，可通过以下命令读取：

```bash
autojoinquant status main --json
```

只有页面出现签到成功、今日已签到、奖励文字或禁用签到控件等真实证据时才确认成功。积分读取不完整返回退出码 `4`，此时不要自动重试。

### `status`

`status` 检查平台、Node、浏览器、Python 求解器、凭据完整性、timer 实际状态和最后积分。该命令不打开浏览器、不访问聚宽。

```bash
autojoinquant status
autojoinquant status main
autojoinquant status --json
```

### `schedule`

每个账号可以使用独立时间：

```bash
autojoinquant schedule start main --time 08:30
autojoinquant schedule status main
autojoinquant schedule remove main
```

平台文件位置：

- macOS：`~/Library/LaunchAgents/io.github.autojoinquant.checkin.<hash>.plist`
- systemd user：`~/.config/systemd/user/autojoinquant-<hash>.{service,timer}`
- cron：每个账号一个 `AUTOJOINQUANT <hash>` managed block

macOS/cron 日志在 `~/.local/state/autojoinquant/users/<hash>/`；systemd 日志使用 `journalctl --user` 查看。

## 平台支持

| 平台 | 浏览器 | Scheduler | 当前证据 |
| --- | --- | --- | --- |
| macOS | 系统 Chrome/Chromium | launchd | 登录、拼图、真实签到和积分已实机验证 |
| Linux 桌面 | Chrome/Chromium | systemd user / cron | CI、测试和打包通过；真实签到待验证 |
| Linux/NixOS 无桌面 | 自动 headless Chromium | systemd user / cron | 尚未实机验证 |

NixOS CLI-only 主机通常需要启用 user lingering：

```nix
users.users.<用户名>.linger = true;
```

不使用项目 Nix package 时，可安装系统 Chromium：

```nix
environment.systemPackages = with pkgs; [ chromium ];
```

## 故障排查

1. 运行 `autojoinquant status <alias>`，先确认 Node、浏览器、求解器、凭据和 timer。
2. Node 不可用时安装 Node.js 22+，或设置 `JOINQUANT_NODE_BIN`。
3. 浏览器未发现时安装 Chrome/Chromium，或设置 `JOINQUANT_CHROME_BIN`。
4. 首次运行使用 `autojoinquant run <alias> --dry-run` 检查页面和登录状态。
5. 验证码或页面 DOM 变化时，程序会停止，不会切换到 Computer Use 或无限重试。
6. 退出码 `4` 表示签到状态已确认但积分不完整；不要自动重试，以免重复外部操作。
7. NixOS 用户 timer 在注销后不运行时，检查 user lingering 和 `systemctl --user status`。

常用运行时覆盖项：

| 变量 | 作用 |
| --- | --- |
| `AUTOJOINQUANT_CONFIG` | 使用其他 registry |
| `JOINQUANT_NODE_BIN` | 指定 Node.js 22+ |
| `JOINQUANT_CHROME_BIN` | 指定 Chrome/Chromium |
| `JOINQUANT_HEADLESS` | `1` 强制无头，`0` 强制有界面 |
| `JOINQUANT_TIMEOUT_MS` | 页面、CDP 和求解器超时 |

## 退出码

| 代码 | 含义 |
| --- | --- |
| `0` | 环境检查/预演成功，或签到和积分均已确认 |
| `1` | 浏览器、运行时或普通自动化错误 |
| `2` | CLI 配置错误，或登录凭据缺失 |
| `3` | 登录、验证码、点击或成功证据失败 |
| `4` | 签到状态确认，但积分读取不完整；不要自动重试 |

## 卸载

先删除每个账号的 timer，再卸载程序：

```bash
autojoinquant config list
autojoinquant schedule remove main
uv tool uninstall autojoinquant
```

Nix 安装可用 `nix profile list` 找到条目后执行 `nix profile remove <name>`。卸载命令不会删除 `~/.config/autojoinquant`、浏览器 profile 或历史结果。

## 开发与发布

```bash
uv sync --locked
uv run pytest
uv run ruff check .
/path/to/node-22-or-newer --check checkin.mjs

# 完整 Nix 环境和检查
nix develop
nix flake check
```

CI 在 macOS 和 Ubuntu 上执行 Python 测试、Ruff、Node 语法检查和包构建。真实签到会修改外部账号状态，因此不会在 CI 中运行。

发布新版本时应同步 `pyproject.toml`、`package.json`、`src/autojoinquant/__init__.py` 和 `uv.lock`，将变更从 CHANGELOG 的 `Unreleased` 固化到版本号，再创建 annotated Git tag。

当前版本：`v0.3.0`。运行 `autojoinquant --version` 查看已安装版本；版本历史见 [CHANGELOG.md](CHANGELOG.md)。安全策略见 [SECURITY.md](SECURITY.md)，贡献指南见 [CONTRIBUTING.md](CONTRIBUTING.md)。项目使用 [MIT License](LICENSE)。
