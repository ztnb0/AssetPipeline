"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

type Status = "processing" | "ready" | "failed";
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
  created_at: string;
  content_url: string;
  thumbnail_url: string | null;
};

const statusText: Record<Status, string> = {
  processing: "AI 分析中",
  ready: "分析完成",
  failed: "处理失败",
};

function absoluteUrl(path: string | null) {
  if (!path) return "";
  return `${API.replace(/\/api$/, "")}${path}`;
}

function durationText(seconds: number | null) {
  if (seconds === null) return "";
  const rounded = Math.round(seconds);
  return `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, "0")}`;
}

const mediaText: Record<string, string> = { image: "图片", video: "视频", audio: "音频" };
const categoryOptions = ["科技", "财经", "民生", "教育", "商业", "文化", "娱乐", "体育", "医疗", "自然", "交通", "工业", "政务", "音频制作", "待内容识别", "其他"];

export default function Home() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [queryTerms, setQueryTerms] = useState<string[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Asset | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [typeFilter, setTypeFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const fileRef = useRef<HTMLInputElement>(null);

  const loadAssets = useCallback(async (q = "") => {
    try {
      const response = await fetch(`${API}/assets?q=${encodeURIComponent(q)}`, { cache: "no-store" });
      if (!response.ok) throw new Error("无法加载素材列表");
      const data = await response.json();
      setAssets(data.items);
      setQueryTerms(data.query_terms ?? []);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "请求失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAssets(); }, [loadAssets]);

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

  async function upload(file: File) {
    setUploading(true);
    setMessage("");
    const form = new FormData();
    form.append("file", file);
    try {
      const response = await fetch(`${API}/assets/upload`, { method: "POST", body: form });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail ?? "上传失败");
      }
      setMessage("上传成功，AI 正在理解画面…");
      await loadAssets(query);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "上传失败");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) upload(file);
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

  const visibleAssets = assets.filter((asset) =>
    (typeFilter === "all" || asset.media_type === typeFilter) &&
    (categoryFilter === "all" || (asset.categories?.length ? asset.categories : [asset.category || "其他"]).includes(categoryFilter))
  );
  const availableCategories = Array.from(new Set(assets.flatMap((asset) => asset.categories?.length ? asset.categories : [asset.category || "其他"]))).sort();

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
        <label className="inline-flex cursor-pointer items-center justify-center rounded-xl bg-teal-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-teal-300 has-[:disabled]:cursor-wait has-[:disabled]:opacity-60">
          {uploading ? "正在上传…" : "+ 上传素材"}
          <input ref={fileRef} disabled={uploading} onChange={onFileChange} type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/x-matroska,video/webm,audio/mpeg,audio/wav,audio/mp4,audio/flac,audio/ogg,.m4a,.mkv" className="sr-only" />
        </label>
      </header>

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
      {queryTerms.length > 1 && <div className="-mt-4 mb-6 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-600"><span>语义扩展：</span>{queryTerms.slice(1).map((term) => <span key={term} className="rounded-full border border-white/[.07] px-2 py-1 text-slate-500">{term}</span>)}</div>}

      <section className="mb-6 flex items-center gap-3 overflow-x-auto pb-1 text-xs">
        <span className="shrink-0 text-slate-600">题材分类</span>
        {["all", ...availableCategories].map((value) => <button key={value} type="button" onClick={() => setCategoryFilter(value)} className={`shrink-0 rounded-full border px-3 py-1.5 transition ${categoryFilter === value ? "border-teal-400/30 bg-teal-400/15 text-teal-300" : "border-white/10 bg-white/[.025] text-slate-500 hover:text-slate-300"}`}>{value === "all" ? "全部题材" : value}</button>)}
      </section>

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
          {Object.entries(visibleAssets.reduce<Record<string, Asset[]>>((groups, asset) => { const sections = categoryFilter === "all" ? (asset.categories?.length ? asset.categories : [asset.category || "其他"]) : [categoryFilter]; sections.forEach((section) => (groups[section] ||= []).push(asset)); return groups; }, {})).map(([section, sectionAssets]) => <section key={section}>
            <header className="mb-4 flex items-center justify-between border-b border-white/10 pb-3"><div><span className="text-[10px] font-semibold uppercase tracking-[.2em] text-teal-400">主题板块</span><h2 className="mt-1 text-lg font-semibold text-white">{section}</h2></div><span className="text-xs text-slate-500">{sectionAssets.length} 项素材</span></header>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {sectionAssets.map((asset) => (
            <article key={asset.id} role="button" tabIndex={0} aria-label={`查看 ${asset.original_name} 详情`} onClick={() => setSelectedAsset(asset)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setSelectedAsset(asset); }} className="cursor-pointer overflow-hidden rounded-2xl border border-white/10 bg-[#11161e]/90 shadow-2xl shadow-black/20 transition hover:-translate-y-0.5 hover:border-teal-400/30 focus:outline-none focus:ring-2 focus:ring-teal-400/60">
              <div className="relative aspect-video overflow-hidden bg-slate-900">
                {asset.media_type !== "audio" && (asset.thumbnail_url || asset.content_url) && <img src={absoluteUrl(asset.thumbnail_url || asset.content_url)} alt={asset.original_name} className="h-full w-full object-cover" />}
                {asset.media_type === "audio" && <div className="flex h-full items-center justify-center bg-gradient-to-br from-violet-950 to-slate-950"><div className="flex h-20 w-20 items-center justify-center rounded-full border border-violet-300/20 bg-violet-400/10 text-4xl text-violet-300">♫</div></div>}
                <div className="absolute left-3 top-3 rounded-md border border-white/10 bg-black/60 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-white/80 backdrop-blur">{mediaText[asset.media_type] ?? asset.media_type}</div>
                <div className={`absolute right-3 top-3 rounded-full border px-2.5 py-1 text-[11px] font-medium backdrop-blur ${asset.status === "ready" ? "border-emerald-300/30 bg-emerald-950/70 text-emerald-300" : asset.status === "failed" ? "border-red-300/30 bg-red-950/70 text-red-300" : "border-amber-300/30 bg-amber-950/70 text-amber-200"}`}>{statusText[asset.status]}</div>
                <button type="button" aria-label={`删除 ${asset.original_name}`} onClick={(event) => { event.stopPropagation(); setDeleteTarget(asset); }} className="absolute bottom-2.5 right-2.5 flex h-8 w-8 items-center justify-center rounded-lg border border-red-300/20 bg-black/65 text-sm text-red-300 opacity-80 backdrop-blur transition hover:bg-red-500/25 hover:opacity-100">⌫</button>
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
              </div>
            </article>
          ))}
            </div>
          </section>)}
        </div>
      )}

      {selectedAsset && <AssetDetail asset={selectedAsset} onClose={() => setSelectedAsset(null)} onSaved={(next) => { setSelectedAsset(next); setAssets((items) => items.map((item) => item.id === next.id ? next : item)); }} onDeleted={(id) => { setSelectedAsset(null); setAssets((items) => items.filter((item) => item.id !== id)); }} />}
      {deleteTarget && <DeleteConfirm asset={deleteTarget} deleting={deleting} onCancel={() => setDeleteTarget(null)} onConfirm={confirmDelete} />}
    </main>
  );
}

function AssetDetail({ asset, onClose, onSaved, onDeleted }: { asset: Asset; onClose: () => void; onSaved: (asset: Asset) => void; onDeleted: (id: string) => void }) {
  const [tags, setTags] = useState(asset.tags);
  const [newTag, setNewTag] = useState("");
  const [categories, setCategories] = useState(asset.categories?.length ? asset.categories : [asset.category || "其他"]);
  const [scene, setScene] = useState(asset.scene || "");
  const [description, setDescription] = useState(asset.description || "");
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState("");
  async function saveMetadata() {
    setSaving(true);
    setEditError("");
    try {
      const cleanedTags = Array.from(new Set(tags.map((tag) => tag.trim()).filter(Boolean)));
      const response = await fetch(`${API}/assets/${asset.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tags: cleanedTags, categories, scene, description }) });
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
            </div>
            <button type="button" onClick={deleteAsset} className="mt-6 w-full rounded-lg border border-red-400/30 bg-red-500/10 px-4 py-2.5 text-sm font-medium text-red-300 transition hover:bg-red-500/20">删除素材</button>
          </aside>
        </div>
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
