/*
 * 지지·저항·추세선·매매 계획 (순위 화면의 종목 차트용)
 *  - 지지/저항: 확정된 스윙 고점·저점(앞뒤 5봉)을 가격대별로 묶음. 여러 번 닿은 가격대일수록 강함
 *  - 추세선: 최근 두 저점이 높아지면 상승 추세선, 두 고점이 낮아지면 하락 추세선
 *  - 매매 계획: 연구(research/chart)에서 가장 견고했던 '추세 눌림목' 규칙
 *      상승 추세(종가>60일선, 20일선>60일선)면 → 지지선 근처 매수, 지지선 아래 0.5ATR 손절, 목표 = 손절폭의 3배(3R)
 *      추세가 아니면 → 관망, 저항선 돌파 시에만 매수 고려
 *  - 지난 신호: 같은 규칙(BT.chartSetup)으로 최근 6개월 동안 나왔던 매수 신호와 결과
 */
const Levels = (() => {
  const SETUP = { setup: "추세 눌림목", pivot: 5, window: 10, tol: 0.3, buf: 0.5, target: "3R", minRR: 2, maxStop: 15, filter: "없음" };

  function cluster(points, tol) {
    const s = points.slice().sort((a, b) => a.p - b.p), out = [];
    for (const x of s) {
      const g = out[out.length - 1];
      if (g && x.p - g.hi <= tol) { g.items.push(x); g.hi = x.p; }
      else out.push({ items: [x], hi: x.p });
    }
    return out.map((g) => ({ p: g.items.reduce((a, x) => a + x.p, 0) / g.items.length, n: g.items.length, last: Math.max(...g.items.map((x) => x.i)) }));
  }

  function analyze(b, opt = {}) {
    const n = b.length; if (n < 40) return null;
    const c = b.map((x) => x.c), a = BT.atr(b, 14), A = a[n - 1] || c[n - 1] * 0.02;
    const m20 = BT.sma(c, 20), m60 = BT.sma(c, 60), px = c[n - 1];
    const sw = BT.swings(b, 5);
    const lv = cluster([...sw.hs, ...sw.ls], Math.max(A * 0.6, px * 0.012));
    const sup = lv.filter((x) => x.p < px * 0.995).sort((x, y) => y.p - x.p).slice(0, 2);
    const res = lv.filter((x) => x.p > px * 1.005).sort((x, y) => x.p - y.p).slice(0, 2);

    // 추세선: 최근 두 스윙 저점(올라가는), 두 스윙 고점(내려가는)
    const line = (p1, p2) => ({ i1: p1.i, p1: p1.p, i2: n - 1, p2: p1.p + (p2.p - p1.p) / (p2.i - p1.i) * (n - 1 - p1.i) });
    let up = null, down = null;
    const L = sw.ls, H = sw.hs;
    for (let k = L.length - 1; k >= 1 && !up; k--) for (let j = k - 1; j >= 0 && j >= k - 3; j--)
      if (L[k].p > L[j].p && L[k].i - L[j].i >= 5) { const t = line(L[j], L[k]); if (px >= t.p2 * 0.97) up = t; break; }
    for (let k = H.length - 1; k >= 1 && !down; k--) for (let j = k - 1; j >= 0 && j >= k - 3; j--)
      if (H[k].p < H[j].p && H[k].i - H[j].i >= 5) { const t = line(H[j], H[k]); if (px <= t.p2 * 1.03) down = t; break; }

    const trendOK = px > m60[n - 1] && m20[n - 1] > m60[n - 1];
    const mktOK = opt.marketUp !== false;
    let plan;
    if (trendOK) {
      const base = sup.length ? Math.max(sup[0].p, Math.min(m20[n - 1], px)) : m20[n - 1];
      const s1 = sup.length ? sup[0].p : base;
      const zoneLo = s1, zoneHi = Math.max(s1 + 0.5 * A, Math.min(m20[n - 1], px));
      const entry = Math.min(px, zoneHi), stop = s1 - 0.5 * A, risk = entry - stop;
      const t3 = entry + 3 * risk, r1 = res.length ? res[0].p : null;
      plan = { kind: "pullback", zoneLo, zoneHi, entry, stop, target: t3, res1: r1 && r1 < t3 ? r1 : null,
        inZone: px <= zoneHi * 1.005, stopPct: stop / entry - 1, targetPct: t3 / entry - 1, ok: risk > 0 && (entry - stop) / entry <= 0.15 };
    } else {
      const r1 = res.length ? res[0].p : Math.max(...b.slice(-60).map((x) => x.h));
      const entry = r1 + 0.2 * A;
      const stop = Math.max(sup.length ? sup[0].p - 0.5 * A : entry - 2 * A, entry - 2.5 * A), risk = entry - stop;
      plan = { kind: "breakout", entry, stop, target: entry + 3 * risk, stopPct: stop / entry - 1, targetPct: 3 * risk / entry, ok: risk > 0 && risk / entry <= 0.15 };
    }
    // 한국 호가 단위로 맞춤 (매수·목표는 위로, 손절은 아래로)
    const tick = (x) => (x < 2000 ? 1 : x < 5000 ? 5 : x < 20000 ? 10 : x < 50000 ? 50 : x < 200000 ? 100 : x < 500000 ? 500 : 1000);
    const rUp = (x) => Math.ceil(x / tick(x)) * tick(x), rDn = (x) => Math.floor(x / tick(x)) * tick(x);
    ["zoneHi", "entry", "target"].forEach((k) => { if (plan[k] != null) plan[k] = rUp(plan[k]); });
    ["zoneLo", "stop"].forEach((k) => { if (plan[k] != null) plan[k] = rDn(plan[k]); });
    if (plan.res1 != null) plan.res1 = Math.round(plan.res1 / tick(plan.res1)) * tick(plan.res1);
    sup.forEach((x) => (x.p = Math.round(x.p / tick(x.p)) * tick(x.p))); res.forEach((x) => (x.p = Math.round(x.p / tick(x.p)) * tick(x.p)));
    plan.trendOK = trendOK; plan.mktOK = mktOK;
    plan.verdict = !plan.ok ? "손절 폭이 너무 커서 자리 아님"
      : plan.kind === "breakout" ? "관망 — 추세가 아니에요. 저항선을 넘으면 그때 고려"
      : !mktOK ? "추세는 좋지만 시장이 하락장 — 과거엔 이때 성적이 나빴어요"
      : plan.inZone ? "매수 구간 안 — 규칙상 진입 가능 자리" : "추세 좋음 — 매수 구간까지 내려오길 기다리기";

    // 지난 신호와 결과 (다음 날 시가 매수, 장중 손절/목표, 같은 날 둘 다면 손절)
    const sg = BT.chartSetup(b, SETUP), sig = [];
    for (let i = 0; i < n - 1; i++) {
      if (!sg.entry[i] || !sg.plan[i]) continue;
      const { stop, target } = sg.plan[i], e = b[i + 1].o;
      if (e <= stop || e >= target) continue;
      let out = null;
      for (let k = i + 1; k < n; k++) {
        if (b[k].l <= stop) { out = { k, why: "손절", px: Math.min(b[k].o, stop) }; break; }
        if (b[k].h >= target) { out = { k, why: "목표", px: Math.max(b[k].o, target) }; break; }
      }
      sig.push({ i: i + 1, entry: e, stop, target, out });
      if (out) i = out.k; else break;   // 보유 중이면 새 신호 무시
    }
    return { sup, res, up, down, plan, sig, atr: A, px };
  }
  return { analyze, SETUP };
})();
