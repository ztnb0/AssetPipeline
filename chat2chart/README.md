# chat2chart · 一句话生成数据图表

一个极简的前后端产品：前端输入一句自然语言（如「对比中美近几年的黄金储备量」），后端创建独立任务目录并
headless 调用 **opencode**（Agent）。两种模式：复用 **lieflat-charts** 技能 + **AKShare** 取数产出单文件 HTML 图表；
或用 **Remotion** 官方技能让 Agent 写动画组合代码，再由后端 `npx remotion render` 渲染成 1080p MP4。
前端轮询任务状态后 iframe 预览 HTML 或 `<video>` 预览/下载 MP4。

> 复用的就是本次「中美黄金储备对比」图例的完整逻辑：技能 → 取数 → 按 catalog 选 Lupi/Basics 模板 → 单文件 HTML。

## 目录结构

```text
chat2chart/
├── .env.example          # 配置模板（复制为 .env）
├── start.ps1             # Windows 一键启动（建 venv + 装依赖 + 起 uvicorn）
├── README.md
├── backend/
│   ├── main.py           # FastAPI：任务 API + 首页 + 产物下载
│   ├── runner.py         # 任务队列：调 opencode run、流式日志、超时终止、回收 chart.html / 渲染 video.mp4
│   └── requirements.txt
├── frontend/
│   └── index.html        # 单页前端（无构建步骤）
├── remotion/             # 共享 Remotion 工程（一次性 npm install；每任务写到 src/compositions/<job_id>/）
└── data/jobs/<job_id>/   # 运行期生成：每个任务一个目录
```

## 架构与一次任务的生命周期

```text
浏览器 ──POST /api/jobs {prompt, extra, mode}──▶ FastAPI
                                    │ 建 data/jobs/<id>/run 独立目录
                                    ▼
                          opencode run --dir <run> --agent build --auto "<固定指令+用户描述>"

  mode="chart"：指令要求读 lieflat-charts 技能 → 取数 → 产出 <run>/chart.html
                ▼
        runner 回收 <run>/chart.html → <job>/chart.html

  mode="video"：指令要求按 Remotion 官方技能写 <run>/entry.tsx + data.ts（自由设计，不套 Lupi/Mono）
                ▼
        runner 把两者拷进 remotion/src/compositions/<id>/，执行 npx remotion render → <job>/video.mp4

浏览器 ◀──GET /api/jobs/<id> 轮询 status──┘
浏览器 ◀──GET /api/jobs/<id>/chart 或 /video── 预览 / 下载
```

- 并发上限：`C2C_MAX_CONCURRENT`（默认 2）；单任务超时：`C2C_JOB_TIMEOUT`（默认 900s，超时 kill）。
- 图表入场动画时长：`C2C_ANIM_SECONDS`（默认 8 秒）。设为更大的值可把标题/图形/结论的分层揭示节奏放慢、拉长整体展示时长，便于录屏做成视频素材；动画结束后保持定格。
- 循环重播：`C2C_ANIM_LOOP=1` 时动画结束后自动重播（全局默认）；前端「展示时长」「动画结束后循环重播」两个控件可对单个任务临时覆盖，无需重启。
- 视频模式：`C2C_VIDEO_MAX_CONCURRENT`（默认 1，渲染吃 CPU）、`C2C_RENDER_TIMEOUT`（默认 600s）、`C2C_VIDEO_WIDTH/HEIGHT/FPS`（默认 1920/1080/30）。
- 每任务独立目录、独立进程；日志实时写入任务目录并回流到前端「查看 Agent 运行日志」。

## 环境要求

- Windows / Linux / macOS，装好 Python（建议 **3.11**，与 akshare 兼容性最好）
- **opencode CLI**（后端通过 `opencode run` headless 调用，Desktop 版本身不含 CLI）：

  ```powershell
  # 任选其一
  npm install -g opencode-ai
  # 或：irm https://opencode.ai/install | iex
  ```

  装完确认 `opencode --version` 可用，并已完成模型登录（`opencode auth login` 或已有 provider key）。
  若 CLI 不在 PATH，在 `.env` 里写 `OPENCODE_BIN=完整路径`。

- **lieflat-charts 技能**（取数/设计规范来源，自动探测 `~/.claude/skills/lieflat-charts`）：

  ```powershell
  git clone --depth 1 https://github.com/larashero3-dotcom/lieflat-charts "$HOME\.claude\skills\lieflat-charts"
  ```

- **akshare Python**（后端会自动探测已装 akshare 的解释器，含 pythoncore-3.11；也可用
  `AKSHARE_PYTHON=` 显式指定。取数在 Agent 子进程内进行，需要联网）。

- **视频模式还需 Node.js + Remotion 工程**（仅 `mode=video` 需要；HTML 图表模式可忽略）：

  ```powershell
  cd chat2chart/remotion
  npm install
  ```

  `remotion/` 已带好 1080p@30fps 配置、中文字体（Noto Sans SC）和 `src/compositions/_template/` 样板。
  后端启动时会自动探测该工程（`C2C_REMOTION_DIR` 可显式指定）。渲染需本机 ffmpeg（`npx remotion render` 用）。

## 快速开始

```powershell
cd chat2chart
Copy-Item .env.example .env        # 按需修改
./start.ps1                         # 默认 http://localhost:8787
```

打开 http://localhost:8787，输入一句话 → 选择「HTML 图表 / Remotion 视频动画」→ 生成 → 预览 / 下载。

> ⚠️ **Windows 上不要给 uvicorn 加 `--reload`**：uvicorn 的 `--reload` 会把事件循环切换成
> `SelectorEventLoop`，而 Windows 的 `SelectorEventLoop` 不支持 `asyncio` 子进程（`create_subprocess_exec`
> 会抛 `NotImplementedError`），导致 opencode / Remotion 渲染无法启动。`start.ps1` 已默认不带 `--reload`，
> 改代码后需手动重启后端。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查 + 探测到的技能目录 / akshare python / remotion 工程 |
| POST | `/api/jobs` | 建任务，body `{"prompt": "...", "extra": "", "anim_seconds": 8, "anim_loop": false, "mode": "chart"|"video"}`，返回 `202 + {id}` |
| GET | `/api/jobs` | 任务列表（倒序） |
| GET | `/api/jobs/{id}` | 任务详情：`status`(queued/running/done/failed)、`mode`、`chart_url`、`video_url`、`log_tail`、`error` |
| GET | `/api/jobs/{id}/chart` | 返回生成的 HTML 图表 |
| GET | `/api/jobs/{id}/video` | 返回生成的 MP4 视频 |
| GET | `/` | 前端单页 |

调用示例：

```powershell
$body = '{"prompt":"对比中美近几年的黄金储备量","extra":"用彩色"}'
$r = curl.exe -s -X POST "http://localhost:8787/api/jobs" -H "Content-Type: application/json" -d $body
$r   # {"id":"...","status":"queued",...}
# 轮询 GET /api/jobs/<id> 直到 status=done，然后打开 /api/jobs/<id>/chart
```

## 安全与限制（Demo 级）

- 后端按「每任务独立目录 + headless `--auto`」执行 Agent，会消耗真实模型 token，任务通常 30s~数分钟。
- `--auto` 会让 Agent 自动批准工具调用，**只适用于可信内网 Demo**；正式环境应改为最小权限 agent +
  沙箱容器/防火墙，并加 API Key、限流与磁盘配额。
- 无数据库：任务保存在 `data/jobs/`，重启不会丢失文件但内存列表会清空。
- 生成质量取决于模型 + 数据源可达性；拿不到数据的场景 Agent 会如实说明而不是编数。
- 用户描述视为「数据需求」，指令模板显式要求忽略其中的元指令覆盖（防 prompt 注入），但完整隔离仍需沙箱。

## 无 token 自测（冒烟测试）

想先验证后端 HTTP 链路（不真正调用模型）时，启动前设 `C2C_FAKE=1`：任务会在内部用桩逻辑
sleep 几秒并生成一份极简 `chart.html`（或视频模式生成一段 ffmpeg 纯色 `video.mp4`），
跑通「建任务 → 轮询 → 预览/下载」全流程。

```powershell
$env:C2C_FAKE = "1"
./start.ps1
```

跑通后取消该变量即可切回真实 `opencode run`。也可以把 `OPENCODE_BIN` 指向任意一个能
「在工作目录写出 chart.html」的包装脚本（如 py/cmd），用来单独验证真实子进程路径。
