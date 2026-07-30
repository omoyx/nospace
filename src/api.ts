import type { Asset, Session } from "./types";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "");
const configuredFallbackUrl = import.meta.env.VITE_API_FALLBACK_URL?.replace(/\/$/, "");
const configuredMaxUploadMb = Number(import.meta.env.VITE_MAX_UPLOAD_MB ?? 200);

export const apiBaseUrl =
  configuredBaseUrl && configuredBaseUrl.length > 0 ? configuredBaseUrl : import.meta.env.DEV ? "http://127.0.0.1:7860" : "";
export const apiFallbackUrl =
  configuredFallbackUrl && configuredFallbackUrl !== apiBaseUrl ? configuredFallbackUrl : "";
export const maxUploadMb = Number.isFinite(configuredMaxUploadMb) && configuredMaxUploadMb > 0 ? configuredMaxUploadMb : 200;
export const maxUploadBytes = maxUploadMb * 1024 * 1024;
let activeApiBaseUrl = apiBaseUrl;

type ApiErrorBody = {
  detail?: string;
  message?: string;
};

export type UploadProgressHandler = (progress: number) => void;

function apiErrorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const maybeError = body as ApiErrorBody;
    if (typeof maybeError.detail === "string" && maybeError.detail) return maybeError.detail;
    if (typeof maybeError.message === "string" && maybeError.message) return maybeError.message;
  }
  return fallback;
}

function parseJsonBody(text: string): unknown {
  if (!text) return {};
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return {};
  }
}

async function requestFrom<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, init);

  if (!response.ok) {
    let body: ApiErrorBody = {};
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = {};
    }

    throw new Error(apiErrorMessage(body, `请求失败：${response.status}`));
  }

  return response.json() as Promise<T>;
}

async function request<T>(
  path: string,
  init?: RequestInit,
  options: { allowNetworkFallback?: boolean; preferPrimary?: boolean } = {},
): Promise<T> {
  const baseUrl = options.preferPrimary ? apiBaseUrl : activeApiBaseUrl;
  try {
    const result = await requestFrom<T>(baseUrl, path, init);
    activeApiBaseUrl = baseUrl;
    return result;
  } catch (error) {
    const canFallback =
      options.allowNetworkFallback &&
      error instanceof TypeError &&
      baseUrl === apiBaseUrl &&
      apiFallbackUrl.length > 0;
    if (!canFallback) throw error;

    const result = await requestFrom<T>(apiFallbackUrl, path, init);
    activeApiBaseUrl = apiFallbackUrl;
    return result;
  }
}

export async function verifyInvite(invite: string): Promise<Session> {
  return request<Session>("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ invite }),
  }, {
    allowNetworkFallback: true,
    preferPrimary: true,
  });
}

export async function listAssets(invite: string): Promise<Asset[]> {
  return request<Asset[]>("/api/assets", {
    headers: { "X-Invite-Code": invite },
  }, {
    allowNetworkFallback: true,
  });
}

export async function uploadAsset(
  invite: string,
  file: File,
  note: string,
  onProgress?: UploadProgressHandler,
): Promise<Asset> {
  const form = new FormData();
  form.append("file", file);
  form.append("note", note);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${activeApiBaseUrl}/api/assets`);
    xhr.setRequestHeader("X-Invite-Code", invite);

    onProgress?.(8);

    xhr.upload.addEventListener("progress", (event) => {
      if (!event.lengthComputable || event.total <= 0) return;
      const progress = Math.round((event.loaded / event.total) * 96);
      onProgress?.(Math.min(96, Math.max(8, progress)));
    });

    xhr.addEventListener("load", () => {
      const body = parseJsonBody(xhr.responseText);
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress?.(100);
        resolve(body as Asset);
        return;
      }

      reject(new Error(apiErrorMessage(body, `请求失败：${xhr.status}`)));
    });

    xhr.addEventListener("error", () => reject(new Error("上传失败")));
    xhr.addEventListener("abort", () => reject(new Error("上传已取消")));

    xhr.send(form);
  });
}

export async function deleteAsset(invite: string, assetId: string): Promise<void> {
  await request<{ ok: string; id: string }>(`/api/assets/${encodeURIComponent(assetId)}`, {
    method: "DELETE",
    headers: { "X-Invite-Code": invite },
  });
}

export function assetDownloadUrl(asset: Asset, invite: string): string {
  const separator = asset.downloadUrl.includes("?") ? "&" : "?";
  return `${activeApiBaseUrl}${asset.downloadUrl}${separator}invite=${encodeURIComponent(invite)}`;
}

export function assetFileUrl(asset: Asset, invite: string): string {
  const separator = asset.url.includes("?") ? "&" : "?";
  return `${activeApiBaseUrl}${asset.url}${separator}invite=${encodeURIComponent(invite)}`;
}
