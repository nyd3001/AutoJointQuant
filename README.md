# AutoJointQuant

[![CI](https://github.com/nyd3001/AutoJointQuant/actions/workflows/ci.yml/badge.svg)](https://github.com/nyd3001/AutoJointQuant/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.3.0-blue.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[English README](README.en.md)

AutoJointQuant 是支持多账号和定时任务的聚宽每日签到 CLI，可自动登录、完成拼图验证、签到并返回积分，不依赖 Computer Use。
项目只执行每日签到。目前已在 macOS 实机验证；Linux/NixOS 已提供配置，但尚未实机验证。
当前使用 Chrome/Chromium，暂不支持 Firefox。

## 安装

先获取项目：

```bash
git clone https://github.com/nyd3001/AutoJointQuant.git
cd AutoJointQuant
```

### 方式一：Nix（推荐）

```bash
nix profile install .
```

Nix package 已包含 Node.js 和拼图求解依赖，Linux/NixOS 下也包含 Chromium。

### 方式二：uv

```bash
uv tool install .
```

uv 安装需要 Python 3.10+、uv、Node.js 22+ 和 Chrome/Chromium。

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

## 卸载

先删除每个账号的 timer，再卸载程序：

```bash
autojoinquant config list
autojoinquant schedule remove main
uv tool uninstall autojoinquant
```

Nix 安装可用 `nix profile list` 找到条目后执行 `nix profile remove <name>`。卸载命令不会删除 `~/.config/autojoinquant`、浏览器 profile 或历史结果。

当前版本：`v0.3.0`。运行 `autojoinquant --version` 查看已安装版本；版本历史见 [CHANGELOG.md](CHANGELOG.md)。安全策略见 [SECURITY.md](SECURITY.md)，贡献指南见 [CONTRIBUTING.md](CONTRIBUTING.md)。项目使用 [MIT License](LICENSE)。
