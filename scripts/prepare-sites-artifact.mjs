import { cp, mkdir, readdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";

const root = process.cwd();
const dist = path.join(root, "dist");
const client = path.join(dist, "client");
const server = path.join(dist, "server");
const publicDir = path.join(server, "public");

if (!existsSync(path.join(dist, "index.html"))) {
  throw new Error("Run vite build before preparing the Sites artifact.");
}

await rm(client, { recursive: true, force: true });
await rm(server, { recursive: true, force: true });
await mkdir(client, { recursive: true });

const entries = await readdir(dist);
for (const entry of entries) {
  if (entry === "client" || entry === "server") continue;
  await rename(path.join(dist, entry), path.join(client, entry));
}

await mkdir(publicDir, { recursive: true });
await cp(client, publicDir, { recursive: true });

const worker = await readFile(path.join(root, "src", "sites-worker.mjs"), "utf8");
await cp(path.join(root, ".openai"), path.join(dist, ".openai"), { recursive: true });
await mkdir(server, { recursive: true });
await writeFile(path.join(server, "index.js"), worker, "utf8");
