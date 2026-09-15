<div align="center">
  <h1>AutoJointQuant</h1>
  <p>聚宽多账号自动签到：支持定时任务、拼图验证和积分回显，不依赖 Computer Use。</p>
  <p><strong>macOS：</strong>已验证 · <strong>Linux/NixOS：</strong>待验证 · <strong>浏览器：</strong>Chrome/Chromium</p>
  <p>
    <a href="https://github.com/nyd3001/AutoJointQuant/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/nyd3001/AutoJointQuant/actions/workflows/ci.yml/badge.svg"></a>
    <a href="CHANGELOG.md"><img alt="Version 0.3.0" src="https://img.shields.io/badge/version-0.3.0-blue.svg"></a>
    <a href="LICENSE"><img alt="License MIT" src="https://img.shields.io/badge/license-MIT-green.svg"></a>
  </p>
  <p><a href="README.en.md">English</a></p>
</div>

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
# 添加账号；按提示输入用户名、密码和定时设置
autojoinquant config add main

# 预演、签到、查看状态
autojoinquant run main --dry-run
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

首次使用或环境变化后先执行 `--dry-run`；完整参数使用 `autojoinquant <command> --help` 查看。

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

<div align="center">
  <a href="CHANGELOG.md">Changelog</a> · <a href="SECURITY.md">Security</a> · <a href="CONTRIBUTING.md">Contributing</a> · <a href="LICENSE">MIT License</a>
</div>
