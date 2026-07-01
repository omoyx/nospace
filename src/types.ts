export type AccessRole = "upload" | "download";

export type Session = {
  role: AccessRole;
  name: string;
};

export type AssetKind = "image" | "text" | "archive" | "pdf" | "file";

export type Asset = {
  id: string;
  filename: string;
  originalName: string;
  mimeType: string;
  size: number;
  uploadedAt: string;
  sourceName: string;
  note?: string;
  width?: number;
  height?: number;
  url: string;
  downloadUrl: string;
};
