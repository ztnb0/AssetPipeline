# Asset Pipeline

AI Video Factory 第一阶段的素材资产中心 Demo。该模块用于统一保存、解析、理解和检索团队的视频、图片及音频素材，并通过 HTTP API 向 AI Director Console、字幕理解模块或其他内部系统提供素材数据。

## 已实现功能

- 批量上传和管理图片、视频、音频素材
- 上传并发可在界面选择 1、3 或 5，默认同时上传 3 个文件
- 支持将文件夹直接拖拽到“批量上传素材”区域，递归读取其中的文件
- 使用 MinIO 保存原始文件和缩略图
- 使用 MySQL 保存文件信息、描述、场景、分类和标签
- 使用 FFmpeg/FFprobe 提取视频时长、分辨率、关键帧及音频技术信息
- 使用 Qwen 多模态模型理解图片和视频内容
- 使用 faster-whisper 转写音频，并由 Qwen 生成内容摘要、场景、分类和标签
- 按图片、视频、音频和题材分类浏览素材
- 一个素材可属于多个题材分类
- 根据文件名、描述、场景、分类和标签检索素材
- 使用 Qwen3-Embedding-8B、Qdrant 和关键词召回进行混合语义检索
- 查看素材详情，播放或预览原始素材
- 修改素材名称、描述、场景、分类和标签
- 重新分析或删除素材

> 当前搜索采用混合检索：Qwen3-Embedding-8B + Qdrant 提供向量语义召回，原有查询扩词和数据库匹配提供关键词召回；两路结果合并后按相关度排序。向量服务暂时不可用时会自动降级为关键词检索。

## 技术架构

| 模块 | 技术 | 默认端口 | 用途 |
| --- | --- | ---: | --- |
| Web 前端 | Next.js、React、TypeScript、Tailwind CSS | 3000 | 素材上传、浏览、搜索和编辑 |
| 后端 API | FastAPI | 8000 | 素材管理、媒体处理和 AI 调用 |
| 元数据存储 | MySQL 8.4 | 3307 | 保存素材结构化信息 |
| 文件存储 | MinIO | 9100 / 9101 | 保存原始素材和缩略图 |
| 媒体处理 | FFmpeg / FFprobe | - | 媒体信息解析和视频抽帧 |
| 视觉与文本理解 | Qwen3.5-35B-A3B | 外部服务 | 描述、分类、标签及查询扩展 |
| 文本向量化 | Qwen3-Embedding-8B | 外部服务 | 将素材元数据和查询转换为 4096 维向量 |
| 向量索引 | Qdrant | 6333 / 6334 | 语义相似度检索和分类过滤 |
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
   PEXELS_API_KEY=your_pexels_api_key
   PIXABAY_API_KEY=your_pixabay_api_key
   UNSPLASH_ACCESS_KEY=your_unsplash_access_key
   FRED_API_KEY=your_fred_api_key
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
   - Qdrant： `http://localhost:6333/dashboard `

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

批量上传由前端对单文件上传接口进行并发调度，每个文件独立成功或失败。后端使用进程内信号量，最多同时执行 2 个 FFmpeg、Whisper 或 Qwen 分析任务；其余已上传素材等待分析槽位。当前方案不依赖 Redis，后端进程重启时正在执行或等待的任务不会自动恢复。

## 支持的文件格式

| 类型 | 格式 |
| --- | --- |
| 图片 | JPG、JPEG、PNG、WebP |
| 视频 | MP4、MOV、MKV、WebM |
| 音频 | MP3、WAV、M4A、FLAC、OGG |

默认单文件大小上限为 250 MB。

## API 使用

完整、可交互的接口文档位于：http://localhost:8000/docs

完整接口说明见 [API.md](API.md)，在线运行时也可以访问 `http://localhost:8000/docs` 查看交互式 OpenAPI 文档。

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

### 外部开放素材导入

外部素材平台统一使用搜索和导入接口。Openverse 只返回 `CC0`、Public Domain、`CC BY` 和 `CC BY-SA` 图片，并在导入时保存作者、许可证及原始页面。

```http
GET /api/external-assets/search?provider=openverse&q=stock%20exchange&media_type=image
GET /api/external-assets/search?provider=mixkit&q=nature&media_type=video
GET /api/external-assets/search?provider=ibaotu&q=%E7%BE%8E%E5%85%83%E9%9C%B8%E6%9D%83&media_type=image
POST /api/external-assets/import
```

```json
{"provider":"openverse","external_id":"素材 ID","media_type":"image"}
```

导入成功后，系统将原始素材保存到 MinIO，在 MySQL 中创建本地素材记录，并在后台自动生成描述、场景、题材分类和标签。分析成功后，素材状态变为 `ready`，同时写入 Qdrant 语义向量索引。

首页输入语义搜索词时会同时展示本地素材和外部素材，但采用两阶段加载：先调用 `GET /api/search?source=local` 展示本地卡片，再调用 `GET /api/search?source=external` 异步追加外部卡片。外部平台或网络变慢不会阻塞本地结果。外部素材卡片带有“导入素材库”按钮，点击后会直接调用 `POST /api/external-assets/import`；导入成功后，当前卡片会替换为本地素材并显示 AI 分析状态。同一 provider 和素材 ID 重复导入时，后端返回已有的本地素材，不会重复保存文件。

统一搜索结果按“图片/视频”以及“内部资源/外部资源”分组。内部图片和视频分别按内部综合得分返回前 20；外部图片从每个平台最多召回 20 条，按平台原始排名合并后返回前 30；外部视频保留各平台原始顺序，每个平台返回前 10。交互式检索不会调用生成式模型扩词，也不会对外部结果再次执行 Embedding，查询向量会在后端进程内缓存，图片和视频检索可复用同一个向量。

Mixkit 通过 Scrapling 读取公开的视频搜索页和详情页，当前仅支持英文关键词与视频素材。搜索阶段只展示远程缩略图；用户点击“导入素材库”后，后端才按 Mixkit Stock Video Free License 获取不超过 1080p 的视频文件。

包图网通过 Scrapling 读取公开搜索结果和预览。中文搜索词会先通过包图网官方转换接口生成官网使用的拼音检索词，并使用与官网“全部”分类一致的 `c1g=0`、`authscope=3` 参数，因此同一关键词的站内顺序与包图网页保持一致；项目再按图片或视频类型截取所需结果。搜索结果不代表普通用户或当前 VIP 套餐一定可以下载；点击“VIP 下载并导入”后，接口立即返回导入任务，前端轮询显示权益校验、下载百分比、解压和入库进度。后台使用 `IBAOTU_ID_TOKEN` 校验权益，将官方源包流式写入临时文件，并把 ZIP 内的无水印媒体直接流式上传到 MinIO，随后删除临时源包。令牌只配置在服务端 `.env`，不要写入前端代码或提交到 Git。

导入任务按素材独立运行。开始下载后可以关闭预览弹窗、继续浏览并同时提交其他素材；关闭弹窗不会取消后台任务，原搜索卡片会继续显示各自的阶段和进度。

视频正文接口支持 HTTP Range 分段响应。分析完成后会生成最大 1080p 的 H.264/AAC faststart MP4 代理供网页快速预览，原始 4K 文件仍保存在素材库并用于后续导出。

包图网授权原文件的默认大小上限为 1024 MB，可通过服务端环境变量 `IBAOTU_MAX_DOWNLOAD_MB` 单独调整；该设置不影响普通素材上传的 `MAX_UPLOAD_MB` 限制。

> FRED 图表接口当前已停用，`GET /api/fred/series` 和 `POST /api/fred/charts` 返回 `410 Gone`。

### 查询和语义搜索

```http
GET /api/assets
GET /api/search?q=对谈
GET /api/search?q=人工智能&media_type=image
GET /api/search?q=人工智能&source=local
GET /api/search?q=人工智能&source=external
```

参数说明：

| 参数 | 可选值/含义 |
| --- | --- |
| `q` | 必填；对本地和外部素材执行统一检索 |
| `media_type` | 可选；`image` 或 `video`，不传时同时检索两者 |
| `category` | 本地素材检索可使用题材分类过滤，例如 `财经`、`科技` |
| `source` | 可选；`all`（默认）、`local` 或 `external`。前端使用后两者分阶段加载 |

响应中的 `query_terms` 当前包含原始搜索词；内置通用近义词只参与内部关键词召回，不会作为扩展词展示。交互式搜索不再同步调用生成式模型提取扩展短语。

#### 向量生成与同步

MySQL 是素材元数据的事实源，Qdrant 是可以从 MySQL 重新生成的语义检索索引。系统不会将整条 SQL 记录直接迁移到 Qdrant，而是为每个 `ready` 素材拼接以下检索文本：

```text
素材类型：video
名称：财经访谈.mp4
描述：主持人与嘉宾讨论市场走势和资产配置。
场景：财经演播室主持人进行市场分析访谈
题材：财经、金融市场
标签：主持人、嘉宾、市场走势、资产配置
视频画面：主持人站在屏幕前；嘉宾展示走势图；双方进行交流
语音内容：今天我们讨论近期市场变化……
```

参与向量化的字段包括：

- `media_type`：素材类型
- `original_name`：素材名称
- `description`：AI 生成或人工修改的内容描述
- `scene`：具体场景
- `categories`：题材分类
- `tags`：检索标签
- `media_metadata.frame_analysis[].description`：视频抽帧描述
- `media_metadata.transcript`：音频转写，最多使用前 6000 个字符

后端将上述文本发送给 `Qwen3-Embedding-8B`，生成 4096 维向量，并以素材 UUID 作为 point ID 写入 Qdrant collection `assets_qwen3_embedding_8b_v1`。Qdrant payload 只保存用于关联和过滤的少量字段：

这 4096 个维度是模型生成的浮点数语义特征，不分别对应“名称维度”“题材维度”或“标签维度”。名称、描述、场景、题材和标签等原始字段仍完整保存在 MySQL 中；Qdrant 中的向量只用于计算语义相似度。

```json
{
  "asset_id": "与 MySQL 素材 ID 相同",
  "media_type": "video",
  "categories": ["财经", "金融市场"],
  "status": "ready"
}
```

索引同步规则：

- 后端启动时在后台扫描全部 `ready` 素材，补建或覆盖对应向量
- 新素材分析成功后自动生成向量
- 人工修改名称、描述、场景、分类或标签后自动覆盖向量
- 删除素材时同步删除 Qdrant point
- 重新分析素材时先删除旧向量，分析成功后写入新向量
- Qdrant 或 Embedding 服务暂时不可用时，素材处理和关键词检索仍可使用；下次后端启动会再次补建缺失向量

用户查询会使用同一个 Embedding 模型生成查询向量。查询向量使用进程内 LRU 缓存，因而同一查询的图片、视频检索以及短期重复检索不需要重复调用远程 Embedding 服务。最终排序分数为 `75%` 向量相似度加 `25%` 关键词命中分，并支持 `media_type` 和 `category` 过滤。响应中的 `search_score` 表示该综合相关度；未提供 `q` 时该字段为 `null`。后端为每次统一搜索记录 `local_ms`、`external_ms`、`total_ms` 和结果数，可通过 `docker compose logs backend` 定位耗时。

Qdrant 管理界面位于 `http://localhost:6333/dashboard`。素材数量较少时，面板可能显示 `indexed_vectors_count = 0`，这是因为 Qdrant 直接遍历少量向量而未建立 HNSW 索引，不表示向量尚未写入；实际记录数应查看 `points_count`。

#### 数据存储职责

| 组件 | 保存内容 | 主要用途 |
| --- | --- | --- |
| MinIO | 原始图片、视频及缩略图 | 媒体文件存储和读取 |
| MySQL | 素材名、描述、场景、题材、标签、来源及媒体信息 | 完整素材详情和事实数据源 |
| Qdrant | 4096 维语义向量，以及 `asset_id`、媒体类型、题材和状态 | 语义相似度召回和条件过滤 |

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
| `PEXELS_API_KEY` | Pexels 图片和视频搜索 API Key | 空；未配置时禁用外部素材搜索 |
| `PIXABAY_API_KEY` | Pixabay 图片和视频搜索 API Key | 空；未配置时禁用 Pixabay 搜索 |
| `UNSPLASH_ACCESS_KEY` | Unsplash 图片搜索 Access Key | 空；未配置时禁用 Unsplash 搜索 |
| `IBAOTU_ID_TOKEN` | 包图网服务端 VIP 登录令牌，仅用于官方权益校验和下载 | 空；不要提交到 Git |
| `IBAOTU_MAX_DOWNLOAD_MB` | 包图网授权原文件独立大小上限（MB） | `1024` |
| `FRED_API_KEY` | FRED 宏观经济数据 API Key | 空；未配置时禁用财经图表生成 |
| `VISION_MODEL` | 模型名称 | `Qwen3.5-35B-A3B` |
| `VISION_API_KEY` | 模型服务密钥 | 无鉴权服务可为空 |
| `EMBEDDING_API_BASE_URL` | OpenAI 兼容向量服务地址 | `http://114.113.151.16:8003/v1` |
| `EMBEDDING_MODEL` | 向量模型名称 | `Qwen3-Embedding-8B` |
| `EMBEDDING_DIMENSION` | 向量维度，必须与模型输出一致 | `4096` |
| `QDRANT_URL` | Qdrant HTTP 地址 | Docker 内为 `http://qdrant:6333` |
| `QDRANT_COLLECTION` | 素材向量集合名称 | `assets_qwen3_embedding_8b_v1` |
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
- `qdrant_data`：素材语义向量和 Qdrant 索引

普通的容器重启、Docker Desktop 重启及 `docker compose down` 不会删除这些数据。

生产或长期团队环境应制定 MySQL 和 MinIO 的定期备份方案。只备份其中一个会造成数据库记录和文件对象不一致。Qdrant 数据可以通过 MySQL 中的素材元数据重新生成，但备份 `qdrant_data` 可以缩短故障恢复后的索引重建时间。

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
