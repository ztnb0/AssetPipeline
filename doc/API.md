# Asset Pipeline API

本文档以当前 `frontend/app/page.tsx` 实际使用的接口为准。默认后端地址为 `http://192.168.7.132:8000`，所有业务接口前缀为 `/api`。api在线文档地址为http://192.168.7.132:8000/docs

## 通用约定

- JSON 请求使用 `Content-Type: application/json`。
- 素材处理接口可能返回 `202 Accepted`，上传或重新分析完成后通过详情接口查询状态。
- `status`：`processing`、`ready`、`failed`。
- `media_type`：`image` 或 `video`。音频功能当前停用。
- `content_url`、`thumbnail_url` 是相对后端地址的路径。

## 健康检查

### `GET /health`

返回：

```json
{"status":"ok"}
```

## 本地素材

### `POST /api/assets/upload`

上传图片或视频。请求为 `multipart/form-data`，字段名为 `file`。

```bash
curl -X POST http://localhost:8000/api/assets/upload -F "file=@./sample.jpg"
```

成功返回 `202` 和素材对象。支持 JPG、JPEG、PNG、WebP、MP4、MOV、MKV、WebM。音频上传返回 `410`。

### `GET /api/assets`

列出本地素材。前端无搜索词时使用此接口。

参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| `media_type` | string | `image` 或 `video` |
| `category` | string | 分类过滤 |

### `GET /api/search`

前端有搜索词时使用。结果按图片/视频、内部/外部分成四组，内部图片和内部视频分别按本地综合得分返回前 20 条。外部图片从每个平台最多召回 20 条，按平台原始排名合并后返回前 30 条；外部视频同样不做项目侧语义重排，每个支持视频的平台保留其站内顺序并返回前 10 条。Pexels、Pixabay、包图网支持图片和视频，Unsplash、Openverse 仅支持图片，Mixkit 仅支持视频。

参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| `q` | string | 必填，搜索词 |
| `media_type` | string | 可选，`image` 或 `video`；不传时同时检索图片和视频 |
| `category` | string | 可选，仅过滤本地素材题材 |
| `source` | string | 可选，`all`、`local` 或 `external`，默认 `all` |

`source=local` 只执行 MySQL、Embedding 和 Qdrant 本地素材检索，不等待外部平台；`source=external` 只请求外部平台。首页采用两阶段加载，先请求 `source=local` 并展示内部卡片，再请求 `source=external` 追加外部卡片。调用方仍可省略 `source`，一次获取完整结果。

```http
GET /api/search?q=城市&source=local
GET /api/search?q=城市&source=external
GET /api/search?q=城市
```

响应通过 `groups.image.local`、`groups.image.external`、`groups.video.local`、`groups.video.external` 提供四组结果，同时保留扁平 `items` 兼容字段。返回项的 `source` 为 `local` 时包含 `asset`；为 `external` 时包含 `provider`、`external_id`、`title`、`preview_url`、`preview_content_url`、`source_page_url`、`score` 等字段。`preview_url` 用于列表缩略图，`preview_content_url` 用于站内大图或视频在线播放；预览不会写入 MySQL 或 MinIO。

### `GET /api/assets/{asset_id}`

获取素材详情及处理状态。

### `GET /api/assets/{asset_id}/content`

流式返回图片或视频内容，支持浏览器 `Range` 请求并返回 `206 Partial Content`、`Accept-Ranges`、`Content-Range` 和准确的 `Content-Length`。视频分析完成后优先返回 faststart MP4 代理；原始高分辨率对象仍保留在 MinIO。

### `GET /api/assets/{asset_id}/thumbnail`

返回素材缩略图。

### `POST /api/assets/{asset_id}/reanalyze`

重新执行素材分析，返回 `202`。

### `PATCH /api/assets/{asset_id}`

更新素材信息。前端发送以下字段：

```json
{
  "original_name": "新名称",
  "tags": ["财经", "市场"],
  "categories": ["财经"],
  "scene": "演播室",
  "description": "素材描述"
}
```

### `DELETE /api/assets/{asset_id}`

删除单个本地素材及其缩略图、向量索引。

### `DELETE /api/assets/batch`

批量删除本地素材。

请求：

```json
{"ids":["asset-id-1","asset-id-2"]}
```

返回：

```json
{"deleted_ids":["asset-id-1"],"failed":{"asset-id-2":"素材不存在"}}
```

## 外部素材

### `GET /api/external-assets/search`

在单个 provider 中搜索外部素材。当前端外部素材浏览器使用此接口。

参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| `q` | string | 必填，搜索词 |
| `provider` | string | `pexels`、`pixabay`、`unsplash`、`openverse`、`mixkit`、`ibaotu` |
| `media_type` | string | `image` 或 `video` |
| `page` | integer | 页码，默认 1 |
| `per_page` | integer | 每页数量，默认 12，最大 40 |

### `POST /api/external-assets/import`

将外部素材下载并保存到本地，随后执行 AI 分析。

请求：

```json
{
  "provider":"pexels",
  "external_id":"12345",
  "media_type":"image"
}
```

普通 provider 成功返回 `202` 和本地素材对象；重复导入同一 provider/id 时返回已有素材。包图网导入立即返回 `202` 和导入任务对象，不等待大文件下载完成。

当 `provider=ibaotu` 时，后台任务使用服务端环境变量 `IBAOTU_ID_TOKEN` 调用包图网官方 `validpackage` 接口校验当前账号对该素材的下载权益。校验通过后，官方 ZIP 流式写入临时文件，ZIP 内无水印媒体流式上传到 MinIO，随后删除临时源包。搜索结果可见不代表普通用户或当前 VIP 套餐一定有权下载；最终以包图网权益接口返回结果为准。授权包中没有浏览器支持的图片或视频时任务失败，不会回退到带水印的公开预览。

### `GET /api/external-assets/import-jobs/{job_id}`

查询包图网后台导入进度。`stage` 依次为 `queued`、`authorizing`、`downloading`、`extracting`、`storing`、`completed` 或 `failed`；`progress` 为 `0` 至 `100`。完成时 `asset_id` 指向已创建素材，失败时 `error_message` 包含原因。

包图网中文关键词会先通过官方转换接口生成官网使用的拼音检索词，搜索请求使用与官网“全部”分类一致的 `c1g=0`、`authscope=3` 参数，并按官网顺序返回图片或视频。授权原文件大小由 `IBAOTU_MAX_DOWNLOAD_MB` 限制，默认 `1024` MB，不受普通上传的 `MAX_UPLOAD_MB` 限制。

### `GET /api/external-assets/preview`

按需解析缺少直接播放地址的外部视频。目前用于 Mixkit，参数为 `provider=mixkit`、`external_id` 和 `media_type=video`。接口只返回远程视频预览 URL，不下载或保存素材。

`mixkit` 当前只支持英文关键词和视频。结果使用 Mixkit Stock Video Free License，导入时后端会重新读取详情页并选择不超过 1080p 的可用规格。

## 已停用接口

以下接口当前统一返回 `410 Gone`：

- `GET /api/fred/series`
- `POST /api/fred/charts`
- 音频上传及音频检索

## 前端调用关系

```text
无搜索词       GET /api/assets
有搜索词（首屏） GET /api/search?source=local
有搜索词（补充） GET /api/search?source=external
上传           POST /api/assets/upload
外部素材浏览   GET /api/external-assets/search
导入外部素材   POST /api/external-assets/import
查询导入进度   GET /api/external-assets/import-jobs/{job_id}
详情/状态      GET /api/assets/{id}
编辑           PATCH /api/assets/{id}
重分析         POST /api/assets/{id}/reanalyze
删除           DELETE /api/assets/{id} 或 /batch
```
