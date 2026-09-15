# AutoJointQuant

[![CI](https://github.com/nyd3001/AutoJointQuant/actions/workflows/ci.yml/badge.svg)](https://github.com/nyd3001/AutoJointQuant/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.3.0-blue.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[English README](README.en.md)

AutoJointQuant 是支持多账号和定时任务的聚宽每日签到 CLI，可自动登录、完成拼图验证、签到并返回积分，不依赖 Computer Use。
项目只执行每日签到。目前已在 macOS 实机验证；Linux/NixOS 已提供配置，但尚未实机验证。
当前使用 Chrome/Chromium，暂不支持 Firefox。

## 安装

uv 安装需要 Python 3.10+、uv、Node.js 22+ 和 Chrome/Chromium。

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

系统不需要预装 Node.js。三种 Nix 入口的作用不同：

| 入口 | 作用域 | 适用场景 |
| --- | --- | --- |
| `nix develop` | 仅当前开发 shell | 提供 Node.js 22、uv、Python 和拼图求解依赖 |
| `nix run . -- <命令>` | 单次运行 | 临时执行 CLI，不安装全局命令 |
| `nix profile install .` | 当前用户、持久化 | 日常使用和 scheduler；推荐 |

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

## 卸载

先删除每个账号的 timer，再卸载程序：

```bash
autojoinquant config list
autojoinquant schedule remove main
uv tool uninstall autojoinquant
```

Nix 安装可用 `nix profile list` 找到条目后执行 `nix profile remove <name>`。卸载命令不会删除 `~/.config/autojoinquant`、浏览器 profile 或历史结果。

当前版本：`v0.3.0`。运行 `autojoinquant --version` 查看已安装版本；版本历史见 [CHANGELOG.md](CHANGELOG.md)。安全策略见 [SECURITY.md](SECURITY.md)，贡献指南见 [CONTRIBUTING.md](CONTRIBUTING.md)。项目使用 [MIT License](LICENSE)。
