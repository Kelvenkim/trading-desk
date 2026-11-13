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
 *
 * 3) 데이트레이딩 모의 계좌:  GET /day (상태 보기) · 예약 실행(Cron)으로 5분마다 혼자 매매
 *    설정: 이 Worker → Settings → Bindings → KV namespace 추가 (변수 이름 DAY)
 *          Settings → Triggers → Cron Triggers 추가 — 5분마다, 월~금 (식: 별표/5 * * * 1-5)
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

    // ---------------- 데이트레이딩 상태 ----------------
    if (reqUrl.pathname === "/day") {
      if (!env.DAY) return json({ error: "KV 'DAY' 바인딩이 없어요" }, 501);
      if (reqUrl.searchParams.get("run") === "1" && env.CHAT_PASSWORD && request.headers.get("x-td-pass") === env.CHAT_PASSWORD) {
        return json(await runDay(env));
      }
      const st = await env.DAY.get("state");
      return new Response(st || "{}", { headers: { ...cors, "content-type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
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

  // 예약 실행 (Cron Trigger): 데이트레이딩 계좌
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runDay(env).catch((e) => console.log("day error", e && e.message)));
  },
};

// ======================= 데이트레이딩 (가상 $10,000, 당일 청산) =======================
const PARAMS_URL = "https://kelvenkim.github.io/trading-desk/data/us/day_params.json";
const DEF = {
  watch: ["SPY", "QQQ", "NVDA", "AMD", "AVGO", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "TSLA", "PLTR", "MU", "NFLX", "CRM", "ORCL", "COIN", "UBER", "JPM", "XOM", "LLY", "COST", "ANET", "CRWD", "SHOP", "MRVL", "SMCI", "HOOD", "INTC", "QCOM"],
  adv: {}, risk_pct: 0.005, max_trades: 5, max_pos: 3, cost: 0.0015, min_score: 0.6,
  w: { orb: 0.25, vwap: 0.20, rs: 0.20, rv: 0.20, mom: 0.15 }, on: { orb: true, vwap: true, rs: true },
  start_min: 585, end_min: 900, flat_min: 950, halt_spy: -0.02, rv_min: 1.2,
};
const UA = { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36" };

function nyNow() {
  const s = new Date().toLocaleString("en-US", { timeZone: "America/New_York", hour12: false });
  const d = new Date(s);
  return { d, day: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`, min: d.getHours() * 60 + d.getMinutes(), wd: d.getDay(), hm: `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}` };
}

async function bars(sym, day) {
  const r = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?interval=5m&range=1d`, { headers: UA });
  if (!r.ok) return null;
  const j = await r.json(); const x = j.chart && j.chart.result && j.chart.result[0];
  if (!x || !x.timestamp) return null;
  const q = x.indicators.quote[0], out = [];
  for (let i = 0; i < x.timestamp.length; i++) {
    if (q.close[i] == null || q.open[i] == null) continue;
    out.push({ t: x.timestamp[i], o: q.open[i], h: q.high[i], l: q.low[i], c: q.close[i], v: q.volume[i] || 0 });
  }
  const pc = x.meta.chartPreviousClose ?? x.meta.previousClose;
  // 오늘 봉만 (5분봉의 마지막은 아직 진행 중일 수 있어 뺌)
  const today = out.filter((b) => new Date(b.t * 1000).toLocaleDateString("en-CA", { timeZone: "America/New_York" }) === day);
  if (today.length && Date.now() / 1000 - today[today.length - 1].t < 300) today.pop();
  return { b: today, pc };
}

function feats(B, spyChg, adv, minNow) {
  const b = B.b; if (b.length < 7 || !B.pc) return null;
  let pv = 0, vv = 0; const vw = [];
  for (const x of b) { pv += (x.h + x.l + x.c) / 3 * x.v; vv += x.v; vw.push(vv ? pv / vv : x.c); }
  const p = b[b.length - 1].c, vwap = vw[vw.length - 1];
  const orh = Math.max(...b.slice(0, 6).map((x) => x.h)), orl = Math.min(...b.slice(0, 6).map((x) => x.l));
  const below = b.map((x, i) => x.c < vw[i]);
  const reclaim = below.length > 8 && below.slice(0, -3).some(Boolean) && !below.slice(-3).some(Boolean);
  const chg = p / B.pc - 1, rel = chg - spyChg;
  const frac = Math.max(0.08, (minNow - 570) / 390);
  const rv = adv ? (vv * p / frac) / adv : null;               // 평소 거래대금 모르면 거래 조건은 건너뜀
  const mom = p / b[Math.max(0, b.length - 7)].c - 1;
  return { p, vwap, orh, orl, reclaim, chg, rel, rv, mom, hi: Math.max(...b.map((x) => x.h)) };
}

function say(S, who, text) {
  S.chat.push({ at: new Date().toISOString(), who, text });
  if (S.chat.length > 600) S.chat = S.chat.slice(-600);
}

function sell(S, sym, px, why, P) {
  const p = S.pos[sym]; if (!p) return;
  const net = px * (1 - P.cost);
  S.cash += p.sh * net;
  const pl = net / p.cost_px - 1, R = (net - p.cost_px) / (p.entry - p.stop0);
  S.trades.push({ sym, day: S.today.day, in: p.at, out: new Date().toISOString(), entry: +p.entry.toFixed(2), exit: +px.toFixed(2), pl: +pl.toFixed(4), R: +R.toFixed(2), why, sig: p.sig, score: p.score, min_in: p.min_in });
  if (S.trades.length > 2000) S.trades = S.trades.slice(-2000);
  delete S.pos[sym];
  say(S, why.includes("손절") ? "risk" : "executor", `${sym} 매도 ${px.toFixed(2)} (${pl >= 0 ? "+" : ""}${(pl * 100).toFixed(2)}%, ${R >= 0 ? "+" : ""}${R.toFixed(1)}R) — ${why}`);
}

async function runDay(env) {
  if (!env.DAY) return { skip: "KV 'DAY' 바인딩 없음" };
  const ny = nyNow();
  if (ny.wd === 0 || ny.wd === 6 || ny.min < 575 || ny.min > 965) return { skip: "장 시간 아님" };
  let P = DEF;
  try { const r = await fetch(PARAMS_URL + "?t=" + Math.floor(Date.now() / 600000)); if (r.ok) P = { ...DEF, ...(await r.json()) }; } catch (_) {}
  let S = await env.DAY.get("state", "json");
  if (!S) S = { start: ny.day, cash: 10000, pos: {}, trades: [], chat: [], eq: [], today: {}, halt: false };
  if (S.today.day !== ny.day) {
    const e0 = S.eq.length ? S.eq[S.eq.length - 1][1] : 10000;
    S.today = { day: ny.day, n: 0, seen: [], eq0: e0 }; S.halt = false;
    say(S, "logger", `── ${ny.day} 데이트레이딩 시작 ──`);
  }
  const syms = [...new Set([...(P.watch || []).slice(0, 40), ...Object.keys(S.pos), "SPY"])].slice(0, 44);
  const D = {};
  await Promise.all(syms.map(async (s) => { try { D[s] = await bars(s, ny.day); } catch (_) {} }));
  const spy = D.SPY && D.SPY.b.length ? D.SPY : null;
  if (!spy) { await env.DAY.put("state", JSON.stringify(S)); return { skip: "오늘 시세 없음(휴장?)" }; }
  const spyChg = spy.b[spy.b.length - 1].c / spy.pc - 1;
  if (spyChg <= P.halt_spy && !S.halt) { S.halt = true; say(S, "risk", `S&P500(SPY) 오늘 ${(spyChg * 100).toFixed(1)}%. 신규 진입 멈춰요.`); }

  // 1) 보유 관리: 지난 확인 이후 봉으로 손절·목표·본전 이동, 마감 전 정리
  for (const sym of Object.keys(S.pos)) {
    const p = S.pos[sym], B = D[sym]; if (!B) continue;
    for (const x of B.b.filter((x) => x.t > p.last_t)) {
      if (x.l <= p.stop) { sell(S, sym, Math.min(x.o, p.stop), p.stop >= p.entry ? "본전 손절" : "손절", P); break; }
      if (x.h >= p.target) { sell(S, sym, Math.max(x.o, p.target), "목표 도달 (2R)", P); break; }
      if (!p.be && x.h >= p.entry + (p.entry - p.stop0)) { p.be = true; p.stop = +(p.entry * (1 + 2 * P.cost)).toFixed(2); say(S, "risk", `${sym} +1R 도달 → 손절을 본전(${p.stop})으로 올려요.`); }
      p.last_t = x.t;
    }
    if (S.pos[sym] && ny.min >= P.flat_min) sell(S, sym, B.b[B.b.length - 1].c, "장 마감 전 정리 (당일 청산)", P);
  }

  // 2) 신규 진입
  const eq0 = S.cash + Object.entries(S.pos).reduce((a, [s, p]) => a + p.sh * (D[s] && D[s].b.length ? D[s].b[D[s].b.length - 1].c : p.entry), 0);
  if (!S.halt && ny.min >= P.start_min && ny.min <= P.end_min && S.today.n < P.max_trades && Object.keys(S.pos).length < P.max_pos) {
    const C = [];
    for (const sym of P.watch || []) {
      if (sym === "SPY" || S.pos[sym] || !D[sym]) continue;
      const f = feats(D[sym], spyChg, (P.adv || {})[sym], ny.min); if (!f) continue;
      if (f.p < f.vwap || (f.rv != null && f.rv < P.rv_min) || f.p < 5) continue;
      const sig = [];
      if (P.on.orb && ny.min >= 600 && f.p > f.orh * 1.001) sig.push("orb");
      if (P.on.vwap && f.reclaim) sig.push("vwap");
      if (P.on.rs && f.rel >= 0.015) sig.push("rs");
      if (!sig.length) continue;
      const sc = (sig.includes("orb") ? P.w.orb : 0) + (sig.includes("vwap") ? P.w.vwap : 0) + Math.max(0, Math.min(1, f.rel / 0.03)) * P.w.rs
        + (f.rv == null ? 0.5 : Math.max(0, Math.min(1, (f.rv - 1) / 2))) * P.w.rv + (f.mom > 0 ? P.w.mom : 0) + ((P.bias || {})[sym] || 0);
      if (f.p >= f.hi * 0.999 && f.chg > 0.04) continue;                 // 이미 급등 꼭대기는 추격 안 함
      C.push({ sym, sc: +sc.toFixed(2), sig, f });
    }
    C.sort((a, b) => b.sc - a.sc);
    const fresh = C.filter((c) => !S.today.seen.includes(c.sym));
    if (fresh.length) say(S, "scout", `뉴욕 ${ny.hm} 장중 신호: ` + fresh.slice(0, 4).map((c) => `${c.sym} ${(c.f.chg * 100).toFixed(1)}% [${c.sig.join("·")}${c.f.rv != null ? " 거래" + c.f.rv.toFixed(1) + "배" : ""}] ${c.sc}`).join(", "));
    S.today.seen = [...new Set([...S.today.seen, ...fresh.map((c) => c.sym)])];
    for (const c of C.filter((c) => c.sc >= P.min_score)) {
      if (S.today.n >= P.max_trades || Object.keys(S.pos).length >= P.max_pos) break;
      if (S.trades.some((t) => t.sym === c.sym && t.day === ny.day)) continue;     // 같은 날 같은 종목 재진입 안 함
      const entry = c.f.p * (1 + 0.0005);
      let stop = c.sig.includes("orb") ? c.f.orl : c.f.vwap * 0.997;
      stop = Math.min(Math.max(stop, entry * 0.97), entry * 0.996);
      const riskPer = entry - stop;
      let sh = (eq0 * P.risk_pct) / riskPer;
      sh = Math.min(sh, (eq0 * 0.3) / entry, (S.cash / (entry * (1 + P.cost))));
      if (sh * entry < 200) { say(S, "risk", `${c.sym} 보류 — 현금 부족`); break; }
      S.cash -= sh * entry * (1 + P.cost);
      S.pos[c.sym] = { sh, entry, cost_px: entry * (1 + P.cost), stop: +stop.toFixed(2), stop0: stop, target: +(entry + 2 * riskPer).toFixed(2), sig: c.sig, score: c.sc, at: new Date().toISOString(), min_in: ny.min, last_t: D[c.sym].b[D[c.sym].b.length - 1].t };
      S.today.n++;
      say(S, "executor", `${c.sym} 매수 ${entry.toFixed(2)} × ${sh.toFixed(2)}주 ($${(sh * entry).toFixed(0)}) · 신호 ${c.sig.join("·")} · 점수 ${c.sc} · 손절 ${stop.toFixed(2)} (−${(riskPer / entry * 100).toFixed(2)}%) · 목표 ${(entry + 2 * riskPer).toFixed(2)} · 오늘 ${S.today.n}/${P.max_trades}번째`);
    }
  }

  // 3) 평가
  const eq = S.cash + Object.entries(S.pos).reduce((a, [s, p]) => a + p.sh * (D[s] && D[s].b.length ? D[s].b[D[s].b.length - 1].c : p.entry), 0);
  const last = S.eq[S.eq.length - 1];
  if (last && last[0] === ny.day) last[1] = +eq.toFixed(2); else S.eq.push([ny.day, +eq.toFixed(2)]);
  if (!S.spy0) S.spy0 = spy.b[0].o;
  S.spy_now = spy.b[spy.b.length - 1].c;
  S.updated = new Date().toISOString(); S.ny = ny.hm; S.params_v = P.v || 0;
  if (ny.min >= P.flat_min && !S.today.closed) {
    S.today.closed = true;
    const td = S.trades.filter((t) => t.day === ny.day), w = td.filter((t) => t.pl > 0).length;
    const d = eq - (S.today.eq0 || 10000);
    say(S, "logger", `오늘 마감: ${td.length}번 매매, ${w}번 이익 · 오늘 손익 ${d >= 0 ? "+" : "−"}$${Math.abs(d).toFixed(0)} (${(d / (S.today.eq0 || 10000) * 100).toFixed(2)}%) · S&P500 ${(spyChg * 100).toFixed(2)}% · 계좌 $${eq.toFixed(0)}`);
  }
  await env.DAY.put("state", JSON.stringify(S));
  return { ok: true, eq, pos: Object.keys(S.pos), n: S.today.n };
}
