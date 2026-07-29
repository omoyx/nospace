import { Buffer } from "node:buffer";
import { createServer } from "node:http";
import process from "node:process";
import { setTimeout as delay } from "node:timers/promises";

const port = Number(process.env.PORT || 4175);
const sessionDelayMs = Number(process.env.SESSION_DELAY_MS || 700);
const sessionRequests = [];
const uploadInvites = [];

function corsHeaders() {
  return {
    "access-control-allow-headers": "content-type,x-invite-code",
    "access-control-allow-methods": "GET,POST,DELETE,OPTIONS",
    "access-control-allow-origin": "*",
  };
}

function json(response, status, body) {
  response.writeHead(status, {
    ...corsHeaders(),
    "content-type": "application/json",
  });
  response.end(JSON.stringify(body));
}

async function requestBody(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
}

const server = createServer(async (request, response) => {
  if (request.method === "OPTIONS") {
    response.writeHead(204, corsHeaders());
    response.end();
    return;
  }

  if (request.method === "POST" && request.url === "/api/session") {
    const body = JSON.parse(await requestBody(request));
    sessionRequests.push(body.invite);
    await delay(sessionDelayMs);

    if (body.invite === "upload-test") {
      json(response, 200, { role: "upload", name: "192.0.2.10" });
      return;
    }
    if (body.invite === "read-test") {
      json(response, 200, { role: "download", name: "Office" });
      return;
    }
    json(response, 401, { detail: "邀请码无效" });
    return;
  }

  if (request.method === "GET" && request.url === "/api/assets") {
    json(response, 200, []);
    return;
  }

  if (request.method === "POST" && request.url === "/api/assets") {
    const invite = request.headers["x-invite-code"] || "";
    uploadInvites.push(invite);
    await requestBody(request);
    json(response, 200, {
      id: `mock-${uploadInvites.length}`,
      originalName: "note.txt",
      displayName: "note.txt",
      filename: "note.txt",
      mimeType: "text/plain",
      size: 4,
      uploadedAt: "2026-07-29T10:00:00+08:00",
      sourceName: "192.0.2.10",
      note: "",
      url: "/files/mock",
      downloadUrl: "/files/mock/download",
    });
    return;
  }

  if (request.method === "GET" && request.url === "/__test") {
    json(response, 200, { sessionRequests, uploadInvites });
    return;
  }

  json(response, 404, { detail: "not found" });
});

server.listen(port, "127.0.0.1");
