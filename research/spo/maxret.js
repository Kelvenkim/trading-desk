/*
 * SPO 최대 수익 탐색
 *  신호(기간·기준선·매도 방식) × 위험 관리(손절·익절·트레일링) 조합을 전부 돌려
 *  1) 전체 기간에서 수익이 가장 큰 설정 (사후 최적화 — 과거에 맞춘 값)
 *  2) 앞 70%(학습)에서 수익이 가장 큰 설정 → 뒤 30%(검증) 성과 (현실적인 기대치)
 * 를 비교. 수익 = 종목별로 자금을 똑같이 나눠 운용한 포트폴리오 수익(종목 수익 평균).
 * 실행: node research/spo/maxret.js
 */
const fs = require("fs"), path = require("path");
const BT = require("../../assets/backtest.js");
const KST = 9 * 3600;
const toBars = (rows) => rows.map(([u, o, h, l, c, v]) => ({ t: u + KST, ms: u * 1000, day: new Date((u + KST) * 1000).toISOString().slice(0, 10), o, h, l, c, v }));

// 미리 계산한 신호를 그대로 쓰는 전략 (계산 속도용)
BT.STRATEGIES._pre = { name: "pre", params: [], signals: (b, p) => ({ entry: p.sig.entry, exit: p.sig.exit, lines: [] }) };

const GROUPS = [
  { id: "stk_1h", label: "대형주 59종 · 1시간봉 (2023-10~2026-10)", load: () => Object.values(JSON.parse(fs.readFileSync(path.join(__dirname, "data/stocks_60m.json")))).map(toBars), etf: false },
  { id: "etf_1h", label: "ETF 3종(KODEX 200·레버리지·코스닥150) · 1시간봉", load: () => ["069500.KS", "122630.KS", "229200.KS"].map((s) => toBars(JSON.parse(fs.readFileSync(path.join(__dirname, "../etf/data", `${s}_60m.json`))).bars)), etf: true },
  { id: "stk_1d", label: "대형주 55종 · 일봉 (2014~2026)", load: () => Object.values(JSON.parse(fs.readFileSync(path.join(__dirname, "data/stocks_1d.json")))).map(toBars).filter((b) => b.length > 1500), etf: false, daily: true },
];

const SIGS = [];
for (const fast of [5, 10, 20, 30]) for (const slow of [40, 60, 90, 120]) {
  if (slow <= fast) continue;
  SIGS.push({ mode: "추세", fast, slow, th: 1, exitAt: "0선 회복" });
  for (const th of [0.5, 1, 1.5, 2]) for (const exitAt of ["0선 회복", "과매수 반락"]) SIGS.push({ mode: "역추세", fast, slow, th, exitAt });
}
const RISKS = [];
for (const stopLoss of [0, 3, 5, 8, 12]) for (const takeProfit of [0, 5, 10, 20, 40]) for (const trailing of [0, 5, 10]) RISKS.push({ stopLoss, takeProfit, trailing });

function signals(bars, s) {
  return BT.STRATEGIES.spo.signals(bars, { ...s, bandLen: 100, k: 2, strength: "일반" });
}
const fmt = (v, d = 1) => (v == null || !isFinite(v) ? "—" : v.toFixed(d));
const sDesc = (s) => `${s.mode}${s.mode === "역추세" ? ` ±${s.th} ${s.exitAt}` : ""} · SS ${s.fast}/${s.slow}`;
const rDesc = (r) => `손절 ${r.stopLoss || "없음"}${r.stopLoss ? "%" : ""} · 익절 ${r.takeProfit || "없음"}${r.takeProfit ? "%" : ""} · 트레일링 ${r.trailing || "없음"}${r.trailing ? "%" : ""}`;

const report = [];
for (const G of GROUPS) {
  const t0 = Date.now();
  const sets = G.load();
  const n0 = sets.map((b) => b.length), ks = sets.map((b) => Math.floor(b.length * 0.7));
  const bh = (a, b) => sets.reduce((s, x, j) => s + (x[(b == null ? x.length : b(j)) - 1].c / x[a == null ? 0 : a(j)].o - 1) * 100, 0) / sets.length;
  const bhAll = bh(), bhTrain = bh(null, (j) => ks[j]), bhTest = bh((j) => ks[j]);
  const rows = [];
  for (const s of SIGS) {
    const sigs = sets.map((b) => signals(b, s));
    for (const r of RISKS) {
      let all = 0, tr = 0, te = 0, trades = 0, wins = 0, mddSum = 0, trT = 0, winT = 0, trV = 0, winV = 0;
      sets.forEach((bars, j) => {
        const res = BT.run(bars, "_pre", { sig: sigs[j] }, { buyFee: 0.015, sellFee: G.etf ? 0.015 : 0.215, slip: G.etf ? 0.02 : 0.05, ...r });
        const eq = res.equity, k = ks[j], n = n0[j];
        all += (eq[n - 1] / 1e7 - 1) * 100; tr += (eq[k - 1] / 1e7 - 1) * 100; te += (eq[n - 1] / eq[k - 1] - 1) * 100;
        trades += res.trades.length; wins += res.trades.filter((t) => t.pnl > 0).length; mddSum += res.stats.mdd;
        res.trades.forEach((t) => { if (t.exitIdx < k) { trT++; if (t.pnl > 0) winT++; } else { trV++; if (t.pnl > 0) winV++; } });
      });
      const m = sets.length;
      rows.push({ s, r, all: all / m, train: tr / m, test: te / m, trades, win: trades ? wins / trades * 100 : 0, mdd: mddSum / m,
        winT: trT ? winT / trT * 100 : 0, winV: trV ? winV / trV * 100 : 0, trT, trV });
    }
  }
  const byAll = [...rows].sort((a, b) => b.all - a.all), byTrain = [...rows].sort((a, b) => b.train - a.train);
  const top10train = byTrain.slice(0, 10);
  const testOfTop10 = top10train.reduce((s, x) => s + x.test, 0) / 10;
  const testPos = rows.filter((x) => x.test > 0).length / rows.length * 100;
  const testBeat = rows.filter((x) => x.test > bhTest).length / rows.length * 100;
  const median = (a) => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; };
  console.log(`\n=== ${G.label} · ${sets.length}종목 · 설정 ${rows.length.toLocaleString()}개 · ${((Date.now() - t0) / 1000).toFixed(0)}s ===`);
  console.log(`그냥 보유(동일 비중): 전체 ${fmt(bhAll)}% · 학습 ${fmt(bhTrain)}% · 검증 ${fmt(bhTest)}%`);
  console.log(`\n① 전체 기간 최고 (사후 최적화 — 과거에 맞춘 값)`);
  byAll.slice(0, 3).forEach((x, i) => console.log(`  ${i + 1}. ${sDesc(x.s)} · ${rDesc(x.r)} → 수익 ${fmt(x.all)}% · 승률 ${fmt(x.win, 0)}% · 거래 ${x.trades} · 평균 MDD ${fmt(x.mdd)}%`));
  console.log(`\n② 학습 기간 최고 → 검증 기간 (현실적인 기대치)`);
  byTrain.slice(0, 3).forEach((x, i) => console.log(`  ${i + 1}. ${sDesc(x.s)} · ${rDesc(x.r)} → 학습 ${fmt(x.train)}% (승률 ${fmt(x.winT, 0)}%, ${x.trT}회) → 검증 ${fmt(x.test)}% (승률 ${fmt(x.winV, 0)}%, ${x.trV}회) | 검증 보유 ${fmt(bhTest)}%`));
  console.log(`  학습 상위 10개의 검증 평균 ${fmt(testOfTop10)}% · 전체 설정 검증 중앙값 ${fmt(median(rows.map((x) => x.test)))}% · 검증 플러스 ${fmt(testPos, 0)}% · 검증에서 보유보다 나은 설정 ${fmt(testBeat, 0)}%`);
  // 위험 관리 효과 (신호 상관없이 평균)
  const byRisk = {};
  rows.forEach((x) => { const k = `손절${x.r.stopLoss}`; (byRisk[k] = byRisk[k] || []).push(x); });
  console.log(`\n  손절별 평균 (모든 신호 설정 평균): ` + Object.entries(byRisk).map(([k, v]) => `${k} 학습 ${fmt(v.reduce((s, x) => s + x.train, 0) / v.length)}%/검증 ${fmt(v.reduce((s, x) => s + x.test, 0) / v.length)}%`).join(" · "));
  report.push({ group: G.id, label: G.label, bh: { all: bhAll, train: bhTrain, test: bhTest }, bestAll: byAll.slice(0, 5), bestTrain: byTrain.slice(0, 5), testOfTop10, testPos, testBeat });
}
fs.writeFileSync(path.join(__dirname, "results", "maxret.json"), JSON.stringify(report, null, 1));
