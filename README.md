# AutoJointQuant

[English README](README.en.md)

AutoJointQuant 是一个支持多账号、可全局安装、可定时运行的聚宽每日签到 CLI。每个账号由本地别名标识，并拥有独立的凭据文件、Chrome/Chromium profile、运行结果和定时任务。

程序通过 Chrome DevTools Protocol 完成登录和签到；拼图缺口由本地 Python 图像匹配计算，滑块由程序通过 CDP 操作，全程不依赖 Computer Use。

项目严格限定为“每日签到”：不会领取其他任务、浏览文章、兑换积分或修改账户设置。

## 推荐命令模型

```text
config add/list/edit/remove   管理本地账号
run <别名>                    立即执行一次签到
status [别名]                 检查环境、账号、定时器和积分结果
schedule start/remove/status  管理单个账号的定时器
```

| 命令 | 网站状态 | 作用 |
| --- | --- | --- |
| `autojoinquant config add main` | 不修改 | 添加别名、用户名和密码，并询问是否定时签到及时间 |
| `autojoinquant config list` | 不访问 | 列出别名、脱敏用户名和定时设置 |
| `autojoinquant config edit main` | 不修改 | 修改凭据或定时设置 |
| `autojoinquant config remove main` | 不访问 | 删除账号配置、凭据和对应定时器；保留浏览器 profile 和历史状态 |
| `autojoinquant run main` | 修改 | 为 `main` 执行一次登录、验证码和签到 |
| `autojoinquant run main --dry-run` | 不修改 | 只检查网页状态；不登录、不签到、不拖动滑块 |
| `autojoinquant status` | 不访问 | 检查运行环境，并显示所有账号、定时器和最后积分结果 |
| `autojoinquant status main` | 不访问 | 只检查 `main` |
| `autojoinquant schedule start main --time 08:30` | 不访问网站 | 诊断环境并安装或更新 `main` 的每日定时器 |
| `autojoinquant schedule remove main` | 不访问 | 只删除 `main` 的定时器，不删除账号 |

`run <别名>` 默认执行真实签到，因为命令中已经明确指定了动作和账号。升级程序、首次使用新系统或排查页面变化时，请先运行 `run <别名> --dry-run`。

## 安装为全局命令

### uv：macOS / 通用 Linux

系统需要 Python 3.10+、uv、Node.js 22+，以及 Chrome 或 Chromium：

```bash
git clone https://github.com/nyd3001/AutoJointQuant.git
cd AutoJointQuant
uv tool install .
autojoinquant --version
autojoinquant status
```

升级当前 checkout：

```bash
uv tool install --force .
```

CLI 会遍历 `PATH`，跳过旧 Node，选择第一个 Node.js 22+；也可设置 `JOINQUANT_NODE_BIN`。

### Nix / NixOS

Nix package 自带 Node.js 和 Python 求解依赖；Linux/NixOS 构建还自带 Chromium：

```bash
nix profile install .
autojoinquant status
```

无需安装也可以临时运行：

```bash
nix run . -- status
```

定时任务建议使用 `nix profile install .`，避免依赖可能被垃圾回收的临时 `nix run` 路径。macOS Nix package 使用系统 Chrome/Chromium。

### 开发环境

```bash
nix develop
uv sync --locked
uv run pytest
uv run ruff check .
node --check checkin.mjs
```

## 添加和管理账号

最简单的初始化方式：

```bash
autojoinquant config add main
```

程序依次询问：

1. 聚宽用户名；
2. 聚宽密码，终端不回显；
3. 是否开启每日自动签到；
4. 如果开启，每日执行时间。

密码不接受 `--password` 参数，避免出现在 shell history、进程列表或 scheduler 文件中。非交互环境可以从标准输入读取一行密码：

```bash
printf '%s\n' "$JOINQUANT_PASSWORD" | \
  autojoinquant config add main \
    --username "$JOINQUANT_USERNAME" \
    --password-stdin \
    --schedule \
    --time 09:00
```

查看账号：

```bash
autojoinquant config list
autojoinquant config list --json
```

修改账号；按 Enter 可保留现有用户名或密码：

```bash
autojoinquant config edit main
```

删除账号：

```bash
autojoinquant config remove main
```

删除会要求确认，并移除账号 registry、凭据和对应 scheduler。为避免不可恢复的数据损失，独立 Chrome profile 和历史运行结果默认保留，命令会输出它们的位置。

## 配置和数据隔离

默认 registry：

```text
~/.config/autojoinquant/config.json
```

每个别名对应一个不可反推用户名的稳定哈希目录或文件名：

```text
~/.config/autojoinquant/users/<账号哈希>.env
~/.local/share/autojoinquant/profiles/<账号哈希>/
~/.local/state/autojoinquant/users/<账号哈希>/last-run.json
```

Registry 和凭据文件权限固定为 `0600`。用户名在 `config list` 和 `status` 中脱敏；密码永不输出。运行命名账号时，程序会移除 shell 中继承的 `JOINQUANT_USERNAME` 和 `JOINQUANT_PASSWORD`，防止误用其他账号的环境变量。

0.3 使用新的多账号配置格式，不自动迁移 0.2 的单账号 `config.json`。如果存在旧配置，请先备份：

```bash
mv ~/.config/autojoinquant/config.json ~/.config/autojoinquant/config.v1.backup.json
autojoinquant config add main
```

旧的 `~/.config/autojoinquant.env` 不会被新账号自动读取。

## 单次签到和积分

首次运行或更新后先预演：

```bash
autojoinquant run main --dry-run
```

执行一次签到：

```bash
autojoinquant run main
```

执行结束会返回：

```text
[joinquant] 积分结果：本次=5，可用=55，累计=55
AUTOJOINQUANT_RESULT={"status":"checked-in","pointsAwarded":5,"pointsAvailable":55,"pointsTotal":55}
```

- `pointsAwarded`：本次签到新增；若今天此前已经签到则为 `0`；预演为 `null`。
- `pointsAvailable`：当前可用积分。
- `pointsTotal`：累计获得积分。

结果按账号保存，`autojoinquant status main` 可查看。只有页面出现签到成功、今日已签到、积分奖励文字或禁用签到按钮等真实证据时才确认成功；按钮缺失本身不算成功。

## 环境检查和定时器

`status` 不打开浏览器、不访问聚宽，也不会签到：

```bash
autojoinquant status
autojoinquant status main
autojoinquant status --json
```

它会检查平台、Node.js 22+、Chrome/Chromium、Python 求解器、凭据完整性、每个 scheduler 的实际状态，以及最后一次积分结果。

每个账号可以独立设置时间：

```bash
autojoinquant schedule start main --time 08:30
autojoinquant schedule status main
autojoinquant schedule remove main
```

平台文件使用账号哈希隔离：

- macOS：`~/Library/LaunchAgents/io.github.autojoinquant.checkin.<账号哈希>.plist`；
- systemd user：`~/.config/systemd/user/autojoinquant-<账号哈希>.{service,timer}`；
- cron：每个账号一个独立的 `AUTOJOINQUANT <账号哈希>` managed block。

## 自动选择运行环境

| 环境 | 浏览器 | 定时器 | 行为 |
| --- | --- | --- | --- |
| macOS | 自动寻找系统 Chrome/Chromium | launchd LaunchAgent | 使用图形浏览器；可显式启用 headless |
| Linux 桌面 | 自动寻找 Chrome/Chromium | systemd user，缺失时 cron | 使用当前 DISPLAY/Wayland |
| Linux 无桌面 | 自动寻找 Chrome/Chromium | systemd user，缺失时 cron | 无 DISPLAY/Wayland 时自动 headless |
| NixOS | flake 自带 Chromium | systemd user | CLI-only 主机通常还需 user lingering |

NixOS 无桌面用户服务可在系统配置中启用 lingering：

```nix
users.users.<用户名>.linger = true;
```

如果不使用项目 flake，也可以安装系统 Chromium：

```nix
environment.systemPackages = with pkgs; [ chromium ];
```

`nix develop`、`nix run` 和 Nix package 会自动设置 Linux Chromium 路径，通常无需手工导出 `JOINQUANT_CHROME_BIN`。

Firefox 当前不支持：本实现使用 CDP，而 Firefox 需要独立的 WebDriver BiDi/Marionette 后端。

## 高级环境变量

多账号凭据、profile 和状态路径由 registry 管理。以下变量仅用于运行时覆盖：

| 变量 | 作用 |
| --- | --- |
| `AUTOJOINQUANT_CONFIG` | 使用其他账号 registry |
| `JOINQUANT_NODE_BIN` | Node.js 22+ 路径 |
| `JOINQUANT_CHROME_BIN` | Chrome/Chromium 路径；通常自动探测 |
| `JOINQUANT_DEBUG_PORT` | `auto`（默认）或固定的 1–65535 端口 |
| `JOINQUANT_HEADLESS` | `1` 强制无头；`0` 强制有界面 |
| `JOINQUANT_TIMEOUT_MS` | 页面、CDP、求解器超时，默认 15000 |
| `JOINQUANT_PYTHON` | 已安装 Pillow/numpy/scipy 的 Python |
| `JOINQUANT_UV` | 直接运行内部 `checkin.mjs` 时使用的 uv 路径 |
| `JOINQUANT_ALLOW_NO_SANDBOX` | Linux root 下显式允许 `--no-sandbox`；不推荐 |

默认调试端口自动分配。程序只选择 JoinQuant 标签页，不会导航普通浏览器标签页；每个账号 profile 有独立进程锁，避免定时任务重叠。

## 验证状态

| 项目 | 当前证据 |
| --- | --- |
| macOS 登录、拼图和真实签到 | 已实机成功验证 |
| macOS 环境诊断、dry-run、旧 9223 兼容和积分读取 | 已实机验证 |
| 多账号 CLI 和 per-account scheduler | 单元测试、静态检查和安全预演覆盖；尚未安装真实新 scheduler |
| Linux | Ubuntu CI 覆盖 Python/Node/package；浏览器真实签到待验证 |
| NixOS | flake 支持四个平台；真实 systemd/headless 签到待验证 |
| 无桌面 headless 登录、拼图与签到 | 尚未实机验证 |

“包能构建”不等于真实网站验收。Linux/NixOS 或 headless 首次使用时，应先运行 `status` 和 `run <别名> --dry-run`，再人工监督一次 `run <别名>`。

## 退出码

- `0`：环境检查/预演成功，或签到状态和积分均已确认；
- `1`：浏览器、配置或其他普通运行错误；
- `2`：CLI 配置错误，或需要登录但凭据缺失；
- `3`：登录、验证码、点击或签到成功证据失败；
- `4`：签到状态已确认，但积分读取不完整；此时不要自动重试。

验证码接口或页面 DOM 可能变化。失败时程序保留明确错误并停止，不切换到 Computer Use，也不无限重试。贡献要求见 [CONTRIBUTING.md](CONTRIBUTING.md)，安全边界见 [SECURITY.md](SECURITY.md)，版本记录见 [CHANGELOG.md](CHANGELOG.md)。

本项目使用 MIT License。验证码布局和积分选择器参考公开页面行为及[公开参考项目](https://github.com/youngyunxing/joinquant-auto-skill)，但本项目只执行每日签到。
