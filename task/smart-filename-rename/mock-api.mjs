import { createServer } from "node:http";

let listRequests = 0;
let uploaded = false;

const renamedAsset = {
  id: "smart-rename-test",
  filename: "smart-rename-test.txt",
  originalName: "æµ‹è¯•æŠ¥å‘Š.txt",
  displayName: "测试报告.txt",
  renameModel: "glm-5.2",
  mimeType: "text/plain",
  size: 27,
  uploadedAt: "2026-07-13T12:00:00+08:00",
  sourceName: "192.0.2.18",
  note: "",
  url: "/files/smart-rename-test",
  downloadUrl: "/files/smart-rename-test/download",
};

const server = createServer((request, response) => {
  response.setHeader("Access-Control-Allow-Origin", "http://127.0.0.1:5173");
  response.setHeader("Access-Control-Allow-Headers", "Content-Type, X-Invite-Code");
  response.setHeader("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS");

  if (request.method === "OPTIONS") {
    response.writeHead(204).end();
    return;
  }

  if (request.method === "POST" && request.url === "/api/session") {
    json(response, { role: "upload", name: "192.0.2.18" });
    return;
  }

  if (request.method === "GET" && request.url === "/api/assets") {
    listRequests += 1;
    json(response, uploaded ? [renamedAsset] : []);
    return;
  }

  if (request.method === "POST" && request.url === "/api/assets") {
    request.on("data", () => {});
    request.on("end", () => {
      uploaded = true;
      json(response, renamedAsset);
    });
    return;
  }

  if (request.method === "GET" && request.url === "/test-stats") {
    json(response, { listRequests, uploaded });
    return;
  }

  if (request.method === "GET" && request.url?.startsWith("/files/smart-rename-test")) {
    response.writeHead(200, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("smart filename rename test");
    return;
  }

  response.writeHead(404).end();
});

function json(response, value) {
  response.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(value));
}

server.listen(7862, "127.0.0.1");
