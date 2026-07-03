import { ChangeEvent, DragEvent, FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDownToLine,
  Copy,
  FileText,
  Loader2,
  LockKeyhole,
  Plus,
  RefreshCcw,
  Search,
  ShieldCheck,
  Trash2,
  Upload,
} from "lucide-react";
import { assetDownloadUrl, assetFileUrl, deleteAsset, listAssets, uploadAsset, verifyInvite } from "./api";
import type { Asset, AssetKind, Session } from "./types";

const defaultInvite = import.meta.env.VITE_DEFAULT_INVITE ?? "";
const inviteStorageKey = "nospace:invite";
const sessionStorageKey = "nospace:session";

function savedInvite(): string {
  if (typeof window === "undefined") return defaultInvite;
  return window.localStorage.getItem(inviteStorageKey) || defaultInvite;
}

function savedSession(): Session | null {
  if (typeof window === "undefined" || !savedInvite()) return null;
  const rawSession = window.localStorage.getItem(sessionStorageKey);
  if (!rawSession) return null;

  try {
    const session = JSON.parse(rawSession) as Partial<Session>;
    if ((session.role === "upload" || session.role === "download") && typeof session.name === "string") {
      return { role: session.role, name: session.name };
    }
  } catch {
    window.localStorage.removeItem(sessionStorageKey);
    return null;
  }

  window.localStorage.removeItem(sessionStorageKey);
  return null;
}

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

function displaySourceName(sourceName: string): string {
  return sourceName === "Anzi" || sourceName === "IP" ? "旧记录" : sourceName;
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
  const [invite, setInvite] = useState(savedInvite);
  const [session, setSession] = useState<Session | null>(savedSession);
  const [authRestoring, setAuthRestoring] = useState(() => Boolean(savedInvite()) && !savedSession());
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [note, setNote] = useState("");
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [deletingId, setDeletingId] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const { assets, setAssets, loading, error, refresh } = useAssetFeed(invite, Boolean(session));

  const signIn = useCallback(async (nextInvite: string, silent = false) => {
    const trimmedInvite = nextInvite.trim();
    if (!trimmedInvite) {
      setAuthError("需要邀请码");
      return;
    }

    setAuthLoading(true);
    if (!silent) setAuthError("");
    try {
      const nextSession = await verifyInvite(trimmedInvite);
      setSession(nextSession);
      setInvite(trimmedInvite);
      window.localStorage.setItem(inviteStorageKey, trimmedInvite);
      window.localStorage.setItem(sessionStorageKey, JSON.stringify(nextSession));
      setAuthError("");
    } catch (error) {
      setSession(null);
      window.localStorage.removeItem(inviteStorageKey);
      window.localStorage.removeItem(sessionStorageKey);
      if (!silent) {
        setAuthError(error instanceof Error ? error.message : "邀请码不可用");
      }
    } finally {
      setAuthLoading(false);
    }
  }, []);

  useEffect(() => {
    const storedInvite = savedInvite();
    if (storedInvite) {
      void signIn(storedInvite, true).finally(() => setAuthRestoring(false));
    } else {
      setAuthRestoring(false);
    }
  }, [signIn]);

  const visibleAssets = useMemo(() => {
    const feed = session ? assets : [];
    if (!query.trim()) return feed;
    const needle = query.trim().toLowerCase();
    return feed.filter((asset) =>
      [asset.originalName, displaySourceName(asset.sourceName), asset.sourceName, asset.note, asset.mimeType]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(needle)),
    );
  }, [assets, query, session]);

  const handleAuth = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await signIn(invite);
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

  const handleDeleteAsset = async (asset: Asset) => {
    if (!session || session.role !== "upload" || deletingId) return;
    const confirmed = window.confirm(`删除 ${asset.originalName}？`);
    if (!confirmed) return;

    setDeletingId(asset.id);
    setActionError("");
    try {
      await deleteAsset(invite, asset.id);
      setAssets((current) => current.filter((item) => item.id !== asset.id));
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "删除失败");
    } finally {
      setDeletingId("");
    }
  };

  const canUpload = session?.role === "upload";
  const hasRealAssets = session && visibleAssets.length > 0;

  if (authRestoring) {
    return (
      <main className="login-shell">
        <div className="login-panel restore-panel" aria-live="polite">
          <h1>NoSpace</h1>
          <div className="restore-indicator">
            <Loader2 className="spin" size={16} />
            <span>恢复中</span>
          </div>
        </div>
      </main>
    );
  }

  if (!session) {
    return (
      <main className="login-shell">
        <form className="login-panel" onSubmit={handleAuth} aria-label="邀请码登录">
          <h1>NoSpace</h1>
          <div className="login-invite">
            <input
              value={invite}
              onChange={(event) => setInvite(event.target.value)}
              placeholder="邀请码"
              type="password"
              autoComplete="off"
              aria-label="邀请码"
            />
            <button type="submit" disabled={authLoading}>
              {authLoading ? <Loader2 className="spin" size={17} /> : <LockKeyhole size={17} />}
              <span>进入</span>
            </button>
          </div>
          {authError && <p className="login-error">{authError}</p>}
        </form>
      </main>
    );
  }

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
            <span>切换</span>
          </button>
        </form>
      </section>

      {authError && <div className="notice error">{authError}</div>}

      <section className="canvas-board" aria-label="内容画布">
        <div className="board-toolbar">
          <div className="session-pill">
            <ShieldCheck size={17} />
            <span>{`${session.name} · ${session.role === "upload" ? "可上传" : "仅下载"}`}</span>
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
          {visibleAssets.map((asset, index) => (
            <AssetCard
              key={asset.id}
              asset={asset}
              index={index}
              invite={invite}
              canDelete={canUpload}
              deleting={deletingId === asset.id}
              onCopy={() => void copyLink(asset)}
              onDelete={() => void handleDeleteAsset(asset)}
            />
          ))}
        </div>

        {!loading && !hasRealAssets && (
          <div className="empty-state">
            <Upload size={20} />
            <p>{canUpload ? "还没有内容，先把第一份文件放上来。" : "这里还没有可下载内容。"}</p>
          </div>
        )}

        {error && <div className="notice error">{error}</div>}
        {actionError && <div className="notice error">{actionError}</div>}

      </section>
    </main>
  );
}

function AssetCard({
  asset,
  index,
  invite,
  canDelete,
  deleting,
  onCopy,
  onDelete,
}: {
  asset: Asset;
  index: number;
  invite: string;
  canDelete: boolean;
  deleting: boolean;
  onCopy: () => void;
  onDelete: () => void;
}) {
  const kind = assetKind(asset);
  const downloadUrl = asset.downloadUrl ? assetDownloadUrl(asset, invite) : "#";
  const isImage = kind === "image" && asset.url;
  const isText = kind === "text";
  const previewUrl = isImage ? assetFileUrl(asset, invite) : asset.url;
  const toneClass = `asset-card tone-${index % 5}`;

  return (
    <article className={toneClass}>
      <div className="asset-meta">
        <span className="asset-name" title={asset.originalName}>
          {asset.originalName}
        </span>
        <time dateTime={asset.uploadedAt}>{formatTime(asset.uploadedAt)}</time>
      </div>

      {isImage && (
        <div className="asset-preview image-preview">
          <img src={previewUrl} alt={asset.originalName} loading="lazy" />
        </div>
      )}

      {isText ? <TextPreview asset={asset} invite={invite} /> : asset.note && <p className="asset-note">{asset.note}</p>}

      <div className="asset-footer">
        <div>
          <span className="source-dot" />
          <strong>{displaySourceName(asset.sourceName)}</strong>
          <small>{formatBytes(asset.size)}</small>
        </div>
        <div className="card-actions">
          <button className="icon-button small" onClick={onCopy} title="复制下载链接">
            <Copy size={15} />
            <span className="sr-only">复制下载链接</span>
          </button>
          {canDelete && (
            <button className="icon-button small danger" onClick={onDelete} disabled={deleting} title="删除资产">
              {deleting ? <Loader2 className="spin" size={15} /> : <Trash2 size={15} />}
              <span className="sr-only">删除资产</span>
            </button>
          )}
          <a className="download-link" href={downloadUrl}>
            <ArrowDownToLine size={15} />
            <span>Get</span>
          </a>
        </div>
      </div>
    </article>
  );
}

function TextPreview({ asset, invite }: { asset: Asset; invite: string }) {
  const [content, setContent] = useState(asset.note || "");

  useEffect(() => {
    let ignored = false;
    if (!asset.url) {
      setContent(asset.note || "");
      return () => {
        ignored = true;
      };
    }

    fetch(assetFileUrl(asset, invite))
      .then((response) => (response.ok ? response.text() : ""))
      .then((text) => {
        if (!ignored) setContent((text || asset.note || "").slice(0, 1600));
      })
      .catch(() => {
        if (!ignored) setContent(asset.note || "");
      });

    return () => {
      ignored = true;
    };
  }, [asset, invite]);

  return <pre className="text-preview">{content || "空文本"}</pre>;
}
