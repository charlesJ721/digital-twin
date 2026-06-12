/**
 * DT Hub — Cloudflare Worker API
 * Pull-push 模型：任何 AI 助理可 GET/POST 维度数据
 */

interface Env {
  GITHUB_REPO: string;
  GITHUB_BRANCH: string;
  GITHUB_TOKEN: string;
  DT_API_KEY_ARSLONGA: string;
  DT_CACHE: KVNamespace;
}

interface DimensionInsight {
  date: string;
  dimension: string;
  insight: string;
  confidence: "high" | "medium" | "low";
  evidence: string;
}

interface PostRequest {
  insights: DimensionInsight[];
  source: string; // "hermes" | "chatgpt" | "claude" | "other"
  fill_rate_updates?: Record<string, number>;
}

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
    headers: {
      "Content-Type": "application/json",
      ...extraHeaders,
    },
  });
}

// 简单 API key 验证（生产环境应使用常量时间比较）
function validateKey(key: string | null, env: Env): string | null {
  if (!key) return null;
  if (key === env.DT_API_KEY_ARSLONGA) return "arslonga";
  // 未来添加更多用户：if (key === env.DT_API_KEY_OTHER) return "other-user";
  return null;
}

// 从请求中提取 API key（支持 Header 和 Query param）
function extractKey(request: Request): string | null {
  // 1. Authorization: Bearer dt_xxx
  const auth = request.headers.get("Authorization");
  if (auth?.startsWith("Bearer ")) return auth.slice(7);
  // 2. X-DT-Key header
  const dtKey = request.headers.get("X-DT-Key");
  if (dtKey) return dtKey;
  // 3. Query param ?key=dt_xxx
  const url = new URL(request.url);
  return url.searchParams.get("key");
}

// 从 GitHub 读取文件内容
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
  if (data.content && data.encoding === "base64") {
    return atob(data.content);
  }
  return null;
}

// 写入文件到 GitHub（如果已存在则更新）
async function commitToGithub(
  path: string,
  content: string,
  message: string,
  env: Env,
): Promise<{ sha: string } | null> {
  const url = `https://api.github.com/repos/${env.GITHUB_REPO}/contents/${path}`;

  // 先获取当前文件的 sha（如果存在）
  let sha: string | undefined;
  const existing = await fetchFromGithub(path, env);
  if (existing !== null) {
    const infoRes = await fetch(url + `?ref=${env.GITHUB_BRANCH}`, {
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        "User-Agent": "dt-hub-worker",
        Accept: "application/vnd.github.v3+json",
      },
    });
    if (infoRes.ok) {
      const info = await infoRes.json() as { sha?: string };
      sha = info.sha;
    }
  }

  const body: Record<string, string> = {
    message,
    content: btoa(content),
    branch: env.GITHUB_BRANCH,
  };
  if (sha) body.sha = sha;

  const res = await fetch(url, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      "User-Agent": "dt-hub-worker",
      "Content-Type": "application/json",
      Accept: "application/vnd.github.v3+json",
    },
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
  return {
    version: full.version,
    last_extraction: full.last_extraction,
    layers: pubLayers,
  };
}

// ============================================================
// Route Handler
// ============================================================
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin") || "*";
    const headers = corsHeaders(origin);

    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers });
    }

    // Health check
    if (url.pathname === "/api/health") {
      return json({ status: "ok", users: ["arslonga"] }, 200, headers);
    }

    // GET /api/user/:username
    const getMatch = url.pathname.match(/^\/api\/user\/([a-zA-Z0-9_-]+)$/);
    if (getMatch && request.method === "GET") {
      const username = getMatch[1];
      const key = extractKey(request);
      const validatedUser = validateKey(key, env);

      try {
        if (validatedUser === username) {
          // 认证用户 → 优先从 KV 读取完整数据
          const kvData = await env.DT_DATA.get(`user:${username}`);
          if (kvData) {
            return json(JSON.parse(kvData), 200, headers);
          }
          // KV 无数据 → 尝试 GitHub
          const raw = await fetchFromGithub(`data/users/${username}/dimensions-public.json`, env);
          if (raw) {
            return json(JSON.parse(raw), 200, headers);
          }
        }
        // 未认证 → 返回公开版
        const raw = await fetchFromGithub(`data/users/${username}/dimensions-public.json`, env);
        if (raw) {
          return json(JSON.parse(raw), 200, headers);
        }
        return json({ error: "user not found" }, 404, headers);
      } catch (e) {
        return json({ error: "internal error", detail: String(e) }, 500, headers);
      }
    }

    // POST /api/user/:username/insights
    const postMatch = url.pathname.match(/^\/api\/user\/([a-zA-Z0-9_-]+)\/insights$/);
    if (postMatch && request.method === "POST") {
      const username = postMatch[1];
      const key = extractKey(request);
      const validatedUser = validateKey(key, env);

      if (validatedUser !== username) {
        return json({ error: "unauthorized" }, 401, headers);
      }

      try {
        const body = await request.json() as PostRequest;
        if (!body.insights || !Array.isArray(body.insights) || body.insights.length === 0) {
          return json({ error: "insights array required" }, 400, headers);
        }

        // 读取当前完整数据
        const raw = await fetchFromGithub(`data/users/${username}/dimensions.json`, env);
        if (!raw) {
          return json({ error: "user data not found" }, 404, headers);
        }
        const dims = JSON.parse(raw);

        // 追加洞察
        for (const insight of body.insights) {
          const layerId = String(insight.dimension?.split?.(".")?.[0] || "4");
          // 尝试匹配到正确的 layer（通过 dimension 名称前缀）
          let bestLayer = layerId;
          for (const [lid, layer] of Object.entries(dims.layers as Record<string, Record<string, unknown>>)) {
            if (insight.dimension && (layer.name as string)?.includes(insight.dimension.slice(0, 4))) {
              bestLayer = lid;
              break;
            }
          }
          const target = (dims.layers as Record<string, Record<string, unknown>>)[bestLayer];
          if (target && target.latest_insights) {
            (target.latest_insights as unknown[]).push(insight);
          }
        }

        // 更新元数据
        dims.last_extraction = new Date().toISOString();
        dims.total_sessions_processed = (dims.total_sessions_processed || 0) + 1;

        // 更新 fill_rates（如果提供了）
        if (body.fill_rate_updates) {
          for (const [layerId, rate] of Object.entries(body.fill_rate_updates)) {
            const target = (dims.layers as Record<string, Record<string, unknown>>)[layerId];
            if (target) target.fill_rate = Math.min(100, Math.max(0, rate));
          }
        }

        // 生成公开版
        const pub = generatePublicVersion(dims);

        const sourceTag = body.source || "api";
        const now = new Date().toISOString().slice(0, 10);

        // 完整数据存 KV
        await env.DT_DATA.put(`user:${username}`, JSON.stringify(dims));

        // 公开版提交到 GitHub
        const pubResult = await commitToGithub(
          `data/users/${username}/dimensions-public.json`,
          JSON.stringify(pub, null, 2),
          `api: ${sourceTag} — ${body.insights.length} insights (${now})`,
          env,
        );

        if (!pubResult) {
          return json({ error: "github commit failed" }, 500, headers);
        }

        return json({
          success: true,
          insights_added: body.insights.length,
          source: sourceTag,
          stored: "kv",
          commit: pubResult.sha.slice(0, 7),
        }, 200, headers);
      } catch (e) {
        return json({ error: "internal error", detail: String(e) }, 500, headers);
      }
    }

    return json({ error: "not found", endpoints: ["GET /api/user/:username", "POST /api/user/:username/insights", "GET /api/health"] }, 404, headers);
  },
};
