/*
 * VWAP 추세 전환 전략 검증 — 사이트와 같은 엔진(assets/backtest.js)
 *  설정 하나를 묶음의 모든 종목에 똑같이 적용, 거래를 모아서 평가
 *  학습 70% / 검증 30%
 *  A) 학습에서 '내 목표 기준'(승률 50%+, 손익비 1.5+, 기대값 +, 거래 수, 종목 MDD 중앙값 -20% 이내) 통과 설정 중 수익 1위
 *  B) 학습 수익 1위
 *  → 각각 검증 성과, 그리고 같은 기간 그냥 보유와 비교
 * 실행: node research/vwap/run.js
 */
const fs = require("fs"), path = require("path");
const BT = require("../../assets/backtest.js");
const KST = 9 * 3600;
const toBars = (rows) => rows.map(([u, o, h, l, c, v]) => ({ t: u + KST, ms: u * 1000, day: new Date((u + KST) * 1000).toISOString().slice(0, 10), o, h, l, c, v }));
BT.STRATEGIES._pre = { params: [], signals: (b, p) => ({ entry: p.sig.entry, exit: p.sig.exit, lines: [] }) };

const ETF6 = ["069500.KS", "122630.KS", "114800.KS", "252670.KS", "229200.KS", "233740.KS"];
const etf = (iv) => ETF6.map((s) => ({ etf: true, bars: toBars(JSON.parse(fs.readFileSync(path.join(__dirname, "../etf/data", `${s}_${iv}.json`))).bars) }));
const stk = (iv) => Object.values(JSON.parse(fs.readFileSync(path.join(__dirname, "../spo/data", `stocks_${iv}.json`)))).map((r) => ({ etf: false, bars: toBars(r) }));

const prod = (...arrs) => arrs.reduce((acc, a) => acc.flatMap((x) => a.map((y) => [...x, y])), [[]]);
const base = { n: 20, slopeN: 3, trendN: 100, noLate: 0 };
const GROUPS = [
  { id: "etf_5m", label: "ETF 6종 · 5분봉 · 당일 VWAP (2026-08~10)", load: () => etf("5m"), minTr: 60, intraday: true,
    sigs: prod(["교차", "기울기"], [0, 0.1, 0.2], [1, 2, 3], ["없음", "이동 VWAP 위에서만 매수"], [0, 6]).map(([mode, buf, confirm, trend, noLate]) => ({ ...base, kind: "당일", mode, buf, confirm, trend, trendN: 390, noLate })),
    risks: prod([0, 0.5, 1], [0, 1, 2], [0, 0.5]).map(([stopLoss, takeProfit, trailing]) => ({ stopLoss, takeProfit, trailing, dayClose: true })) },
  { id: "stk_5m", label: "대형주 60종 · 5분봉 · 당일 VWAP (2026-08~10)", load: () => stk("5m"), minTr: 100, intraday: true,
    sigs: prod(["교차", "기울기"], [0, 0.1, 0.2], [1, 2, 3], ["없음", "이동 VWAP 위에서만 매수"], [0, 6]).map(([mode, buf, confirm, trend, noLate]) => ({ ...base, kind: "당일", mode, buf, confirm, trend, trendN: 390, noLate })),
    risks: prod([0, 0.5, 1], [0, 1, 2], [0, 0.5]).map(([stopLoss, takeProfit, trailing]) => ({ stopLoss, takeProfit, trailing, dayClose: true })) },
  { id: "etf_1h", label: "ETF 6종 · 1시간봉 · 주간/이동 VWAP (2023-10~2026-10)", load: () => etf("60m"), minTr: 60, intraday: true,
    sigs: prod([["주간", 20], ["N봉 이동", 24], ["N봉 이동", 60], ["N봉 이동", 120]], ["교차", "기울기"], [0, 0.3], [1, 2], ["없음", "이동 VWAP 위에서만 매수"]).map(([[kind, n], mode, buf, confirm, trend]) => ({ ...base, kind, n, mode, buf, confirm, trend, trendN: 240 })),
    risks: prod([0, 2, 4], [0, 5, 10], [0, 3]).map(([stopLoss, takeProfit, trailing]) => ({ stopLoss, takeProfit, trailing, dayClose: false })) },
  { id: "stk_1h", label: "대형주 59종 · 1시간봉 · 주간/이동 VWAP (2023-10~2026-10)", load: () => stk("60m"), minTr: 100, intraday: true,
    sigs: prod([["주간", 20], ["N봉 이동", 24], ["N봉 이동", 60], ["N봉 이동", 120]], ["교차", "기울기"], [0, 0.3], [1, 2], ["없음", "이동 VWAP 위에서만 매수"]).map(([[kind, n], mode, buf, confirm, trend]) => ({ ...base, kind, n, mode, buf, confirm, trend, trendN: 240 })),
    risks: prod([0, 2, 4], [0, 5, 10], [0, 3]).map(([stopLoss, takeProfit, trailing]) => ({ stopLoss, takeProfit, trailing, dayClose: false })) },
  { id: "stk_1d", label: "대형주 55종 · 일봉 · 이동 VWAP (2014~2026)", load: () => stk("1d").filter((x) => x.bars.length > 1500), minTr: 100, intraday: false,
    sigs: prod([10, 20, 60, 120], ["교차", "기울기"], [0, 0.5, 1], [1, 2], ["없음", "이동 VWAP 위에서만 매수"]).map(([n, mode, buf, confirm, trend]) => ({ ...base, kind: "N봉 이동", n, mode, buf, confirm, trend, trendN: 200 })),
    risks: prod([0, 5, 10], [0, 20, 40], [0, 10]).map(([stopLoss, takeProfit, trailing]) => ({ stopLoss, takeProfit, trailing, dayClose: false })) },
];

const only = process.argv[2];
const f = (v, d = 1) => (v == null || !isFinite(v) ? "—" : v.toFixed(d));
const med = (a) => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; };
const spear = (a, b) => {
  const rank = (arr) => { const idx = arr.map((v, i) => [v, i]).sort((x, y) => x[0] - y[0]); const r = []; for (let i = 0; i < idx.length;) { let j = i; while (j + 1 < idx.length && idx[j + 1][0] === idx[i][0]) j++; for (let q = i; q <= j; q++) r[idx[q][1]] = (i + j) / 2; i = j + 1; } return r; };
  const ra = rank(a), rb = rank(b), n = a.length, m = (n - 1) / 2; let nu = 0, da = 0, db = 0;
  for (let i = 0; i < n; i++) { nu += (ra[i] - m) * (rb[i] - m); da += (ra[i] - m) ** 2; db += (rb[i] - m) ** 2; }
  return nu / Math.sqrt(da * db);
};
const sDesc = (s) => `${s.kind}${s.kind === "N봉 이동" ? " " + s.n + "봉" : ""} · ${s.mode} · 여유 ${s.buf}% · 확인 ${s.confirm}봉${s.trend !== "없음" ? " · 추세필터" : ""}${s.noLate ? " · 막판 " + s.noLate + "봉 진입금지" : ""}`;
const rDesc = (r) => `손절 ${r.stopLoss || "없음"} · 익절 ${r.takeProfit || "없음"} · 트레일링 ${r.trailing || "없음"}${r.dayClose ? " · 당일청산" : ""}`;
const mline = (m) => `수익 ${f(m.ret)}% · 승률 ${f(m.win, 0)}% · 손익비 ${f(m.payoff, 2)} · 기대값 ${f(m.exp, 2)}% · 거래 ${m.trades} · MDD 중앙값 ${f(m.mdd)}% · 플러스인 날 ${f(m.posDays, 0)}%`;

const report = [];
for (const G of GROUPS) {
  if (only && G.id !== only) continue;
  const t0 = Date.now(), sets = G.load();
  sets.forEach((x) => { x.n = x.bars.length; x.k = Math.floor(x.n * 0.7); });
  // 그냥 보유
  const bh = (seg) => {
    const rets = [], mdds = [];
    sets.forEach((x) => { const [a, b] = seg === "train" ? [0, x.k] : [x.k, x.n]; rets.push((x.bars[b - 1].c / x.bars[a].o - 1) * 100);
      let pk = x.bars[a].o, m = 0; for (let i = a; i < b; i++) { pk = Math.max(pk, x.bars[i].c); m = Math.min(m, x.bars[i].c / pk - 1); } mdds.push(m * 100); });
    return { ret: rets.reduce((s, v) => s + v, 0) / rets.length, mdd: med(mdds) };
  };
  const BH = { train: bh("train"), test: bh("test") };
  const rows = [];
  for (const s of G.sigs) {
    const sigs = sets.map((x) => BT.STRATEGIES.vwap.signals(x.bars, s));
    for (const r of G.risks) {
      const agg = { train: { t: [], ret: [], mdd: [], days: 0, pos: 0 }, test: { t: [], ret: [], mdd: [], days: 0, pos: 0 } };
      sets.forEach((x, j) => {
        const bars = x.bars;
        const res = BT.run(bars, "_pre", { sig: sigs[j] }, { buyFee: 0.015, sellFee: x.etf ? 0.015 : 0.215, slip: x.etf ? 0.02 : 0.05, ...r, dayKey: (i) => bars[i].day });
        const eq = res.equity;
        for (const [seg, a, b] of [["train", 0, x.k], ["test", x.k, x.n]]) {
          const A = agg[seg], start = a ? eq[a - 1] : 1e7;
          A.t.push(...res.trades.filter((t) => t.exitIdx >= a && t.exitIdx < b));
          A.ret.push((eq[b - 1] / start - 1) * 100);
          let pk = start, m = 0, dPrev = start;
          for (let i = a; i < b; i++) {
            pk = Math.max(pk, eq[i]); m = Math.min(m, eq[i] / pk - 1);
            if (i === b - 1 || bars[i].day !== bars[i + 1].day) { const d = eq[i] / dPrev - 1; if (Math.abs(d) > 1e-9) { A.days++; if (d > 0) A.pos++; } dPrev = eq[i]; }
          }
          A.mdd.push(m * 100);
        }
      });
      const sum = (A) => {
        const W = A.t.filter((z) => z.pnl > 0), L = A.t.filter((z) => z.pnl <= 0);
        const aw = W.length ? W.reduce((q, z) => q + z.ret, 0) / W.length : 0, al = L.length ? L.reduce((q, z) => q + z.ret, 0) / L.length : 0;
        return { ret: A.ret.reduce((q, v) => q + v, 0) / A.ret.length, mdd: med(A.mdd), trades: A.t.length,
          win: A.t.length ? W.length / A.t.length * 100 : 0, payoff: al < 0 ? aw / -al : aw > 0 ? 99 : 0,
          exp: A.t.length ? A.t.reduce((q, z) => q + z.ret, 0) / A.t.length : 0, posDays: A.days ? A.pos / A.days * 100 : 0 };
      };
      rows.push({ s, r, train: sum(agg.train), test: sum(agg.test) });
    }
  }
  const pass = (m, minTr) => m.trades >= minTr && m.win >= 50 && m.payoff >= 1.5 && m.exp > 0 && m.mdd >= -20;
  const goalOk = rows.filter((x) => pass(x.train, G.minTr)).sort((a, b) => b.train.ret - a.train.ret);
  const byRet = [...rows].sort((a, b) => b.train.ret - a.train.ret);
  const rho = spear(rows.map((x) => x.train.ret), rows.map((x) => x.test.ret));
  console.log(`\n=== ${G.label} · ${sets.length}종목 · 설정 ${rows.length.toLocaleString()}개 · ${((Date.now() - t0) / 1000).toFixed(0)}s ===`);
  console.log(`그냥 보유: 학습 수익 ${f(BH.train.ret)}% (MDD 중앙값 ${f(BH.train.mdd)}%) · 검증 수익 ${f(BH.test.ret)}% (MDD 중앙값 ${f(BH.test.mdd)}%)`);
  console.log(`학습 목표 통과 ${goalOk.length}개 → 그중 검증도 통과 ${goalOk.filter((x) => pass(x.test, Math.round(G.minTr * 0.3))).length}개 · 전체 설정 중 검증 기대값 플러스 ${f(rows.filter((x) => x.test.exp > 0).length / rows.length * 100, 0)}% · 검증에서 보유보다 수익 높은 설정 ${f(rows.filter((x) => x.test.ret > BH.test.ret).length / rows.length * 100, 0)}% · 학습↔검증 수익 순위상관 ${f(rho, 2)}`);
  const show = (title, x) => {
    if (!x) { console.log(`  ${title}: 없음`); return; }
    console.log(`  ${title}: ${sDesc(x.s)} · ${rDesc(x.r)}`);
    console.log(`     학습: ${mline(x.train)}`);
    console.log(`     검증: ${mline(x.test)}`);
  };
  show("A) 목표 통과 중 학습 수익 1위", goalOk[0]);
  show("B) 학습 수익 1위", byRet[0]);
  // 손절·신호 종류별 평균 (설정에 덜 민감한 경향 확인)
  const avgBy = (key) => { const m = {}; rows.forEach((x) => { const k = key(x); (m[k] = m[k] || []).push(x); }); return Object.entries(m).map(([k, v]) => `${k} 학습 ${f(v.reduce((q, x) => q + x.train.ret, 0) / v.length)}%/검증 ${f(v.reduce((q, x) => q + x.test.ret, 0) / v.length)}%`).join(" · "); };
  console.log(`  신호별 평균: ${avgBy((x) => x.s.mode + (x.s.trend !== "없음" ? "+필터" : ""))}`);
  console.log(`  손절별 평균: ${avgBy((x) => "손절" + x.r.stopLoss)}`);
  report.push({ group: G.id, label: G.label, BH, nGoal: goalOk.length, rho, A: goalOk[0] || null, B: byRet[0], top: byRet.slice(0, 10) });
}
fs.writeFileSync(path.join(__dirname, "results", `vwap_${only || "all"}.json`), JSON.stringify(report, null, 1));
