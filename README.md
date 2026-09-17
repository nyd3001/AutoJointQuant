<h1 align="center">AutoJointQuant</h1>
<p align="center">聚宽多账号自动签到：支持定时任务、拼图验证和积分回显，不依赖 Computer Use。</p>
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

# 登录、解析拼图并拖到偏离求解位置的位置后停止
autojoinquant run main --dry-run

# 真实签到、查看状态
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

首次使用或环境变化后先执行 `--dry-run`。输出会区分登录拼图与签到拼图；预演涉及网页操作，无法保证站点状态不变。完整参数见 `autojoinquant <command> --help`。

页面加载较慢时可调整等待时间：`JOINQUANT_PAGE_READY_TIMEOUT_MS=90000 autojoinquant run main --dry-run`

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
