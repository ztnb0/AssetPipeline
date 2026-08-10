"use client";

import { ChangeEvent, DragEvent, FormEvent, useCallback, useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";
const FORMAT_EXPORT_ENABLED = false;

type Status = "processing" | "ready" | "failed";
type UploadStatus = "queued" | "uploading" | "processing" | "ready" | "failed";
type UploadItem = {
  id: string;
  file: File;
  status: UploadStatus;
  progress: number;
  assetId?: string;
  error?: string;
};

type DroppedEntry = {
  isFile: boolean;
  isDirectory: boolean;
  file?: (callback: (file: File) => void) => void;
  createReader?: () => { readEntries: (callback: (entries: DroppedEntry[]) => void) => void };
};
type Asset = {
  id: string;
  original_name: string;
  media_type: string;
  mime_type: string;
  file_size: number;
  width: number | null;
  height: number | null;
  duration: number | null;
  media_metadata: Record<string, unknown>;
  status: Status;
  description: string | null;
  scene: string | null;
  tags: string[];
  category: string | null;
  categories: string[];
  error_message: string | null;
  source_type: string;
  source_id: string | null;
  source_page_url: string | null;
  source_author: string | null;
  source_license: string | null;
  created_at: string;
  content_url: string;
  thumbnail_url: string | null;
  search_score?: number | null;
  external_provider?: ExternalProvider;
  search_group?: "image-local" | "image-external" | "video-local" | "video-external";
};

type ExternalProvider = "pexels" | "pixabay" | "unsplash" | "openverse" | "mixkit";
type ExternalAsset = {
  provider: ExternalProvider;
  external_id: string;
  media_type: "image" | "video";
  title: string;
  preview_url: string;
  author: string;
  source_page_url: string;
  width: number | null;
  height: number | null;
  duration: number | null;
  license: string | null;
  license_url: string | null;
};

type FredSeries = { id: string; label: string; short: string; category: string };

const statusText: Record<Status, string> = {
  processing: "AI 分析中",
  ready: "分析完成",
  failed: "处理失败",
};

const uploadStatusText: Record<UploadStatus, string> = {
  queued: "等待上传",
  uploading: "上传中",
  processing: "AI 分析中",
  ready: "完成",
  failed: "失败",
};

function absoluteUrl(path: string | null) {
  if (!path) return "";
  // External providers return absolute CDN URLs; only resolve API-relative paths.
  if (/^(?:https?:|data:|blob:)/i.test(path)) return path;
  if (path.startsWith("//")) return `https:${path}`;
  return `${API.replace(/\/api$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
}

function createUploadId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `upload-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function durationText(seconds: number | null) {
  if (seconds === null) return "";
  const rounded = Math.round(seconds);
  return `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, "0")}`;
}

const mediaText: Record<string, string> = { image: "图片", video: "视频", audio: "音频" };
const providerText: Record<ExternalProvider, string> = { pexels: "Pexels", pixabay: "Pixabay", unsplash: "Unsplash", openverse: "Openverse", mixkit: "Mixkit" };
const categoryOptions = ["科技", "财经", "金融市场", "宏观经济", "金融理财", "投资管理", "保险规划", "养老规划", "税务规划", "财富传承", "私人银行", "金融教育", "财经新闻", "民生", "教育", "商业", "文化", "娱乐", "体育", "医疗", "自然", "交通", "工业", "政务", "音频制作", "待内容识别", "其他"];

export default function Home() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploadItems, setUploadItems] = useState<UploadItem[]>([]);
  const [uploadConcurrency, setUploadConcurrency] = useState<1 | 3 | 5>(3);
  const [message, setMessage] = useState("");
  const [queryTerms, setQueryTerms] = useState<string[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Asset | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchDeleting, setBatchDeleting] = useState(false);
  const [importingExternalId, setImportingExternalId] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [externalOpen, setExternalOpen] = useState(false);
  const [fredOpen, setFredOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const activeUploads = useRef(new Map<string, XMLHttpRequest | null>());

  const loadAssets = useCallback(async (q = "") => {
    try {
      const response = await fetch(q.trim() ? `${API}/search?q=${encodeURIComponent(q)}` : `${API}/assets`, { cache: "no-store" });
      if (!response.ok) throw new Error("无法加载素材列表");
      const data = await response.json();
      const nextAssets: Asset[] = q.trim() ? data.items.map((item: any) => {
        const source = item.source === "local" ? "local" : "external";
        const mediaType = item.source === "local" ? item.asset.media_type : item.media_type;
        const searchGroup = `${mediaType}-${source}` as Asset["search_group"];
        return item.source === "local" ? { ...item.asset, search_group: searchGroup } : ({
          id: `external:${item.provider}:${item.external_id}`, original_name: item.title, media_type: item.media_type,
          mime_type: item.media_type === "video" ? "video/mp4" : "image/jpeg", file_size: 0, width: item.width, height: item.height,
          duration: item.duration ?? null, media_metadata: {}, status: "ready", description: `${providerText[item.provider as ExternalProvider]} 外部素材`,
          scene: "External", tags: [item.provider], category: "External", categories: ["External"], error_message: null,
          source_type: "external", source_id: item.external_id, source_page_url: item.source_page_url, source_author: item.author,
          source_license: item.license, created_at: new Date().toISOString(), content_url: item.preview_url,
          thumbnail_url: item.preview_url, search_score: item.score, external_provider: item.provider, search_group: searchGroup,
        });
      }) : data.items;
      setAssets(nextAssets);
      setQueryTerms(data.query_terms ?? []);
      setUploadItems((items) => items.map((item) => {
        if (!item.assetId || (item.status !== "processing" && item.status !== "ready")) return item;
        const asset = nextAssets.find((candidate: Asset) => candidate.id === item.assetId);
        if (!asset || asset.status === "processing") return item;
        return { ...item, status: asset.status, error: asset.error_message ?? undefined };
      }));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "请求失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAssets(); }, [loadAssets]);

  useEffect(() => {
    const availableIds = new Set(assets.map((asset) => asset.id));
    setSelectedIds((current) => {
      const next = new Set([...current].filter((id) => availableIds.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [assets]);

  useEffect(() => {
    if (!selectedAsset) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelectedAsset(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [selectedAsset]);

  useEffect(() => {
    if (!assets.some((asset) => asset.status === "processing")) return;
    const timer = window.setInterval(() => loadAssets(query), 2000);
    return () => window.clearInterval(timer);
  }, [assets, loadAssets, query]);

  const processingUploadIds = uploadItems
    .filter((item) => item.status === "processing" && item.assetId)
    .map((item) => item.assetId)
    .join(",");

  useEffect(() => {
    if (!processingUploadIds) return;
    let cancelled = false;
    const refreshUploadStatuses = async () => {
      const ids = processingUploadIds.split(",");
      const results = await Promise.all(ids.map(async (id) => {
        try {
          const response = await fetch(`${API}/assets/${id}`, { cache: "no-store" });
          return response.ok ? await response.json() as Asset : null;
        } catch {
          return null;
        }
      }));
      if (cancelled) return;
      const statuses = new Map(results.filter(Boolean).map((asset) => [asset!.id, asset!]));
      const hasCompleted = results.some((asset) => asset && asset.status !== "processing");
      setUploadItems((items) => {
        let changed = false;
        const next = items.map((item) => {
          const asset = item.assetId ? statuses.get(item.assetId) : undefined;
          if (!asset || asset.status === "processing" || item.status !== "processing") return item;
          changed = true;
          return { ...item, status: asset.status, error: asset.error_message ?? undefined };
        });
        return changed ? next : items;
      });
      if (hasCompleted) await loadAssets(query);
    };
    refreshUploadStatuses();
    const timer = window.setInterval(refreshUploadStatuses, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [processingUploadIds, loadAssets, query]);

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (!files.length) return;
    enqueueFiles(files);
    event.target.value = "";
  }

  function enqueueFiles(files: File[]) {
    setUploadItems((items) => {
      const existing = new Set(items.map((item) => `${item.file.name}:${item.file.size}:${item.file.lastModified}`));
      const next = files
        .filter((file) => !existing.has(`${file.name}:${file.size}:${file.lastModified}`))
        .map((file) => ({
          id: createUploadId(), file, status: "queued" as const, progress: 0,
        }));
      return [...items, ...next];
    });
  }

  async function readDroppedEntry(entry: DroppedEntry): Promise<File[]> {
    if (entry.isFile && entry.file) {
      return new Promise((resolve) => entry.file!((file) => resolve([file])));
    }
    if (!entry.isDirectory || !entry.createReader) return [];
    const reader = entry.createReader();
    const entries: DroppedEntry[] = [];
    const readBatch = (): Promise<void> => new Promise((resolve) => reader.readEntries(async (batch) => {
      if (!batch.length) return resolve();
      entries.push(...batch);
      await readBatch();
      resolve();
    }));
    await readBatch();
    return (await Promise.all(entries.map(readDroppedEntry))).flat();
  }

  async function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    const items = Array.from(event.dataTransfer.items ?? []);
    const entries = items.map((item) => (item as DataTransferItem & { webkitGetAsEntry?: () => DroppedEntry | null }).webkitGetAsEntry?.()).filter(Boolean) as DroppedEntry[];
    const files = entries.length
      ? (await Promise.all(entries.map(readDroppedEntry))).flat()
      : Array.from(event.dataTransfer.files ?? []);
    if (files.length) enqueueFiles(files);
  }

  const startUpload = useCallback((item: UploadItem) => {
    const xhr = new XMLHttpRequest();
    activeUploads.current.set(item.id, xhr);
    xhr.open("POST", `${API}/assets/upload`);
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      const progress = Math.min(99, Math.round((event.loaded / event.total) * 100));
      setUploadItems((items) => items.map((candidate) => candidate.id === item.id ? { ...candidate, progress } : candidate));
    };
    xhr.onload = async () => {
      activeUploads.current.delete(item.id);
      if (xhr.status >= 200 && xhr.status < 300) {
        const asset: Asset = JSON.parse(xhr.responseText);
        setUploadItems((items) => items.map((candidate) => candidate.id === item.id
          ? { ...candidate, status: "processing", progress: 100, assetId: asset.id, error: undefined }
          : candidate));
        await loadAssets();
      } else {
        let error = "上传失败";
        try { error = JSON.parse(xhr.responseText).detail ?? error; } catch { /* Keep the fallback message. */ }
        setUploadItems((items) => items.map((candidate) => candidate.id === item.id ? { ...candidate, status: "failed", error } : candidate));
      }
    };
    xhr.onerror = () => {
      activeUploads.current.delete(item.id);
      setUploadItems((items) => items.map((candidate) => candidate.id === item.id ? { ...candidate, status: "failed", error: "网络连接失败" } : candidate));
    };
    xhr.onabort = () => {
      activeUploads.current.delete(item.id);
      setUploadItems((items) => items.filter((candidate) => candidate.id !== item.id));
    };
    const form = new FormData();
    form.append("file", item.file);
    xhr.send(form);
  }, [loadAssets]);

  useEffect(() => {
    const available = uploadConcurrency - activeUploads.current.size;
    if (available <= 0) return;
    const queued = uploadItems.filter((item) => item.status === "queued" && !activeUploads.current.has(item.id)).slice(0, available);
    if (!queued.length) return;
    queued.forEach((item) => activeUploads.current.set(item.id, null));
    setUploadItems((items) => items.map((item) => queued.some((candidate) => candidate.id === item.id) ? { ...item, status: "uploading" } : item));
    queued.forEach(startUpload);
  }, [startUpload, uploadConcurrency, uploadItems]);

  function removeUpload(item: UploadItem) {
    const request = activeUploads.current.get(item.id);
    if (request) request.abort();
    else setUploadItems((items) => items.filter((candidate) => candidate.id !== item.id));
  }

  async function retryUpload(item: UploadItem) {
    if (item.assetId) {
      setUploadItems((items) => items.map((candidate) => candidate.id === item.id ? { ...candidate, status: "processing", error: undefined } : candidate));
      const response = await fetch(`${API}/assets/${item.assetId}/reanalyze`, { method: "POST" });
      if (!response.ok) setUploadItems((items) => items.map((candidate) => candidate.id === item.id ? { ...candidate, status: "failed", error: "重新分析失败" } : candidate));
      return;
    }
    setUploadItems((items) => items.map((candidate) => candidate.id === item.id ? { ...candidate, status: "queued", progress: 0, error: undefined } : candidate));
  }

  function search(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    loadAssets(query);
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      const response = await fetch(`${API}/assets/${deleteTarget.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error("删除素材失败");
      setAssets((items) => items.filter((item) => item.id !== deleteTarget.id));
      if (selectedAsset?.id === deleteTarget.id) setSelectedAsset(null);
      setMessage(`已删除：${deleteTarget.original_name}`);
      setDeleteTarget(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除素材失败");
    } finally {
      setDeleting(false);
    }
  }

  function toggleSelected(assetId: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(assetId)) next.delete(assetId);
      else next.add(assetId);
      return next;
    });
  }

  async function deleteSelected() {
    const ids = [...selectedIds];
    if (!ids.length || !window.confirm(`确定删除已选择的 ${ids.length} 项素材吗？原始文件、缩略图和索引也会被删除，无法恢复。`)) return;
    setBatchDeleting(true);
    try {
      const response = await fetch(`${API}/assets/batch`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids }),
      });
      if (!response.ok) throw new Error("批量删除素材失败");
      const result: { deleted_ids: string[]; failed: Record<string, string> } = await response.json();
      const deleted = new Set(result.deleted_ids);
      setAssets((items) => items.filter((item) => !deleted.has(item.id)));
      setSelectedIds(new Set(Object.keys(result.failed)));
      if (selectedAsset && deleted.has(selectedAsset.id)) setSelectedAsset(null);
      const failedCount = Object.keys(result.failed).length;
      setMessage(failedCount
        ? `已删除 ${result.deleted_ids.length} 项，${failedCount} 项删除失败并保持选中`
        : `已删除 ${result.deleted_ids.length} 项素材`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "批量删除素材失败");
    } finally {
      setBatchDeleting(false);
    }
  }

  async function importExternalAsset(asset: Asset) {
    if (!asset.external_provider || !asset.source_id) return;
    setImportingExternalId(asset.id);
    setMessage("");
    try {
      const response = await fetch(`${API}/external-assets/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: asset.external_provider,
          external_id: asset.source_id,
          media_type: asset.media_type,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `${providerText[asset.external_provider]} 素材导入失败`);
      setAssets((items) => items.map((item) => item.id === asset.id ? data : item));
      setMessage(`${providerText[asset.external_provider]} 素材已导入，正在进行 AI 分析`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "素材导入失败");
    } finally {
      setImportingExternalId(null);
    }
  }

  const visibleAssets = assets.filter((asset) =>
    (typeFilter === "all" || asset.media_type === typeFilter) &&
    (categoryFilter === "all" || (asset.categories?.length ? asset.categories : [asset.category || "其他"]).includes(categoryFilter))
  );
  const availableCategories = Array.from(new Set(assets.flatMap((asset) => asset.categories?.length ? asset.categories : [asset.category || "其他"]))).sort();
  const visibleAssetIds = Array.from(new Set(visibleAssets.filter((asset) => asset.source_type !== "external").map((asset) => asset.id)));
  const allVisibleSelected = visibleAssetIds.length > 0 && visibleAssetIds.every((id) => selectedIds.has(id));
  const isSearchResults = assets.some((asset) => asset.search_group !== undefined);
  const browseSections = Object.entries(visibleAssets.reduce<Record<string, Asset[]>>((groups, asset) => {
    const sections = categoryFilter === "all" ? (asset.categories?.length ? asset.categories : [asset.category || "其他"]) : [categoryFilter];
    sections.forEach((section) => (groups[section] ||= []).push(asset));
    return groups;
  }, {})).map(([title, sectionAssets]) => ({ key: `category-${title}`, title, eyebrow: "主题板块", assets: sectionAssets, mediaHeader: null as string | null }));
  const searchSections = (["image", "video"] as const).flatMap((mediaType) => {
    const sections = (["local", "external"] as const).map((source) => ({
      key: `${mediaType}-${source}`,
      title: source === "local" ? "内部资源" : "外部资源",
      eyebrow: source === "local" ? "本地素材库" : "开放素材平台",
      assets: visibleAssets.filter((asset) => asset.search_group === `${mediaType}-${source}`),
      mediaHeader: null as string | null,
    })).filter((section) => section.assets.length > 0);
    if (sections.length) sections[0].mediaHeader = mediaType === "image" ? "图片" : "视频";
    return sections;
  });
  const displaySections = isSearchResults ? searchSections : browseSections;

  function toggleAllVisible() {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (allVisibleSelected) visibleAssetIds.forEach((id) => next.delete(id));
      else visibleAssetIds.forEach((id) => next.add(id));
      return next;
    });
  }

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-5 py-8 sm:px-8">
      <header className="mb-10 flex flex-col justify-between gap-5 border-b border-white/10 pb-7 md:flex-row md:items-end">
        <div>
          <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[.28em] text-teal-400">
            <span className="h-2 w-2 rounded-full bg-teal-400 shadow-[0_0_14px_#2dd4bf]" />
            AI Video Factory
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">素材资产中心</h1>
          <p className="mt-2 max-w-xl text-sm leading-6 text-slate-400">统一管理图片、视频和音频；自动解析媒体信息，并由多模态模型理解视觉内容。</p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <button type="button" onClick={() => setFredOpen(true)} className="inline-flex items-center justify-center rounded-lg border border-white/15 bg-white/[.06] px-5 py-3 text-sm font-semibold text-white transition hover:border-teal-400/40 hover:bg-white/10">生成财经图表</button>
          <button type="button" onClick={() => setExternalOpen(true)} className="inline-flex items-center justify-center rounded-lg border border-white/15 bg-white/[.06] px-5 py-3 text-sm font-semibold text-white transition hover:border-teal-400/40 hover:bg-white/10">从素材平台导入</button>
          <label onDragOver={(event) => event.preventDefault()} onDrop={onDrop} className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-teal-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-teal-300">
            <span>+ 批量上传素材</span><span className="text-[11px] font-normal text-slate-700">可拖拽文件夹</span>
            <input ref={fileRef} multiple onChange={onFileChange} type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/x-matroska,video/webm,audio/mpeg,audio/wav,audio/mp4,audio/flac,audio/ogg,.m4a,.mkv" className="sr-only" />
          </label>
        </div>
      </header>

      {uploadItems.length > 0 && <section className="mb-7 border-y border-white/10 bg-white/[.025] py-5">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white">上传队列</h2>
            <p className="mt-1 text-xs text-slate-500">
              {uploadItems.filter((item) => item.status === "ready").length} 完成 · {uploadItems.filter((item) => item.status === "failed").length} 失败 · {uploadItems.length} 个文件
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs text-slate-500">上传并发</span>
            <div className="flex rounded-lg border border-white/10 bg-black/20 p-1">
              {([1, 3, 5] as const).map((value) => <button key={value} type="button" onClick={() => setUploadConcurrency(value)} className={`h-8 min-w-9 rounded-md text-xs font-medium transition ${uploadConcurrency === value ? "bg-teal-400 text-slate-950" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}>{value}</button>)}
            </div>
            <button type="button" onClick={() => setUploadItems((items) => items.filter((item) => item.status !== "ready"))} className="rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-400 hover:bg-white/5 hover:text-white">清除已完成</button>
          </div>
        </div>
        <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
          {uploadItems.map((item) => <div key={item.id} className="grid gap-3 border-b border-white/[.07] px-1 py-3 last:border-0 sm:grid-cols-[minmax(0,1fr)_150px_88px] sm:items-center">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="truncate text-sm text-slate-200" title={item.file.name}>{item.file.name}</span>
                <span className="shrink-0 text-[11px] text-slate-600">{(item.file.size / 1024 / 1024).toFixed(2)} MB</span>
              </div>
              {item.error && <p className="mt-1 truncate text-xs text-red-300" title={item.error}>{item.error}</p>}
            </div>
            <div>
              <div className="mb-1 flex justify-between text-[11px]"><span className={item.status === "failed" ? "text-red-300" : item.status === "ready" ? "text-emerald-300" : "text-slate-400"}>{uploadStatusText[item.status]}</span><span className="text-slate-600">{item.progress}%</span></div>
              <div className="h-1.5 overflow-hidden rounded-full bg-white/[.07]"><div className={`h-full transition-all ${item.status === "failed" ? "bg-red-400" : item.status === "ready" ? "bg-emerald-400" : "bg-teal-400"}`} style={{ width: `${item.progress}%` }} /></div>
            </div>
            <div className="flex justify-end gap-2">
              {item.status === "failed" && <button type="button" onClick={() => retryUpload(item)} className="rounded-md border border-teal-400/20 px-2.5 py-1.5 text-xs text-teal-300 hover:bg-teal-400/10">重试</button>}
              {(item.status === "queued" || item.status === "uploading" || item.status === "failed" || item.status === "ready") && <button type="button" onClick={() => removeUpload(item)} aria-label={`移除 ${item.file.name}`} className="rounded-md border border-white/10 px-2.5 py-1.5 text-xs text-slate-500 hover:bg-white/5 hover:text-white">移除</button>}
            </div>
          </div>)}
        </div>
      </section>}

      <section className="mb-7 flex flex-col gap-3 sm:flex-row sm:items-center">
        <form onSubmit={search} className="flex min-w-0 flex-1 gap-2">
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="语义搜索：例如对谈、经济、人工智能…" className="min-w-0 flex-1 rounded-xl border border-white/10 bg-white/[.055] px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-teal-400/60 focus:bg-white/[.075]" />
          <button className="rounded-xl border border-white/10 bg-white/10 px-5 text-sm font-medium text-slate-200 transition hover:bg-white/15">语义搜索</button>
        </form>
        <div className="flex items-center gap-2 text-sm tabular-nums text-slate-500">
          {[["all", "全部"], ["video", "视频"], ["image", "图片"], ["audio", "音频"]].map(([value, label]) => <button key={value} type="button" onClick={() => setTypeFilter(value)} className={`rounded-lg px-3 py-1.5 text-xs ${typeFilter === value ? "bg-teal-400/15 text-teal-300" : "text-slate-500 hover:text-slate-300"}`}>{label}</button>)}
          <span>{visibleAssets.length} 项素材</span>
        </div>
      </section>
      {queryTerms.length > 1 && <div className="-mt-4 mb-6 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-600"><span>素材相关扩展：</span>{queryTerms.slice(1).map((term) => <button type="button" key={term} aria-label={`搜索 ${term}`} onClick={() => { setQuery(term); setLoading(true); loadAssets(term); }} className="rounded-full border border-white/[.07] px-2 py-1 text-slate-500 transition hover:border-teal-400/30 hover:bg-teal-400/10 hover:text-teal-300">{term}</button>)}</div>}

      {!isSearchResults && <section className="mb-6 flex items-center gap-3 overflow-x-auto pb-1 text-xs">
        <span className="shrink-0 text-slate-600">题材分类</span>
        {["all", ...availableCategories].map((value) => <button key={value} type="button" onClick={() => setCategoryFilter(value)} className={`shrink-0 rounded-full border px-3 py-1.5 transition ${categoryFilter === value ? "border-teal-400/30 bg-teal-400/15 text-teal-300" : "border-white/10 bg-white/[.025] text-slate-500 hover:text-slate-300"}`}>{value === "all" ? "全部题材" : value}</button>)}
      </section>}

      {visibleAssetIds.length > 0 && <section className="mb-6 flex flex-wrap items-center justify-between gap-3 border-y border-white/10 py-3">
        <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={allVisibleSelected} onChange={toggleAllVisible} className="h-4 w-4 accent-teal-400" />
          全选当前结果
        </label>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">已选择 {selectedIds.size} 项</span>
          <button type="button" disabled={!selectedIds.size || batchDeleting} onClick={deleteSelected} className="rounded-lg border border-red-400/30 bg-red-500/10 px-4 py-2 text-sm font-medium text-red-300 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-40">
            {batchDeleting ? "删除中…" : "批量删除"}
          </button>
        </div>
      </section>}

      {message && <div className="mb-6 rounded-xl border border-teal-400/20 bg-teal-400/10 px-4 py-3 text-sm text-teal-200">{message}</div>}

      {loading ? (
        <div className="py-24 text-center text-sm text-slate-500">正在读取素材库…</div>
      ) : assets.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-white/15 bg-white/[.025] py-24 text-center">
          <p className="text-lg text-slate-300">素材库还是空的</p>
          <p className="mt-2 text-sm text-slate-600">上传图片、视频或音频，开始构建智能素材库。</p>
        </div>
      ) : (
        <div className="space-y-9">
          {displaySections.map((section) => <section key={section.key}>
            {section.mediaHeader && <header className="mb-5 border-b border-teal-400/25 pb-3"><h2 className="text-2xl font-semibold text-white">{section.mediaHeader}</h2></header>}
            <header className="mb-4 flex items-center justify-between border-b border-white/10 pb-3"><div><span className="text-[10px] font-semibold uppercase tracking-[.2em] text-teal-400">{section.eyebrow}</span><h3 className="mt-1 text-lg font-semibold text-white">{section.title}</h3></div><span className="text-xs text-slate-500">{section.assets.length} 项素材</span></header>
            <div className="grid items-start gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {section.assets.map((asset) => (
            <article key={asset.id} role="button" tabIndex={0} aria-label={`查看 ${asset.original_name} 详情`} onClick={() => setSelectedAsset(asset)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setSelectedAsset(asset); }} className="cursor-pointer overflow-hidden rounded-2xl border border-white/10 bg-[#11161e]/90 shadow-2xl shadow-black/20 transition hover:-translate-y-0.5 hover:border-teal-400/30 focus:outline-none focus:ring-2 focus:ring-teal-400/60">
              <div className="relative overflow-hidden bg-slate-900" style={{ aspectRatio: asset.width && asset.height ? `${asset.width} / ${asset.height}` : "16 / 9" }}>
                {asset.source_type !== "external" && <label className="absolute bottom-2.5 left-2.5 z-10 flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg border border-white/20 bg-black/70 backdrop-blur" onClick={(event) => event.stopPropagation()}>
                  <input type="checkbox" aria-label={`选择 ${asset.original_name}`} checked={selectedIds.has(asset.id)} onChange={() => toggleSelected(asset.id)} className="h-4 w-4 accent-teal-400" />
                </label>}
                {asset.media_type !== "audio" && (asset.thumbnail_url || asset.content_url) && <img loading="lazy" decoding="async" src={absoluteUrl(asset.thumbnail_url || asset.content_url)} alt="" onError={(event) => { event.currentTarget.style.display = "none"; }} className="h-full w-full object-contain" />}
                {asset.media_type === "audio" && <div className="flex h-full items-center justify-center bg-gradient-to-br from-violet-950 to-slate-950"><div className="flex h-20 w-20 items-center justify-center rounded-full border border-violet-300/20 bg-violet-400/10 text-4xl text-violet-300">♫</div></div>}
                <div className="absolute left-3 top-3 rounded-md border border-white/10 bg-black/60 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-white/80 backdrop-blur">{mediaText[asset.media_type] ?? asset.media_type}</div>
                {asset.search_score !== null && asset.search_score !== undefined && <div className="absolute left-3 top-11 rounded-md border border-teal-300/25 bg-teal-950/80 px-2 py-1 text-[10px] font-semibold text-teal-200 backdrop-blur">{asset.search_group === "video-external" ? "平台排名" : "相关度"} {(asset.search_score * 100).toFixed(0)}%</div>}
                <div className={`absolute right-3 top-3 rounded-full border px-2.5 py-1 text-[11px] font-medium backdrop-blur ${asset.status === "ready" ? "border-emerald-300/30 bg-emerald-950/70 text-emerald-300" : asset.status === "failed" ? "border-red-300/30 bg-red-950/70 text-red-300" : "border-amber-300/30 bg-amber-950/70 text-amber-200"}`}>{statusText[asset.status]}</div>
                {asset.source_type !== "external" && <button type="button" aria-label={`删除 ${asset.original_name}`} onClick={(event) => { event.stopPropagation(); setDeleteTarget(asset); }} className="absolute bottom-2.5 right-2.5 flex h-8 w-8 items-center justify-center rounded-lg border border-red-300/20 bg-black/65 text-sm text-red-300 opacity-80 backdrop-blur transition hover:bg-red-500/25 hover:opacity-100">⌫</button>}
              </div>
              <div className="p-4">
                <h2 className="truncate text-sm font-semibold text-white" title={asset.original_name}>{asset.original_name}</h2>
                <div className="mt-2 flex gap-3 text-xs text-slate-500">
                  <span>{(asset.file_size / 1024 / 1024).toFixed(2)} MB</span>
                  {asset.duration !== null && <span>{durationText(asset.duration)}</span>}
                  {asset.width && <span>{asset.width} × {asset.height}</span>}
                  {(asset.categories?.length || asset.category || asset.scene) && <span className="truncate text-teal-400">板块：{(asset.categories?.length ? asset.categories : [asset.category || asset.scene]).join(" / ")}</span>}
                </div>
                <p className="mt-3 min-h-10 line-clamp-2 text-xs leading-5 text-slate-400">{asset.description || (asset.status === "failed" ? asset.error_message : "模型正在分析画面内容，请稍候…")}</p>
                <div className="mt-3 flex min-h-12 flex-wrap content-start gap-1.5">
                  {asset.tags.slice(0, 6).map((tag) => <span key={tag} className="rounded-md border border-white/10 bg-white/[.055] px-2 py-1 text-[10px] text-slate-300">{tag}</span>)}
                  {asset.tags.length > 6 && <span className="px-1 py-1 text-[10px] text-slate-600">+{asset.tags.length - 6}</span>}
                </div>
                {asset.source_type === "external" && <button type="button" disabled={importingExternalId !== null} onClick={(event) => { event.stopPropagation(); void importExternalAsset(asset); }} className="mt-3 h-10 w-full rounded-md bg-teal-400 text-xs font-semibold text-slate-950 transition hover:bg-teal-300 disabled:cursor-wait disabled:opacity-50">{importingExternalId === asset.id ? "正在下载并导入…" : "导入素材库"}</button>}
              </div>
            </article>
          ))}
            </div>
          </section>)}
        </div>
      )}

      {selectedAsset && <AssetDetail asset={selectedAsset} onClose={() => setSelectedAsset(null)} onSaved={(next) => { setSelectedAsset(next); setAssets((items) => items.map((item) => item.id === next.id ? next : item)); }} onDeleted={(id) => { setSelectedAsset(null); setAssets((items) => items.filter((item) => item.id !== id)); }} />}
      {deleteTarget && <DeleteConfirm asset={deleteTarget} deleting={deleting} onCancel={() => setDeleteTarget(null)} onConfirm={confirmDelete} />}
      {externalOpen && <ExternalAssetBrowser onClose={() => setExternalOpen(false)} onImported={async (provider) => { setMessage(`${providerText[provider]} 素材已导入，正在进行 AI 分析`); await loadAssets(query); }} />}
      {fredOpen && <FredChartBuilder onClose={() => setFredOpen(false)} onCreated={async () => { setMessage("FRED 财经图表已生成，正在进行 AI 分析"); await loadAssets(query); }} />}
    </main>
  );
}

function AssetDetail({ asset, onClose, onSaved, onDeleted }: { asset: Asset; onClose: () => void; onSaved: (asset: Asset) => void; onDeleted: (id: string) => void }) {
  const [name, setName] = useState(asset.original_name);
  const [tags, setTags] = useState(asset.tags);
  const [newTag, setNewTag] = useState("");
  const [categories, setCategories] = useState(asset.categories?.length ? asset.categories : [asset.category || "其他"]);
  const [scene, setScene] = useState(asset.scene || "");
  const [description, setDescription] = useState(asset.description || "");
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState("");
  const [exportOpen, setExportOpen] = useState(false);
  async function saveMetadata() {
    if (!name.trim()) { setEditError("素材名称不能为空"); return; }
    setSaving(true);
    setEditError("");
    try {
      const cleanedTags = Array.from(new Set(tags.map((tag) => tag.trim()).filter(Boolean)));
      const response = await fetch(`${API}/assets/${asset.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ original_name: name.trim(), tags: cleanedTags, categories, scene, description }) });
      if (!response.ok) throw new Error("素材信息保存失败");
      onSaved(await response.json());
      setTags(cleanedTags);
    } catch (error) { setEditError(error instanceof Error ? error.message : "素材信息保存失败"); }
    finally { setSaving(false); }
  }
  function addTag() { const value = newTag.trim(); if (!value || tags.includes(value)) return; setTags([...tags, value]); setNewTag(""); }
  function removeTag(index: number) { setTags(tags.filter((_, itemIndex) => itemIndex !== index)); }
  function renameTag(index: number, value: string) { setTags(tags.map((tag, itemIndex) => itemIndex === index ? value : tag)); }
  function toggleCategory(value: string) {
    setCategories((items) => items.includes(value) ? (items.length > 1 ? items.filter((item) => item !== value) : items) : [...items, value]);
  }
  async function deleteAsset() {
    if (!window.confirm(`确定删除“${asset.original_name}”吗？原始文件和缩略图也会一起删除，无法恢复。`)) return;
    const response = await fetch(`${API}/assets/${asset.id}`, { method: "DELETE" });
    if (!response.ok) { window.alert("删除素材失败"); return; }
    onDeleted(asset.id);
  }
  const streams = Array.isArray(asset.media_metadata.streams)
    ? asset.media_metadata.streams as Array<Record<string, unknown>>
    : [];
  const primaryStream = streams.find((stream) => stream.codec_type === asset.media_type) ?? streams[0] ?? {};
  const bitRate = typeof asset.media_metadata.bit_rate === "number"
    ? `${Math.round(asset.media_metadata.bit_rate / 1000)} kbps`
    : null;
  const transcript = typeof asset.media_metadata.transcript === "string" ? asset.media_metadata.transcript : null;
  const detailRows = [
    ["素材类型", mediaText[asset.media_type] ?? asset.media_type],
    ["文件格式", asset.mime_type],
    ["文件大小", `${(asset.file_size / 1024 / 1024).toFixed(2)} MB`],
    ["时长", asset.duration !== null ? durationText(asset.duration) : null],
    ["分辨率", asset.width && asset.height ? `${asset.width} × ${asset.height}` : null],
    ["编码", typeof primaryStream.codec_name === "string" ? primaryStream.codec_name.toUpperCase() : null],
    ["码率", bitRate],
    ["采样率", primaryStream.sample_rate ? `${primaryStream.sample_rate} Hz` : null],
    ["声道", primaryStream.channels ? `${primaryStream.channels} 声道` : null],
    ["帧率", primaryStream.r_frame_rate && primaryStream.r_frame_rate !== "0/0" ? String(primaryStream.r_frame_rate) : null],
    ["素材来源", asset.source_type === "fred" ? "FRED" : asset.source_type in providerText ? providerText[asset.source_type as ExternalProvider] : "本地上传"],
    ["来源作者", asset.source_author],
    ["使用许可", asset.source_license],
    ["上传时间", new Date(asset.created_at).toLocaleString("zh-CN")],
  ].filter((row) => row[1]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section role="dialog" aria-modal="true" aria-labelledby="asset-detail-title" className="max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-2xl border border-white/15 bg-[#10151d] shadow-2xl shadow-black/60">
        <header className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-white/10 bg-[#10151d]/95 px-5 py-4 backdrop-blur sm:px-6">
          <div className="min-w-0">
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-[.2em] text-teal-400">素材详情</div>
            <h2 id="asset-detail-title" className="truncate text-lg font-semibold text-white">{asset.original_name}</h2>
          </div>
          <button onClick={onClose} aria-label="关闭素材详情" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/5 text-xl text-slate-300 transition hover:bg-white/10 hover:text-white">×</button>
        </header>

        <div className="grid gap-0 lg:grid-cols-[minmax(0,1.45fr)_minmax(300px,.75fr)]">
          <div className="flex min-h-72 items-center justify-center bg-black/35 p-4 sm:p-6">
            {asset.media_type === "image" && <img src={absoluteUrl(asset.content_url)} alt={asset.original_name} className="max-h-[65vh] max-w-full rounded-lg object-contain" />}
            {asset.media_type === "video" && <video src={absoluteUrl(asset.content_url)} poster={absoluteUrl(asset.thumbnail_url)} controls preload="metadata" className="max-h-[65vh] w-full rounded-lg bg-black" />}
            {asset.media_type === "audio" && <div className="w-full max-w-xl rounded-2xl border border-violet-300/15 bg-gradient-to-br from-violet-950/80 to-slate-950 p-8 text-center"><div className="mx-auto mb-6 flex h-24 w-24 items-center justify-center rounded-full border border-violet-300/20 bg-violet-400/10 text-5xl text-violet-300">♫</div><p className="mb-6 truncate text-sm text-violet-100">{asset.original_name}</p><audio src={absoluteUrl(asset.content_url)} controls preload="metadata" className="w-full" /></div>}
          </div>

          <aside className="border-t border-white/10 p-5 lg:border-l lg:border-t-0 lg:p-6">
              <div className="mb-6">
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">内容信息（可修改）</h3>
                <label className="mb-3 block text-xs text-slate-500">素材名称<input aria-label="素材名称" value={name} onChange={(event) => setName(event.target.value)} maxLength={255} className="mt-1.5 w-full rounded-lg border border-white/10 bg-white/[.055] px-3 py-2 text-xs text-white outline-none focus:border-teal-400/50" /></label>
                <div className="mb-3 text-xs text-slate-500">题材分类（可多选）<div className="mt-2 flex flex-wrap gap-1.5">{Array.from(new Set([...categoryOptions, ...categories])).map((item) => { const active = categories.includes(item); return <button key={item} type="button" aria-pressed={active} onClick={() => toggleCategory(item)} className={`rounded-full border px-2.5 py-1.5 text-xs transition ${active ? "border-teal-400/40 bg-teal-400/15 text-teal-300" : "border-white/10 bg-white/[.03] text-slate-500 hover:text-slate-300"}`}>{active ? "✓ " : ""}{item}</button>; })}</div><p className="mt-1.5 text-[10px] text-slate-600">至少保留一个分类；第一个分类作为存储主目录。</p></div>
                <label className="mb-3 block text-xs text-slate-500">具体场景<input value={scene} onChange={(event) => setScene(event.target.value)} placeholder="例如：演播室访谈" className="mt-1.5 w-full rounded-lg border border-white/10 bg-white/[.055] px-3 py-2 text-xs text-white outline-none focus:border-teal-400/50" /></label>
                <label className="mb-4 block text-xs text-slate-500">内容描述<textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={4} className="mt-1.5 w-full resize-y rounded-lg border border-white/10 bg-white/[.055] px-3 py-2 text-xs leading-5 text-white outline-none focus:border-teal-400/50" /></label>
              <div className="mb-2 flex items-center gap-2"><span className="rounded-md bg-teal-400/10 px-2 py-1 text-[11px] font-medium text-teal-300">{asset.scene || "未分类"}</span><span className="text-xs text-slate-500">{statusText[asset.status]}</span></div>
            </div>

            <div className="mb-6">
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">检索标签</h3>
              <div className="mb-3 grid grid-cols-2 gap-2">{tags.length ? tags.map((tag, index) => <div key={`tag-${index}`} className="flex min-w-0 rounded-lg border border-white/10 bg-white/[.04]"><input aria-label={`修改标签 ${index + 1}`} value={tag} onChange={(event) => renameTag(index, event.target.value)} className="min-w-0 flex-1 bg-transparent px-2 py-1.5 text-xs text-slate-300 outline-none" /><button type="button" aria-label={`删除标签 ${tag}`} onClick={() => removeTag(index)} className="px-2 text-red-300/70 hover:text-red-200">×</button></div>) : <span className="col-span-2 text-sm text-slate-600">暂无标签</span>}</div>
              <div className="flex gap-2"><input value={newTag} onChange={(event) => setNewTag(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); addTag(); } }} placeholder="添加自定义标签" className="min-w-0 flex-1 rounded-lg border border-white/10 bg-white/[.055] px-3 py-2 text-xs text-white outline-none" /><button type="button" onClick={addTag} disabled={!newTag.trim()} className="rounded-lg bg-teal-400/15 px-3 py-2 text-xs text-teal-300 disabled:opacity-40">添加</button></div>
              {editError && <p className="mt-2 text-xs text-red-300">{editError}</p>}
              <button type="button" onClick={saveMetadata} disabled={saving} className="mt-3 w-full rounded-lg bg-teal-400 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-teal-300 disabled:opacity-50">{saving ? "保存中…" : "保存全部修改"}</button>
            </div>

            {transcript && <details className="mb-6 rounded-lg border border-white/[.07] bg-white/[.025] p-3"><summary className="cursor-pointer text-xs font-semibold text-slate-400">ASR 语音转写</summary><p className="mt-3 max-h-44 overflow-y-auto whitespace-pre-wrap text-xs leading-5 text-slate-400">{transcript}</p></details>}

            <div>
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">技术信息</h3>
              <dl className="divide-y divide-white/[.06] border-y border-white/[.06]">{detailRows.map(([label, value]) => <div key={String(label)} className="flex justify-between gap-4 py-2.5 text-xs"><dt className="text-slate-500">{label}</dt><dd className="text-right text-slate-300">{value}</dd></div>)}</dl>
              {asset.source_page_url && <a href={asset.source_page_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex text-xs text-teal-300 hover:text-teal-200">查看素材原始页面 ↗</a>}
            </div>
            {FORMAT_EXPORT_ENABLED && asset.media_type !== "audio" && asset.status === "ready" && <button type="button" onClick={() => setExportOpen(true)} className="mt-6 w-full rounded-lg bg-teal-400 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-teal-300">选择比例并下载</button>}
            <button type="button" onClick={deleteAsset} className="mt-3 w-full rounded-lg border border-red-400/30 bg-red-500/10 px-4 py-2.5 text-sm font-medium text-red-300 transition hover:bg-red-500/20">删除素材</button>
          </aside>
        </div>
      </section>
      {exportOpen && <ExportEditor asset={asset} onClose={() => setExportOpen(false)} />}
    </div>
  );
}

type ExportRatio = "9:16" | "16:9" | "4:3" | "3:4";
type ExportMode = "smart" | "contain";

const exportPresets: Record<ExportRatio, Array<[number, number]>> = {
  "9:16": [[1080, 1920], [720, 1280]],
  "16:9": [[1920, 1080], [1280, 720]],
  "4:3": [[1600, 1200], [1024, 768]],
  "3:4": [[1200, 1600], [768, 1024]],
};

function ExportEditor({ asset, onClose }: { asset: Asset; onClose: () => void }) {
  const [ratio, setRatio] = useState<ExportRatio>("9:16");
  const [resolutionIndex, setResolutionIndex] = useState(0);
  const [mode, setMode] = useState<ExportMode>("smart");
  const [focusMode, setFocusMode] = useState<"auto" | "manual">("auto");
  const [focus, setFocus] = useState({ x: 0.5, y: 0.5 });
  const [zoom, setZoom] = useState(1);
  const [trackSubject, setTrackSubject] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [cacheMessage, setCacheMessage] = useState("");
  const [width, height] = exportPresets[ratio][resolutionIndex];

  function updateFocus(event: React.PointerEvent<HTMLDivElement>) {
    if (event.type === "pointermove" && event.buttons !== 1) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    const y = Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height));
    setFocus({ x, y });
    setFocusMode("manual");
  }

  async function downloadExport() {
    setExporting(true);
    setError("");
    setCacheMessage("");
    try {
      const response = await fetch(`${API}/assets/${asset.id}/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ratio, width, height, mode, focus_mode: focusMode,
          focus_x: focus.x, focus_y: focus.y, zoom,
          track_subject: asset.media_type === "video" && trackSubject,
        }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.detail || "导出失败");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const suffix = asset.media_type === "video" ? "mp4" : "jpg";
      anchor.href = url;
      anchor.download = `${asset.original_name.replace(/\.[^.]+$/, "")}_${ratio.replace(":", "x")}_${width}x${height}.${suffix}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setCacheMessage(response.headers.get("X-Export-Cache") === "hit" ? "已从缓存完成下载" : "导出完成，已加入缓存");
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : "导出失败");
    } finally {
      setExporting(false);
    }
  }

  const previewStyle: React.CSSProperties = mode === "contain"
    ? { objectFit: "contain", objectPosition: "center" }
    : { objectFit: "cover", objectPosition: `${focus.x * 100}% ${focus.y * 100}%`, transform: `scale(${zoom})` };

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/85 p-3 backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget && !exporting) onClose(); }}>
      <section role="dialog" aria-modal="true" aria-labelledby="export-editor-title" className="flex max-h-[95vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-white/15 bg-[#0f141b] shadow-2xl">
        <header className="flex items-center justify-between border-b border-white/10 px-5 py-4 sm:px-6">
          <div><div className="text-[10px] font-semibold uppercase text-teal-400">下载版本</div><h2 id="export-editor-title" className="mt-1 text-lg font-semibold text-white">裁剪与安全框预览</h2></div>
          <button type="button" onClick={onClose} disabled={exporting} aria-label="关闭导出编辑器" className="flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-xl text-slate-300 hover:bg-white/10 disabled:opacity-40">×</button>
        </header>
        <div className="grid min-h-0 flex-1 overflow-y-auto lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="flex min-h-[420px] items-center justify-center bg-black/35 p-5 sm:p-8">
            <div className="relative max-h-[68vh] w-full max-w-3xl touch-none overflow-hidden bg-black shadow-2xl" style={{ aspectRatio: `${width} / ${height}`, maxWidth: height > width ? "min(100%, 430px)" : "100%" }} onPointerDown={(event) => { event.currentTarget.setPointerCapture(event.pointerId); updateFocus(event); }} onPointerMove={updateFocus}>
              {asset.media_type === "image"
                ? <img src={absoluteUrl(asset.content_url)} alt="裁剪预览" draggable={false} className="pointer-events-none h-full w-full select-none transition-transform duration-150" style={previewStyle} />
                : <video src={absoluteUrl(asset.content_url)} poster={absoluteUrl(asset.thumbnail_url)} controls preload="metadata" className="h-full w-full bg-black transition-transform duration-150" style={previewStyle} />}
              <div className="pointer-events-none absolute inset-[7%] border border-dashed border-white/90 shadow-[0_0_0_999px_rgba(0,0,0,.12)]" aria-hidden="true" />
              <div className="pointer-events-none absolute inset-[7%] grid grid-cols-3 grid-rows-3 opacity-35" aria-hidden="true">{Array.from({ length: 9 }).map((_, index) => <span key={index} className="border border-white/35" />)}</div>
              {mode === "smart" && <div className="pointer-events-none absolute h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-teal-300 bg-teal-400/20 shadow" style={{ left: `${focus.x * 100}%`, top: `${focus.y * 100}%` }} />}
            </div>
          </div>
          <aside className="border-t border-white/10 p-5 lg:border-l lg:border-t-0 lg:p-6">
            <div className="mb-5"><div className="mb-2 text-xs font-medium text-slate-400">画面比例</div><div className="grid grid-cols-4 gap-2">{(Object.keys(exportPresets) as ExportRatio[]).map((value) => <button key={value} type="button" onClick={() => { setRatio(value); setResolutionIndex(0); }} className={`h-10 rounded-md border text-xs font-semibold ${ratio === value ? "border-teal-400 bg-teal-400/15 text-teal-300" : "border-white/10 text-slate-400 hover:bg-white/5"}`}>{value}</button>)}</div></div>
            <div className="mb-5"><div className="mb-2 text-xs font-medium text-slate-400">分辨率</div><div className="grid grid-cols-2 gap-2">{exportPresets[ratio].map(([presetWidth, presetHeight], index) => <button key={`${presetWidth}x${presetHeight}`} type="button" onClick={() => setResolutionIndex(index)} className={`h-10 rounded-md border text-xs ${resolutionIndex === index ? "border-teal-400 bg-teal-400/15 text-teal-300" : "border-white/10 text-slate-400 hover:bg-white/5"}`}>{presetWidth} × {presetHeight}</button>)}</div></div>
            <div className="mb-5"><div className="mb-2 text-xs font-medium text-slate-400">适配方式</div><div className="grid grid-cols-2 gap-2"><button type="button" onClick={() => setMode("smart")} className={`h-11 rounded-md border text-xs font-semibold ${mode === "smart" ? "border-teal-400 bg-teal-400/15 text-teal-300" : "border-white/10 text-slate-400"}`}>智能裁剪</button><button type="button" onClick={() => setMode("contain")} className={`h-11 rounded-md border text-xs font-semibold ${mode === "contain" ? "border-teal-400 bg-teal-400/15 text-teal-300" : "border-white/10 text-slate-400"}`}>完整显示</button></div></div>
            {mode === "smart" && <div className="mb-5 space-y-4 rounded-lg border border-white/10 bg-white/[.025] p-4">
              <div className="flex items-center justify-between"><span className="text-xs text-slate-400">焦点</span><button type="button" onClick={() => { setFocusMode("auto"); setFocus({ x: 0.5, y: 0.5 }); }} className={`rounded-md px-2.5 py-1 text-[11px] ${focusMode === "auto" ? "bg-teal-400/15 text-teal-300" : "bg-white/5 text-slate-400"}`}>{focusMode === "auto" ? "自动识别" : "恢复自动"}</button></div>
              <label className="block text-xs text-slate-400">缩放 {zoom.toFixed(1)}×<input type="range" min="1" max="3" step="0.1" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} className="mt-2 w-full accent-teal-400" /></label>
              {asset.media_type === "video" && <label className="flex cursor-pointer items-center justify-between gap-3 text-xs text-slate-400"><span>逐段动态跟踪</span><input type="checkbox" checked={trackSubject} onChange={(event) => setTrackSubject(event.target.checked)} className="h-4 w-4 accent-teal-400" /></label>}
            </div>}
            <div className="mb-5 rounded-lg border border-white/[.08] bg-black/20 px-3 py-2.5 text-[11px] leading-5 text-slate-500">虚线区域为安全框。拖动画面可改为手动焦点；完整显示会保留全部内容并使用黑色边缘填充。</div>
            {error && <p className="mb-3 text-xs text-red-300">{error}</p>}
            {cacheMessage && <p className="mb-3 text-xs text-emerald-300">{cacheMessage}</p>}
            <button type="button" disabled={exporting} onClick={downloadExport} className="flex h-12 w-full items-center justify-center rounded-md bg-teal-400 text-sm font-semibold text-slate-950 transition hover:bg-teal-300 disabled:cursor-wait disabled:opacity-60">{exporting ? (asset.media_type === "video" ? "正在逐段分析并导出…" : "正在生成下载版本…") : `下载 ${width} × ${height}`}</button>
          </aside>
        </div>
      </section>
    </div>
  );
}

function ExternalAssetBrowser({ onClose, onImported }: { onClose: () => void; onImported: (provider: ExternalProvider) => Promise<void> }) {
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState<ExternalProvider>("pexels");
  const [mediaType, setMediaType] = useState<"image" | "video">("image");
  const [items, setItems] = useState<ExternalAsset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [importingId, setImportingId] = useState<string | null>(null);
  const [importedIds, setImportedIds] = useState<string[]>([]);

  async function searchExternal(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ q: query.trim(), provider, media_type: mediaType, per_page: "12" });
      const response = await fetch(`${API}/external-assets/search?${params}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `${providerText[provider]} 搜索失败`);
      setItems(data.items || []);
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : `${providerText[provider]} 搜索失败`);
    } finally {
      setLoading(false);
    }
  }

  async function importAsset(item: ExternalAsset) {
    setImportingId(item.external_id);
    setError("");
    try {
      const response = await fetch(`${API}/external-assets/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: item.provider, external_id: item.external_id, media_type: item.media_type }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `${providerText[item.provider]} 素材导入失败`);
      setImportedIds((ids) => ids.includes(item.external_id) ? ids : [...ids, item.external_id]);
      await onImported(item.provider);
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : `${providerText[item.provider]} 素材导入失败`);
    } finally {
      setImportingId(null);
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/80 p-3 backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section role="dialog" aria-modal="true" aria-labelledby="external-assets-title" className="flex max-h-[94vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-white/15 bg-[#10151d] shadow-2xl">
        <header className="flex items-center justify-between border-b border-white/10 px-5 py-4 sm:px-6">
          <div><div className="text-[10px] font-semibold uppercase text-teal-400">外部素材</div><h2 id="external-assets-title" className="mt-1 text-lg font-semibold text-white">从素材平台导入</h2></div>
          <button type="button" onClick={onClose} aria-label="关闭外部素材窗口" className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5 text-xl text-slate-300 hover:bg-white/10">×</button>
        </header>
        <div className="flex gap-2 overflow-x-auto border-b border-white/10 px-5 pt-4 sm:px-6">{(Object.entries(providerText) as [ExternalProvider, string][]).map(([value, label]) => <button key={value} type="button" onClick={() => { setProvider(value); if (value === "unsplash" || value === "openverse") setMediaType("image"); if (value === "mixkit") setMediaType("video"); setItems([]); setError(""); }} className={`shrink-0 border-b-2 px-3 pb-3 text-sm font-medium transition ${provider === value ? "border-teal-400 text-white" : "border-transparent text-slate-500 hover:text-slate-300"}`}>{label}</button>)}</div>
        <form onSubmit={searchExternal} className="flex flex-col gap-3 border-b border-white/10 p-5 sm:flex-row sm:p-6">
          <div className="flex shrink-0 rounded-lg border border-white/10 bg-black/20 p-1">
            {([['image', '图片'], ['video', '视频']] as const).map(([value, label]) => <button key={value} type="button" disabled={((provider === "unsplash" || provider === "openverse") && value === "video") || (provider === "mixkit" && value === "image")} onClick={() => { setMediaType(value); setItems([]); }} className={`h-9 px-4 text-xs disabled:cursor-not-allowed disabled:opacity-30 ${mediaType === value ? "rounded-md bg-teal-400 text-slate-950" : "text-slate-400"}`}>{label}</button>)}
          </div>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={provider === "mixkit" ? "搜索 Mixkit，例如：city night、data center" : `搜索 ${providerText[provider]}，例如：城市夜景、数据中心`} className="min-w-0 flex-1 rounded-lg border border-white/10 bg-white/[.055] px-4 py-2.5 text-sm text-white outline-none placeholder:text-slate-600 focus:border-teal-400/60" />
          <button disabled={loading || !query.trim()} className="h-11 rounded-lg bg-teal-400 px-6 text-sm font-semibold text-slate-950 disabled:opacity-50">{loading ? "搜索中…" : "搜索"}</button>
        </form>
        {error && <div className="mx-5 mt-4 rounded-lg border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300 sm:mx-6">{error}</div>}
        <div className="min-h-64 flex-1 overflow-y-auto p-5 sm:p-6">
          {!loading && !items.length && <div className="flex min-h-56 items-center justify-center text-sm text-slate-500">输入关键词搜索 {providerText[provider]} {provider === "unsplash" || provider === "openverse" ? "图片" : "图片或视频"}</div>}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{items.map((item) => {
            const imported = importedIds.includes(item.external_id);
            const importing = importingId === item.external_id;
            return <article key={`${item.media_type}-${item.external_id}`} className="overflow-hidden rounded-lg border border-white/10 bg-white/[.035]">
              <a href={item.source_page_url} target="_blank" rel="noreferrer" className="block overflow-hidden bg-black/30" style={{ aspectRatio: item.width && item.height ? `${item.width} / ${item.height}` : "16 / 9" }}><img src={item.preview_url} alt={item.title} className="h-full w-full object-contain transition hover:scale-[1.02]" /></a>
              <div className="p-3"><h3 title={item.title} className="truncate text-sm font-medium text-white">{item.title}</h3><p className="mt-1 truncate text-xs text-slate-500">作者：{item.author || `${providerText[item.provider]} 创作者`}</p>{item.license && <p className="mt-1 truncate text-[11px] text-emerald-400">许可：{item.license}</p>}
                <button type="button" disabled={importing || imported || importingId !== null} onClick={() => importAsset(item)} className="mt-3 h-9 w-full rounded-md bg-teal-400/15 text-xs font-semibold text-teal-300 transition hover:bg-teal-400/25 disabled:opacity-50">{importing ? "正在下载…" : imported ? "已导入" : "导入素材库"}</button>
              </div>
            </article>;
          })}</div>
        </div>
        <footer className="border-t border-white/10 px-5 py-3 text-[11px] text-slate-500 sm:px-6">素材由 {providerText[provider]} 提供。导入前请确认其许可证适用于你的使用场景。</footer>
      </section>
    </div>
  );
}

function FredChartBuilder({ onClose, onCreated }: { onClose: () => void; onCreated: () => Promise<void> }) {
  const [series, setSeries] = useState<FredSeries[]>([]);
  const [seriesId, setSeriesId] = useState("CPIAUCSL");
  const [years, setYears] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/fred/series`, { cache: "no-store" })
      .then((response) => response.json())
      .then((data) => { if (!cancelled) setSeries(data.items || []); })
      .catch(() => { if (!cancelled) setError("无法加载 FRED 指标列表"); });
    return () => { cancelled = true; };
  }, []);

  async function generate(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setCreated(false);
    try {
      const response = await fetch(`${API}/fred/charts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ series_id: seriesId, years }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "FRED 图表生成失败");
      setCreated(true);
      await onCreated();
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : "FRED 图表生成失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section role="dialog" aria-modal="true" aria-labelledby="fred-chart-title" className="w-full max-w-2xl overflow-hidden rounded-xl border border-white/15 bg-[#10151d] shadow-2xl">
        <header className="flex items-center justify-between border-b border-white/10 px-5 py-4 sm:px-6"><div><div className="text-[10px] font-semibold uppercase text-teal-400">财经数据素材</div><h2 id="fred-chart-title" className="mt-1 text-lg font-semibold text-white">生成 FRED 财经图表</h2></div><button type="button" onClick={onClose} aria-label="关闭 FRED 图表窗口" className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5 text-xl text-slate-300 hover:bg-white/10">×</button></header>
        <form onSubmit={generate} className="p-5 sm:p-6">
          <label className="block text-xs text-slate-500">经济指标<select value={seriesId} onChange={(event) => setSeriesId(event.target.value)} className="mt-2 h-11 w-full rounded-lg border border-white/10 bg-[#171d26] px-3 text-sm text-white outline-none focus:border-teal-400/60">{series.map((item) => <option key={item.id} value={item.id}>{item.short} · {item.label}</option>)}</select></label>
          <div className="mt-5 text-xs text-slate-500">时间范围<div className="mt-2 grid grid-cols-4 gap-2">{[5, 10, 20, 30].map((value) => <button key={value} type="button" onClick={() => setYears(value)} className={`h-10 rounded-lg border text-sm ${years === value ? "border-teal-400/40 bg-teal-400/15 text-teal-300" : "border-white/10 text-slate-400 hover:bg-white/5"}`}>{value} 年</button>)}</div></div>
          <div className="mt-5 border-y border-white/[.07] py-4 text-xs leading-5 text-slate-500">生成 1600 × 900 PNG，自动保存到素材库并进行 AI 描述、分类和标签分析。数据来源及 FRED Series ID 会写入图片和素材详情。</div>
          {error && <div className="mt-4 rounded-lg border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}
          {created && <div className="mt-4 rounded-lg border border-emerald-400/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">图表已生成并加入素材库</div>}
          <button disabled={loading || !series.length} className="mt-5 h-11 w-full rounded-lg bg-teal-400 text-sm font-semibold text-slate-950 hover:bg-teal-300 disabled:opacity-50">{loading ? "正在获取数据并绘图…" : "生成并加入素材库"}</button>
        </form>
      </section>
    </div>
  );
}

function DeleteConfirm({ asset, deleting, onCancel, onConfirm }: { asset: Asset; deleting: boolean; onCancel: () => void; onConfirm: () => void }) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
      <section role="alertdialog" aria-modal="true" aria-labelledby="delete-title" className="w-full max-w-md rounded-2xl border border-red-300/20 bg-[#151921] p-6 shadow-2xl">
        <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-full bg-red-500/10 text-xl text-red-300">!</div>
        <h2 id="delete-title" className="text-lg font-semibold text-white">删除这项素材？</h2>
        <p className="mt-2 break-all text-sm leading-6 text-slate-400">“{asset.original_name}”的原始文件、缩略图和数据库记录都会被删除，此操作无法恢复。</p>
        <div className="mt-6 flex justify-end gap-3"><button type="button" disabled={deleting} onClick={onCancel} className="rounded-lg border border-white/10 px-4 py-2 text-sm text-slate-300 hover:bg-white/5">取消</button><button type="button" disabled={deleting} onClick={onConfirm} className="rounded-lg bg-red-500 px-4 py-2 text-sm font-semibold text-white hover:bg-red-400 disabled:opacity-50">{deleting ? "删除中…" : "确认删除"}</button></div>
      </section>
    </div>
  );
}
