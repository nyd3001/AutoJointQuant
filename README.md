# AutoJointQuant

[English README](README.en.md)

AutoJointQuant 是一个可全局安装、可定时运行的聚宽每日签到 CLI。它使用独立 Chrome/Chromium profile，通过 Chrome DevTools Protocol 完成登录和签到；拼图缺口由本地 Python 图像匹配计算，滑块也由程序通过 CDP 操作，全程不依赖 Computer Use。

项目严格限定为“每日签到”：不会领取其他任务、浏览文章、兑换积分或修改账户设置。

## 命令地图

| 命令 | 是否修改网站状态 | 作用 |
| --- | --- | --- |
| `autojoinquant init --time 09:00` | 是 | 隐藏输入凭据，检测环境并安装每日定时器 |
| `autojoinquant run` | 否 | 默认预演；不登录、不签到、不拖动滑块 |
| `autojoinquant run --execute` | 是 | 执行一次登录、验证码和签到 |
| `autojoinquant diagnose` | 否 | 检查 Node、浏览器、Python 和配置，不访问聚宽 |
| `autojoinquant status` | 否 | 显示定时器及最后一次积分结果，不显示凭据 |
| `autojoinquant schedule install --time 08:30` | 是 | 安装或更新时间 |
| `autojoinquant schedule remove` | 是 | 删除本项目管理的定时器 |

## 安装为全局命令

### uv：macOS / 通用 Linux

系统需要 Python 3.10+、uv、Node.js 22+，以及 Chrome 或 Chromium：

```bash
git clone https://github.com/nyd3001/AutoJointQuant.git
cd AutoJointQuant
uv tool install .
autojoinquant --version
autojoinquant diagnose
```

如果升级当前 checkout：

```bash
uv tool install --force .
```

CLI 会遍历 `PATH`，跳过旧 Node，选择第一个 Node.js 22+；也可显式设置 `JOINQUANT_NODE_BIN`。例如系统默认 `node` 很旧，但 Homebrew、Conda 或 Nix profile 中另有新版本时，无需手工切换 PATH 顺序。

### Nix / NixOS

Nix package 自带 Node.js、Python 求解依赖；Linux/NixOS 构建还自带 Chromium：

```bash
nix profile install .
autojoinquant diagnose
```

无需安装也可以临时运行：

```bash
nix run . -- diagnose
```

建议定时任务使用 `nix profile install .`，而不是依赖可能被垃圾回收的临时 `nix run` 路径。macOS 的 Nix package 仍使用系统安装的 Chrome/Chromium。

### 开发环境

```bash
nix develop
uv sync --locked
uv run pytest
uv run ruff check .
node --check checkin.mjs
```

也可只使用 uv；注意 uv 不负责安装 Node 和浏览器。

## 初始化和凭据

交互式初始化：

```bash
autojoinquant init --time 09:00
```

`init` 会：

1. 隐藏输入密码，且不接受 `--password` 参数，避免进入 shell history；
2. 将账号和密码写入 `~/.config/autojoinquant.env`，权限固定为 `0600`；
3. 将时间、Node 路径和独立浏览器 profile 写入 `~/.config/autojoinquant/config.json`；
4. 运行不联网的环境诊断；
5. 诊断通过后，根据系统安装 launchd、systemd user timer 或 cron。

只保存配置、不安装定时器：

```bash
autojoinquant init --time 09:00 --no-schedule
```

非交互环境可把密码从标准输入提供：

```bash
printf '%s\n' "$JOINQUANT_PASSWORD" | \
  autojoinquant init --username "$JOINQUANT_USERNAME" --password-stdin --time 09:00
```

不要把真实密码直接写进命令参数，也不要提交 `.env`、Chrome profile 或日志。凭据文件由 Node 自己读取，不要求写进 `.zprofile`，也不建议 `source ~/.config/autojoinquant.env`。已存在的进程环境变量优先于文件。

仍可完全依赖环境变量：

```bash
export JOINQUANT_USERNAME='手机号'
export JOINQUANT_PASSWORD='密码'
autojoinquant run --execute
```

## 自动选择运行环境

| 环境 | 浏览器 | 定时器 | 行为 |
| --- | --- | --- | --- |
| macOS | 自动寻找系统 Chrome/Chromium | launchd LaunchAgent | 使用图形浏览器；可显式启用 headless |
| Linux 桌面 | 自动寻找 Chrome/Chromium | systemd user，缺失时 cron | 使用当前 DISPLAY/Wayland |
| Linux 无桌面 | 自动寻找 Chrome/Chromium | systemd user，缺失时 cron | 无 DISPLAY/Wayland 时自动 headless |
| NixOS | flake 自带 Chromium | systemd user | CLI-only 主机通常还需 user lingering |

NixOS 无桌面用户服务需要在系统配置中启用 lingering，例如：

```nix
users.users.<用户名>.linger = true;
```

如果不通过本项目 flake 安装 Chromium，也可以系统级安装：

```nix
environment.systemPackages = with pkgs; [ chromium ];
```

`nix develop` 和 `nix run` 会自动设置正确的 `JOINQUANT_CHROME_BIN`，通常无需手工执行 `export JOINQUANT_CHROME_BIN="$(command -v chromium)"`。

Firefox 当前不受支持：本实现使用 CDP，而 Firefox 需要独立的 WebDriver BiDi/Marionette 后端，不能只把 `JOINQUANT_CHROME_BIN` 改成 Firefox。

## 运行与积分结果

任何升级后先预演：

```bash
autojoinquant run
```

确认后执行一次：

```bash
autojoinquant run --execute
```

执行结束会返回：

```text
[joinquant] 积分结果：本次=5，可用=55，累计=55
AUTOJOINQUANT_RESULT={"status":"checked-in","pointsAwarded":5,"pointsAvailable":55,"pointsTotal":55}
```

- `pointsAwarded`：本次签到新增；若今天此前已经签到则为 `0`；预演为 `null`。
- `pointsAvailable`：当前可用积分。
- `pointsTotal`：累计获得积分。

CLI 会把最后一次结构化结果写入 `~/.local/state/autojoinquant/last-run.json`，`autojoinquant status` 可查看。脚本只在页面出现签到成功、今日已签到、积分奖励文字或禁用签到按钮等真实证据时确认成功；不会根据旧缓存或按钮缺失猜测成功。

## 定时器管理

`init` 默认安装定时器，也可以单独管理：

```bash
autojoinquant schedule install --time 08:30
autojoinquant schedule status
autojoinquant schedule remove
```

平台文件位置：

- macOS：`~/Library/LaunchAgents/io.github.autojoinquant.checkin.plist`；
- systemd user：`~/.config/systemd/user/autojoinquant.{service,timer}`；
- cron：带 `AUTOJOINQUANT MANAGED BLOCK` 标记的单个 crontab 区块。

macOS 日志位于 `~/.local/state/autojoinquant/launchd.*.log`；cron 日志为 `~/.local/state/autojoinquant/cron.log`；systemd 使用 `journalctl --user -u autojoinquant.service`。机器必须处于开机状态；macOS 睡眠期间不会保证准点运行。

## 配置变量

| 变量 | 作用 |
| --- | --- |
| `JOINQUANT_USERNAME` / `JOINQUANT_PASSWORD` | 登录凭据 |
| `JOINQUANT_ENV_FILE` | 凭据文件；默认 `~/.config/autojoinquant.env`，设为 `-` 可禁用文件加载 |
| `AUTOJOINQUANT_CONFIG` | CLI 设置 JSON 路径 |
| `JOINQUANT_NODE_BIN` | Node.js 22+ 路径 |
| `JOINQUANT_CHROME_BIN` | Chrome/Chromium 路径；通常自动探测 |
| `JOINQUANT_PROFILE_DIR` | 独立 Chrome profile |
| `JOINQUANT_DEBUG_PORT` | `auto`（默认）或固定的 1–65535 端口 |
| `JOINQUANT_HEADLESS` | `1` 强制无头；`0` 强制有界面 |
| `JOINQUANT_TIMEOUT_MS` | 页面、CDP、求解器超时，默认 15000 |
| `JOINQUANT_PYTHON` | 已安装 Pillow/numpy/scipy 的 Python |
| `JOINQUANT_UV` | 直接运行 `checkin.mjs` 时使用的 uv 路径 |
| `JOINQUANT_ALLOW_NO_SANDBOX` | Linux root 下显式允许 `--no-sandbox`；不推荐 |

默认调试端口为自动分配，避免与其他浏览器冲突；旧版项目遗留且仍在运行的专用 9223 profile 可以安全复用。程序只选择 JoinQuant 标签页，不会导航或覆盖普通浏览器标签页。每个 profile 还有进程锁，避免定时器重叠执行。

## 验证状态

| 项目 | 当前证据 |
| --- | --- |
| macOS 登录、拼图和真实签到 | 已实机成功验证 |
| macOS 0.2 CLI 环境诊断、dry-run、旧 9223 兼容和积分读取 | 已实机验证；只读结果正确返回可用/累计积分 |
| macOS launchd 到点触发 | 配置生成和单元测试通过；尚未等待下一次真实定时触发 |
| Linux | Ubuntu CI 覆盖 Python/Node/package；浏览器真实签到待验证 |
| NixOS | flake 的四个平台输出可评估；真实 systemd/headless 签到待验证 |
| 无桌面 headless 登录、拼图与签到 | 尚未实机验证 |

“包能构建”“flake 能评估”不等于真实网站验收。Linux/NixOS 或 headless 首次使用时，应先运行 `diagnose` 和 dry-run，再人工监督一次 `--execute`。

## 退出码

- `0`：预演成功，或签到状态和积分均已确认；
- `1`：浏览器、配置或其他普通运行错误；
- `2`：需要登录但凭据缺失；
- `3`：登录、验证码、点击或签到成功证据失败；
- `4`：签到状态已经确认，但积分数量读取不完整。此时不要自动重试，以免重复外部操作。

## 项目结构与开发

```text
.
├── src/autojoinquant/       # 可安装 CLI、配置、运行时探测和定时器
├── checkin.mjs              # CDP 登录、签到、滑块和积分读取
├── captcha_solver.py        # 本地图像匹配求解器
├── tests/                   # solver、配置、Node 发现、定时器测试
├── pyproject.toml / uv.lock # uv 安装与锁文件
├── flake.nix / flake.lock   # nix run / profile / develop / checks
└── README.en.md             # 英文文档
```

验证码接口或页面 DOM 可能变化。失败时程序保留明确错误并停止，不切换到 Computer Use，也不无限重试。贡献要求见 [CONTRIBUTING.md](CONTRIBUTING.md)，安全边界见 [SECURITY.md](SECURITY.md)，版本记录见 [CHANGELOG.md](CHANGELOG.md)。

本项目使用 MIT License。验证码布局和积分选择器参考公开页面行为及[公开参考项目](https://github.com/youngyunxing/joinquant-auto-skill)，但本项目只执行每日签到，不包含该参考项目的其他积分任务。
