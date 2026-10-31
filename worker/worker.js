/**
 * Trading Desk 시세 중계 서버 (Cloudflare Workers 무료 플랜)
 *
 * 브라우저는 보안 정책(CORS) 때문에 네이버·야후 시세를 직접 받을 수 없어서,
 * 이 Worker가 대신 받아서 전달합니다. 허용된 주소만 중계하므로 다른 용도로 쓰일 수 없어요.
 *
 * 사용: https://<내 워커>.workers.dev/?url=<인코딩된 원본 주소>
 */
const ALLOWED_HOSTS = [
  "fchart.stock.naver.com",
  "query1.finance.yahoo.com",
  "query2.finance.yahoo.com",
];

// 내 사이트에서만 쓰게 하려면 아래에 주소를 넣으세요 (예: "https://kelvenkim.github.io"). 비워두면 모두 허용.
const ALLOWED_ORIGINS = [];

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin") || "";
    const allowOrigin = ALLOWED_ORIGINS.length === 0 ? "*" : (ALLOWED_ORIGINS.includes(origin) ? origin : "");
    const cors = {
      "Access-Control-Allow-Origin": allowOrigin || "null",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "*",
      "Vary": "Origin",
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    if (!allowOrigin) return new Response("origin not allowed", { status: 403, headers: cors });

    const target = new URL(request.url).searchParams.get("url");
    if (!target) return new Response("Trading Desk proxy OK", { headers: cors });

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
      const upstream = await fetch(url.toString(), {
        headers: {
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
          "Accept": "*/*",
        },
      });
      res = new Response(upstream.body, upstream);
      res.headers.set("Cache-Control", "public, max-age=60");
      if (upstream.ok) ctx.waitUntil(cache.put(cacheKey, res.clone()));
    }
    const out = new Response(res.body, res);
    Object.entries(cors).forEach(([k, v]) => out.headers.set(k, v));
    return out;
  },
};
