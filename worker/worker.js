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
 *          Settings → Trigger events → Cron Triggers 추가 — 5분마다 매일 (식: 별표/5 * * * *)
 *          (주식은 코드가 미국장 시간인지 스스로 확인해요. 코인은 주말에도 돌아요)
 *
 * 4) 코인 5분봉 단기 실험(10배):  GET /scalp10 (상태 보기) — 같은 Cron에서 5분마다, 주말 포함
 *    BTC·ETH 5분봉 볼린저 밴드(20봉, 2.5표준편차) 바깥 → 평균 회귀. 손절 ATR×3, 평균 닿으면 정리, 최대 1시간.
 *    ⚠ 과거 60일 시험(research/crypto5m)에서 수수료 0.05% 기준으로는 비용을 이기는 우위가 없었어요. 기록용 실험이에요.
 *    11/21 사용자 요청으로 10배만 운영 (코인마다 계좌의 5배어치, 손절 ATR×3, 하루 −10%면 멈춤)
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

    // ---------------- 코인 5분봉 실험 상태 ----------------
    if (["/scalp", "/scalp5", "/scalp10"].includes(reqUrl.pathname)) {
      if (!env.DAY) return json({ error: "KV 'DAY' 바인딩이 없어요" }, 501);
      const st = await env.DAY.get(reqUrl.pathname.slice(1));
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
    ctx.waitUntil(runScalpAll(env).catch((e) => console.log("scalp error", e && e.message)));
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


// ======================= 코인 5분봉 단기 실험 (가상 $10,000, 롱·숏, 주말 포함) =======================
// 근거: research/crypto5m/bt.py — 2026-09-23~11-21 BTC·ETH 5분봉 72가지 시험.
//  수수료 한쪽 0.05%: 모든 방식이 거래당 약 −0.03~−0.12%로 손실(무작위 진입 −0.10%와 비슷).
//  한쪽 0.02%(지정가)일 때만 이 방식(볼린저 20·2.5·손절 ATR×3·최대 12봉)이 BTC +0.005%·ETH +0.019%로 겨우 플러스.
//  → '돈을 벌 거라 믿는 전략'이 아니라 '5분봉 단타가 비용을 이길 수 있는지' 실제로 기록해 보는 실험이에요.
const SC = { syms: ["BTC-USD", "ETH-USD"], n: 20, k: 2.5, atrN: 14, stopAtr: 3, maxBars: 12, risk: 0.005, capW: 0.5, fee: 0.0005, dayHalt: -0.02 };
// 레버리지(11/21 사용자 요청 → 10배로, 1배 단타는 지움): 같은 신호, 코인마다 계좌의 5배어치(둘 다 잡으면 10배). 손절·수수료 같음.
// 과거 60일: 수수료 없으면 +478%, 왕복 0.10%면 −86%(낙폭 −90%) — 레버리지는 수수료 손실도 같이 키워요.
const SC10 = { ...SC, key: "scalp10", lev: 10, notionalW: 5, dayHalt: -0.10 };
SC.key = "scalp";

async function cbars(sym) {
  const r = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?interval=5m&range=2d`, { headers: UA });
  if (!r.ok) return null;
  const j = await r.json(); const x = j.chart && j.chart.result && j.chart.result[0];
  if (!x || !x.timestamp) return null;
  const q = x.indicators.quote[0], out = [];
  for (let i = 0; i < x.timestamp.length; i++) {
    if (q.close[i] == null || q.open[i] == null || q.high[i] == null || q.low[i] == null) continue;
    out.push({ t: x.timestamp[i], o: q.open[i], h: q.high[i], l: q.low[i], c: q.close[i] });
  }
  if (out.length && Date.now() / 1000 - out[out.length - 1].t < 300) out.pop();   // 진행 중인 봉 제외
  return out;
}

function cind(b) {
  const n = SC.n, m = b.length; if (m < 60) return null;
  const cl = b.slice(-n).map((x) => x.c), mean = cl.reduce((a, v) => a + v, 0) / n;
  const sd = Math.sqrt(cl.reduce((a, v) => a + (v - mean) ** 2, 0) / (n - 1));
  let atr = null;
  for (let i = 1; i < m; i++) {
    const tr = Math.max(b[i].h - b[i].l, Math.abs(b[i].h - b[i - 1].c), Math.abs(b[i].l - b[i - 1].c));
    atr = atr == null ? tr : atr + (tr - atr) / SC.atrN;
  }
  return { mean, sd, atr, c: b[m - 1].c, t: b[m - 1].t };
}

function scEq(S, px) {
  let e = S.cash;
  for (const [sym, p] of Object.entries(S.pos)) e += p.side * p.qty * ((px[sym] || p.entry) - p.entry);
  return e;
}

function scClose(S, sym, px, why, t) {
  const p = S.pos[sym]; if (!p) return;
  const fee = p.qty * px * SC.fee, pnl = p.side * p.qty * (px - p.entry) - fee;
  S.cash += pnl;
  const pl = p.side * (px / p.entry - 1) - 2 * SC.fee;                     // 가격 기준(수수료 포함)
  const acct = pl * (p.w || 1);                                               // 계좌 대비 (레버리지면 노출 배수만큼 커짐)
  S.trades.push({ sym, side: p.side, in: p.at, out: new Date(t * 1000).toISOString(), entry: +p.entry.toFixed(2), exit: +px.toFixed(2), pl: +pl.toFixed(5), acct: +acct.toFixed(5), usd: +(pnl - p.fee_in).toFixed(2), why, bars: p.bars });
  if (S.trades.length > 3000) S.trades = S.trades.slice(-3000);
  delete S.pos[sym];
  S.chat.push({ at: new Date().toISOString(), who: why.includes("손절") ? "risk" : "executor", text: `${sym.replace("-USD", "")} ${p.side > 0 ? "롱" : "숏"} 정리 ${px.toFixed(2)} (${pl >= 0 ? "+" : ""}${(pl * 100).toFixed(2)}%${p.w > 1 ? `, 계좌 ${acct >= 0 ? "+" : ""}${(acct * 100).toFixed(2)}%` : ""}, 수수료 포함) — ${why}` });
}

async function runScalp(env, C = SC, pre = null) {
  if (!env.DAY) return { skip: "KV 'DAY' 바인딩 없음" };
  let S = await env.DAY.get(C.key, "json");
  const now = new Date(), day = now.toISOString().slice(0, 10);
  if (!S) S = { start: day, cash: 10000, pos: {}, trades: [], chat: [], eq: [], last: {}, day: {}, liq_n: 0, lev: C.lev || 1,
    rule: "5분봉 볼린저(20봉·2.5σ) 바깥 → 평균 회귀, 손절 ATR×3, 최대 1시간, 롱·숏, 수수료 한쪽 0.05%" + (C.lev ? ` · ${C.lev}배 레버리지(코인마다 계좌의 ${C.notionalW}배)` : "") };
  const px = {}, B = pre || {};
  if (!pre) for (const sym of SC.syms) { try { B[sym] = await cbars(sym); } catch (_) { B[sym] = null; } }
  for (const sym of SC.syms) if (B[sym] && B[sym].length) px[sym] = B[sym][B[sym].length - 1].c;
  if (S.day.d !== day) S.day = { d: day, e0: scEq(S, px) };
  for (const sym of SC.syms) {
    const b = B[sym]; if (!b || b.length < 60) continue;
    // 1) 보유 중이면: 마지막으로 본 봉 다음부터 손절·평균 회귀·시간 정리 확인
    const p = S.pos[sym];
    if (p) {
      for (const x of b.filter((x) => x.t > p.seen)) {
        p.seen = x.t; p.bars += 1;
        if (p.side > 0 && x.l <= p.stop) { scClose(S, sym, Math.min(x.o, p.stop), "손절 (ATR×3)", x.t); break; }
        if (p.side < 0 && x.h >= p.stop) { scClose(S, sym, Math.max(x.o, p.stop), "손절 (ATR×3)", x.t); break; }
        const upto = b.filter((y) => y.t <= x.t), I = cind(upto);
        if (I && ((p.side > 0 && x.c >= I.mean) || (p.side < 0 && x.c <= I.mean))) { scClose(S, sym, x.c, "평균 닿음 (익절·정리)", x.t); break; }
        if (p.bars >= SC.maxBars) { scClose(S, sym, x.c, "1시간 지남 (시간 정리)", x.t); break; }
      }
    }
    // 2) 새 봉이 닫혔고 보유 없음 → 진입 판단
    const I = cind(b);
    if (!I || S.last[sym] === I.t) continue;
    S.last[sym] = I.t;
    if (S.pos[sym]) continue;
    const eq = scEq(S, px);
    if (eq <= 0) continue;
    if (S.day.e0 && eq / S.day.e0 - 1 <= C.dayHalt) { if (!S.day.halt) { S.day.halt = true; S.chat.push({ at: now.toISOString(), who: "risk", text: `오늘(UTC) 손실 ${((eq / S.day.e0 - 1) * 100).toFixed(1)}% — 하루 ${(C.dayHalt * 100).toFixed(0)}% 한도라 신규 진입 멈춰요.` }); } continue; }
    const side = I.c < I.mean - SC.k * I.sd ? 1 : I.c > I.mean + SC.k * I.sd ? -1 : 0;
    if (!side || !I.atr) continue;
    const stopD = SC.stopAtr * I.atr, qty = C.notionalW ? (eq * C.notionalW) / I.c : Math.min((eq * SC.risk) / stopD, (eq * SC.capW) / I.c);
    const fee_in = qty * I.c * SC.fee;
    S.cash -= fee_in;
    S.pos[sym] = { side, qty, entry: I.c, stop: I.c - side * stopD, at: new Date(I.t * 1000 + 300000).toISOString(), seen: I.t, bars: 0, fee_in, z: +((I.c - I.mean) / I.sd).toFixed(2), w: +(qty * I.c / eq).toFixed(3) };
    S.chat.push({ at: now.toISOString(), who: "executor", text: `${sym.replace("-USD", "")} ${side > 0 ? "롱" : "숏"} ${I.c.toFixed(2)} — 5분봉이 20봉 평균에서 ${((I.c - I.mean) / I.sd).toFixed(1)}σ 벗어남 · 손절 ${(I.c - side * stopD).toFixed(2)} · $${(qty * I.c).toFixed(0)}어치` });
  }
  const e = scEq(S, px);
  const last = S.eq[S.eq.length - 1];
  if (!last || Date.now() - Date.parse(last[0]) > 25 * 60 * 1000) S.eq.push([now.toISOString().slice(0, 16), +e.toFixed(2)]);
  if (S.eq.length > 4000) S.eq = S.eq.slice(-4000);
  if (S.chat.length > 600) S.chat = S.chat.slice(-600);
  S.eq_now = +e.toFixed(2); S.made = now.toISOString(); S.px = px;
  await env.DAY.put(C.key, JSON.stringify(S));
  return { ok: true, eq: S.eq_now, B };
}

async function runScalpAll(env) {
  return runScalp(env, SC10);
}
