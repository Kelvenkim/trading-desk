/* =========================================================
 * 백테스트 엔진 v2
 *  - 신호는 봉 종가로 판단, 체결은 다음 봉 시가 (미래 참조 방지)
 *  - 방향: 롱 / 숏 / 양방향(신호마다 뒤집기)
 *  - 비중: 전액 / 자산의 일정 비율 / ATR 위험 기준
 *  - 분할매수(물타기·불타기·신호 반복), 1차 익절 일부 매도
 *  - 손절·익절·트레일링은 봉 안에서 체결, 같은 봉에 둘 다 닿으면 손절 우선 (보수적)
 *  - 체결 규칙(선택): 한국 호가 단위, 상·하한가 체결 불가, 거래량 대비 주문 한도
 * bars: [{t, ms, day, o, h, l, c, v}]
 * ========================================================= */
const BT = (() => {
  // ================= 지표 =================
  const sma = (a, n) => {
    const out = new Array(a.length).fill(NaN);
    let s = 0;
    for (let i = 0; i < a.length; i++) {
      s += a[i];
      if (i >= n) s -= a[i - n];
      if (i >= n - 1) out[i] = s / n;
    }
    return out;
  };
  const ema = (a, n) => {
    const out = new Array(a.length).fill(NaN);
    const k = 2 / (n + 1);
    let prev = NaN, start = a.findIndex((v) => !isNaN(v));
    if (start < 0) return out;
    for (let i = start; i < a.length; i++) {
      if (i === start + n - 1) {
        let s = 0;
        for (let j = start; j <= i; j++) s += a[j];
        prev = s / n; out[i] = prev;
      } else if (i >= start + n) {
        prev = a[i] * k + prev * (1 - k); out[i] = prev;
      }
    }
    return out;
  };
  // Wilder RSI (TradingView ta.rsi 와 같은 방식)
  const rsi = (a, n) => {
    const out = new Array(a.length).fill(NaN);
    let ag = 0, al = 0;
    for (let i = 1; i < a.length; i++) {
      const d = a[i] - a[i - 1], g = Math.max(d, 0), l = Math.max(-d, 0);
      if (i <= n) {
        ag += g / n; al += l / n;
        if (i === n) out[i] = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
      } else {
        ag = (ag * (n - 1) + g) / n; al = (al * (n - 1) + l) / n;
        out[i] = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
      }
    }
    return out;
  };
  // 모표준편차 (TradingView ta.stdev 와 같음)
  const stdev = (a, n) => {
    const m = sma(a, n), out = new Array(a.length).fill(NaN);
    for (let i = n - 1; i < a.length; i++) {
      let s = 0;
      for (let j = i - n + 1; j <= i; j++) s += (a[j] - m[i]) ** 2;
      out[i] = Math.sqrt(s / n);
    }
    return out;
  };
  // ATR (Wilder, TradingView ta.atr 와 같음)
  const atr = (b, n) => {
    const out = new Array(b.length).fill(NaN);
    let prev = NaN;
    for (let i = 0; i < b.length; i++) {
      const tr = i === 0 ? b[i].h - b[i].l : Math.max(b[i].h - b[i].l, Math.abs(b[i].h - b[i - 1].c), Math.abs(b[i].l - b[i - 1].c));
      if (i < n - 1) { prev = isNaN(prev) ? tr : prev + tr; continue; }
      if (i === n - 1) { prev = (prev + tr) / n; out[i] = prev; continue; }
      prev = (prev * (n - 1) + tr) / n; out[i] = prev;
    }
    return out;
  };
  // 직전 n개 봉(현재 봉 제외)의 최고/최저
  const prevHighest = (a, n) => {
    const out = new Array(a.length).fill(NaN);
    for (let i = n; i < a.length; i++) { let m = -Infinity; for (let j = i - n; j < i; j++) if (a[j] > m) m = a[j]; out[i] = m; }
    return out;
  };
  const prevLowest = (a, n) => {
    const out = new Array(a.length).fill(NaN);
    for (let i = n; i < a.length; i++) { let m = Infinity; for (let j = i - n; j < i; j++) if (a[j] < m) m = a[j]; out[i] = m; }
    return out;
  };
  const shift1 = (a) => a.map((_, i) => (i === 0 ? NaN : a[i - 1]));

  // ---------- VWAP ----------
  // ISO 주 번호 키 (주간 VWAP 초기화용)
  const weekKey = (ms) => { const d = new Date(ms + 9 * 3600e3); const dow = (d.getUTCDay() + 6) % 7; return new Date(d.getTime() - dow * 86400000).toISOString().slice(0, 10); };
  /**
   * kind: "session"(매일 초기화) | "week"(매주 초기화) | "rolling"(최근 n봉)
   * 반환: { vwap, sd } — sd는 VWAP 기준 거래량 가중 표준편차 (밴드용)
   */
  function vwapCalc(b, kind = "session", n = 20) {
    const N = b.length, vw = new Array(N).fill(NaN), sd = new Array(N).fill(NaN);
    const tp = b.map((x) => (x.h + x.l + x.c) / 3), vol = b.map((x) => (x.v > 0 ? x.v : 0));
    if (kind === "rolling") {
      let spv = 0, sv = 0, sp2v = 0, sp = 0;
      for (let i = 0; i < N; i++) {
        spv += tp[i] * vol[i]; sv += vol[i]; sp2v += tp[i] * tp[i] * vol[i]; sp += tp[i];
        if (i >= n) { spv -= tp[i - n] * vol[i - n]; sv -= vol[i - n]; sp2v -= tp[i - n] * tp[i - n] * vol[i - n]; sp -= tp[i - n]; }
        if (i >= n - 1) {
          vw[i] = sv > 0 ? spv / sv : sp / n;
          sd[i] = sv > 0 ? Math.sqrt(Math.max(0, sp2v / sv - vw[i] * vw[i])) : 0;
        }
      }
      return { vwap: vw, sd };
    }
    let key = null, spv = 0, sv = 0, sp2v = 0, sp = 0, cnt = 0;
    for (let i = 0; i < N; i++) {
      const k = kind === "week" ? weekKey(b[i].ms) : (b[i].day || String(b[i].t));
      if (k !== key) { key = k; spv = sv = sp2v = sp = 0; cnt = 0; }
      spv += tp[i] * vol[i]; sv += vol[i]; sp2v += tp[i] * tp[i] * vol[i]; sp += tp[i]; cnt++;
      vw[i] = sv > 0 ? spv / sv : sp / cnt;
      sd[i] = sv > 0 ? Math.sqrt(Math.max(0, sp2v / sv - vw[i] * vw[i])) : 0;
    }
    return { vwap: vw, sd };
  }

  // ---------- 종합 점수용 강세 조건 ----------
  const CONF_LIST = [
    { key: "trend", label: "큰 추세 (종가 > 긴 VWAP)" },
    { key: "vslope", label: "VWAP 기울기 상승" },
    { key: "spo", label: "SPO 0선 위" },
    { key: "ema", label: "이평 정배열 (EMA 짧은 > 긴)" },
    { key: "brk", label: "최근 돌파 (직전 고점 위)" },
    { key: "vol", label: "거래량 증가 (평균 1.2배↑)" },
    { key: "rsi", label: "RSI 50~75 (힘 있되 과열 아님)" },
    { key: "wvwap", label: "중기 VWAP 위 (분봉 주간 / 일봉 20봉)" },
  ];
  /** 각 봉에서 8가지 강세 조건이 맞는지. short·long: 짧은·긴 기간(봉) */
  function confluence(b, short = 24, long = 240) {
    const n = b.length, c = b.map((x) => x.c), h = b.map((x) => x.h), v = b.map((x) => x.v);
    const intraday = b.length > 1 && b[1].ms - b[0].ms < 20 * 3600e3;
    const lv = vwapCalc(b, "rolling", long).vwap, sv = vwapCalc(b, "rolling", short).vwap;
    const mid = intraday ? vwapCalc(b, "week").vwap : vwapCalc(b, "rolling", 20).vwap;
    const spo = spoCalc(b, 20, 90).osc, ef = ema(c, 20), es = ema(c, 60), r = rsi(c, 14);
    const hh = prevHighest(h, short), va = shift1(sma(v, 20));
    const brk = c.map((x, i) => x > hh[i]);
    const out = {};
    out.trend = c.map((x, i) => x > lv[i]);
    out.vslope = sv.map((x, i) => i >= 3 && x > sv[i - 3]);
    out.spo = spo.map((x) => x > 0);
    out.ema = ef.map((x, i) => x > es[i]);
    out.brk = brk.map((_, i) => brk[i] || (i > 0 && brk[i - 1]) || (i > 1 && brk[i - 2]));
    out.vol = v.map((x, i) => va[i] > 0 && x > va[i] * 1.2);
    out.rsi = r.map((x) => x >= 50 && x <= 75);
    out.wvwap = c.map((x, i) => x > mid[i]);
    return out;
  }

  // ---------- 차트 구조: 스윙 고점·저점 ----------
  /**
   * 좌우 L봉보다 높은(낮은) 봉을 스윙 고점(저점)으로 봄. j봉의 스윙은 j+L봉 종가가 나와야 확정되므로
   * 반환 배열 confH[i], confL[i] 에는 'i봉까지 확정된' 스윙만 들어감 (미래 참조 없음).
   */
  function swings(b, L) {
    const n = b.length, hs = [], ls = [];
    const confH = new Array(n), confL = new Array(n);
    for (let i = 0; i < n; i++) {
      const j = i - L;
      if (j >= L) {
        let isH = true, isL = true;
        for (let k = j - L; k <= j + L; k++) {
          if (k === j) continue;
          if (b[k].h >= b[j].h) isH = false;
          if (b[k].l <= b[j].l) isL = false;
        }
        if (isH) hs.push({ i: j, p: b[j].h });
        if (isL) ls.push({ i: j, p: b[j].l });
      }
      confH[i] = hs.length; confL[i] = ls.length;
    }
    return { hs, ls, confH, confL };
  }
  // i봉 기준, 가격 px 바로 위의 확정된 스윙 고점(=다음 저항). 최근 lookback 봉 안에서만
  function nextResistance(sw, i, px, lookback, b) {
    let best = Infinity;
    for (let k = sw.confH[i] - 1; k >= 0; k--) {
      const h = sw.hs[k];
      if (i - h.i > lookback) break;
      if (h.p > px * 1.002 && h.p < best) best = h.p;
    }
    return best;
  }

  /**
   * 차트 매매 셋업
   *  돌파 후 되돌림 : 확정된 스윙 고점을 종가로 돌파 → K봉 안에 그 가격대까지 되돌림(저가가 저항선+허용폭 이내) 후
   *                  양봉으로 저항선 위에서 마감하면 매수. 손절은 되돌림 저점 − 여유폭
   *  추세 눌림목   : 최근 스윙 저점 2개·고점 2개가 모두 높아지는 상승 추세, EMA20 > EMA50,
   *                  저가가 EMA20(+허용폭)까지 눌린 뒤 전 봉 고가를 넘겨 마감하면 매수. 손절은 최근 3봉 저점 − 여유폭
   *  지지선 반등   : 확정된 스윙 저점(지지선) 근처까지 내려왔다가 전 봉 고가를 넘기며 지지선 위에서 마감하면 매수. 손절은 지지선 − 여유폭
   *  목표가: '다음 저항'이면 바로 위 스윙 고점(없으면 3R), 손익비(목표까지 거리 ÷ 손절 폭)가 minRR 미만이면 진입하지 않음
   */
  function chartSetup(b, p) {
    const n = b.length, L = p.pivot, a = atr(b, 14), c = b.map((x) => x.c);
    const e20 = ema(c, 20), e50 = ema(c, 50), s200 = sma(c, 200);
    const sw = swings(b, L);
    const entry = new Array(n).fill(false), exit = new Array(n).fill(false), plan = new Array(n).fill(null);
    const lookback = p.resLook || 250;
    const trendOK = (i) => (p.filter === "200일선 위에서만" ? c[i] > s200[i] : true) && (!p.mkt || p.mkt[i]);
    const mkPlan = (i, stop) => {
      const px = c[i], risk = px - stop;
      if (!(risk > 0) || risk / px > (p.maxStop || 15) / 100) return null;   // 손절 폭이 너무 크면 자리 아님
      let target;
      if (p.target === "다음 저항") {
        const r = nextResistance(sw, i, px, lookback, b);
        target = isFinite(r) ? r : px + 3 * risk;
      } else target = px + (p.target === "3R" ? 3 : 2) * risk;
      if ((target - px) / risk < p.minRR) return null;
      return { stop, target };
    };
    let lvl = NaN, brokeAt = -1, lastUsedH = -1;
    for (let i = 1; i < n; i++) {
      if (!isFinite(a[i])) continue;
      const tol = p.tol * a[i], buf = p.buf * a[i];
      let pl = null;
      if (p.setup === "돌파 후 되돌림") {
        // 아직 쓰지 않은 가장 최근 확정 고점을 종가로 돌파하면 대기 상태
        const hk = sw.confH[i] - 1;
        if (hk >= 0 && hk !== lastUsedH && c[i] > sw.hs[hk].p && c[i - 1] <= sw.hs[hk].p) { lvl = sw.hs[hk].p; brokeAt = i; lastUsedH = hk; }
        if (brokeAt >= 0 && i > brokeAt) {
          if (i - brokeAt > p.window || c[i] < lvl - tol) { brokeAt = -1; }
          else if (b[i].l <= lvl + tol && c[i] > lvl && c[i] > b[i].o && trendOK(i)) {
            let lo = Infinity; for (let k = brokeAt; k <= i; k++) lo = Math.min(lo, b[k].l);
            pl = mkPlan(i, Math.min(lo, lvl) - buf);
            if (pl) brokeAt = -1;
          }
        }
      } else if (p.setup === "추세 눌림목") {
        const lk = sw.confL[i], hk = sw.confH[i];
        const up = lk >= 2 && hk >= 2 && sw.ls[lk - 1].p > sw.ls[lk - 2].p && sw.hs[hk - 1].p > sw.hs[hk - 2].p && e20[i] > e50[i];
        if (up && b[i].l <= e20[i] + tol && c[i] > e20[i] && c[i] > b[i - 1].h && trendOK(i)) {
          const lo = Math.min(b[i].l, b[i - 1].l, i > 1 ? b[i - 2].l : Infinity);
          pl = mkPlan(i, lo - buf);
        }
      } else if (p.setup === "지지선 반등") {
        const lk = sw.confL[i];
        for (let k = lk - 1; k >= 0 && k >= lk - 5; k--) {
          const sp = sw.ls[k].p;
          if (i - sw.ls[k].i < 2 * L || i - sw.ls[k].i > lookback) continue;
          if (b[i].l <= sp + tol && b[i].l >= sp - tol && c[i] > sp && c[i] > b[i - 1].h && trendOK(i)) { pl = mkPlan(i, sp - buf); break; }
        }
      }
      if (pl) { entry[i] = true; plan[i] = pl; }
    }
    const lines = [{ name: "EMA20", data: e20, color: "#f2b84b" }];
    return { entry, exit, plan, lines, swings: sw };
  }

  // John Ehlers SuperSmoother (2극 버터워스 필터)
  const superSmoother = (a, len) => {
    const out = new Array(a.length).fill(NaN);
    const f = (1.414 * Math.PI) / len, a1 = Math.exp(-f), c2 = 2 * a1 * Math.cos(f), c3 = -a1 * a1, c1 = 1 - c2 - c3;
    for (let i = 0; i < a.length; i++) {
      if (i < 2) { out[i] = a[i]; continue; }
      out[i] = (c1 * (a[i] + a[i - 1])) / 2 + c2 * out[i - 1] + c3 * out[i - 2];
    }
    return out;
  };
  /**
   * Smooth Price Oscillator (BigBeluga 지표의 공개 설명을 바탕으로 재구성)
   *  osc  = (SuperSmoother(종가, 짧은 기간) − SuperSmoother(종가, 긴 기간)) ÷ 종가 표준편차(긴 기간)
   *  밴드 = ±EMA(k × osc 표준편차(밴드 기간), 밴드 기간)
   */
  function spoCalc(b, fast = 10, slow = 40, bandLen = 100, k = 2) {
    const c = b.map((x) => x.c);
    const f = superSmoother(c, fast), s = superSmoother(c, slow), sd = stdev(c, slow);
    const osc = c.map((_, i) => (sd[i] > 0 ? (f[i] - s[i]) / sd[i] : NaN));
    const clean = osc.map((v) => (isNaN(v) ? 0 : v));
    const sdo = stdev(clean, bandLen).map((v) => (isNaN(v) ? 0 : k * v));
    const band = ema(sdo, bandLen);
    return { osc, upper: band, lower: band.map((v) => -v), fast: f, slow: s };
  }

  // ================= 조건 조합용 지표 =================
  const IND = {
    close: { label: "종가", args: [] }, open: { label: "시가", args: [] }, high: { label: "고가", args: [] }, low: { label: "저가", args: [] },
    volume: { label: "거래량", args: [] },
    sma: { label: "이동평균", args: ["n"], def: { n: 20 } },
    ema: { label: "지수이동평균", args: ["n"], def: { n: 20 } },
    rsi: { label: "RSI", args: ["n"], def: { n: 14 } },
    bb_up: { label: "볼린저 상단", args: ["n", "k"], def: { n: 20, k: 2 } },
    bb_mid: { label: "볼린저 중심", args: ["n"], def: { n: 20 } },
    bb_low: { label: "볼린저 하단", args: ["n", "k"], def: { n: 20, k: 2 } },
    hh: { label: "직전 N봉 최고가", args: ["n"], def: { n: 20 } },
    ll: { label: "직전 N봉 최저가", args: ["n"], def: { n: 20 } },
    vol_sma: { label: "직전 N봉 평균 거래량", args: ["n"], def: { n: 20 } },
    roc: { label: "N봉 등락률(%)", args: ["n"], def: { n: 1 } },
    atr: { label: "ATR", args: ["n"], def: { n: 14 } },
    macd: { label: "MACD", args: [] }, macd_sig: { label: "MACD 시그널", args: [] }, macd_hist: { label: "MACD 히스토그램", args: [] },
    spo: { label: "SPO 오실레이터", args: ["n", "m"], def: { n: 10, m: 40 } },
    spo_up: { label: "SPO 과매수 밴드", args: ["n", "m"], def: { n: 10, m: 40 } },
    spo_low: { label: "SPO 과매도 밴드", args: ["n", "m"], def: { n: 10, m: 40 } },
    ss: { label: "SuperSmoother", args: ["n"], def: { n: 20 } },
    vwap: { label: "VWAP (당일)", args: [] },
    vwap_w: { label: "VWAP (주간)", args: [] },
    vwap_n: { label: "VWAP (N봉 이동)", args: ["n"], def: { n: 20 } },
    num: { label: "숫자", args: ["v"], def: { v: 0 } },
  };
  const OPS = { ">": "보다 크면", "<": "보다 작으면", ">=": "이상이면", "<=": "이하면", cross_up: "을 위로 뚫으면", cross_down: "을 아래로 뚫으면" };

  function series(b, s, cache) {
    const key = JSON.stringify(s);
    if (cache[key]) return cache[key];
    const c = b.map((x) => x.c), n = +s.n || 14, k = +s.k || 2;
    let out;
    switch (s.ind) {
      case "close": out = c; break;
      case "open": out = b.map((x) => x.o); break;
      case "high": out = b.map((x) => x.h); break;
      case "low": out = b.map((x) => x.l); break;
      case "volume": out = b.map((x) => x.v); break;
      case "sma": out = sma(c, n); break;
      case "ema": out = ema(c, n); break;
      case "rsi": out = rsi(c, n); break;
      case "bb_mid": out = sma(c, n); break;
      case "bb_up": case "bb_low": {
        const m = sma(c, n), sd = stdev(c, n), sg = s.ind === "bb_up" ? 1 : -1;
        out = m.map((v, i) => v + sg * k * sd[i]); break;
      }
      case "hh": out = prevHighest(b.map((x) => x.h), n); break;
      case "ll": out = prevLowest(b.map((x) => x.l), n); break;
      case "vol_sma": out = shift1(sma(b.map((x) => x.v), n)); break;
      case "roc": out = c.map((v, i) => (i >= n ? (v / c[i - n] - 1) * 100 : NaN)); break;
      case "atr": out = atr(b, n); break;
      case "macd": case "macd_sig": case "macd_hist": {
        const e26 = ema(c, 26), e12 = ema(c, 12), mm = e12.map((v, i) => v - e26[i]);
        const sg = ema(mm, 9);
        out = s.ind === "macd" ? mm : s.ind === "macd_sig" ? sg : mm.map((v, i) => v - sg[i]);
        break;
      }
      case "spo": case "spo_up": case "spo_low": {
        const r = spoCalc(b, +s.n || 10, +s.m || 40);
        out = s.ind === "spo" ? r.osc : s.ind === "spo_up" ? r.upper : r.lower; break;
      }
      case "ss": out = superSmoother(c, n); break;
      case "vwap": out = vwapCalc(b, "session").vwap; break;
      case "vwap_w": out = vwapCalc(b, "week").vwap; break;
      case "vwap_n": out = vwapCalc(b, "rolling", n).vwap; break;
      case "num": out = new Array(b.length).fill(+s.v || 0); break;
      default: out = new Array(b.length).fill(NaN);
    }
    cache[key] = out;
    return out;
  }
  function evalRules(b, group, cache) {
    const n = b.length, rules = (group && group.rules) || [];
    if (!rules.length) return new Array(n).fill(false);
    const res = rules.map((r) => {
      const A = series(b, r.a, cache), B0 = series(b, r.b, cache), m = r.mult == null || r.mult === "" ? 1 : +r.mult;
      const B = m === 1 ? B0 : B0.map((v) => v * m);
      return A.map((a, i) => {
        const x = B[i];
        if (isNaN(a) || isNaN(x)) return false;
        switch (r.op) {
          case ">": return a > x;
          case "<": return a < x;
          case ">=": return a >= x;
          case "<=": return a <= x;
          case "cross_up": return i > 0 && A[i - 1] <= B[i - 1] && a > x;
          case "cross_down": return i > 0 && A[i - 1] >= B[i - 1] && a < x;
        }
        return false;
      });
    });
    const any = group.logic === "OR";
    return new Array(n).fill(0).map((_, i) => (any ? res.some((r) => r[i]) : res.every((r) => r[i])));
  }
  function describeSpec(s) {
    const d = IND[s.ind] || { label: s.ind };
    if (s.ind === "num") return String(s.v);
    const a = d.args.map((k) => s[k]).filter((v) => v != null && v !== "");
    return a.length ? `${d.label}(${a.join(",")})` : d.label;
  }

  // ================= 전략 =================
  // signals(bars, p) → { entry: bool[], exit: bool[], lines: [{name, data, color}] }
  // 롱 기준으로 entry=매수 신호, exit=매도 신호. 숏 방향에서는 exit 신호로 숏 진입, entry 신호로 청산.
  const STRATEGIES = {
    ma_cross: {
      name: "이동평균 크로스",
      desc: "단기선이 장기선을 위로 뚫으면 매수, 아래로 뚫으면 매도. 추세 추종의 기본형.",
      params: [
        { key: "type", label: "이평 종류", type: "select", options: ["SMA", "EMA"], def: "SMA" },
        { key: "fast", label: "단기", def: 20, min: 2, max: 200 },
        { key: "slow", label: "장기", def: 60, min: 3, max: 400 },
      ],
      signals(b, p) {
        const c = b.map((x) => x.c), f = p.type === "EMA" ? ema : sma;
        const fa = f(c, p.fast), sl = f(c, p.slow);
        return {
          entry: c.map((_, i) => i > 0 && fa[i - 1] <= sl[i - 1] && fa[i] > sl[i]),
          exit: c.map((_, i) => i > 0 && fa[i - 1] >= sl[i - 1] && fa[i] < sl[i]),
          lines: [{ name: `${p.type}${p.fast}`, data: fa, color: "#f2b84b" }, { name: `${p.type}${p.slow}`, data: sl, color: "#7aa2ff" }],
        };
      },
    },
    rsi: {
      name: "RSI 역추세",
      desc: "RSI가 과매도선을 아래에서 위로 올라오면 매수, 과매수선을 넘으면 매도.",
      params: [
        { key: "period", label: "기간", def: 14, min: 2, max: 100 },
        { key: "low", label: "과매도", def: 30, min: 1, max: 50 },
        { key: "high", label: "과매수", def: 70, min: 50, max: 99 },
      ],
      signals(b, p) {
        const r = rsi(b.map((x) => x.c), p.period);
        return {
          entry: r.map((v, i) => i > 0 && r[i - 1] <= p.low && v > p.low),
          exit: r.map((v, i) => i > 0 && r[i - 1] <= p.high && v > p.high),
          lines: [],
        };
      },
    },
    bollinger: {
      name: "볼린저 박스권",
      desc: "종가가 하단 밴드 아래로 내려가면 매수, 중심선(또는 상단)을 넘으면 매도. 박스권 종목용.",
      params: [
        { key: "period", label: "기간", def: 20, min: 5, max: 200 },
        { key: "k", label: "표준편차 배수", def: 2, min: 0.5, max: 4, step: 0.1 },
        { key: "exitAt", label: "매도 기준", type: "select", options: ["중심선", "상단"], def: "중심선" },
      ],
      signals(b, p) {
        const c = b.map((x) => x.c), mid = sma(c, p.period), sd = stdev(c, p.period);
        const up = mid.map((m, i) => m + p.k * sd[i]), lo = mid.map((m, i) => m - p.k * sd[i]);
        const tgt = p.exitAt === "상단" ? up : mid;
        return {
          entry: c.map((v, i) => v < lo[i]),
          exit: c.map((v, i) => v > tgt[i]),
          lines: [{ name: "상단", data: up, color: "#8d98b3" }, { name: "중심", data: mid, color: "#f2b84b" }, { name: "하단", data: lo, color: "#8d98b3" }],
        };
      },
    },
    breakout: {
      name: "거래량 돌파 (급등 포착)",
      desc: "종가가 최근 N봉 최고가를 넘고, 거래량이 평균의 X배 이상이면 매수. 최근 M봉 최저가를 깨면 매도.",
      params: [
        { key: "lookback", label: "돌파 기준 봉 수", def: 20, min: 2, max: 250 },
        { key: "volLen", label: "거래량 평균 기간", def: 20, min: 2, max: 250 },
        { key: "volMult", label: "거래량 배수", def: 2, min: 1, max: 20, step: 0.1 },
        { key: "exitLen", label: "이탈 기준 봉 수", def: 10, min: 2, max: 250 },
      ],
      signals(b, p) {
        const h = b.map((x) => x.h), l = b.map((x) => x.l), c = b.map((x) => x.c), v = b.map((x) => x.v);
        const hh = prevHighest(h, p.lookback), ll = prevLowest(l, p.exitLen), va = shift1(sma(v, p.volLen));
        return {
          entry: c.map((x, i) => x > hh[i] && v[i] > va[i] * p.volMult),
          exit: c.map((x, i) => x < ll[i]),
          lines: [{ name: `${p.lookback}봉 최고`, data: hh, color: "#f0525c" }, { name: `${p.exitLen}봉 최저`, data: ll, color: "#3d8bfd" }],
        };
      },
    },
    spo: {
      name: "Smooth Price Oscillator",
      desc: "Ehlers SuperSmoother 두 개의 차이로 만든 오실레이터. 역추세: 과매도(-기준선 또는 밴드 아래)에서 다시 올라오면 매수. 추세: 0선을 위로 넘으면 매수, 아래로 내려가면 매도.",
      params: [
        { key: "mode", label: "사용법", type: "select", options: ["역추세", "추세"], def: "역추세" },
        { key: "fast", label: "짧은 기간", def: 10, min: 2, max: 200 },
        { key: "slow", label: "긴 기간", def: 40, min: 3, max: 400 },
        { key: "th", label: "기준선 (±)", def: 1, min: 0.1, max: 5, step: 0.1 },
        { key: "bandLen", label: "밴드 기간", def: 100, min: 10, max: 500 },
        { key: "k", label: "밴드 배수", def: 2, min: 0.5, max: 5, step: 0.1 },
        { key: "strength", label: "신호 세기", type: "select", options: ["일반", "강한 신호만"], def: "일반" },
        { key: "exitAt", label: "역추세 매도", type: "select", options: ["0선 회복", "과매수 반락"], def: "0선 회복" },
      ],
      signals(b, p) {
        const r = spoCalc(b, p.fast, p.slow, p.bandLen, p.k), o = r.osc, n = b.length;
        const crossUp = (i, lv) => i > 0 && o[i - 1] <= lv[i - 1] && o[i] > lv[i];
        const crossDn = (i, lv) => i > 0 && o[i - 1] >= lv[i - 1] && o[i] < lv[i];
        const cst = (v) => new Array(n).fill(v);
        let entry, exit;
        if (p.mode === "추세") {
          const z = cst(0);
          entry = o.map((_, i) => crossUp(i, z)); exit = o.map((_, i) => crossDn(i, z));
        } else {
          const lo = p.strength === "강한 신호만" ? r.lower : cst(-p.th);
          const hi = p.strength === "강한 신호만" ? r.upper : cst(p.th);
          entry = o.map((_, i) => crossUp(i, lo));
          exit = p.exitAt === "과매수 반락" ? o.map((_, i) => crossDn(i, hi)) : o.map((_, i) => crossUp(i, cst(0)));
        }
        return { entry, exit, lines: [{ name: `SS${p.fast}`, data: r.fast, color: "#f2b84b" }, { name: `SS${p.slow}`, data: r.slow, color: "#7aa2ff" }] };
      },
    },
    vwap: {
      name: "VWAP 추세 전환",
      desc: "거래량 가중 평균가(VWAP)를 기준으로 추세가 바뀔 때 사고팔아요. 교차: 종가가 VWAP 위로 올라서면 매수, 아래로 내려가면 매도. 기울기: VWAP이 오르기 시작하면 매수, 내리기 시작하면 매도. 당일 VWAP은 분봉 단타용, 주간은 1시간봉, N봉 이동은 일봉에 맞아요.",
      params: [
        { key: "kind", label: "VWAP 종류", type: "select", options: ["당일", "주간", "N봉 이동"], def: "당일" },
        { key: "n", label: "N봉 (이동일 때)", def: 20, min: 2, max: 500 },
        { key: "mode", label: "전환 신호", type: "select", options: ["교차", "기울기"], def: "교차" },
        { key: "buf", label: "여유폭 %", def: 0, min: 0, max: 5, step: 0.05 },
        { key: "confirm", label: "확인 봉 수", def: 1, min: 1, max: 10 },
        { key: "slopeN", label: "기울기 비교 봉", def: 3, min: 1, max: 50 },
        { key: "trend", label: "큰 추세 필터", type: "select", options: ["없음", "이동 VWAP 위에서만 매수"], def: "없음" },
        { key: "trendN", label: "필터 N봉", def: 100, min: 5, max: 1000 },
        { key: "noLate", label: "장 막판 진입 금지 (봉)", def: 0, min: 0, max: 30 },
      ],
      signals(b, p) {
        const kind = p.kind === "주간" ? "week" : p.kind === "N봉 이동" ? "rolling" : "session";
        const { vwap: v } = vwapCalc(b, kind, p.n), n = b.length, c = b.map((x) => x.c);
        const up = (i) => c[i] > v[i] * (1 + p.buf / 100), dn = (i) => c[i] < v[i] * (1 - p.buf / 100);
        const tf = p.trend !== "없음" ? vwapCalc(b, "rolling", p.trendN).vwap : null;
        // 장 막판 N봉 안에는 새로 진입하지 않음 (당일 청산 단타에서 바로 청산되는 진입 방지)
        const late = new Array(n).fill(false);
        if (p.noLate > 0) {
          let cntBack = 0;
          for (let i = n - 1; i >= 0; i--) { if (i === n - 1 || (b[i].day || b[i].t) !== (b[i + 1].day || b[i + 1].t)) cntBack = 0; late[i] = cntBack < p.noLate; cntBack++; }
        }
        const entry = new Array(n).fill(false), exit = new Array(n).fill(false);
        let runUp = 0, runDn = 0;
        for (let i = 1; i < n; i++) {
          if (isNaN(v[i])) continue;
          let bull, bear;
          if (p.mode === "기울기") {
            const k = Math.max(1, p.slopeN), prev = v[i - k];
            bull = isFinite(prev) && v[i] > prev * (1 + p.buf / 100); bear = isFinite(prev) && v[i] < prev * (1 - p.buf / 100);
          } else { bull = up(i); bear = dn(i); }
          runUp = bull ? runUp + 1 : 0; runDn = bear ? runDn + 1 : 0;
          // 같은 상태가 confirm 봉 이어진 첫 순간에만 신호 (전환 시점)
          if (runUp === p.confirm && !late[i] && (!tf || (isFinite(tf[i]) && c[i] > tf[i]))) entry[i] = true;
          if (runDn === p.confirm) exit[i] = true;
        }
        const lines = [{ name: `VWAP(${p.kind})`, data: v, color: "#4fd1a5" }];
        if (tf) lines.push({ name: `VWAP ${p.trendN}봉`, data: tf, color: "#c792ea" });
        return { entry, exit, lines };
      },
    },
    chart: {
      name: "차트 매매 (지지·저항 셋업)",
      desc: "차트 트레이더처럼 자리를 골라 들어가요. 손절은 차트 구조(되돌림 저점·지지선 아래), 목표는 다음 저항선. 목표까지 거리가 손절 폭의 '최소 손익비'배 이상일 때만 진입. 비중 방식을 'ATR 위험 기준'으로 두면 손절 시 계좌의 '1회 위험 %'만 잃도록 수량을 맞춰요.",
      params: [
        { key: "setup", label: "셋업", type: "select", options: ["돌파 후 되돌림", "추세 눌림목", "지지선 반등"], def: "돌파 후 되돌림" },
        { key: "pivot", label: "스윙 강도 (좌우 봉)", def: 5, min: 2, max: 20 },
        { key: "window", label: "되돌림 대기 봉", def: 10, min: 2, max: 60 },
        { key: "tol", label: "가격대 허용폭 (ATR 배수)", def: 0.5, min: 0, max: 3, step: 0.1 },
        { key: "buf", label: "손절 여유폭 (ATR 배수)", def: 0.3, min: 0, max: 3, step: 0.1 },
        { key: "target", label: "목표가", type: "select", options: ["다음 저항", "2R", "3R"], def: "다음 저항" },
        { key: "minRR", label: "최소 손익비", def: 2, min: 0.5, max: 10, step: 0.5 },
        { key: "maxStop", label: "최대 손절 폭 %", def: 15, min: 1, max: 50 },
        { key: "filter", label: "추세 필터", type: "select", options: ["없음", "200일선 위에서만"], def: "200일선 위에서만" },
      ],
      signals(b, p) { return chartSetup(b, p); },
    },
    confluence: {
      name: "종합 점수 (여러 조건 합의)",
      desc: "8가지 강세 조건 중 몇 개가 동시에 맞는지 점수로 세요. 점수가 '매수 점수' 이상이 되는 순간 사고, '매도 점수' 이하로 떨어지면 팔아요. 끈 조건은 점수에서 빠져요.",
      params: [
        { key: "buyScore", label: "매수 점수 (이상)", def: 6, min: 1, max: 8 },
        { key: "sellScore", label: "매도 점수 (이하)", def: 3, min: 0, max: 7 },
        { key: "short", label: "짧은 기간 (봉)", def: 24, min: 3, max: 200 },
        { key: "long", label: "긴 기간 (봉)", def: 240, min: 20, max: 1000 },
        ...CONF_LIST.map((x) => ({ key: "use_" + x.key, label: x.label, type: "select", options: ["켬", "끔"], def: "켬" })),
      ],
      signals(b, p) {
        const cf = confluence(b, p.short, p.long), n = b.length;
        const keys = CONF_LIST.map((x) => x.key).filter((k) => p["use_" + k] !== "끔");
        const score = new Array(n).fill(0).map((_, i) => keys.reduce((s, k) => s + (cf[k][i] ? 1 : 0), 0));
        const entry = score.map((s, i) => i > 0 && s >= p.buyScore && score[i - 1] < p.buyScore);
        const exit = score.map((s) => s <= p.sellScore);
        return { entry, exit, lines: [{ name: `VWAP ${p.long}봉`, data: vwapCalc(b, "rolling", p.long).vwap, color: "#c792ea" }], score, cf };
      },
    },
    custom: {
      name: "직접 만들기 (조건 조합)",
      desc: "지표와 조건을 직접 골라 매수·매도 규칙을 만들어요. 각 묶음 안에서 '모두(AND)' 또는 '하나라도(OR)' 만족하면 신호.",
      params: [],
      signals(b, p) {
        const cache = {}, rules = p.rules || {};
        const entry = evalRules(b, rules.entry, cache), exit = evalRules(b, rules.exit, cache);
        const lines = [];
        const colors = ["#f2b84b", "#7aa2ff", "#c792ea", "#4fd1a5"];
        const seen = new Set();
        for (const g of [rules.entry, rules.exit]) for (const r of (g && g.rules) || []) for (const s of [r.a, r.b]) {
          // 가격 단위 지표만 차트에 표시
          if (["sma", "ema", "bb_up", "bb_mid", "bb_low", "hh", "ll", "ss", "vwap", "vwap_w", "vwap_n"].includes(s.ind)) {
            const key = describeSpec(s);
            if (seen.has(key)) continue;
            seen.add(key);
            lines.push({ name: key, data: series(b, s, cache), color: colors[lines.length % colors.length] });
          }
        }
        return { entry, exit, lines };
      },
    },
  };

  // ================= 한국 시장 규칙 =================
  // 2023년 1월부터 코스피·코스닥 공통 호가 단위
  function tickSize(px, etf) {
    if (etf) return 5;
    if (px < 2000) return 1;
    if (px < 5000) return 5;
    if (px < 20000) return 10;
    if (px < 50000) return 50;
    if (px < 200000) return 100;
    if (px < 500000) return 500;
    return 1000;
  }
  function roundTick(px, up, etf) {
    const t = tickSize(px, etf);
    return (up ? Math.ceil(px / t - 1e-9) : Math.floor(px / t + 1e-9)) * t;
  }
  // 각 봉의 전일 종가 (일봉은 직전 봉, 분봉은 직전 거래일 마지막 봉)
  function prevDayClose(b) {
    const out = new Array(b.length).fill(NaN);
    let lastClose = NaN, prevDay = null, carry = NaN;
    for (let i = 0; i < b.length; i++) {
      const d = b[i].day || String(b[i].t);
      if (d !== prevDay) { carry = lastClose; prevDay = d; }
      out[i] = carry;
      lastClose = b[i].c;
    }
    return out;
  }

  // ================= 엔진 =================
  const DEFAULTS = {
    capital: 10000000, buyFee: 0.015, sellFee: 0.215, slip: 0.05, borrowFee: 0,
    stopLoss: 0, takeProfit: 0, trailing: 0, maxHold: 0, dayClose: false, dayKey: null,
    direction: "long", sizing: "all", sizePct: 100, riskPct: 1, atrMult: 2,
    pyrN: 1, pyrMode: "down", pyrPct: 3, tp1Pct: 0, tp1Frac: 50,
    tick: false, etf: false, limit: false, volCap: 0,
    beAfterR: 0,   // 수익이 손절 폭의 N배(R)에 닿으면 손절가를 본전으로 (차트 셋업용)
  };

  function run(bars, strategyId, p, o) {
    const opt = { ...DEFAULTS, ...o };
    const S = STRATEGIES[strategyId];
    const sig = S.signals(bars, p);
    const n = bars.length;
    const A = opt.sizing === "risk" ? atr(bars, 20) : null;
    const pdc = opt.limit ? prevDayClose(bars) : null;
    const dirOK = (side) => opt.direction === "both" || (side > 0 ? opt.direction === "long" : opt.direction === "short");

    let cash = opt.capital, qty = 0, avg = 0, entryIdx = -1, lastFill = 0, tranches = 0, unit = 0, peak = 0, trough = 0, tp1Done = false;
    let trade = null, pending = null, blocked = 0, capped = 0, skippedGap = 0;
    let tStop = NaN, tTarget = NaN, tRisk = NaN;   // 차트 셋업이 넘겨준 이번 거래의 손절가·목표가·1R 폭
    const equity = new Array(n), trades = [], fills = [];

    const mark = (i) => cash + qty * bars[i].c;

    function startTrade(i, side) {
      trade = { side, entryIdx: i, flow: 0, invested: 0, inQty: 0, inVal: 0, outQty: 0, outVal: 0, adds: 0, partial: false };
    }
    function closeTrade(i, reason) {
      const t = trade;
      trades.push({
        side: t.side, entryIdx: t.entryIdx, exitIdx: i, bars: i - t.entryIdx,
        entryPx: t.inVal / t.inQty, exitPx: t.outQty ? t.outVal / t.outQty : NaN,
        pnl: t.flow, ret: t.invested ? (t.flow / t.invested) * 100 : 0, reason, adds: t.adds, partial: t.partial,
        r: t.riskCash > 0 ? t.flow / t.riskCash : NaN, stopPx: t.stopPx, targetPx: t.targetPx,
      });
      trade = null; entryIdx = -1; tranches = 0; tp1Done = false; tStop = tTarget = tRisk = NaN;
    }

    /** 주문 체결. want: 부호 있는 수량(+매수, −매도). 반환: 실제 체결 수량(부호 포함) */
    function exec(i, want, refPx, kind) {
      const b = bars[i], buy = want > 0;
      if (opt.limit && isFinite(pdc[i])) {
        // 상한가 근처에서는 매수 불가, 하한가 근처에서는 매도 불가 (잠긴 호가 가정)
        if (buy && refPx >= pdc[i] * 1.295) { blocked++; return 0; }
        if (!buy && refPx <= pdc[i] * 0.705) { blocked++; return 0; }
      }
      let px = refPx * (1 + (buy ? 1 : -1) * opt.slip / 100);
      if (opt.tick) px = roundTick(px, buy, opt.etf);
      let q = Math.abs(want);
      if (opt.volCap > 0) { const cap = b.v * opt.volCap / 100; if (q > cap) { q = cap; capped++; } }
      if (opt.tick) q = Math.floor(q + 1e-9);
      if (!(q > 0)) return 0;
      const notional = q * px, fee = notional * (buy ? opt.buyFee : opt.sellFee) / 100;
      const delta = buy ? -notional - fee : notional - fee;
      cash += delta;
      const sq = buy ? q : -q;
      const opening = qty === 0 || Math.sign(qty) === Math.sign(sq);
      if (opening) {
        avg = (avg * Math.abs(qty) + px * q) / (Math.abs(qty) + q);
        trade.inQty += q; trade.inVal += px * q;
      } else {
        trade.outQty += q; trade.outVal += px * q;
      }
      qty += sq;
      if (Math.abs(qty) < 1e-9) qty = 0;
      trade.flow += delta;
      trade.invested = Math.max(trade.invested, Math.abs(qty) * avg);
      fills.push({ i, buy, px, q, kind });
      lastFill = px;
      return sq;
    }
    function targetUnit(i, refPx) {
      const eq = cash + qty * refPx;
      let notional;
      if (opt.sizing === "fixed") notional = eq * opt.sizePct / 100;
      else if (opt.sizing === "risk" && isFinite(tStop) && tStop < refPx) {
        // 차트 손절가까지의 거리로 수량 결정: 손절되면 계좌의 riskPct%만 잃게
        const dist = (refPx * (1 + opt.slip / 100) - tStop * (1 - opt.slip / 100)) / refPx;
        notional = Math.min(eq * opt.riskPct / 100 / dist, eq);
      } else if (opt.sizing === "risk") {
        const a = A[i - 1] || A[i];
        const dist = isFinite(a) && a > 0 ? (opt.atrMult * a) / refPx : NaN;
        notional = isFinite(dist) ? Math.min(eq * opt.riskPct / 100 / dist, eq) : eq * opt.riskPct / 100 * 10;
      } else notional = eq;
      return notional / Math.max(1, opt.pyrN);
    }
    function open(i, side, refPx, plan) {
      tStop = plan && isFinite(plan.stop) ? plan.stop : NaN;
      tTarget = plan && isFinite(plan.target) ? plan.target : NaN;
      // 시가가 이미 손절가 아래(갭 하락)거나 목표가 위(갭 상승)면 자리가 무너진 것 → 진입하지 않음
      if (side > 0 && ((isFinite(tStop) && refPx <= tStop) || (isFinite(tTarget) && refPx >= tTarget))) { skippedGap++; tStop = tTarget = NaN; return false; }
      startTrade(i, side);
      unit = targetUnit(i, refPx);
      // 롱은 수수료·슬리피지까지 포함해 현금 안에서 살 수 있는 수량
      const q = side > 0 ? unit / (refPx * (1 + opt.slip / 100) * (1 + opt.buyFee / 100)) : unit / refPx;
      const got = exec(i, side * q, refPx, "open");
      if (!got) { trade = null; tStop = tTarget = NaN; return false; }
      entryIdx = i; tranches = 1; peak = refPx; trough = refPx; tp1Done = false;
      tRisk = isFinite(tStop) ? avg - tStop : NaN;
      trade.stopPx = tStop; trade.targetPx = tTarget;
      trade.riskCash = isFinite(tRisk) ? Math.abs(qty) * (tRisk + avg * (opt.buyFee + opt.sellFee) / 100) : NaN;
      return true;
    }
    function closeAll(i, refPx, reason) {
      if (!qty) return;
      exec(i, -qty, refPx, "close");
      if (!qty) closeTrade(i, reason);
    }

    for (let i = 0; i < n; i++) {
      const b = bars[i];
      // 1) 전 봉 신호를 이번 봉 시가에 체결
      if (pending && i > 0) {
        const pd = pending; pending = null;
        if (pd.kind === "close") closeAll(i, b.o, "신호");
        else if (pd.kind === "reverse") { closeAll(i, b.o, "신호(전환)"); if (!qty) open(i, pd.side, b.o); }
        else if (pd.kind === "open" && !qty) open(i, pd.side, b.o, pd.plan);
        else if (pd.kind === "add" && qty && tranches < opt.pyrN) {
          const side = Math.sign(qty);
          if (exec(i, side * unit / b.o, b.o, "add")) { tranches++; trade.adds++; }
        }
      }
      // 숏 대주 수수료 (보유 시간만큼)
      if (qty < 0 && opt.borrowFee > 0 && i > 0) {
        const fee = Math.abs(qty) * b.c * opt.borrowFee / 100 * (b.ms - bars[i - 1].ms) / (365 * 86400000);
        cash -= fee; trade.flow -= fee;
      }
      // 2) 봉 안에서 손절 / 1차 익절 / 익절
      if (qty) {
        const L = qty > 0;
        const slPx = opt.stopLoss > 0 ? avg * (1 - (L ? 1 : -1) * opt.stopLoss / 100) : NaN;
        const trPx = opt.trailing > 0 ? (L ? peak * (1 - opt.trailing / 100) : trough * (1 + opt.trailing / 100)) : NaN;
        const stPx = L && isFinite(tStop) ? tStop : NaN;
        const stopPx = L ? Math.max(isNaN(slPx) ? -Infinity : slPx, isNaN(trPx) ? -Infinity : trPx, isNaN(stPx) ? -Infinity : stPx)
                         : Math.min(isNaN(slPx) ? Infinity : slPx, isNaN(trPx) ? Infinity : trPx);
        const hitStop = L ? b.l <= stopPx : b.h >= stopPx;
        if (isFinite(stopPx) && hitStop) {
          const px = L ? Math.min(b.o, stopPx) : Math.max(b.o, stopPx);
          const isTrail = !isNaN(trPx) && (isNaN(slPx) || (L ? trPx > slPx : trPx < slPx)) && (isNaN(stPx) || trPx > stPx);
          const isStruct = !isNaN(stPx) && stopPx === stPx;
          closeAll(i, px, isStruct ? (isFinite(tRisk) && stPx >= avg - 1e-9 ? "본전 손절" : "차트 손절") : isTrail ? "트레일링" : "손절");
        }
        if (qty && L && isFinite(tTarget) && b.h >= tTarget) closeAll(i, Math.max(b.o, tTarget), "목표가");
        if (qty && opt.tp1Pct > 0 && !tp1Done) {
          const tp1 = avg * (1 + (L ? 1 : -1) * opt.tp1Pct / 100);
          if (L ? b.h >= tp1 : b.l <= tp1) {
            const px = L ? Math.max(b.o, tp1) : Math.min(b.o, tp1);
            if (exec(i, -qty * opt.tp1Frac / 100, px, "tp1")) { tp1Done = true; trade.partial = true; if (!qty) closeTrade(i, "1차 익절"); }
          }
        }
        if (qty && opt.takeProfit > 0) {
          const tp = avg * (1 + (L ? 1 : -1) * opt.takeProfit / 100);
          if (L ? b.h >= tp : b.l <= tp) closeAll(i, L ? Math.max(b.o, tp) : Math.min(b.o, tp), "익절");
        }
        if (qty) {
          peak = Math.max(peak, b.h); trough = Math.min(trough, b.l);
          // 1R 등 일정 수익에 닿으면 다음 봉부터 손절가를 본전으로
          if (L && opt.beAfterR > 0 && isFinite(tRisk) && tRisk > 0 && peak >= avg + opt.beAfterR * tRisk) tStop = Math.max(tStop, avg);
        }
      }
      // 3) 보유기간 초과 / 장 마감 청산 (종가)
      const lastOfDay = opt.dayClose && opt.dayKey && (i === n - 1 || opt.dayKey(i) !== opt.dayKey(i + 1));
      if (qty && opt.maxHold > 0 && i - entryIdx >= opt.maxHold) closeAll(i, b.c, "보유기간");
      if (qty && lastOfDay) closeAll(i, b.c, "당일청산");

      // 4) 이번 봉 종가 신호 → 다음 봉 시가에 체결
      if (i < n - 1 && !lastOfDay) {
        const up = sig.entry[i], dn = sig.exit[i];
        if (qty > 0) {
          if (dn) pending = dirOK(-1) ? { kind: "reverse", side: -1 } : { kind: "close" };
        } else if (qty < 0) {
          if (up) pending = dirOK(1) ? { kind: "reverse", side: 1 } : { kind: "close" };
        } else {
          if (up && dirOK(1)) pending = { kind: "open", side: 1, plan: sig.plan ? sig.plan[i] : null };
          else if (dn && dirOK(-1)) pending = { kind: "open", side: -1 };
        }
        // 분할매수
        if (!pending && qty && opt.pyrN > 1 && tranches < opt.pyrN) {
          const L = qty > 0, c = b.c;
          const add = opt.pyrMode === "signal" ? (L ? up : dn)
            : opt.pyrMode === "down" ? (L ? c <= lastFill * (1 - opt.pyrPct / 100) : c >= lastFill * (1 + opt.pyrPct / 100))
            : (L ? c >= lastFill * (1 + opt.pyrPct / 100) : c <= lastFill * (1 - opt.pyrPct / 100));
          if (add) pending = { kind: "add" };
        }
      }
      equity[i] = mark(i);
    }

    let openPos = null;
    if (qty && trade) {
      const last = bars[n - 1];
      openPos = { side: Math.sign(qty), entryIdx: trade.entryIdx, entryPx: trade.inVal / trade.inQty, lastPx: last.c, qty, stopPx: tStop, targetPx: tTarget,
        ret: trade.invested ? ((trade.flow + qty * last.c) / trade.invested) * 100 : 0 };
    }
    const st = stats(bars, equity, trades, opt, openPos);
    st.blocked = blocked; st.capped = capped; st.skippedGap = skippedGap;
    const rs = trades.map((t) => t.r).filter((v) => isFinite(v));
    st.avgR = rs.length ? rs.reduce((a, v) => a + v, 0) / rs.length : null;
    return { equity, trades, open: openPos, lines: sig.lines, fills, stats: st };
  }

  // ================= 성과 지표 =================
  function stats(bars, eq, trades, opt, open) {
    const n = bars.length, cap = opt.capital;
    const final = eq[n - 1];
    const rets = eq.map((v, i) => (i === 0 ? v / cap - 1 : v / eq[i - 1] - 1));
    let peak = cap, mdd = 0, ddLen = 0, maxDdLen = 0;
    const dd = eq.map((v) => {
      if (v >= peak) { peak = v; ddLen = 0; } else { ddLen++; maxDdLen = Math.max(maxDdLen, ddLen); }
      const d = v / peak - 1; mdd = Math.min(mdd, d); return d * 100;
    });
    const years = Math.max((bars[n - 1].ms - bars[0].ms) / (365.25 * 86400000), 1 / 365);
    const bpy = n / years;
    const mean = rets.reduce((s, r) => s + r, 0) / n;
    const sd = Math.sqrt(rets.reduce((s, r) => s + (r - mean) ** 2, 0) / n);
    const dsd = Math.sqrt(rets.reduce((s, r) => s + Math.min(r, 0) ** 2, 0) / n);
    const totalRet = final / cap - 1;
    const cagr = years >= 0.25 && final > 0 ? Math.pow(final / cap, 1 / years) - 1 : null;
    const wins = trades.filter((t) => t.pnl > 0), losses = trades.filter((t) => t.pnl <= 0);
    const gw = wins.reduce((s, t) => s + t.pnl, 0), gl = -losses.reduce((s, t) => s + t.pnl, 0);
    let streak = 0, maxLoseStreak = 0;
    trades.forEach((t) => { if (t.pnl <= 0) { streak++; maxLoseStreak = Math.max(maxLoseStreak, streak); } else streak = 0; });
    // 보유 노출(봉 기준)
    const held = trades.reduce((s, t) => s + t.bars + 1, 0) + (open ? n - open.entryIdx : 0);
    // 월별 수익률
    const monthly = {};
    let prevEq = cap, prevKey = null;
    for (let i = 0; i < n; i++) {
      const key = (bars[i].day || String(bars[i].t)).slice(0, 7);
      if (prevKey && key !== prevKey) { monthly[prevKey] = (eq[i - 1] / prevEq - 1) * 100; prevEq = eq[i - 1]; }
      prevKey = key;
    }
    if (prevKey) monthly[prevKey] = (eq[n - 1] / prevEq - 1) * 100;
    // 일별 손익 (그날 자산 변화). 포지션 없이 그대로인 날은 '쉰 날'로 따로 셈
    const daily = [];
    let dPrev = cap;
    for (let i = 0; i < n; i++) {
      const last = i === n - 1 || (bars[i].day || bars[i].t) !== (bars[i + 1].day || bars[i + 1].t);
      if (last) { daily.push((eq[i] / dPrev - 1) * 100); dPrev = eq[i]; }
    }
    const active = daily.filter((d) => Math.abs(d) > 1e-9);
    const avgWinR = wins.length ? wins.reduce((s, t) => s + t.ret, 0) / wins.length : 0;
    const avgLossR = losses.length ? losses.reduce((s, t) => s + t.ret, 0) / losses.length : 0;
    return {
      totalRet: totalRet * 100,
      cagr: cagr == null ? null : cagr * 100,
      mdd: mdd * 100,
      sharpe: sd > 0 ? (mean / sd) * Math.sqrt(bpy) : 0,
      sortino: dsd > 0 ? (mean / dsd) * Math.sqrt(bpy) : 0,
      calmar: cagr != null && mdd < 0 ? cagr / -mdd : null,
      trades: trades.length,
      winRate: trades.length ? (wins.length / trades.length) * 100 : 0,
      avgWin: avgWinR,
      avgLoss: avgLossR,
      payoff: avgLossR < 0 ? avgWinR / -avgLossR : (avgWinR > 0 ? Infinity : 0),
      expectancy: trades.length ? trades.reduce((s, t) => s + t.ret, 0) / trades.length : 0,
      days: daily.length, activeDays: active.length,
      posDays: active.length ? (active.filter((d) => d > 0).length / active.length) * 100 : 0,
      bestDay: active.length ? Math.max(...active) : 0, worstDay: active.length ? Math.min(...active) : 0,
      avgDay: active.length ? active.reduce((s, d) => s + d, 0) / active.length : 0,
      dailyRets: active,
      profitFactor: gl > 0 ? gw / gl : (gw > 0 ? Infinity : 0),
      maxLoseStreak,
      avgHold: trades.length ? trades.reduce((s, t) => s + t.bars, 0) / trades.length : 0,
      buyHold: (bars[n - 1].c / bars[0].o - 1) * 100,
      exposure: (held / n) * 100,
      maxDdBars: maxDdLen,
      final, drawdown: dd, monthly, bpy, years,
    };
  }

  // ================= Pine Script =================
  const pineSpec = (s) => {
    const n = +s.n || 14, k = +s.k || 2;
    switch (s.ind) {
      case "close": case "open": case "high": case "low": case "volume": return s.ind;
      case "sma": return `ta.sma(close, ${n})`;
      case "ema": return `ta.ema(close, ${n})`;
      case "rsi": return `ta.rsi(close, ${n})`;
      case "bb_mid": return `ta.sma(close, ${n})`;
      case "bb_up": return `(ta.sma(close, ${n}) + ${k} * ta.stdev(close, ${n}))`;
      case "bb_low": return `(ta.sma(close, ${n}) - ${k} * ta.stdev(close, ${n}))`;
      case "hh": return `ta.highest(high, ${n})[1]`;
      case "ll": return `ta.lowest(low, ${n})[1]`;
      case "vol_sma": return `ta.sma(volume, ${n})[1]`;
      case "roc": return `((close / close[${n}] - 1) * 100)`;
      case "atr": return `ta.atr(${n})`;
      case "macd": return `(ta.ema(close, 12) - ta.ema(close, 26))`;
      case "macd_sig": return `ta.ema(ta.ema(close, 12) - ta.ema(close, 26), 9)`;
      case "macd_hist": return `((ta.ema(close, 12) - ta.ema(close, 26)) - ta.ema(ta.ema(close, 12) - ta.ema(close, 26), 9))`;
      case "spo": return `spoOsc(${+s.n || 10}, ${+s.m || 40})`;
      case "spo_up": return `spoBand(${+s.n || 10}, ${+s.m || 40})`;
      case "spo_low": return `(-spoBand(${+s.n || 10}, ${+s.m || 40}))`;
      case "ss": return `ss(close, ${n})`;
      case "vwap": return "ta.vwap(hlc3)";
      case "vwap_w": return `ta.vwap(hlc3, timeframe.change("W"))`;
      case "vwap_n": return `(math.sum(hlc3 * volume, ${n}) / math.sum(volume, ${n}))`;
      case "num": return String(+s.v || 0);
    }
    return "na";
  };
  function pineRules(g) {
    const rules = (g && g.rules) || [];
    if (!rules.length) return "false";
    const parts = rules.map((r) => {
      const a = pineSpec(r.a), m = r.mult == null || r.mult === "" ? 1 : +r.mult;
      const b = m === 1 ? pineSpec(r.b) : `${pineSpec(r.b)} * ${m}`;
      if (r.op === "cross_up") return `ta.crossover(${a}, ${b})`;
      if (r.op === "cross_down") return `ta.crossunder(${a}, ${b})`;
      return `${a} ${r.op} ${b}`;
    });
    return parts.map((x) => `(${x})`).join(g.logic === "OR" ? " or " : " and ");
  }

  function pine(strategyId, p, o, title) {
    const opt = { ...DEFAULTS, ...o };
    const perSide = ((opt.buyFee + opt.sellFee) / 2 + opt.slip).toFixed(4);
    const qtyPct = opt.sizing === "fixed" ? opt.sizePct : 100;
    const L = [];
    const notes = [];
    if (opt.sizing === "risk") notes.push("ATR 위험 기준 비중은 Pine에서 고정 100%로 바뀌었어요.");
    if (opt.pyrN > 1 && opt.pyrMode !== "signal") notes.push("가격 기준 분할매수(물타기·불타기)는 Pine으로 옮기지 않았어요. 신호 반복 분할매수만 반영돼요.");
    if (opt.tick || opt.limit || opt.volCap) notes.push("호가 단위·상하한가·거래량 한도는 TradingView 체결 방식에 맡겼어요.");
    L.push("//@version=5");
    L.push(`strategy("${title.replace(/"/g, "'")}", overlay=true, initial_capital=${opt.capital},`);
    L.push(`     default_qty_type=strategy.percent_of_equity, default_qty_value=${(qtyPct / Math.max(1, opt.pyrN)).toFixed(2)},`);
    L.push(`     pyramiding=${Math.max(1, opt.pyrN)}, commission_type=strategy.commission.percent, commission_value=${perSide})`);
    notes.forEach((x) => L.push(`// 참고: ${x}`));
    L.push("");
    L.push("// ===== 설정 (0 = 사용 안 함) =====");
    L.push(`direction = input.string("${{ long: "롱", short: "숏", both: "양방향" }[opt.direction]}", "방향", options=["롱", "숏", "양방향"])`);
    L.push(`stopPct   = input.float(${opt.stopLoss}, "손절 %", minval=0)`);
    L.push(`tpPct     = input.float(${opt.takeProfit}, "익절 %", minval=0)`);
    L.push(`trailPct  = input.float(${opt.trailing}, "트레일링 %", minval=0)`);
    L.push(`tp1Pct    = input.float(${opt.tp1Pct}, "1차 익절 %", minval=0)`);
    L.push(`tp1Frac   = input.float(${opt.tp1Frac}, "1차 익절 비율 %", minval=1, maxval=100)`);
    L.push(`maxHold   = input.int(${opt.maxHold}, "최대 보유 봉 수", minval=0)`);
    L.push(`dayClose  = input.bool(${opt.dayClose ? "true" : "false"}, "장 마감 전 청산 (분봉)")`);
    L.push("");
    L.push("// ===== Ehlers SuperSmoother / Smooth Price Oscillator =====");
    L.push("ss(src, len) =>");
    L.push("    f = 1.414 * math.pi / len");
    L.push("    a1 = math.exp(-f)");
    L.push("    c2 = 2 * a1 * math.cos(f)");
    L.push("    c3 = -a1 * a1");
    L.push("    c1 = 1 - c2 - c3");
    L.push("    float s = na");
    L.push("    s := bar_index < 2 ? src : c1 * (src + src[1]) / 2 + c2 * nz(s[1], src) + c3 * nz(s[2], src)");
    L.push("    s");
    L.push("spoOsc(fast, slow) =>");
    L.push("    sd = ta.stdev(close, slow)");
    L.push("    sd > 0 ? (ss(close, fast) - ss(close, slow)) / sd : 0.0");
    L.push(`spoBand(fast, slow) => ta.ema(${strategyId === "spo" ? p.k : 2} * ta.stdev(spoOsc(fast, slow), ${strategyId === "spo" ? p.bandLen : 100}), ${strategyId === "spo" ? p.bandLen : 100})`);
    L.push("");
    L.push("// ===== 전략 =====");
    let entry = "false", exit = "false";
    if (strategyId === "ma_cross") {
      const f = p.type === "EMA" ? "ta.ema" : "ta.sma";
      L.push(`fast = ${f}(close, input.int(${p.fast}, "단기"))`, `slow = ${f}(close, input.int(${p.slow}, "장기"))`);
      L.push(`plot(fast, "단기", color.orange)`, `plot(slow, "장기", color.blue)`);
      entry = "ta.crossover(fast, slow)"; exit = "ta.crossunder(fast, slow)";
    } else if (strategyId === "rsi") {
      L.push(`r = ta.rsi(close, input.int(${p.period}, "RSI 기간"))`, `lo = input.float(${p.low}, "과매도")`, `hi = input.float(${p.high}, "과매수")`);
      entry = "ta.crossover(r, lo)"; exit = "ta.crossover(r, hi)";
    } else if (strategyId === "bollinger") {
      L.push(`len = input.int(${p.period}, "기간")`, `mult = input.float(${p.k}, "표준편차 배수")`);
      L.push(`basis = ta.sma(close, len)`, `dev = mult * ta.stdev(close, len)`, `upper = basis + dev`, `lower = basis - dev`);
      L.push(`plot(upper, "상단", color.gray)`, `plot(basis, "중심", color.orange)`, `plot(lower, "하단", color.gray)`);
      entry = "close < lower"; exit = p.exitAt === "상단" ? "close > upper" : "close > basis";
    } else if (strategyId === "breakout") {
      L.push(`hh = ta.highest(high, input.int(${p.lookback}, "돌파 기준 봉 수"))[1]`, `ll = ta.lowest(low, input.int(${p.exitLen}, "이탈 기준 봉 수"))[1]`);
      L.push(`va = ta.sma(volume, input.int(${p.volLen}, "거래량 평균 기간"))[1]`, `volMult = input.float(${p.volMult}, "거래량 배수")`);
      L.push(`plot(hh, "돌파선", color.red)`, `plot(ll, "이탈선", color.blue)`);
      entry = "close > hh and volume > va * volMult"; exit = "close < ll";
    } else if (strategyId === "spo") {
      L.push(`osc = spoOsc(${p.fast}, ${p.slow})`, `band = spoBand(${p.fast}, ${p.slow})`, `th = input.float(${p.th}, "기준선")`);
      L.push(`plot(ss(close, ${p.fast}), "SS 짧은", color.orange)`, `plot(ss(close, ${p.slow}), "SS 긴", color.blue)`);
      if (p.mode === "추세") { entry = "ta.crossover(osc, 0)"; exit = "ta.crossunder(osc, 0)"; }
      else {
        const lo = p.strength === "강한 신호만" ? "-band" : "-th", hi = p.strength === "강한 신호만" ? "band" : "th";
        entry = `ta.crossover(osc, ${lo})`; exit = p.exitAt === "과매수 반락" ? `ta.crossunder(osc, ${hi})` : "ta.crossover(osc, 0)";
      }
    } else if (strategyId === "vwap") {
      const vx = p.kind === "주간" ? `ta.vwap(hlc3, timeframe.change("W"))` : p.kind === "N봉 이동" ? `math.sum(hlc3 * volume, ${p.n}) / math.sum(volume, ${p.n})` : "ta.vwap(hlc3)";
      L.push(`vw = ${vx}`, `plot(vw, "VWAP", color.teal, 2)`, `buf = input.float(${p.buf}, "여유폭 %") / 100`, `conf = input.int(${p.confirm}, "확인 봉 수")`);
      if (p.mode === "기울기") L.push(`bullNow = vw > vw[${p.slopeN}] * (1 + buf)`, `bearNow = vw < vw[${p.slopeN}] * (1 - buf)`);
      else L.push(`bullNow = close > vw * (1 + buf)`, `bearNow = close < vw * (1 - buf)`);
      L.push(`upRun = ta.barssince(not bullNow)`, `dnRun = ta.barssince(not bearNow)`);
      let filt = "";
      if (p.trend !== "없음") { L.push(`tvw = math.sum(hlc3 * volume, ${p.trendN}) / math.sum(volume, ${p.trendN})`, `plot(tvw, "추세 VWAP", color.purple)`); filt = " and close > tvw"; }
      entry = `upRun == conf${filt}`; exit = "dnRun == conf";
      if (p.noLate > 0) L.push(`// 참고: 장 막판 ${p.noLate}봉 진입 금지는 Pine에서 생략했어요.`);
    } else if (strategyId === "confluence") {
      const S = p.short, Lg = p.long, on = (k) => p["use_" + k] !== "끔";
      L.push(`vwN(n) => math.sum(hlc3 * volume, n) / math.sum(volume, n)`);
      L.push(`lv = vwN(${Lg})`, `sv = vwN(${S})`, `mid = timeframe.isintraday ? ta.vwap(hlc3, timeframe.change("W")) : vwN(20)`);
      L.push(`r = ta.rsi(close, 14)`, `hh = ta.highest(high, ${S})[1]`, `brk = close > hh`);
      L.push(`plot(lv, "긴 VWAP", color.purple)`);
      const parts = [];
      if (on("trend")) parts.push("(close > lv ? 1 : 0)");
      if (on("vslope")) parts.push("(sv > sv[3] ? 1 : 0)");
      if (on("spo")) parts.push("(spoOsc(20, 90) > 0 ? 1 : 0)");
      if (on("ema")) parts.push("(ta.ema(close, 20) > ta.ema(close, 60) ? 1 : 0)");
      if (on("brk")) parts.push("(brk or brk[1] or brk[2] ? 1 : 0)");
      if (on("vol")) parts.push("(volume > ta.sma(volume, 20)[1] * 1.2 ? 1 : 0)");
      if (on("rsi")) parts.push("(r >= 50 and r <= 75 ? 1 : 0)");
      if (on("wvwap")) parts.push("(close > mid ? 1 : 0)");
      L.push(`score = ${parts.join(" + ") || "0"}`);
      L.push(`plotchar(score, "점수", "", location.top)`);
      entry = `score >= ${p.buyScore} and score[1] < ${p.buyScore}`; exit = `score <= ${p.sellScore}`;
    } else if (strategyId === "custom") {
      entry = pineRules(p.rules && p.rules.entry); exit = pineRules(p.rules && p.rules.exit);
    }
    L.push(`buySig  = ${entry}`);
    L.push(`sellSig = ${exit}`);
    L.push("");
    L.push("lastBar = dayClose and timeframe.isintraday and session.islastbar_regular");
    L.push(`allowL = direction != "숏"`);
    L.push(`allowS = direction != "롱"`);
    L.push("if not lastBar");
    L.push("    if buySig");
    L.push("        if strategy.position_size < 0");
    L.push(`            strategy.close("S", comment="신호")`);
    L.push(`        if allowL and (strategy.position_size <= 0 or strategy.opentrades < ${Math.max(1, opt.pyrN)})`);
    L.push(`            strategy.entry("L", strategy.long)`);
    L.push("    if sellSig");
    L.push("        if strategy.position_size > 0");
    L.push(`            strategy.close("L", comment="신호")`);
    L.push(`        if allowS and (strategy.position_size >= 0 or strategy.opentrades < ${Math.max(1, opt.pyrN)})`);
    L.push(`            strategy.entry("S", strategy.short)`);
    L.push("");
    L.push("ep = strategy.position_avg_price");
    L.push("isL = strategy.position_size > 0");
    L.push("sl = stopPct > 0 ? (isL ? ep * (1 - stopPct / 100) : ep * (1 + stopPct / 100)) : na");
    L.push("tp = tpPct > 0 ? (isL ? ep * (1 + tpPct / 100) : ep * (1 - tpPct / 100)) : na");
    L.push("tp1 = tp1Pct > 0 ? (isL ? ep * (1 + tp1Pct / 100) : ep * (1 - tp1Pct / 100)) : na");
    L.push("trailTicks = trailPct > 0 ? ep * trailPct / 100 / syminfo.mintick : na");
    L.push("if strategy.position_size != 0");
    L.push(`    id = isL ? "L" : "S"`);
    L.push(`    if tp1Pct > 0`);
    L.push(`        strategy.exit("TP1", id, qty_percent=tp1Frac, limit=tp1, stop=sl)`);
    L.push(`    strategy.exit("R", id, stop=sl, limit=tp, trail_points=trailPct > 0 ? 0 : na, trail_offset=trailTicks)`);
    L.push("    if maxHold > 0 and bar_index - strategy.opentrades.entry_bar_index(0) >= maxHold");
    L.push(`        strategy.close_all(comment="보유기간", immediately=true)`);
    L.push("    if lastBar");
    L.push(`        strategy.close_all(comment="당일청산", immediately=true)`);
    return L.join("\n");
  }

  return {
    STRATEGIES, IND, OPS, DEFAULTS, run, pine, stats, describeSpec, tickSize, roundTick,
    sma, ema, rsi, stdev, atr, superSmoother, spoCalc, vwapCalc, confluence, CONF_LIST, swings, chartSetup,
  };
})();
if (typeof module !== "undefined") module.exports = BT;
