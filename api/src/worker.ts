/**
 * DT Hub — Cloudflare Worker API v2.1
 * Pull-Push + Review Gate + Notes endpoint
 */

interface Env {
  GITHUB_REPO: string;
  GITHUB_BRANCH: string;
  GITHUB_TOKEN: string;
  DT_API_KEY_ARSLONGA: string;
  DT_DATA: KVNamespace;
}

interface DimensionInsight {
  date: string;
  dimension: string;
  insight: string;
  confidence: "high" | "medium" | "low";
  evidence: string;
}

interface PendingInsight {
  id: string;
  insight: DimensionInsight;
  source: string;
  pushed_at: string;
  status: "pending" | "approved" | "rejected";
  reviewed_at?: string;
}

interface PostRequest {
  insights: DimensionInsight[];
  source: string;
  fill_rate_updates?: Record<string, number>;
}

interface Note {
  id: string;
  title: string;
  body: string;
  created_at: string;
  source?: string;
}

// Trusted sources that auto-approve (Hermes cron job)
const AUTO_APPROVE_SOURCES = ["hermes-cron", "hermes"];

function corsHeaders(origin: string): HeadersInit {
  return {
    "Access-Control-Allow-Origin": origin || "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-DT-Key",
    "Access-Control-Max-Age": "86400",
  };
}

function json(data: unknown, status = 200, extraHeaders?: HeadersInit): Response {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: { "Content-Type": "application/json", ...extraHeaders },
  });
}

function html(body: string, status = 200): Response {
  return new Response(body, { status, headers: { "Content-Type": "text/html; charset=utf-8" } });
}

function validateKey(key: string | null, env: Env): string | null {
  if (!key) return null;
  if (key === env.DT_API_KEY_ARSLONGA) return "arslonga";
  return null;
}

function extractKey(request: Request): string | null {
  const auth = request.headers.get("Authorization");
  if (auth?.startsWith("Bearer ")) return auth.slice(7);
  const dtKey = request.headers.get("X-DT-Key");
  if (dtKey) return dtKey;
  const url = new URL(request.url);
  return url.searchParams.get("key");
}

function uid(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

// ========== Validation ==========

const DIMENSION_MAP: Record<string, string> = {
  "开放性": "1", "尽责性": "1", "外向性": "1", "宜人性": "1",
  "情绪稳定": "1", "人格特质": "1", "动机结构": "1", "核心驱动力": "1",
  "核心恐惧": "1", "诚实": "1", "谦逊": "1",
  "推理风格": "2", "认知偏误": "2", "心智模型": "2", "元认知": "2",
  "信息处理": "2", "创造力": "2", "system": "2", "双过程": "2",
  "认知架构": "2", "决策风格": "2", "学习方式": "2",
  "价值观": "3", "信念": "3", "世界假设": "3", "伦理": "3",
  "价值排序": "3", "核心需求": "3", "被需要感": "3",
  "行为模式": "4", "习惯": "4", "节律": "4", "应激": "4",
  "防御机制": "4", "能量周期": "4", "矛盾表达": "4",
  "战略性放弃": "4",
  "知识结构": "5", "领域专长": "5", "信息食谱": "5",
  "社会关系": "6", "互动模式": "6", "信任建立": "6",
  "影响力": "6", "安全测试": "6", "亲密关系": "6",
  "叙事自我": "7", "自我概念": "7", "人生叙事": "7",
  "关键转折": "7", "自我叙事": "7", "冰山意识": "7",
};

function mapDimension(dimension: string): string | null {
  for (const [keyword, layerId] of Object.entries(DIMENSION_MAP)) {
    if (dimension.includes(keyword)) return layerId;
  }
  return null;
}

function validateInsight(insight: DimensionInsight): string | null {
  if (!insight.insight || insight.insight.length < 5) return "洞察文本过短";
  if (!insight.dimension) return "缺少维度标注";
  if (!insight.confidence || !["high", "medium"].includes(insight.confidence)) return "置信度无效";
  if (insight.insight.length > 200) return "洞察文本过长（>200字）";
  return null;
}

// ========== Notes: HTML rendering ==========

function renderNoteHtml(note: Note): string {
  // Basic markdown → HTML (handles headers, lists, bold, code, links)
  let body = note.body
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>')
    .replace(/\n\n/g, "</p><p>")
    .replace(/\n/g, "<br>");

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${note.title} — DT Notes</title>
<style>
  body { max-width: 720px; margin: 2rem auto; padding: 0 1rem; font-family: -apple-system, system-ui, sans-serif; line-height: 1.7; color: #1a1a1a; background: #fafafa; }
  h1 { font-size: 1.6rem; border-bottom: 2px solid #e0e0e0; padding-bottom: .5rem; }
  h2 { font-size: 1.3rem; margin-top: 2rem; }
  h3 { font-size: 1.1rem; }
  code { background: #eee; padding: .15em .4em; border-radius: 3px; font-size: .9em; }
  pre { background: #f0f0f0; padding: 1rem; border-radius: 6px; overflow-x: auto; }
  li { margin: .3em 0; }
  .meta { color: #888; font-size: .85rem; margin-bottom: 1.5rem; }
  a { color: #2563eb; }
</style>
</head>
<body>
<h1>${note.title}</h1>
<div class="meta">${note.created_at.slice(0, 10)} · DT Hub Notes</div>
<p>${body}</p>
</body>
</html>`;
}

// ========== GitHub helpers ==========

async function fetchFromGithub(path: string, env: Env): Promise<string | null> {
  const url = `https://api.github.com/repos/${env.GITHUB_REPO}/contents/${path}?ref=${env.GITHUB_BRANCH}`;
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      "User-Agent": "dt-hub-worker",
      Accept: "application/vnd.github.v3+json",
    },
  });
  if (!res.ok) return null;
  const data = await res.json() as { content?: string; encoding?: string };
  if (data.content && data.encoding === "base64") return atob(data.content);
  return null;
}

async function commitToGithub(path: string, content: string, message: string, env: Env): Promise<{ sha: string } | null> {
  const url = `https://api.github.com/repos/${env.GITHUB_REPO}/contents/${path}`;
  let sha: string | undefined;
  const existing = await fetchFromGithub(path, env);
  if (existing !== null) {
    const infoRes = await fetch(url + `?ref=${env.GITHUB_BRANCH}`, {
      headers: { Authorization: `Bearer ${env.GITHUB_TOKEN}`, "User-Agent": "dt-hub-worker", Accept: "application/vnd.github.v3+json" },
    });
    if (infoRes.ok) sha = (await infoRes.json() as { sha?: string }).sha;
  }
  const body: Record<string, string> = { message, content: btoa(unescape(encodeURIComponent(content))), branch: env.GITHUB_BRANCH };
  if (sha) body.sha = sha;
  const res = await fetch(url, {
    method: "PUT",
    headers: { Authorization: `Bearer ${env.GITHUB_TOKEN}`, "User-Agent": "dt-hub-worker", "Content-Type": "application/json", Accept: "application/vnd.github.v3+json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) return null;
  return await res.json() as { sha: string };
}

function generatePublicVersion(full: Record<string, unknown>): Record<string, unknown> {
  const layers = full.layers as Record<string, Record<string, unknown>>;
  const pubLayers: Record<string, Record<string, unknown>> = {};
  for (const [id, layer] of Object.entries(layers)) {
    pubLayers[id] = {
      name: layer.name,
      fill_rate: layer.fill_rate,
      status: layer.status,
      insight_count: Array.isArray(layer.latest_insights) ? layer.latest_insights.length : 0,
    };
  }
  return { version: full.version, last_extraction: full.last_extraction, layers: pubLayers };
}

async function syncPublicToGithub(username: string, env: Env): Promise<void> {
  const kvData = await env.DT_DATA.get(`user:${username}`);
  if (!kvData) return;
  const dims = JSON.parse(kvData);
  const pub = generatePublicVersion(dims);
  await commitToGithub(
    `data/users/${username}/dimensions-public.json`,
    JSON.stringify(pub, null, 2),
    `sync: public version updated`,
    env,
  );
}

// Sync a note to GitHub Pages (accessible in China without proxy)
async function syncNoteToGithub(username: string, note: Note, env: Env): Promise<string | null> {
  const html = renderNoteHtml(note);
  const path = `notes/${note.id}.html`;
  const result = await commitToGithub(path, html, `note: ${note.title}`, env);
  if (result) {
    return `https://charlesj721.github.io/digital-twin/${path}`;
  }
  return null;
}

// ========== Route Handler ==========

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin") || "*";
    const headers = corsHeaders(origin);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers });
    }

    // Health
    if (url.pathname === "/api/health") {
      return json({ status: "ok", users: ["arslonga"], version: "v2.1-notes" }, 200, headers);
    }

    // ============================================================
    // Notes endpoints (v2.1)
    // ============================================================

    // POST /api/user/:username/notes — 创建笔记
    const notesPost = url.pathname.match(/^\/api\/user\/([a-zA-Z0-9_-]+)\/notes$/);
    if (notesPost && request.method === "POST") {
      const username = notesPost[1];
      const authUser = validateKey(extractKey(request), env);
      if (authUser !== username) return json({ error: "unauthorized" }, 401, headers);

      try {
        const body = await request.json() as { title: string; body: string; source?: string };
        if (!body.title || !body.body) return json({ error: "title and body required" }, 400, headers);

        const note: Note = {
          id: uid(),
          title: body.title,
          body: body.body,
          created_at: new Date().toISOString(),
          source: body.source || "hermes",
        };

        // Store in KV, keep last 50 notes
        const listKey = `notes:${username}`;
        let existing: Note[] = [];
        const raw = await env.DT_DATA.get(listKey);
        if (raw) existing = JSON.parse(raw);
        existing.unshift(note);
        if (existing.length > 50) existing = existing.slice(0, 50);
        await env.DT_DATA.put(listKey, JSON.stringify(existing));

        // Sync to GitHub Pages (accessible from China without proxy)
        const ghUrl = await syncNoteToGithub(username, note, env);

        return json({
          success: true,
          id: note.id,
          url: `https://dt-hub.chindowj721.workers.dev/api/user/${username}/notes/${note.id}`,
          gh_url: ghUrl,
        }, 201, headers);
      } catch (e) {
        return json({ error: String(e) }, 500, headers);
      }
    }

    // GET /api/user/:username/notes — 列出所有笔记
    const notesList = url.pathname.match(/^\/api\/user\/([a-zA-Z0-9_-]+)\/notes$/);
    if (notesList && request.method === "GET") {
      const username = notesList[1];
      try {
        const raw = await env.DT_DATA.get(`notes:${username}`);
        const notes: Note[] = raw ? JSON.parse(raw) : [];
        // Return list without full body
        const summaries = notes.map(n => ({
          id: n.id,
          title: n.title,
          created_at: n.created_at,
          source: n.source,
          preview: n.body.slice(0, 120) + (n.body.length > 120 ? "…" : ""),
        }));
        return json({ notes: summaries, count: summaries.length }, 200, headers);
      } catch (e) {
        return json({ error: String(e) }, 500, headers);
      }
    }

    // GET /api/user/:username/notes/:id — 渲染单篇笔记
    const notesGet = url.pathname.match(/^\/api\/user\/([a-zA-Z0-9_-]+)\/notes\/([a-zA-Z0-9]+)$/);
    if (notesGet && request.method === "GET") {
      const username = notesGet[1];
      const noteId = notesGet[2];
      try {
        const raw = await env.DT_DATA.get(`notes:${username}`);
        const notes: Note[] = raw ? JSON.parse(raw) : [];
        const note = notes.find(n => n.id === noteId);
        if (!note) return html("<h1>404</h1><p>Note not found</p>", 404);

        // Check if client wants JSON
        const accept = request.headers.get("Accept") || "";
        if (accept.includes("application/json")) {
          return json(note, 200, headers);
        }
        return html(renderNoteHtml(note));
      } catch (e) {
        return json({ error: String(e) }, 500, headers);
      }
    }

    // ============================================================
    // GET /api/user/:username — 拉取数据
    // ============================================================
    const getMatch = url.pathname.match(/^\/api\/user\/([a-zA-Z0-9_-]+)$/);
    if (getMatch && request.method === "GET") {
      const username = getMatch[1];
      const authUser = validateKey(extractKey(request), env);
      try {
        if (authUser === username) {
          const kvData = await env.DT_DATA.get(`user:${username}`);
          if (kvData) return json(JSON.parse(kvData), 200, headers);
        }
        const raw = await fetchFromGithub(`data/users/${username}/dimensions-public.json`, env);
        if (raw) return json(JSON.parse(raw), 200, headers);
        return json({ error: "user not found" }, 404, headers);
      } catch (e) {
        return json({ error: String(e) }, 500, headers);
      }
    }

    // ============================================================
    // POST /api/user/:username/insights — 推送洞察
    // ============================================================
    const postMatch = url.pathname.match(/^\/api\/user\/([a-zA-Z0-9_-]+)\/insights$/);
    if (postMatch && request.method === "POST") {
      const username = postMatch[1];
      const authUser = validateKey(extractKey(request), env);
      if (authUser !== username) return json({ error: "unauthorized" }, 401, headers);

      try {
        const body = await request.json() as PostRequest;
        if (!body.insights?.length) return json({ error: "insights array required" }, 400, headers);

        const results: Record<string, unknown>[] = [];
        const autoApprove = AUTO_APPROVE_SOURCES.includes(body.source);

        let pendingRaw = await env.DT_DATA.get(`review:${username}`);
        const pending: PendingInsight[] = pendingRaw ? JSON.parse(pendingRaw) : [];

        for (const raw of body.insights) {
          const err = validateInsight(raw);
          if (err) {
            results.push({ insight: raw.insight?.slice(0, 30), status: "rejected", reason: err });
            continue;
          }

          const mappedLayer = mapDimension(raw.dimension);

          const pendingItem: PendingInsight = {
            id: uid(),
            insight: { ...raw, dimension: raw.dimension + (mappedLayer ? ` → L${mappedLayer}` : "") },
            source: body.source,
            pushed_at: new Date().toISOString(),
            status: autoApprove ? "approved" : "pending",
          };

          if (autoApprove) {
            pendingItem.reviewed_at = pendingItem.pushed_at;
            await mergeToCore(username, pendingItem.insight, body.fill_rate_updates, env);
            pendingItem.status = "approved";
            results.push({ id: pendingItem.id, status: "auto_approved", dimension: pendingItem.insight.dimension });
          } else {
            pending.push(pendingItem);
            results.push({ id: pendingItem.id, status: "pending_review", dimension: pendingItem.insight.dimension });
          }
        }

        if (!autoApprove) {
          await env.DT_DATA.put(`review:${username}`, JSON.stringify(pending));
        }

        await logReview(username, results, body.source, env);

        return json({
          success: true,
          received: body.insights.length,
          results,
          mode: autoApprove ? "auto_approved" : "pending_review",
          pending_count: autoApprove ? 0 : pending.length,
        }, 200, headers);
      } catch (e) {
        return json({ error: String(e) }, 500, headers);
      }
    }

    // ============================================================
    // Review endpoints (unchanged)
    // ============================================================
    const reviewGet = url.pathname.match(/^\/api\/user\/([a-zA-Z0-9_-]+)\/review$/);
    if (reviewGet && request.method === "GET") {
      const username = reviewGet[1];
      const authUser = validateKey(extractKey(request), env);
      if (authUser !== username) return json({ error: "unauthorized" }, 401, headers);
      try {
        const raw = await env.DT_DATA.get(`review:${username}`);
        const pending: PendingInsight[] = raw ? JSON.parse(raw) : [];
        return json({ pending, count: pending.length }, 200, headers);
      } catch (e) {
        return json({ error: String(e) }, 500, headers);
      }
    }

    const approveMatch = url.pathname.match(/^\/api\/user\/([a-zA-Z0-9_-]+)\/review\/approve$/);
    if (approveMatch && request.method === "POST") {
      const username = approveMatch[1];
      const authUser = validateKey(extractKey(request), env);
      if (authUser !== username) return json({ error: "unauthorized" }, 401, headers);
      try {
        const body = await request.json() as { ids: string[] };
        if (!body.ids?.length) return json({ error: "ids array required" }, 400, headers);
        const raw = await env.DT_DATA.get(`review:${username}`);
        let pending: PendingInsight[] = raw ? JSON.parse(raw) : [];
        const approved: PendingInsight[] = [];
        const remaining: PendingInsight[] = [];
        for (const item of pending) {
          if (body.ids.includes(item.id)) {
            item.status = "approved";
            item.reviewed_at = new Date().toISOString();
            await mergeToCore(username, item.insight, undefined, env);
            approved.push(item);
          } else {
            remaining.push(item);
          }
        }
        await env.DT_DATA.put(`review:${username}`, JSON.stringify(remaining));
        await syncPublicToGithub(username, env);
        await logReview(username, approved.map(i => ({ id: i.id, action: "approved" })), "manual-review", env);
        return json({ approved: approved.length, remaining: remaining.length }, 200, headers);
      } catch (e) {
        return json({ error: String(e) }, 500, headers);
      }
    }

    const rejectMatch = url.pathname.match(/^\/api\/user\/([a-zA-Z0-9_-]+)\/review\/reject$/);
    if (rejectMatch && request.method === "POST") {
      const username = rejectMatch[1];
      const authUser = validateKey(extractKey(request), env);
      if (authUser !== username) return json({ error: "unauthorized" }, 401, headers);
      try {
        const body = await request.json() as { ids: string[] };
        const raw = await env.DT_DATA.get(`review:${username}`);
        let pending: PendingInsight[] = raw ? JSON.parse(raw) : [];
        const rejected: PendingInsight[] = [];
        pending = pending.filter(item => {
          if (body.ids.includes(item.id)) {
            item.status = "rejected";
            item.reviewed_at = new Date().toISOString();
            rejected.push(item);
            return false;
          }
          return true;
        });
        await env.DT_DATA.put(`review:${username}`, JSON.stringify(pending));
        await logReview(username, rejected.map(i => ({ id: i.id, action: "rejected" })), "manual-review", env);
        return json({ rejected: rejected.length, remaining: pending.length }, 200, headers);
      } catch (e) {
        return json({ error: String(e) }, 500, headers);
      }
    }

    return json({
      error: "not found",
      endpoints: [
        "GET /api/user/:username",
        "POST /api/user/:username/insights",
        "GET /api/user/:username/review",
        "POST /api/user/:username/review/approve",
        "POST /api/user/:username/review/reject",
        "POST /api/user/:username/notes",
        "GET /api/user/:username/notes",
        "GET /api/user/:username/notes/:id",
        "GET /api/health",
      ]
    }, 404, headers);
  },
};

// ========== Core helpers ==========

async function mergeToCore(username: string, insight: DimensionInsight, fillRateUpdates: Record<string, number> | undefined, env: Env): Promise<void> {
  let kvData = await env.DT_DATA.get(`user:${username}`);
  if (!kvData) {
    const pubRaw = await fetchFromGithub(`data/users/${username}/dimensions-public.json`, env);
    if (!pubRaw) return;
    const pub = JSON.parse(pubRaw);
    const layers: Record<string, Record<string, unknown>> = {};
    for (const [id, l] of Object.entries(pub.layers as Record<string, Record<string, unknown>>)) {
      layers[id] = { ...l as Record<string, unknown>, latest_insights: [] };
    }
    kvData = JSON.stringify({ version: pub.version, last_extraction: pub.last_extraction, total_sessions_processed: 0, layers });
  }

  const dims = JSON.parse(kvData);
  let targetLayer = mapDimension(insight.dimension) || "4";
  const arrowMatch = insight.dimension.match(/→ L(\d)/);
  if (arrowMatch) targetLayer = arrowMatch[1];

  const layer = (dims.layers as Record<string, Record<string, unknown>>)[targetLayer];
  if (layer) {
    if (!layer.latest_insights) layer.latest_insights = [];
    (layer.latest_insights as unknown[]).push(insight);
  }

  dims.last_extraction = new Date().toISOString();
  dims.total_sessions_processed = (dims.total_sessions_processed || 0) + 1;

  if (fillRateUpdates) {
    for (const [lid, rate] of Object.entries(fillRateUpdates)) {
      const l = (dims.layers as Record<string, Record<string, unknown>>)[lid];
      if (l) l.fill_rate = Math.min(100, Math.max(0, rate));
    }
  }

  await env.DT_DATA.put(`user:${username}`, JSON.stringify(dims));
}

async function logReview(username: string, entries: Record<string, unknown>[], source: string, env: Env): Promise<void> {
  const key = `review_log:${username}`;
  const raw = await env.DT_DATA.get(key);
  const log: Record<string, unknown>[] = raw ? JSON.parse(raw) : [];
  log.push({ timestamp: new Date().toISOString(), source, entries });
  if (log.length > 500) log.splice(0, log.length - 500);
  await env.DT_DATA.put(key, JSON.stringify(log));
}
