const INDEX_KEY = "__nospace_index.json";

const jsonHeaders = {
  "content-type": "application/json; charset=utf-8",
};

function json(data, init = {}) {
  return new Response(JSON.stringify(data), {
    ...init,
    headers: {
      ...jsonHeaders,
      ...(init.headers || {}),
    },
  });
}

function parseInvites(raw = "") {
  const invites = new Map();
  for (const entry of raw.split(",")) {
    const [code, role, name] = entry.split(":").map((part) => part?.trim());
    if (!code || !name || !["upload", "download"].includes(role)) continue;
    invites.set(code, { role, name });
  }
  return invites;
}

function inviteFrom(request) {
  const url = new URL(request.url);
  return request.headers.get("X-Invite-Code") || url.searchParams.get("invite") || "";
}

function sessionFor(request, env) {
  const invites = parseInvites(env.INVITES || "");
  const session = invites.get(inviteFrom(request));
  if (!session) return null;
  return session;
}

async function readJson(request) {
  try {
    return await request.json();
  } catch {
    return {};
  }
}

async function loadIndex(env) {
  const object = await env.FILES.get(INDEX_KEY);
  if (!object) return [];
  try {
    return JSON.parse(await object.text());
  } catch {
    return [];
  }
}

async function saveIndex(env, items) {
  await env.FILES.put(INDEX_KEY, JSON.stringify(items), {
    httpMetadata: { contentType: "application/json; charset=utf-8" },
  });
}

function publicItem(item) {
  return {
    ...item,
    url: `/files/${item.id}`,
    downloadUrl: `/files/${item.id}/download`,
  };
}

function safeFilename(name) {
  return (name || "upload.bin").replace(/[^\w.\- \u4e00-\u9fa5]/g, "_").slice(0, 160) || "upload.bin";
}

function inferMime(file, originalName) {
  if (file.type) return file.type;
  if (originalName.endsWith(".txt")) return "text/plain";
  if (originalName.endsWith(".json")) return "application/json";
  if (originalName.endsWith(".pdf")) return "application/pdf";
  if (originalName.endsWith(".png")) return "image/png";
  if (originalName.endsWith(".jpg") || originalName.endsWith(".jpeg")) return "image/jpeg";
  if (originalName.endsWith(".webp")) return "image/webp";
  if (originalName.endsWith(".zip")) return "application/zip";
  return "application/octet-stream";
}

async function handleSession(request, env) {
  const body = await readJson(request);
  const invites = parseInvites(env.INVITES || "");
  const session = invites.get(body.invite || "");
  if (!session) return json({ detail: "邀请码无效" }, { status: 401 });
  return json(session);
}

async function handleList(request, env) {
  if (!sessionFor(request, env)) return json({ detail: "邀请码无效" }, { status: 401 });
  const items = await loadIndex(env);
  return json(items.sort((a, b) => b.uploadedAt.localeCompare(a.uploadedAt)).map(publicItem));
}

async function handleUpload(request, env) {
  const session = sessionFor(request, env);
  if (!session) return json({ detail: "邀请码无效" }, { status: 401 });
  if (session.role !== "upload") return json({ detail: "当前邀请码没有上传权限" }, { status: 403 });

  const maxUploadMb = Number(env.MAX_UPLOAD_MB || 80);
  const form = await request.formData();
  const file = form.get("file");
  const note = String(form.get("note") || "").slice(0, 400);
  if (!(file instanceof File)) return json({ detail: "没有收到文件" }, { status: 400 });

  const size = file.size;
  if (size > maxUploadMb * 1024 * 1024) {
    return json({ detail: `文件超过 ${maxUploadMb} MB` }, { status: 413 });
  }

  const originalName = safeFilename(file.name);
  const id = `${Date.now()}-${crypto.randomUUID().replaceAll("-", "").slice(0, 18)}`;
  const key = `files/${id}/${originalName}`;
  const mimeType = inferMime(file, originalName.toLowerCase());

  await env.FILES.put(key, await file.arrayBuffer(), {
    httpMetadata: { contentType: mimeType },
  });

  const item = {
    id,
    key,
    filename: originalName,
    originalName,
    mimeType,
    size,
    uploadedAt: new Date().toISOString(),
    sourceName: session.name,
    note,
  };

  const items = await loadIndex(env);
  items.push(item);
  await saveIndex(env, items);
  return json(publicItem(item));
}

async function fileItem(request, env, itemId) {
  if (!sessionFor(request, env)) return { response: json({ detail: "邀请码无效" }, { status: 401 }) };
  const items = await loadIndex(env);
  const item = items.find((candidate) => candidate.id === itemId);
  if (!item) return { response: json({ detail: "文件不存在" }, { status: 404 }) };
  const object = await env.FILES.get(item.key);
  if (!object) return { response: json({ detail: "文件不存在" }, { status: 404 }) };
  return { item, object };
}

async function handleFile(request, env, itemId, download) {
  const { item, object, response } = await fileItem(request, env, itemId);
  if (response) return response;

  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("etag", object.httpEtag);
  if (download) {
    headers.set("content-disposition", `attachment; filename*=UTF-8''${encodeURIComponent(item.originalName)}`);
  }
  return new Response(object.body, { headers });
}

async function handleStatic(request, env) {
  if (env.ASSETS?.fetch) {
    const direct = await env.ASSETS.fetch(request);
    if (direct.status !== 404) return direct;

    const fallbackUrl = new URL(request.url);
    fallbackUrl.pathname = "/index.html";
    return env.ASSETS.fetch(new Request(fallbackUrl, request));
  }

  return new Response("NoSpace", { headers: { "content-type": "text/plain; charset=utf-8" } });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const pathname = url.pathname;

    if (request.method === "POST" && pathname === "/api/session") return handleSession(request, env);
    if (request.method === "GET" && pathname === "/api/assets") return handleList(request, env);
    if (request.method === "POST" && pathname === "/api/assets") return handleUpload(request, env);

    const fileMatch = pathname.match(/^\/files\/([^/]+)(\/download)?$/);
    if (request.method === "GET" && fileMatch) {
      return handleFile(request, env, fileMatch[1], Boolean(fileMatch[2]));
    }

    if (pathname.startsWith("/api/") || pathname.startsWith("/files/")) {
      return json({ detail: "Not found" }, { status: 404 });
    }

    return handleStatic(request, env);
  },
};
