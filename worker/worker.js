/**
 * Trading Desk 중계 서버 (Cloudflare Workers 무료 플랜)
 *
 * 1) 시세 중계:  GET  /?url=<인코딩된 원본 주소>
 *    브라우저는 보안 정책(CORS) 때문에 네이버·야후 시세를 직접 받을 수 없어서 대신 받아 전달해요.
 *    아래 ALLOWED_HOSTS 주소만 중계해요.
 *
 * 2) AI 대화:    POST /chat
 *    백테스트 탭 대화창이 Claude API를 부를 때 씀. API 키는 코드에 넣지 말고
 *    Cloudflare 대시보드 → 이 Worker → Settings → Variables and Secrets 에 비밀값(Secret)으로 넣으세요.
 *      ANTHROPIC_API_KEY  (필수) Claude API 키
 *      CHAT_PASSWORD      (권장) 사이트 ⚙ 설정에 같은 값을 넣어야 대화 가능 → 남이 내 키를 쓰는 것 방지
 */
const ALLOWED_HOSTS = [
  "fchart.stock.naver.com",
  "query1.finance.yahoo.com",
  "query2.finance.yahoo.com",
];

// 이 주소의 사이트에서만 사용 가능. 다른 주소에서 쓰려면 여기에 추가하세요.
const ALLOWED_ORIGINS = [
  "https://kelvenkim.github.io",
  "http://localhost:8000",
];

// 대화에 쓸 수 있는 모델 (첫 번째가 기본값)
const MODELS = ["claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5-5"];
const MAX_TOKENS = 4000;

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin") || "";
    const allowOrigin = ALLOWED_ORIGINS.length === 0 ? "*" : (ALLOWED_ORIGINS.includes(origin) ? origin : "");
    const cors = {
      "Access-Control-Allow-Origin": allowOrigin || "null",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "content-type, x-td-pass",
      "Vary": "Origin",
    };
    const json = (obj, status = 200) =>
      new Response(JSON.stringify(obj), { status, headers: { ...cors, "content-type": "application/json; charset=utf-8" } });

    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    if (!allowOrigin) return new Response("origin not allowed", { status: 403, headers: cors });

    const reqUrl = new URL(request.url);

    // ---------------- AI 대화 ----------------
    if (reqUrl.pathname === "/chat") {
      if (request.method !== "POST") return json({ error: { message: "POST only" } }, 405);
      if (!env.ANTHROPIC_API_KEY) {
        return json({ error: { type: "not_configured", message: "중계 서버에 ANTHROPIC_API_KEY 비밀값이 없어요." } }, 501);
      }
      if (env.CHAT_PASSWORD && request.headers.get("x-td-pass") !== env.CHAT_PASSWORD) {
        return json({ error: { type: "bad_password", message: "대화 비밀번호가 맞지 않아요." } }, 401);
      }
      let body;
      try { body = await request.json(); } catch { return json({ error: { message: "bad json" } }, 400); }
      const payload = {
        model: MODELS.includes(body.model) ? body.model : MODELS[0],
        max_tokens: Math.min(Number(body.max_tokens) || 2000, MAX_TOKENS),
        system: body.system,
        messages: body.messages,
      };
      if (Array.isArray(body.tools) && body.tools.length) payload.tools = body.tools;
      try {
        const r = await fetch("https://api.anthropic.com/v1/messages", {
          method: "POST",
          headers: {
            "x-api-key": env.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
          },
          body: JSON.stringify(payload),
        });
        return new Response(r.body, { status: r.status, headers: { ...cors, "content-type": "application/json; charset=utf-8" } });
      } catch (e) {
        return json({ error: { message: "Claude API에 연결하지 못했어요: " + e.message } }, 502);
      }
    }

    // ---------------- 시세 중계 ----------------
    const target = reqUrl.searchParams.get("url");
    if (!target) return new Response("Trading Desk proxy OK" + (env.ANTHROPIC_API_KEY ? " · chat ready" : ""), { headers: cors });

    let url;
    try { url = new URL(target); } catch { return new Response("bad url", { status: 400, headers: cors }); }
    if (url.protocol !== "https:" || !ALLOWED_HOSTS.includes(url.hostname)) {
      return new Response("host not allowed", { status: 403, headers: cors });
    }

    // 같은 요청은 60초 동안 캐시 (요청 수 절약)
    const cache = caches.default;
    const cacheKey = new Request(url.toString(), { method: "GET" });
    let res = await cache.match(cacheKey);
    if (!res) {
      let upstream;
      try {
        upstream = await fetch(url.toString(), {
          headers: {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
            "Accept": "*/*",
          },
        });
      } catch (e) {
        return new Response("upstream error: " + e.message, { status: 502, headers: cors });
      }
      res = new Response(upstream.body, upstream);
      res.headers.set("Cache-Control", "public, max-age=60");
      if (upstream.ok) ctx.waitUntil(cache.put(cacheKey, res.clone()));
    }
    const out = new Response(res.body, res);
    Object.entries(cors).forEach(([k, v]) => out.headers.set(k, v));
    return out;
  },
};
