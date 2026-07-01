import { ChangeEvent, DragEvent, FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Archive,
  ArrowDownToLine,
  Copy,
  FileText,
  Image,
  Loader2,
  LockKeyhole,
  Plus,
  RefreshCcw,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { apiBaseUrl, assetDownloadUrl, assetFileUrl, listAssets, uploadAsset, verifyInvite } from "./api";
import type { Asset, AssetKind, Session } from "./types";

const defaultInvite = import.meta.env.VITE_DEFAULT_INVITE ?? "";

const sampleAssets: Asset[] = [
  {
    id: "sample-brief",
    filename: "sample-brief.txt",
    originalName: "today-note.txt",
    mimeType: "text/plain",
    size: 1240,
    uploadedAt: new Date(Date.now() - 1000 * 60 * 22).toISOString(),
    sourceName: "Mira",
    note: "内网临时要用的说明文本",
    url: "",
    downloadUrl: "",
  },
  {
    id: "sample-image",
    filename: "sample-image.png",
    originalName: "desk-reference.png",
    mimeType: "image/png",
    size: 814000,
    uploadedAt: new Date(Date.now() - 1000 * 60 * 80).toISOString(),
    sourceName: "Anzi",
    note: "视觉参考图",
    width: 1200,
    height: 760,
    url: "",
    downloadUrl: "",
  },
  {
    id: "sample-pack",
    filename: "sample-pack.zip",
    originalName: "handoff-assets.zip",
    mimeType: "application/zip",
    size: 4381000,
    uploadedAt: new Date(Date.now() - 1000 * 60 * 260).toISOString(),
    sourceName: "Gate",
    note: "脚本和配置备份",
    url: "",
    downloadUrl: "",
  },
  {
    id: "sample-pdf",
    filename: "sample-pdf.pdf",
    originalName: "handoff-brief.pdf",
    mimeType: "application/pdf",
    size: 289000,
    uploadedAt: new Date(Date.now() - 1000 * 60 * 410).toISOString(),
    sourceName: "Office",
    note: "只读邀请码要下载的说明书",
    url: "",
    downloadUrl: "",
  },
  {
    id: "sample-copy",
    filename: "sample-copy.txt",
    originalName: "proxy-list.txt",
    mimeType: "text/plain",
    size: 920,
    uploadedAt: new Date(Date.now() - 1000 * 60 * 620).toISOString(),
    sourceName: "Gate",
    note: "一些需要复制进内网的短文本",
    url: "",
    downloadUrl: "",
  },
  {
    id: "sample-scan",
    filename: "sample-scan.png",
    originalName: "whiteboard-scan.png",
    mimeType: "image/png",
    size: 1411000,
    uploadedAt: new Date(Date.now() - 1000 * 60 * 740).toISOString(),
    sourceName: "Mira",
    note: "会后白板照片",
    width: 1600,
    height: 1100,
    url: "",
    downloadUrl: "",
  },
];

function assetKind(asset: Asset): AssetKind {
  if (asset.mimeType.startsWith("image/")) return "image";
  if (asset.mimeType.startsWith("text/")) return "text";
  if (asset.mimeType === "application/pdf") return "pdf";
  if (
    asset.mimeType.includes("zip") ||
    asset.mimeType.includes("rar") ||
    asset.mimeType.includes("tar") ||
    asset.originalName.match(/\.(zip|rar|7z|tar|gz)$/i)
  ) {
    return "archive";
  }
  return "file";
}

function kindLabel(kind: AssetKind): string {
  const labels: Record<AssetKind, string> = {
    image: "Image",
    text: "Text",
    archive: "Archive",
    pdf: "PDF",
    file: "File",
  };
  return labels[kind];
}

function KindIcon({ kind }: { kind: AssetKind }) {
  const icons = {
    image: Image,
    text: FileText,
    archive: Archive,
    pdf: FileText,
    file: FileText,
  };
  const Icon = icons[kind];
  return <Icon aria-hidden="true" size={18} strokeWidth={1.9} />;
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  const units = ["KB", "MB", "GB"];
  let value = size / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value >= 100 ? 0 : 1)} ${units[unitIndex]}`;
}

function formatTime(iso: string): string {
  const formatter = new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  return formatter.format(new Date(iso));
}

function useAssetFeed(invite: string, hasSession: boolean) {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!hasSession || !invite) return;
    setLoading(true);
    setError("");
    try {
      const nextAssets = await listAssets(invite);
      setAssets(nextAssets);
    } catch (error) {
      setError(error instanceof Error ? error.message : "列表加载失败");
    } finally {
      setLoading(false);
    }
  }, [hasSession, invite]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { assets, setAssets, loading, error, refresh };
}

export function App() {
  const [invite, setInvite] = useState(defaultInvite);
  const [session, setSession] = useState<Session | null>(null);
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [note, setNote] = useState("");
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const { assets, setAssets, loading, error, refresh } = useAssetFeed(invite, Boolean(session));

  const visibleAssets = useMemo(() => {
    const feed = session ? assets : sampleAssets;
    if (!query.trim()) return feed;
    const needle = query.trim().toLowerCase();
    return feed.filter((asset) =>
      [asset.originalName, asset.sourceName, asset.note, asset.mimeType]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(needle)),
    );
  }, [assets, query, session]);

  const sourceNames = useMemo(
    () => Array.from(new Set(visibleAssets.map((asset) => asset.sourceName))).slice(0, 4),
    [visibleAssets],
  );

  const handleAuth = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!invite.trim()) {
      setAuthError("需要邀请码");
      return;
    }
    setAuthLoading(true);
    setAuthError("");
    try {
      const nextSession = await verifyInvite(invite.trim());
      setSession(nextSession);
      setInvite(invite.trim());
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "邀请码不可用");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleUploadFiles = async (files: FileList | File[]) => {
    if (!session || session.role !== "upload") return;

    const queue = Array.from(files);
    if (queue.length === 0) return;

    setUploading(true);
    setUploadError("");
    try {
      const uploaded: Asset[] = [];
      for (const file of queue) {
        uploaded.push(await uploadAsset(invite, file, note));
      }
      setAssets((current) => [...uploaded, ...current]);
      setNote("");
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "上传失败");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleTextUpload = async () => {
    if (!session || session.role !== "upload" || !note.trim()) return;
    const file = new File([note.trim()], `nospace-note-${Date.now()}.txt`, {
      type: "text/plain",
    });
    await handleUploadFiles([file]);
  };

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragging(false);
    void handleUploadFiles(event.dataTransfer.files);
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      void handleUploadFiles(event.target.files);
    }
  };

  const copyLink = async (asset: Asset) => {
    if (!session || !asset.downloadUrl) return;
    await navigator.clipboard.writeText(assetDownloadUrl(asset, invite));
  };

  const canUpload = session?.role === "upload";
  const hasRealAssets = session && visibleAssets.length > 0;

  return (
    <main className="page-shell">
      <section className="top-strip" aria-label="访问控制">
        <div className="brand-block">
          <div className="mark" aria-hidden="true">
            ns
          </div>
          <div>
            <h1>NoSpace</h1>
            <p>邀请访问的轻量内容交换画布</p>
          </div>
        </div>

        <form className="invite-form" onSubmit={handleAuth}>
          <label>
            <span>Invite</span>
            <input
              value={invite}
              onChange={(event) => setInvite(event.target.value)}
              placeholder="输入邀请码"
              type="password"
              autoComplete="off"
            />
          </label>
          <button type="submit" disabled={authLoading}>
            {authLoading ? <Loader2 className="spin" size={17} /> : <LockKeyhole size={17} />}
            <span>{session ? "切换" : "进入"}</span>
          </button>
        </form>
      </section>

      {authError && <div className="notice error">{authError}</div>}

      <section className="canvas-board" aria-label="内容画布">
        <div className="board-toolbar">
          <div className="session-pill">
            {session ? <ShieldCheck size={17} /> : <Sparkles size={17} />}
            <span>
              {session
                ? `${session.name} · ${session.role === "upload" ? "可上传" : "仅下载"}`
                : "预览模式"}
            </span>
          </div>

          <div className="tool-cluster">
            <label className="search-box">
              <Search size={16} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="按文件、来源、备注搜索"
              />
            </label>
            <button className="icon-button" onClick={() => void refresh()} disabled={!session || loading}>
              <RefreshCcw className={loading ? "spin" : ""} size={17} />
              <span className="sr-only">刷新</span>
            </button>
          </div>
        </div>

        <div className="ambient-stack" aria-hidden="true">
          <div className="ghost-card ghost-card-a" />
          <div className="ghost-card ghost-card-b" />
          <div className="ghost-card ghost-card-c" />
        </div>

        <div className="masonry">
          {canUpload && (
            <article className="upload-tile">
              <label
                className={dragging ? "drop-zone dragging" : "drop-zone"}
                onDragEnter={(event) => {
                  event.preventDefault();
                  setDragging(true);
                }}
                onDragOver={(event) => event.preventDefault()}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
              >
                <input ref={fileInputRef} type="file" multiple onChange={handleFileChange} />
                <span className="upload-symbol">{uploading ? <Loader2 className="spin" /> : <Plus />}</span>
                <strong>{uploading ? "上传中" : "拖入或选择文件"}</strong>
                <small>图片、文本、PDF、压缩包都可以</small>
              </label>
              <textarea
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="粘贴文字，或给这批文件留一句备注"
                rows={3}
              />
              <button className="text-upload-button" onClick={() => void handleTextUpload()} disabled={!note.trim() || uploading}>
                {uploading ? <Loader2 className="spin" size={16} /> : <FileText size={16} />}
                <span>存为文本</span>
              </button>
              {uploadError && <p className="tile-error">{uploadError}</p>}
            </article>
          )}

          {!session && <IntroTile apiBaseUrl={apiBaseUrl} />}

          {visibleAssets.map((asset, index) => (
            <AssetCard
              key={asset.id}
              asset={asset}
              index={index}
              invite={invite}
              isPreview={!session}
              onCopy={() => void copyLink(asset)}
            />
          ))}
        </div>

        {session && !loading && !hasRealAssets && (
          <div className="empty-state">
            <Upload size={20} />
            <p>{canUpload ? "还没有内容，先把第一份文件放上来。" : "这里还没有可下载内容。"}</p>
          </div>
        )}

        {error && <div className="notice error">{error}</div>}

        <footer className="board-footer">
          <span>{visibleAssets.length} items</span>
          <span>{sourceNames.length ? `from ${sourceNames.join(", ")}` : "quiet canvas"}</span>
        </footer>
      </section>
    </main>
  );
}

function IntroTile({ apiBaseUrl }: { apiBaseUrl: string }) {
  return (
    <article className="intro-tile">
      <span className="eyebrow">Simple relay</span>
      <h2>把外网内容临时放到一个清楚的地方。</h2>
      <p>
        静态页面负责呈现和交互，Hugging Face Space 负责鉴权与文件存储。下载邀请码只能看和取，上传邀请码才能写入。
      </p>
      <code>{apiBaseUrl}</code>
    </article>
  );
}

function AssetCard({
  asset,
  index,
  invite,
  isPreview,
  onCopy,
}: {
  asset: Asset;
  index: number;
  invite: string;
  isPreview: boolean;
  onCopy: () => void;
}) {
  const kind = assetKind(asset);
  const downloadUrl = isPreview || !asset.downloadUrl ? "#" : assetDownloadUrl(asset, invite);
  const isImage = kind === "image" && asset.url;
  const previewUrl = isImage && !isPreview ? assetFileUrl(asset, invite) : asset.url;
  const toneClass = `asset-card tone-${index % 5}`;

  return (
    <article className={toneClass}>
      <div className="asset-meta">
        <span className="kind-badge">
          <KindIcon kind={kind} />
          {kindLabel(kind)}
        </span>
        <span>{formatTime(asset.uploadedAt)}</span>
      </div>

      <div className={isImage ? "asset-preview image-preview" : "asset-preview file-preview"}>
        {isImage ? (
          <img src={previewUrl} alt={asset.originalName} loading="lazy" />
        ) : (
          <div className="file-symbol">
            <KindIcon kind={kind} />
          </div>
        )}
      </div>

      <div className="asset-body">
        <h3>{asset.originalName}</h3>
        {asset.note && <p>{asset.note}</p>}
      </div>

      <div className="asset-footer">
        <div>
          <span className="source-dot" />
          <strong>{asset.sourceName}</strong>
          <small>{formatBytes(asset.size)}</small>
        </div>
        <div className="card-actions">
          {!isPreview && (
            <button className="icon-button small" onClick={onCopy} title="复制下载链接">
              <Copy size={15} />
              <span className="sr-only">复制下载链接</span>
            </button>
          )}
          <a
            className={isPreview ? "download-link disabled" : "download-link"}
            href={downloadUrl}
            aria-disabled={isPreview}
          >
            {isPreview ? <X size={15} /> : <ArrowDownToLine size={15} />}
            <span>{isPreview ? "Locked" : "Get"}</span>
          </a>
        </div>
      </div>
    </article>
  );
}
