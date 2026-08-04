# Asset Pipeline 最终交付与验收说明

## 1. 项目定位

Asset Pipeline 是 AI Video Factory 第一阶段 MVP 的 AI 素材资产中心，负责统一接收、存储、解析、理解和检索图片、视频及音频素材，并通过 HTTP API 向 Subtitle Intelligence Engine、AI Director Console 及后续视频生成模块提供素材数据。

本文依据《AI Video Factory 项目研发任务分工》中第三个模块“Asset Pipeline（AI 素材资产中心）”整理，用于团队联调、成果演示和阶段验收。

## 2. 原始任务完成情况

| 任务要求 | 当前实现 | 验收入口或依据 | 状态 |
| --- | --- | --- | --- |
| 上传视频、图片、音频 | 支持常用图片、视频和音频格式上传，原始文件保存到 MinIO | Web 上传区、`POST /api/assets/upload` | 已完成 |
| 记录素材信息 | MySQL 保存文件名、类型、时长、分辨率、标签、创建时间、处理状态等信息 | 素材列表及详情接口 | 已完成 |
| 素材管理 | 展示缩略图、名称、类型、时长、标签和创建时间，支持预览、编辑及删除 | Web 素材库、详情页 | 已完成 |
| FFmpeg 视频解析 | 使用 FFmpeg/FFprobe 获取时长、分辨率，并生成截图和关键帧分析输入 | 上传视频后自动处理 | 已完成 |
| AI 素材理解 | Qwen 多模态模型生成描述、标签、场景和题材分类 | 素材详情、重新分析接口 | 已完成 |
| 关键词检索 | 可按文件名、描述、场景、分类和标签搜索 | `GET /api/assets?q=关键词` | 已完成 |
| FastAPI 后端 | 提供素材上传、查询、修改、删除、内容访问和重新分析 API | `http://localhost:8000/docs` | 已完成 |
| MinIO 文件存储 | 保存原始素材和缩略图 | Docker Compose 中的 MinIO 服务 | 已完成 |
| MySQL 元数据存储 | 持久化素材记录和 AI 分析结果 | Docker Compose 中的 MySQL 服务 | 已完成 |
| 可运行 Demo | 前后端及依赖服务可通过 Docker Compose 一键运行 | `docker compose up -d --build` | 已完成 |

结论：当前 Demo 已覆盖第三模块规定的素材上传、素材管理、素材解析、AI 标签和素材搜索五项最终交付内容。

## 3. 系统架构

| 层级 | 技术 | 作用 |
| --- | --- | --- |
| Web 前端 | Next.js、React、TypeScript、Tailwind CSS | 上传、浏览、搜索、预览和编辑素材 |
| 后端接口 | FastAPI | 业务接口、任务调度、媒体处理和 AI 调用 |
| 元数据存储 | MySQL 8.4 | 保存素材属性、分析结果和处理状态 |
| 对象存储 | MinIO | 保存原始文件和缩略图 |
| 媒体处理 | FFmpeg、FFprobe | 获取媒体参数、视频截图和关键帧 |
| 多模态理解 | Qwen3.5-35B-A3B | 生成描述、场景、题材分类、标签及查询扩展 |
| 音频识别 | faster-whisper | 将音频转写为文本，供 Qwen 继续分析 |
| 部署方式 | Docker Compose | 统一启动前端、后端、MySQL 和 MinIO |

```text
浏览器 / 团队其他模块
          |
          +--> Next.js Web :3000
          |          |
          +----------+--> FastAPI :8000
                              |-- MySQL：素材元数据
                              |-- MinIO：原始文件与缩略图
                              |-- FFmpeg / Whisper：媒体解析
                              `-- Qwen：内容理解与检索扩展
```

## 4. 核心处理流程

```text
用户上传素材
  -> MinIO 保存原始文件
  -> MySQL 创建 processing 状态记录
  -> 后台解析文件类型和媒体参数
  -> 图片/视频：抽取画面并调用 Qwen
  -> 音频：Whisper 转写后调用 Qwen
  -> 写入描述、场景、分类和标签
  -> 状态更新为 ready；失败时更新为 failed
  -> 前端与 API 可搜索、预览、修改或删除素材
```

上传接口返回 HTTP `202 Accepted`，表示文件已经接收并进入后台处理，不代表 AI 分析已经结束。调用方应通过素材详情接口轮询 `status`：

- `processing`：正在处理或等待分析资源。
- `ready`：分析完成，可以正常检索和使用。
- `failed`：处理失败，可读取 `error_message` 并发起重新分析。

## 5. 已实现的增强能力

以下能力超出原始任务的最低要求，但已包含在当前 Demo 中：

- 批量上传图片、视频和音频，上传并发可选 `1 / 3 / 5`，默认并发为 3。
- 支持直接拖拽文件夹并递归发现其中可用的媒体文件。
- 后端使用进程内信号量，将 FFmpeg、Whisper 和 Qwen 的同时分析任务限制为 2 个，不依赖 Redis。
- 一个素材可属于多个题材分类，例如同时属于“财经”和“科技”。
- 素材详情页支持重命名，以及修改描述、场景、分类和标签。
- 支持素材预览、重新分析和彻底删除。
- 支持语义相似检索，通过 Qwen 查询扩展与本地同义词提高召回率。
- 页面展示的“素材相关扩展”只来自素材库中真实存在的元数据，点击后可直接执行搜索。
- 音频经语音识别后生成内容描述、场景、题材分类和更细致的标签。

## 6. 素材数据输出

典型素材记录可包含以下数据：

```json
{
  "id": "素材唯一标识",
  "original_name": "黄金市场访谈.mp4",
  "media_type": "video",
  "duration": 35.2,
  "width": 1920,
  "height": 1080,
  "description": "演播室内两位嘉宾讨论黄金价格走势。",
  "scene": "财经访谈",
  "categories": ["财经", "投资"],
  "tags": ["黄金", "访谈", "价格走势"],
  "status": "ready",
  "content_url": "/api/assets/{asset_id}/content",
  "thumbnail_url": "/api/assets/{asset_id}/thumbnail",
  "created_at": "2026-08-03T10:00:00"
}
```

字段以实际 API 响应为准；交互式接口定义可在 Swagger 页面中查看。

## 7. API 交付清单

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/health` | 服务健康检查 |
| `POST` | `/api/assets/upload` | 上传单个素材并启动后台分析 |
| `GET` | `/api/assets` | 查询、筛选和语义搜索素材 |
| `GET` | `/api/assets/{asset_id}` | 获取素材详情和处理状态 |
| `PATCH` | `/api/assets/{asset_id}` | 修改名称、描述、场景、分类和标签 |
| `DELETE` | `/api/assets/{asset_id}` | 删除数据库记录及 MinIO 文件 |
| `GET` | `/api/assets/{asset_id}/content` | 获取或播放原始素材 |
| `GET` | `/api/assets/{asset_id}/thumbnail` | 获取素材缩略图 |
| `POST` | `/api/assets/{asset_id}/reanalyze` | 重新执行媒体和 AI 分析 |
| `PUT` | `/api/assets/{asset_id}/tags` | 更新素材标签 |

完整 API 文档：` `

团队模块通过局域网调用时，应将 `localhost` 替换为素材库主机 IP，例如：

```text
http://<素材库主机IP>:8000/api/assets?q=黄金走势
```

响应中的 `content_url` 与 `thumbnail_url` 为后端相对路径，调用方需要拼接 FastAPI 服务地址。

## 8. 启动与演示

### 环境要求

- Docker Desktop，或 Docker Engine + Docker Compose Plugin。
- 建议至少 16 GB 内存。
- 主机可以访问配置的 Qwen 服务。
- 首次运行音频分析时允许下载 Whisper 模型。

### 启动步骤

```powershell
git clone git@github.com:ztnb0/AssetPipeline.git
cd AssetPipeline
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
```

默认访问地址：

- 素材中心：`http://localhost:3000`
- FastAPI：`http://localhost:8000`
- Swagger：`http://localhost:8000/docs`
- MinIO 控制台：`http://localhost:9101`

停止服务但保留素材数据：

```powershell
docker compose down
```

不要在需要保留素材时执行 `docker compose down -v`，因为该命令会删除 MySQL、MinIO 和 Whisper 缓存数据卷。

## 9. 建议验收步骤

1. 打开素材中心，分别上传一张图片、一段视频和一段音频。
2. 检查列表是否立即出现素材，并显示 `processing` 状态。
3. 等待状态变为 `ready`，检查缩略图、文件名、类型、时长、标签及创建时间。
4. 打开视频详情，检查时长、分辨率、预览画面、描述、场景、分类和标签。
5. 打开音频详情，检查是否可播放，并已生成转写后的描述和标签。
6. 修改素材名、描述、场景、多个分类及标签，刷新后确认数据仍然存在。
7. 输入与标签不完全相同但语义接近的词，检查是否能召回相关素材。
8. 点击素材相关扩展词，检查其是否填入检索框并立即搜索。
9. 使用 Swagger 或其他团队模块调用列表、详情和内容接口。
10. 删除测试素材，确认列表、数据库记录和对象存储文件同步删除。

当前项目已经完成过前端生产构建、后端 Python 编译、健康检查、混合批量上传、分析并发限制、语义扩展、素材重命名和浏览器控制台检查。正式演示前仍建议按以上步骤使用演示主机及目标网络重新执行一次冒烟验收。

## 10. 团队集成方式

### Subtitle Intelligence Engine

字幕模块可以把字幕关键词、主题或场景提示作为 `q` 参数搜索素材，再把返回的素材 ID、描述和内容地址交给下游模块。Asset Pipeline 当前不会生成标准 SRT 或 `subtitle.json`，这些属于字幕模块职责。

### AI Director Console

导演工作台可以根据每个分镜的画面描述、关键词和题材分类调用素材搜索接口，展示候选素材缩略图，并通过内容接口进行预览。项目管理、分镜编辑、素材评分和 Timeline 属于导演工作台职责。

### Remotion 或视频生成模块

素材确认后，下游模块可使用素材 ID 访问原始内容。Asset Pipeline 负责提供素材，不负责生成 Remotion 工程或渲染最终视频。

## 11. 第一阶段 Demo 边界

- 当前语义检索是“查询扩展 + MySQL 元数据匹配”，不是向量数据库或专用检索引擎。
- 分析并发限制保存在单个后端进程内；多实例部署时不能形成全局并发控制。
- 未引入 Redis 或持久化任务队列，后端重启时正在运行或等待的分析任务不会自动恢复。
- 当前未实现用户登录、角色权限、操作审计、配额和租户隔离，不应直接暴露到公网。
- AI 输出受模型服务可用性和素材质量影响，保留人工修改和重新分析能力。
- 删除操作会同步删除数据库记录和对象存储文件，当前没有回收站或恢复机制。
- 生产环境还需要补充鉴权、HTTPS、备份、监控、任务恢复和多实例调度。

以上限制符合“优先完成可运行 Demo、验证完整流程”的第一阶段原则，不影响当前模块与团队其他模块进行接口联调。

## 12. 验收结论

当前 Asset Pipeline 已形成可独立运行、可通过 Web 演示、可通过 API 集成的素材资产中心 Demo。实现范围覆盖任务文档对第三模块提出的全部基础交付要求，并在批量上传、多分类、可编辑元数据、音频理解和语义检索方面提供了增强能力。

本阶段可进入团队联调和演示验收。进入生产部署前，应优先建设鉴权、持久化任务队列、失败任务恢复、数据备份和可观测性能力。
