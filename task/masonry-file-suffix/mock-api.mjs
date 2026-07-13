import { createServer } from "node:http";

const textBodies = {
  "short.txt": "一行短文本。",
  "medium.txt": "这是一个中等高度的文本卡片。\n".repeat(8),
  "long.txt": "这张卡片用于验证较长内容旁边的短卡片会继续向上密铺。\n".repeat(18),
};

const assets = [
  asset("short", "季度汇报最终确认版本真的非常非常长需要省略.txt", "text/plain", 720, "/files/short.txt"),
  asset("image-tall", "华为园区竖版现场照片原始文件超长命名.png", "image/png", 128000, "/files/tall.svg"),
  asset("pdf", "跨部门协作项目完整交付说明与所有附件清单.pdf", "application/pdf", 820000, "/files/blank"),
  asset("medium", "会议纪要与后续执行安排第二次修订.txt", "text/plain", 4200, "/files/medium.txt"),
  asset("archive", "nospace-production-release-artifacts-2026-07-13.tar.gz", "application/gzip", 1200000, "/files/blank"),
  asset("image-wide", "设计评审横版截图导出最终版.jpeg", "image/jpeg", 96000, "/files/wide.svg"),
  asset("long", "瀑布流密铺算法验证用的超长文本内容.txt", "text/plain", 8900, "/files/long.txt"),
  asset("sheet", "2026年第三季度项目排期与负责人列表.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 46000, "/files/blank"),
];

function asset(id, originalName, mimeType, size, url) {
  return {
    id,
    filename: originalName,
    originalName,
    mimeType,
    size,
    uploadedAt: "2026-07-13T10:30:00+08:00",
    sourceName: "192.0.2.18",
    note: mimeType === "application/pdf" ? "用于验证矮文件卡片会紧接在上一张矮卡片下方。" : "",
    url,
    downloadUrl: `/download/${id}`,
  };
}

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
    json(response, assets);
    return;
  }

  const path = request.url?.split("?")[0] || "";
  if (path === "/files/tall.svg" || path === "/files/wide.svg") {
    const tall = path.includes("tall");
    const width = tall ? 700 : 1200;
    const height = tall ? 1100 : 620;
    response.writeHead(200, { "Content-Type": "image/svg+xml" });
    response.end(`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><rect width="100%" height="100%" fill="#dfe2e4"/><path d="M0 ${height * 0.72} L${width * 0.42} ${height * 0.38} L${width} ${height * 0.8} V${height} H0Z" fill="#aeb4b9"/><circle cx="${width * 0.72}" cy="${height * 0.24}" r="${Math.min(width, height) * 0.09}" fill="#f7f7f7"/></svg>`);
    return;
  }

  const textName = path.replace("/files/", "");
  if (textName in textBodies) {
    response.writeHead(200, { "Content-Type": "text/plain; charset=utf-8" });
    response.end(textBodies[textName]);
    return;
  }

  response.writeHead(200, { "Content-Type": "application/octet-stream" });
  response.end("");
});

function json(response, value) {
  response.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(value));
}

server.listen(7861, "127.0.0.1");
