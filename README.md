# Asset Pipeline

AI Video Factory 第一阶段的素材资产中心 Demo。该模块用于统一保存、解析、理解和检索团队的视频、图片及音频素材，并通过 HTTP API 向 AI Director Console、字幕理解模块或其他内部系统提供素材数据。

## 已实现功能

- 上传和管理图片、视频、音频素材
- 使用 MinIO 保存原始文件和缩略图
- 使用 MySQL 保存文件信息、描述、场景、分类和标签
- 使用 FFmpeg/FFprobe 提取视频时长、分辨率、关键帧及音频技术信息
- 使用 Qwen 多模态模型理解图片和视频内容
- 使用 faster-whisper 转写音频，并由 Qwen 生成内容摘要、场景、分类和标签
- 按图片、视频、音频和题材分类浏览素材
- 一个素材可属于多个题材分类
- 根据文件名、描述、场景、分类和标签检索素材
- 使用 Qwen 查询扩展和本地同义词进行语义相似检索
- 查看素材详情，播放或预览原始素材
- 修改描述、场景、分类和标签
- 重新分析或删除素材

> 当前语义检索采用“查询扩词 + 数据库匹配”，不是向量数据库检索。例如搜索“对谈”时，会同时搜索“访谈、谈话、对话、采访”等相关词。

## 技术架构

| 模块 | 技术 | 默认端口 | 用途 |
| --- | --- | ---: | --- |
| Web 前端 | Next.js、React、TypeScript、Tailwind CSS | 3000 | 素材上传、浏览、搜索和编辑 |
| 后端 API | FastAPI | 8000 | 素材管理、媒体处理和 AI 调用 |
| 元数据存储 | MySQL 8.4 | 3307 | 保存素材结构化信息 |
| 文件存储 | MinIO | 9100 / 9101 | 保存原始素材和缩略图 |
| 媒体处理 | FFmpeg / FFprobe | - | 媒体信息解析和视频抽帧 |
| 视觉与文本理解 | Qwen3.5-35B-A3B | 外部服务 | 描述、分类、标签及查询扩展 |
| 音频转写 | faster-whisper | 后端本地运行 | ASR 语音转写 |

调用关系：

```text
浏览器或团队系统
        |
        +--> Next.js 前端 :3000
        |          |
        +----------+--> FastAPI :8000
                           |-- MySQL：元数据
                           |-- MinIO：媒体文件
                           |-- FFmpeg / Whisper：媒体处理
                           `-- Qwen：内容理解
```

## 环境要求

- Windows、Linux 或 macOS
- Docker Desktop，或 Docker Engine + Docker Compose Plugin
- 至少 8 GB 内存，建议 16 GB
- 能访问配置的 Qwen 服务
- 首次分析音频时需要联网下载 Whisper 模型；下载完成后会缓存在 Docker 数据卷中

## 本机快速启动

1. 克隆项目并进入项目目录：

   ```powershell
   git clone git@github.com:ztnb0/AssetPipeline.git
   cd AssetPipeline
   ```

2. 创建环境配置：

   ```powershell
   Copy-Item .env.example .env
   ```

3. 按实际环境修改 `.env`，至少检查 Qwen 服务配置：

   ```env
   VISION_API_BASE_URL=http://114.113.151.16:8000/v1
   VISION_MODEL=Qwen3.5-35B-A3B
   VISION_API_KEY=
   ```

   当前示例 Qwen 服务不要求 API Key，因此 `VISION_API_KEY` 可以为空。更换为需要鉴权的服务时，在此填写对应密钥。不要把包含真实密码或密钥的 `.env` 提交到 Git。

4. 构建并启动所有服务：

   ```powershell
   docker compose up -d --build
   ```

5. 检查运行状态：

   ```powershell
   docker compose ps
   ```

6. 打开服务：

   - 素材中心：http://localhost:3000
   - API 文档：http://localhost:8000/docs
   - 后端健康检查：http://localhost:8000/health
   - MinIO 控制台：http://localhost:9101

## 日常运维命令

```powershell
# 后台启动服务
docker compose up -d

# 代码或依赖变化后重新构建并启动
docker compose up -d --build

# 查看服务状态
docker compose ps

# 查看后端日志
docker compose logs -f backend

# 停止并删除容器和项目网络，保留数据卷
docker compose down
```

不要在需要保留素材时执行 `docker compose down -v`。`-v` 会同时删除 MySQL、MinIO 和 Whisper 缓存数据卷。

电脑重启后，先启动 Docker Desktop，然后在项目目录执行：

```powershell
docker compose up -d
```

## 素材处理流程

```text
上传素材
  -> MinIO 保存原始文件
  -> MySQL 创建 processing 状态记录
  -> 后台解析媒体信息
  -> 图片/视频：抽帧并调用 Qwen
  -> 音频：Whisper 转写后调用 Qwen
  -> 写入描述、场景、分类和标签
  -> 状态变为 ready 或 failed
```

上传接口返回 HTTP `202 Accepted`，表示任务已进入后台处理，不代表 AI 分析已经完成。调用方应根据返回的素材 ID 轮询详情接口，直到 `status` 变为：

- `processing`：正在处理
- `ready`：处理完成
- `failed`：处理失败，可查看 `error_message`

## 支持的文件格式

| 类型 | 格式 |
| --- | --- |
| 图片 | JPG、JPEG、PNG、WebP |
| 视频 | MP4、MOV、MKV、WebM |
| 音频 | MP3、WAV、M4A、FLAC、OGG |

默认单文件大小上限为 250 MB。

## API 使用

完整、可交互的接口文档位于：http://localhost:8000/docs

### 健康检查

```http
GET /health
```

### 上传素材

```http
POST /api/assets/upload
Content-Type: multipart/form-data
```

PowerShell 示例：

```powershell
curl.exe -X POST "http://localhost:8000/api/assets/upload" `
  -F "file=@E:\media\example.mp4"
```

### 查询和语义搜索

```http
GET /api/assets?q=对谈
GET /api/assets?media_type=video
GET /api/assets?category=财经
GET /api/assets?q=人工智能&media_type=image&category=科技
```

参数说明：

| 参数 | 可选值/含义 |
| --- | --- |
| `q` | 搜索文件名、描述、场景、分类和标签，并进行语义扩词 |
| `media_type` | `image`、`video` 或 `audio` |
| `category` | 题材分类名称，例如 `财经`、`科技` |

响应中的 `query_terms` 表示实际参与匹配的语义扩展词。

### 获取详情与媒体内容

```http
GET /api/assets/{asset_id}
GET /api/assets/{asset_id}/content
GET /api/assets/{asset_id}/thumbnail
```

接口返回的 `content_url` 和 `thumbnail_url` 是相对于后端服务的路径。其他模块调用时需要拼接后端地址，例如：

```text
http://localhost:8000 + /api/assets/{asset_id}/content
```

### 修改素材信息

```http
PATCH /api/assets/{asset_id}
Content-Type: application/json
```

请求示例：

```json
{
  "description": "财经访谈节目，两位主持人讨论 AI 企业成本。",
  "scene": "演播室访谈",
  "categories": ["财经", "科技"],
  "tags": ["访谈", "人工智能", "企业成本"]
}
```

每个素材最多保存 8 个分类和 30 个标签。

### 重新分析

```http
POST /api/assets/{asset_id}/reanalyze
```

该接口返回 `202`，调用方同样需要轮询素材详情状态。

### 删除素材

```http
DELETE /api/assets/{asset_id}
```

删除操作会同时删除 MySQL 记录、MinIO 原始文件和缩略图，无法通过系统界面恢复。

## 供其他团队模块调用

团队成员不需要启动前端也可以直接调用 FastAPI。局域网内将 `localhost` 替换为运行本项目的主机 IP：

```text
http://<素材库主机IP>:8000/api/assets
```

推荐集成流程：

1. 调用 `GET /api/assets` 根据分镜关键词、媒体类型或题材搜索素材。
2. 从 `items` 中读取 `id`、`description`、`scene`、`tags`、`categories`、`duration` 和分辨率。
3. 使用 `content_url` 获取可播放或可下载的原始素材。
4. 使用 `thumbnail_url` 在素材选择界面展示缩略图。
5. 上传后轮询状态，不要把 `processing` 状态的素材直接交给下游生成流程。

Python 调用示例：

```python
import requests

api_base = "http://192.168.1.100:8000"
response = requests.get(
    f"{api_base}/api/assets",
    params={"q": "黄金走势", "media_type": "video"},
    timeout=30,
)
response.raise_for_status()

for asset in response.json()["items"]:
    print(asset["id"], asset["description"])
    print(api_base + asset["content_url"])
```

## 在另一台主机部署或演示

建议将源代码提交到团队 GitHub、GitLab 或内部 Git 服务，但不要提交 `.env`、数据库文件、模型密钥和业务素材。

在新主机上：

1. 安装 Git 和 Docker。
2. 克隆仓库并创建 `.env`。
3. 确认新主机能够访问 Qwen 服务。
4. 将 `.env` 中的前端 API 地址改为新主机可访问的地址：

   ```env
   NEXT_PUBLIC_API_BASE_URL=http://192.168.1.100:8000/api
   ```

5. 将 `docker-compose.yml` 中后端的 `CORS_ORIGINS` 改为前端地址：

   ```yaml
   CORS_ORIGINS: http://192.168.1.100:3000
   ```

6. 构建并启动：

   ```powershell
   docker compose up -d --build
   ```

7. 在操作系统防火墙中按实际需要开放 `3000` 和 `8000`。MySQL 和 MinIO 端口通常不应向其他成员开放。

8. 团队成员访问：

   ```text
   http://192.168.1.100:3000
   ```

如果需要迁移现有素材，不能只复制 Git 仓库，还需要备份并迁移 MySQL 和 MinIO 数据卷。Git 只负责代码版本管理，不负责业务素材和数据库数据。

## 配置项

主要环境变量：

| 变量 | 作用 | 示例 |
| --- | --- | --- |
| `MYSQL_DATABASE` | 数据库名称 | `asset_pipeline` |
| `MYSQL_USER` | MySQL 用户 | `asset_user` |
| `MYSQL_PASSWORD` | MySQL 密码 | 请在团队环境修改 |
| `MYSQL_ROOT_PASSWORD` | MySQL root 密码 | 请在团队环境修改 |
| `MINIO_ROOT_USER` | MinIO 管理员用户 | 请在团队环境修改 |
| `MINIO_ROOT_PASSWORD` | MinIO 管理员密码 | 请在团队环境修改 |
| `MINIO_BUCKET` | 素材 Bucket | `assets` |
| `VISION_API_BASE_URL` | OpenAI 兼容模型服务基础地址 | `http://host:8000/v1` |
| `VISION_MODEL` | 模型名称 | `Qwen3.5-35B-A3B` |
| `VISION_API_KEY` | 模型服务密钥 | 无鉴权服务可为空 |
| `ASR_MODEL_SIZE` | Whisper 模型大小 | `base` |
| `NEXT_PUBLIC_API_BASE_URL` | 浏览器访问后端的地址 | `http://localhost:8000/api` |

修改 `NEXT_PUBLIC_API_BASE_URL` 后必须重新构建前端，因为该值会在 Next.js 构建时写入浏览器端代码：

```powershell
docker compose up -d --build frontend
```

## 数据持久化

Docker Compose 使用以下命名数据卷：

- `mysql_data`：MySQL 素材元数据
- `minio_data`：原始素材和缩略图
- `asr_cache`：Whisper 模型缓存

普通的容器重启、Docker Desktop 重启及 `docker compose down` 不会删除这些数据。

生产或长期团队环境应制定 MySQL 和 MinIO 的定期备份方案。只备份其中一个会造成数据库记录和文件对象不一致。

## 当前 Demo 限制与安全说明

- 当前 API 没有登录、API Key 或权限控制。
- 任何能够访问后端端口的人都可以查询、上传、修改和删除素材。
- 不要将 `8000`、`3307`、`9100` 或 `9101` 直接暴露到公网。
- 局域网演示应通过主机防火墙限制来源 IP。
- 正式团队服务应增加 HTTPS、API Key/JWT、角色权限、上传限额、访问日志和请求限流。
- 当前后台分析使用 FastAPI 进程内任务；服务重启时，正在执行的任务可能中断。正式环境建议接入 Redis + Celery/RQ 等持久任务队列。
- 当前项目没有使用 Redis。Docker Desktop 中独立的 `redis` 容器不属于本项目。
- ASR 转写可能存在同音字、专有名词和简繁体误差，业务使用前应人工复核。
- 当前 Qwen 服务通过 HTTP 且无鉴权，仅适合可信网络内的 Demo。

## 常见问题

### 浏览器无法打开 `localhost:3000`

确认 Docker Desktop 已启动，然后执行：

```powershell
docker compose up -d
docker compose ps
```

### 上传后一直显示正在分析

查看后端日志：

```powershell
docker compose logs -f backend
```

首次音频分析需要下载 Whisper 模型，耗时会比后续分析长。

### 新主机可以打开前端，但素材请求失败

检查：

- `NEXT_PUBLIC_API_BASE_URL` 是否仍然指向 `localhost`
- 修改地址后是否重新构建了前端
- 后端 `CORS_ORIGINS` 是否包含实际前端地址
- 主机防火墙是否允许访问 `8000`
- 浏览器所在机器是否能访问后端主机 IP

### Qwen 分析失败

确认：

- `VISION_API_BASE_URL` 以 `/v1` 结尾
- `VISION_MODEL` 与 `/v1/models` 返回的模型名称一致
- 当前主机可以访问模型服务
- 需要鉴权的服务已经配置 `VISION_API_KEY`

### 如何确认后端正常

访问：

```text
http://localhost:8000/health
```

正常响应：

```json
{"status": "ok"}
```

## 项目定位

该仓库对应《AI Video Factory 项目研发任务分工》中的第三个模块：Asset Pipeline（AI 素材资产中心）。当前交付覆盖素材上传、管理、媒体解析、AI 标签和素材搜索，并为后续 AI Director Console 的素材推荐与 Remotion 视频生成提供 API 基础。
