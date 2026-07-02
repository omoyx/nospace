import type { Asset, Session } from "./types";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "");

export const apiBaseUrl =
  configuredBaseUrl && configuredBaseUrl.length > 0 ? configuredBaseUrl : import.meta.env.DEV ? "http://127.0.0.1:7860" : "";

type ApiErrorBody = {
  detail?: string;
  message?: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, init);

  if (!response.ok) {
    let body: ApiErrorBody = {};
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = {};
    }

    throw new Error(body.detail || body.message || `请求失败：${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function verifyInvite(invite: string): Promise<Session> {
  return request<Session>("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ invite }),
  });
}

export async function listAssets(invite: string): Promise<Asset[]> {
  return request<Asset[]>("/api/assets", {
    headers: { "X-Invite-Code": invite },
  });
}

export async function uploadAsset(invite: string, file: File, note: string): Promise<Asset> {
  const form = new FormData();
  form.append("file", file);
  form.append("note", note);

  return request<Asset>("/api/assets", {
    method: "POST",
    headers: { "X-Invite-Code": invite },
    body: form,
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
  return `${apiBaseUrl}${asset.downloadUrl}${separator}invite=${encodeURIComponent(invite)}`;
}

export function assetFileUrl(asset: Asset, invite: string): string {
  const separator = asset.url.includes("?") ? "&" : "?";
  return `${apiBaseUrl}${asset.url}${separator}invite=${encodeURIComponent(invite)}`;
}
