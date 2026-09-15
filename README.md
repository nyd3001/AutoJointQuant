# AutoJointQuant

[English](README.en.md)

支持多账号的聚宽每日签到 CLI。程序使用独立 Chrome/Chromium profile，通过 CDP 登录、求解拼图并移动滑块，不依赖 Computer Use。项目只执行每日签到，不领取其他任务或修改账户设置。

## 快速开始

需要 Python 3.10+、[uv](https://docs.astral.sh/uv/)、Node.js 22+ 和 Chrome/Chromium。

```bash
git clone https://github.com/nyd3001/AutoJointQuant.git
cd AutoJointQuant
uv tool install .

autojoinquant config add main
autojoinquant run main --dry-run  # 首次先预演
autojoinquant run main            # 执行一次签到
autojoinquant status main         # 查看环境、定时器和积分
```

`config add` 会隐藏输入密码，并询问是否启用定时签到及执行时间。密码不会进入命令行参数。

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `config add <别名>` | 添加账号，并可同时设置定时签到 |
| `config list` | 列出账号、脱敏用户名和定时设置 |
| `config edit <别名>` | 修改账号或定时设置 |
| `config remove <别名>` | 删除账号、凭据和定时器；保留 profile 与历史结果 |
| `run <别名>` | 执行一次真实签到 |
| `run <别名> --dry-run` | 只检查页面，不登录、不签到、不拖动滑块 |
| `status [别名]` | 检查 Node、浏览器、求解器、账号、定时器和积分 |
| `schedule start <别名> --time HH:MM` | 安装或更新时间 |
| `schedule remove <别名>` | 删除该账号的定时器 |

示例：

```bash
autojoinquant config list
autojoinquant config edit main
autojoinquant schedule start main --time 08:30
autojoinquant schedule status main
autojoinquant schedule remove main
```

`run <别名>` 默认会修改网站状态；升级程序、首次换机器或页面异常时，先使用 `--dry-run`。

## 安装与卸载

更新 uv 安装：

```bash
uv tool install --force .
```

Nix/NixOS package 自带 Node、Python 依赖，并在 Linux 上自带 Chromium：

```bash
nix profile install .
nix run . -- status       # 临时运行
```

定时任务建议使用 `uv tool install` 或 `nix profile install` 的全局命令。卸载 uv 版本前，先删除各账号定时器：

```bash
autojoinquant schedule remove main
uv tool uninstall autojoinquant
```

卸载程序不会删除账号配置和 Chrome profile。

## 账号与安全

每个别名使用独立的凭据、浏览器 profile、运行结果和 scheduler：

```text
~/.config/autojoinquant/config.json
~/.config/autojoinquant/users/<账号哈希>.env
~/.local/share/autojoinquant/profiles/<账号哈希>/
~/.local/state/autojoinquant/users/<账号哈希>/last-run.json
```

- Registry 和凭据权限为 `0600`；密码不显示，用户名默认脱敏。
- 不要提交凭据、`.env`、日志或 Chrome profile。
- `config remove` 默认保留 profile 和历史状态，避免误删浏览器数据。
- 0.3 不迁移 0.2 的单账号配置。升级前可执行：

```bash
mv ~/.config/autojoinquant/config.json ~/.config/autojoinquant/config.v1.backup.json
```

然后重新运行 `autojoinquant config add <别名>`。旧的 `~/.config/autojoinquant.env` 不会被自动读取。

非交互环境可从 stdin 提供密码：

```bash
printf '%s\n' "$JOINQUANT_PASSWORD" | \
  autojoinquant config add main --username "$JOINQUANT_USERNAME" \
  --password-stdin --schedule --time 09:00
```

## 积分结果

成功后输出本次、可用和累计积分：

```text
[joinquant] 积分结果：本次=5，可用=55，累计=55
```

结构化结果在 CLI 内部解析，不重复打印；结果按账号保存，可用 `autojoinquant status <别名>` 或 `status --json` 查看。只有页面出现真实成功证据时才确认签到；积分读取不完整会返回退出码 `4`，此时不要自动重试。

## 平台说明

| 平台 | 浏览器 | 定时器 | 验证状态 |
| --- | --- | --- | --- |
| macOS | 系统 Chrome/Chromium | launchd | 登录、拼图、签到和积分已实机验证 |
| Linux 桌面 | Chrome/Chromium | systemd user 或 cron | CI/打包通过；真实签到待验证 |
| Linux/NixOS 无桌面 | 自动 headless Chromium | systemd user 或 cron | 尚未实机验证 |

NixOS CLI-only 主机通常需要：

```nix
users.users.<用户名>.linger = true;
```

Firefox 当前不支持。程序会自动寻找 Chrome/Chromium；必要时可设置 `JOINQUANT_CHROME_BIN`。其他常用覆盖项包括 `JOINQUANT_NODE_BIN`、`JOINQUANT_HEADLESS`、`JOINQUANT_TIMEOUT_MS` 和 `AUTOJOINQUANT_CONFIG`。

## 开发

```bash
uv sync --locked
uv run pytest
uv run ruff check .
node --check checkin.mjs  # 需要 Node.js 22+

# 或使用完整 Nix 环境
nix develop
nix flake check
```

详细安全边界见 [SECURITY.md](SECURITY.md)，贡献指南见 [CONTRIBUTING.md](CONTRIBUTING.md)，版本记录见 [CHANGELOG.md](CHANGELOG.md)。项目使用 MIT License。
