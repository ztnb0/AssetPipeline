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

前端有搜索词时使用。结果按图片/视频、内部/外部分成四组，内部图片和内部视频分别按本地综合得分返回前 20 条。外部图片从每个平台最多召回 20 条，跨平台评分后返回前 30 条；外部视频不做项目侧语义重排，每个支持视频的平台保留其站内顺序并返回前 10 条。Pexels、Pixabay 支持图片和视频，Unsplash、Openverse 仅支持图片，Mixkit 仅支持视频。

参数：`q`（必填）、`media_type`（可选，`image` 或 `video`；不传时同时检索图片和视频）、`category`（可选）。

响应通过 `groups.image.local`、`groups.image.external`、`groups.video.local`、`groups.video.external` 提供四组结果，同时保留扁平 `items` 兼容字段。返回项的 `source` 为 `local` 时包含 `asset`；为 `external` 时包含 `provider`、`external_id`、`title`、`preview_url`、`source_page_url`、`score` 等字段。

### `GET /api/assets/{asset_id}`

获取素材详情及处理状态。

### `GET /api/assets/{asset_id}/content`

流式返回原始图片或视频文件。

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
| `provider` | string | `pexels`、`pixabay`、`unsplash`、`openverse`、`mixkit` |
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

成功返回 `202` 和本地素材对象；重复导入同一 provider/id 时返回已有素材。

`mixkit` 当前只支持英文关键词和视频。结果使用 Mixkit Stock Video Free License，导入时后端会重新读取详情页并选择不超过 1080p 的可用规格。

## 已停用接口

以下接口当前统一返回 `410 Gone`：

- `GET /api/fred/series`
- `POST /api/fred/charts`
- 音频上传及音频检索

## 前端调用关系

```text
无搜索词       GET /api/assets
有搜索词       GET /api/search
上传           POST /api/assets/upload
外部素材浏览   GET /api/external-assets/search
导入外部素材   POST /api/external-assets/import
详情/状态      GET /api/assets/{id}
编辑           PATCH /api/assets/{id}
重分析         POST /api/assets/{id}/reanalyze
删除           DELETE /api/assets/{id} 或 /batch
```
