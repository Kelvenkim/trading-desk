/* =========================================================
 * 데이터 계층
 *  - 관심종목(watchlist)은 GitHub Actions가 저장한 data/ 파일 사용
 *  - 그 외 종목은 중계 서버(Cloudflare Worker)를 통해 네이버·야후에서 받음
 *  - 봉 형식: { t(차트용 시간), ms, day, o, h, l, c, v }
 * ========================================================= */
const Data = (() => {
  const KST = 9 * 3600;
  const PROXY_KEY = "tradingdesk.proxy";
  const INTERVALS = [
    { id: "1m", label: "1분", min: 1 },
    { id: "5m", label: "5분", min: 5 },
    { id: "15m", label: "15분", min: 15 },
    { id: "30m", label: "30분", min: 30 },
    { id: "1h", label: "1시간", min: 60 },
    { id: "1d", label: "일", daily: true },
    { id: "1w", label: "주", daily: true },
    { id: "1M", label: "월", daily: true },
  ];
  const IV = Object.fromEntries(INTERVALS.map((x) => [x.id, x]));

  let meta = { symbols: [], updated: "" };
  const bySym = {};
  let symbols = null, symbolsPromise = null;
  const cache = new Map();

  class NeedProxyError extends Error {
    constructor() { super("이 종목은 시세 중계 서버를 설정해야 볼 수 있어요. 오른쪽 위 ⚙ 설정에서 주소를 넣어주세요."); this.needProxy = true; }
  }

  const isKR = (s) => /\.(KS|KQ)$/.test(s);
  const kstDay = (ms) => new Date(ms + KST * 1000).toISOString().slice(0, 10);

  // ---------- 설정 ----------
  // 기기마다 따로 넣지 않아도 되게: 이 브라우저에 저장한 주소 → 없으면 data/config.json 의 기본 주소
  let siteProxy = "";
  function getProxy() { let v = ""; try { v = (localStorage.getItem(PROXY_KEY) || "").trim(); } catch (_) {} return v || siteProxy; }
  function setProxy(v) { try { localStorage.setItem(PROXY_KEY, (v || "").trim()); } catch (_) {} cache.clear(); }

  async function getJSON(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(`${url} (${r.status})`);
    return r.json();
  }

  async function init() {
    try { siteProxy = ((await getJSON("data/config.json")).proxy || "").trim(); } catch (_) {}
    meta = await getJSON("data/meta.json");
    meta.symbols.forEach((s) => (bySym[s.symbol] = s));
    return meta;
  }

  function loadSymbols() {
    if (symbols) return Promise.resolve(symbols);
    if (!symbolsPromise) {
      symbolsPromise = getJSON("data/symbols.json")
        .then((j) => (symbols = j.list.map(([symbol, name, market], rank) => ({ symbol, name, market, rank, key: norm(name), cho: chosung(name) }))))
        .catch(() => (symbols = meta.symbols.map((s, rank) => ({ symbol: s.symbol, name: s.name, market: isKR(s.symbol) ? "KR" : "US", rank, key: norm(s.name), cho: chosung(s.name) }))));
    }
    return symbolsPromise;
  }

  // ---------- 검색 ----------
  const norm = (s) => String(s).toLowerCase().replace(/\s+/g, "");
  const CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ";
  function chosung(s) {
    let out = "";
    for (const ch of String(s)) {
      const c = ch.charCodeAt(0) - 0xac00;
      out += c >= 0 && c < 11172 ? CHO[Math.floor(c / 588)] : ch.toLowerCase();
    }
    return out.replace(/\s+/g, "");
  }
  async function search(q, limit = 12) {
    const list = await loadSymbols();
    const n = norm(q);
    if (!n) return [];
    const onlyCho = /^[ㄱ-ㅎ]+$/.test(n);
    const scored = [];
    for (const s of list) {
      const code = s.symbol.toLowerCase().split(".")[0];
      let score = -1;
      if (code === n || s.symbol.toLowerCase() === n) score = 0;
      else if (s.key === n) score = 1;
      else if (code.startsWith(n)) score = 2;
      else if (s.key.startsWith(n)) score = 3;
      else if (onlyCho && s.cho.startsWith(n)) score = 3;
      else if (s.key.includes(n)) score = 4;
      else if (onlyCho && s.cho.includes(n)) score = 5;
      if (score >= 0) scored.push([score, s.rank, s]);
    }
    scored.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    return scored.slice(0, limit).map((x) => x[2]);
  }
  function info(sym) {
    if (bySym[sym]) return { symbol: sym, name: bySym[sym].name, market: isKR(sym) ? (sym.endsWith(".KQ") ? "KOSDAQ" : "KOSPI") : "US" };
    const s = symbols && symbols.find((x) => x.symbol === sym);
    return s ? { symbol: sym, name: s.name, market: s.market } : { symbol: sym, name: sym, market: isKR(sym) ? "KR" : "US" };
  }

  // ---------- 정규화 / 집계 ----------
  const fromDailyRows = (rows) => rows.map(([d, o, h, l, c, v]) => ({ t: d, ms: Date.parse(d + "T00:00:00Z"), day: d, o, h, l, c, v }));
  const fromIntradayRows = (rows) => rows.map(([u, o, h, l, c, v]) => ({ t: u + KST, ms: u * 1000, day: kstDay(u * 1000), o, h, l, c, v }));

  function aggregate(bars, keyFn, timeFn) {
    const out = [];
    let cur = null, curKey = null;
    for (const b of bars) {
      const k = keyFn(b);
      if (k !== curKey) {
        if (cur) out.push(cur);
        curKey = k;
        cur = { ...b, ...timeFn(b, k) };
      } else {
        cur.h = Math.max(cur.h, b.h); cur.l = Math.min(cur.l, b.l); cur.c = b.c; cur.v += b.v;
      }
    }
    if (cur) out.push(cur);
    return out;
  }
  function toMinutes(bars, n) {
    const step = n * 60000;
    return aggregate(bars, (b) => Math.floor((b.ms + KST * 1000) / step),
      (b, k) => { const ms = k * step - KST * 1000; return { ms, t: ms / 1000 + KST }; });
  }
  function toWeekly(bars) {
    return aggregate(bars, (b) => {
      const d = new Date(b.ms); const dow = (d.getUTCDay() + 6) % 7; // 월요일 = 0
      return new Date(b.ms - dow * 86400000).toISOString().slice(0, 10);
    }, (b) => ({}));
  }
  const toMonthly = (bars) => aggregate(bars, (b) => b.day.slice(0, 7), () => ({}));

  // ---------- 원격 (중계 서버 경유) ----------
  async function viaProxy(url, decode) {
    const p = getProxy();
    if (!p) throw new NeedProxyError();
    const full = p + (p.includes("?") ? "&" : "?") + "url=" + encodeURIComponent(url);
    const r = await fetch(full);
    if (!r.ok) throw new Error(`시세 서버 응답 오류 (${r.status})`);
    if (decode === "euc-kr") return new TextDecoder("euc-kr").decode(await r.arrayBuffer());
    return decode === "json" ? r.json() : r.text();
  }
  async function naverDaily(code, count = 2500) {
    const xml = await viaProxy(`https://fchart.stock.naver.com/sise.nhn?symbol=${code}&timeframe=day&count=${count}&requestType=0`, "euc-kr");
    const rows = [];
    const re = /data="(\d{4})(\d{2})(\d{2})\|([\d.]+)\|([\d.]+)\|([\d.]+)\|([\d.]+)\|(\d+)"/g;
    let m;
    while ((m = re.exec(xml))) {
      const v = +m[8];
      if (v === 0) continue; // 거래정지일
      rows.push([`${m[1]}-${m[2]}-${m[3]}`, +m[4], +m[5], +m[6], +m[7], v]);
    }
    if (!rows.length) throw new Error("네이버에서 시세를 찾지 못했어요");
    return fromDailyRows(rows);
  }
  async function yahoo(sym, interval, range) {
    const j = await viaProxy(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?interval=${interval}&range=${range}&includePrePost=false`, "json");
    const r = j.chart && j.chart.result && j.chart.result[0];
    if (!r || !r.timestamp) throw new Error("야후에서 시세를 찾지 못했어요");
    const q = r.indicators.quote[0], out = [];
    r.timestamp.forEach((u, i) => {
      const o = q.open[i], h = q.high[i], l = q.low[i], c = q.close[i];
      if (o == null || h == null || l == null || c == null) return;
      out.push([u, o, h, l, c, q.volume[i] || 0]);
    });
    if (interval === "1d" || interval === "1wk") {
      const off = (r.meta && r.meta.gmtoffset) || 0;
      return fromDailyRows(out.map(([u, ...rest]) => [new Date((u + off) * 1000).toISOString().slice(0, 10), ...rest]));
    }
    return fromIntradayRows(out);
  }

  // ---------- 공개 함수 ----------
  // 순위 화면 자료(시총 상위 300, 최근 6개월 일봉) — 중계 서버 없이도 볼 수 있게
  let rankBars = null; const fromRank = new Set();
  async function rankDaily(code) {
    if (!rankBars) rankBars = getJSON("data/rank/bars.json").catch(() => null);
    const B = await rankBars; if (!B || !B.bars[code]) return null;
    const rows = B.bars[code].map((x, i) => x && [B.days[i], ...x]).filter(Boolean);
    return rows.length ? fromDailyRows(rows) : null;
  }
  async function daily(sym, fresh) {
    const loc = bySym[sym];
    if (loc && !fresh) {
      const j = await getJSON(`data/daily/${loc.file}`);
      return fromDailyRows(j.bars);
    }
    if (isKR(sym)) {
      const code = sym.split(".")[0];
      try { const b = await naverDaily(code); fromRank.delete(sym); return b; }
      catch (e) {
        const r = await rankDaily(code);   // 중계 서버가 없거나 안 될 때
        if (r) { fromRank.add(sym); return r; }
        throw e;
      }
    }
    return yahoo(sym, "1d", "10y");
  }
  async function intraday(sym, iv, fresh) {
    const loc = bySym[sym];
    if (loc && loc.intraday && iv.min >= 5 && !fresh) {
      const j = await getJSON(`data/intraday/${loc.file}`);
      const base = fromIntradayRows(j.bars);
      return iv.min === 5 ? base : toMinutes(base, iv.min);
    }
    const map = { 1: ["1m", "5d"], 5: ["5m", "60d"], 15: ["15m", "60d"], 30: ["30m", "60d"], 60: ["60m", "730d"] };
    const [yi, yr] = map[iv.min];
    return yahoo(sym, yi, yr);
  }

  /** 봉 데이터. opts.fresh = true 면 저장본 대신 최신 시세를 원격에서 받음 */
  async function getBars(sym, ivId, opts = {}) {
    const iv = IV[ivId];
    const key = `${sym}|${ivId}|${opts.fresh ? 1 : 0}`;
    const hit = cache.get(key);
    if (hit && (!hit.remote || Date.now() - hit.at < 60000)) return hit.bars;
    const remote = opts.fresh || !bySym[sym] || (!iv.daily && (!bySym[sym].intraday || iv.min < 5));
    let bars;
    if (iv.daily) {
      // 주봉·월봉은 이미 받은 일봉을 묶어서 만듦
      const d = ivId === "1d" ? await daily(sym, opts.fresh) : await getBars(sym, "1d", opts);
      bars = ivId === "1d" ? d : ivId === "1w" ? toWeekly(d) : toMonthly(d);
    } else {
      bars = await intraday(sym, iv, opts.fresh);
    }
    // 차트 라이브러리는 시간이 겹치면 안 되므로 정리
    bars = bars.filter((b, i) => i === 0 || b.t !== bars[i - 1].t);
    cache.set(key, { bars, at: Date.now(), remote });
    return bars;
  }

  /** 현재가 요약 */
  async function quote(sym) {
    if (bySym[sym]) return bySym[sym];
    const b = await getBars(sym, "1d");
    const last = b[b.length - 1], prev = b[b.length - 2] || last, y = b.slice(-252);
    return {
      symbol: sym, name: info(sym).name, date: last.day, close: last.c, prevClose: prev.c,
      change: last.c - prev.c, changePct: (last.c / prev.c - 1) * 100,
      high52: Math.max(...y.map((x) => x.h)), low52: Math.min(...y.map((x) => x.l)), volume: last.v,
    };
  }

  return {
    INTERVALS, IV, init, search, info, getBars, quote, loadSymbols, getProxy, setProxy, isKR,
    get meta() { return meta; }, isLocal: (s) => !!bySym[s], fromRank: (s) => fromRank.has(s), hasLocalIntraday: (s) => !!(bySym[s] && bySym[s].intraday),
    kstDay, KST,
  };
})();
