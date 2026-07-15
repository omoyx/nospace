import { ChangeEvent, DragEvent, FormEvent, ReactNode, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
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
import { assetDownloadUrl, assetFileUrl, deleteAsset, listAssets, maxUploadBytes, maxUploadMb, uploadAsset, verifyInvite } from "./api";
import type { Asset, AssetKind, Session } from "./types";

const defaultInvite = import.meta.env.VITE_DEFAULT_INVITE ?? "";
const inviteStorageKey = "nospace:invite";
const sessionStorageKey = "nospace:session";
const assetRefreshIntervalMs = 60_000;

type UploadPlaceholderStatus = "waiting" | "uploading" | "processing" | "error";

type UploadPlaceholder = {
  id: string;
  name: string;
  size: number;
  progress: number;
  status: UploadPlaceholderStatus;
  error?: string;
};

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

function assetDisplayName(asset: Asset): string {
  return asset.displayName || asset.originalName;
}

function uploadPlaceholderId(file: File, index: number): string {
  return `upload-${Date.now()}-${index}-${file.name}`;
}

function uploadStatusLabel(status: UploadPlaceholderStatus): string {
  if (status === "waiting") return "等待中";
  if (status === "processing") return "处理中";
  if (status === "error") return "失败";
  return "上传中";
}

function splitFileName(name: string): { base: string; extension: string } {
  const extensionStart = name.lastIndexOf(".");
  if (extensionStart <= 0 || extensionStart === name.length - 1) {
    return { base: name, extension: "" };
  }

  return {
    base: name.slice(0, extensionStart),
    extension: name.slice(extensionStart),
  };
}

function FileName({ name }: { name: string }) {
  const { base, extension } = splitFileName(name);

  return (
    <span className="asset-name" title={name}>
      <span className="asset-name-base">{base}</span>
      {extension && <span className="asset-name-extension">{extension}</span>}
    </span>
  );
}

function Masonry({ children }: { children: ReactNode }) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let frameId = 0;

    const layout = () => {
      const items = Array.from(container.children) as HTMLElement[];
      const width = container.clientWidth;
      if (width === 0) return;

      const styles = window.getComputedStyle(container);
      const gap = Number.parseFloat(styles.columnGap) || 0;
      const tileMinValue = styles.getPropertyValue("--tile-min").trim();
      const parsedTileMin = Number.parseFloat(tileMinValue) || width;
      const tileMin = tileMinValue.endsWith("%") ? width * (parsedTileMin / 100) : parsedTileMin;
      const columnCount = Math.max(1, Math.floor((width + gap) / (tileMin + gap)));
      const itemWidth = (width - gap * (columnCount - 1)) / columnCount;
      const columnHeights = Array<number>(columnCount).fill(0);

      container.classList.add("is-packed");
      items.forEach((item) => {
        item.style.width = `${itemWidth}px`;
      });

      items.forEach((item) => {
        const shortestColumn = columnHeights.indexOf(Math.min(...columnHeights));
        const x = shortestColumn * (itemWidth + gap);
        const y = columnHeights[shortestColumn];

        item.style.transform = `translate3d(${x}px, ${y}px, 0)`;
        columnHeights[shortestColumn] = y + item.offsetHeight + gap;
      });

      const height = Math.max(0, ...columnHeights) - (items.length > 0 ? gap : 0);
      container.style.height = `${height}px`;
    };

    const scheduleLayout = () => {
      window.cancelAnimationFrame(frameId);
      frameId = window.requestAnimationFrame(layout);
    };

    layout();

    const observer = new ResizeObserver(scheduleLayout);
    observer.observe(container);
    Array.from(container.children).forEach((item) => observer.observe(item));

    return () => {
      window.cancelAnimationFrame(frameId);
      observer.disconnect();
    };
  }, [children]);

  return (
    <div className="masonry" ref={containerRef}>
      {children}
    </div>
  );
}

function uploadLimitError(file: File): string {
  return `${file.name} 是 ${formatBytes(file.size)}，超过 ${maxUploadMb} MB 上限`;
}

function batchUploadLimitError(files: File[]): string {
  if (files.length === 1) return `${uploadLimitError(files[0])}，请压缩或拆分后再上传。`;
  return `${files.length} 个文件超过 ${maxUploadMb} MB 上限，已跳过。`;
}

function isFileDrag(event: DragEvent<HTMLElement>): boolean {
  return Array.from(event.dataTransfer.types).includes("Files");
}

function useAssetFeed(invite: string, hasSession: boolean) {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async (options: { silent?: boolean } = {}) => {
    if (!hasSession || !invite) return;
    if (!options.silent) setLoading(true);
    setError("");
    try {
      const nextAssets = await listAssets(invite);
      setAssets(nextAssets);
    } catch (error) {
      setError(error instanceof Error ? error.message : "列表加载失败");
    } finally {
      if (!options.silent) setLoading(false);
    }
  }, [hasSession, invite]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!hasSession || !invite) return;

    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") {
        void refresh({ silent: true });
      }
    };

    const intervalId = window.setInterval(refreshWhenVisible, assetRefreshIntervalMs);
    document.addEventListener("visibilitychange", refreshWhenVisible);

    return () => {
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, [hasSession, invite, refresh]);

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
  const [dragOverlayExiting, setDragOverlayExiting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadItems, setUploadItems] = useState<UploadPlaceholder[]>([]);
  const [uploadError, setUploadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [deletingId, setDeletingId] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Asset | null>(null);
  const [deleteError, setDeleteError] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const dragDepthRef = useRef(0);
  const dragOverlayTimerRef = useRef<number | null>(null);

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
      [assetDisplayName(asset), asset.originalName, displaySourceName(asset.sourceName), asset.sourceName, asset.note, asset.mimeType]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(needle)),
    );
  }, [assets, query, session]);

  const canUpload = session?.role === "upload";
  const hasRealAssets = session && visibleAssets.length > 0;
  const hasVisibleContent = hasRealAssets || uploadItems.length > 0;
  const showDragOverlay = dragging || dragOverlayExiting;
  const canvasClassName = ["canvas-board", dragging ? "drop-active" : ""].filter(Boolean).join(" ");
  const dragOverlayClassName = dragging ? "drag-overlay is-active" : "drag-overlay is-leaving";

  const clearDragOverlayTimer = () => {
    if (dragOverlayTimerRef.current !== null) {
      window.clearTimeout(dragOverlayTimerRef.current);
      dragOverlayTimerRef.current = null;
    }
  };

  const openDragOverlay = () => {
    clearDragOverlayTimer();
    setDragOverlayExiting(false);
    setDragging(true);
  };

  const closeDragOverlay = () => {
    clearDragOverlayTimer();
    setDragging(false);
    setDragOverlayExiting(true);
    dragOverlayTimerRef.current = window.setTimeout(() => {
      setDragOverlayExiting(false);
      dragOverlayTimerRef.current = null;
    }, 240);
  };

  useEffect(() => {
    return () => {
      if (dragOverlayTimerRef.current !== null) {
        window.clearTimeout(dragOverlayTimerRef.current);
      }
    };
  }, []);

  const handleAuth = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await signIn(invite);
  };

  const handleUploadFiles = async (files: FileList | File[]) => {
    if (!session || session.role !== "upload") return;

    const queue = Array.from(files);
    if (queue.length === 0) return;

    const queuedItems = queue.map((file, index) => ({
      file,
      placeholder: {
        id: uploadPlaceholderId(file, index),
        name: file.name,
        size: file.size,
        progress: 0,
        status: "waiting" as const,
      },
    }));
    const rejectedBatch = queuedItems.map(({ file, placeholder }) => ({
      file,
      placeholder: {
        ...placeholder,
        status: "error" as const,
        error: uploadLimitError(file),
      },
    })).filter(({ file }) => file.size > maxUploadBytes);
    const batch = queuedItems.filter(({ file }) => file.size <= maxUploadBytes);
    const rejectedIds = new Set(rejectedBatch.map(({ placeholder }) => placeholder.id));

    if (rejectedBatch.length > 0) {
      setUploadError(batchUploadLimitError(rejectedBatch.map(({ file }) => file)));
      setUploadItems((current) => [
        ...rejectedBatch.map(({ placeholder }) => placeholder),
        ...current.filter((item) => item.status !== "error"),
      ]);
      window.setTimeout(() => {
        setUploadItems((current) => current.filter((item) => !rejectedIds.has(item.id)));
      }, 7000);
    }

    if (batch.length === 0) {
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    const batchIds = new Set(batch.map(({ placeholder }) => placeholder.id));
    const failedIds = new Set<string>();
    const noteForUpload = note;

    setUploading(true);
    if (rejectedBatch.length === 0) setUploadError("");
    setUploadItems((current) => [
      ...batch.map(({ placeholder }) => placeholder),
      ...current.filter((item) => item.status !== "error" || rejectedIds.has(item.id)),
    ]);
    try {
      const uploaded: Asset[] = [];
      for (const { file, placeholder } of batch) {
        setUploadItems((current) =>
          current.map((item) =>
            item.id === placeholder.id ? { ...item, status: "uploading", progress: Math.max(item.progress, 8) } : item,
          ),
        );

        try {
          const asset = await uploadAsset(invite, file, noteForUpload, (progress) => {
            setUploadItems((current) =>
              current.map((item) =>
                item.id === placeholder.id
                  ? {
                      ...item,
                      progress,
                      status: progress >= 96 ? "processing" : "uploading",
                    }
                  : item,
              ),
            );
          });

          uploaded.push(asset);
          setUploadItems((current) =>
            current.map((item) => (item.id === placeholder.id ? { ...item, status: "processing", progress: 100 } : item)),
          );
        } catch (error) {
          failedIds.add(placeholder.id);
          const message = error instanceof Error ? error.message : "上传失败";
          setUploadError(message);
          setUploadItems((current) =>
            current.map((item) =>
              item.id === placeholder.id ? { ...item, status: "error", error: message, progress: Math.max(item.progress, 8) } : item,
            ),
          );
        }
      }

      if (uploaded.length > 0) {
        setAssets((current) => [...uploaded, ...current]);
        setNote("");
        await refresh({ silent: true });
      }

      setUploadItems((current) =>
        current.filter((item) => !batchIds.has(item.id) || failedIds.has(item.id)),
      );

      if (failedIds.size > 0) {
        window.setTimeout(() => {
          setUploadItems((current) => current.filter((item) => !failedIds.has(item.id)));
        }, 7000);
      }
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

  const handleCanvasDragEnter = (event: DragEvent<HTMLElement>) => {
    if (!isFileDrag(event)) return;

    event.preventDefault();
    if (!canUpload) return;

    dragDepthRef.current += 1;
    openDragOverlay();
  };

  const handleCanvasDragOver = (event: DragEvent<HTMLElement>) => {
    if (!isFileDrag(event)) return;

    event.preventDefault();
    event.dataTransfer.dropEffect = canUpload ? "copy" : "none";
  };

  const handleCanvasDragLeave = (event: DragEvent<HTMLElement>) => {
    if (!isFileDrag(event)) return;

    event.preventDefault();
    if (!canUpload) return;

    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) {
      closeDragOverlay();
    }
  };

  const handleDrop = (event: DragEvent<HTMLElement>) => {
    if (!isFileDrag(event) && event.dataTransfer.files.length === 0) return;

    event.preventDefault();
    dragDepthRef.current = 0;
    closeDragOverlay();
    if (!canUpload) return;

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

    setDeletingId(asset.id);
    setActionError("");
    setDeleteError("");
    try {
      await deleteAsset(invite, asset.id);
      setAssets((current) => current.filter((item) => item.id !== asset.id));
      setDeleteTarget(null);
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "删除失败");
    } finally {
      setDeletingId("");
    }
  };

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
          <div>
            <h1>NoSpace</h1>
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

      <section
        className={canvasClassName}
        aria-label="内容画布"
        onDragEnter={handleCanvasDragEnter}
        onDragOver={handleCanvasDragOver}
        onDragLeave={handleCanvasDragLeave}
        onDrop={handleDrop}
      >
        {showDragOverlay && (
          <div className={dragOverlayClassName} aria-hidden="true">
            <span className="drag-overlay-icon">
              <Upload size={30} strokeWidth={1.7} />
            </span>
          </div>
        )}
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

        <Masonry>
          {canUpload && (
            <article className="upload-tile">
              <label
                className={dragging ? "drop-zone dragging" : "drop-zone"}
              >
                <input ref={fileInputRef} type="file" multiple onChange={handleFileChange} />
                <span className="upload-symbol">{uploading ? <Loader2 className="spin" /> : <Plus />}</span>
                <strong>{uploading ? "上传中" : "拖入或选择文件"}</strong>
                <small>{`单个文件不超过 ${maxUploadMb} MB`}</small>
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
          {uploadItems.map((item) => (
            <UploadPlaceholderCard key={item.id} item={item} />
          ))}
          {visibleAssets.map((asset, index) => (
            <AssetCard
              key={asset.id}
              asset={asset}
              index={index}
              invite={invite}
              canDelete={canUpload}
              deleting={deletingId === asset.id}
              confirming={deleteTarget?.id === asset.id}
              deleteError={deleteTarget?.id === asset.id ? deleteError : ""}
              onCopy={() => void copyLink(asset)}
              onDelete={() => {
                setDeleteError("");
                setDeleteTarget(asset);
              }}
              onCancelDelete={() => {
                setDeleteError("");
                setDeleteTarget(null);
              }}
              onConfirmDelete={() => void handleDeleteAsset(asset)}
            />
          ))}
        </Masonry>

        {!loading && !hasVisibleContent && (
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

function UploadPlaceholderCard({ item }: { item: UploadPlaceholder }) {
  const progress = Math.min(100, Math.max(0, item.progress));
  const statusLabel = uploadStatusLabel(item.status);

  return (
    <article className={`upload-placeholder status-${item.status}`} aria-label={`${item.name} ${statusLabel}`}>
      <div className="asset-meta">
        <FileName name={item.name} />
        <span>{`${statusLabel} · ${progress}%`}</span>
      </div>

      <div
        className="upload-progress-track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
        aria-label={`${item.name} 上传进度`}
      >
        <span style={{ width: `${progress}%` }} />
      </div>
      {item.error && <p className="upload-placeholder-error">{item.error}</p>}
    </article>
  );
}

function AssetCard({
  asset,
  index,
  invite,
  canDelete,
  deleting,
  confirming,
  deleteError,
  onCopy,
  onDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  asset: Asset;
  index: number;
  invite: string;
  canDelete: boolean;
  deleting: boolean;
  confirming: boolean;
  deleteError: string;
  onCopy: () => void;
  onDelete: () => void;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
}) {
  const kind = assetKind(asset);
  const displayName = assetDisplayName(asset);
  const downloadUrl = asset.downloadUrl ? assetDownloadUrl(asset, invite) : "#";
  const isImage = kind === "image" && asset.url;
  const isText = kind === "text";
  const previewUrl = isImage ? assetFileUrl(asset, invite) : asset.url;
  const toneClass = `asset-card tone-${index % 5}`;

  return (
    <article className={`${toneClass}${confirming ? " is-confirming-delete" : ""}`}>
      <div className="asset-card-content">
      <div className="asset-meta">
        <div className="asset-title-stack">
          <FileName name={displayName} />
          {asset.displayName && asset.displayName !== asset.originalName && (
            <span className="asset-original-name" title={asset.originalName}>{asset.originalName}</span>
          )}
        </div>
        <time dateTime={asset.uploadedAt}>{formatTime(asset.uploadedAt)}</time>
      </div>

      {isImage && (
        <div className="asset-preview image-preview">
          <img src={previewUrl} alt={displayName} loading="lazy" />
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
          <a className="download-link" href={downloadUrl} download={displayName}>
            <ArrowDownToLine size={15} />
            <span>Get</span>
          </a>
        </div>
      </div>
      </div>
      {confirming && (
        <div className="asset-delete-confirm" role="alertdialog" aria-label={`确认删除 ${displayName}`}>
          <button className="asset-delete-confirm-button" onClick={onConfirmDelete} disabled={deleting} autoFocus>
            {deleting ? <Loader2 className="spin" size={16} /> : <Trash2 size={16} />}
            <span>{deleting ? "删除中" : "确认删除"}</span>
          </button>
          <button className="asset-delete-cancel-button" onClick={onCancelDelete} disabled={deleting}>取消</button>
          {deleteError && <p role="alert">{deleteError}</p>}
        </div>
      )}
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
