/*
 * Smooth Price Oscillator 검증 — 사이트와 같은 엔진(assets/backtest.js)
 *  한 가지 설정을 묶음의 모든 종목에 똑같이 적용하고, 거래를 모아서 평가 (종목별 최적화로 생기는 우연을 줄임)
 *  학습 70% / 검증 30%. 학습에서 '내 목표 기준'(승률 50%+, 손익비 1.5+, 거래 100회+, 종목 MDD 중앙값 -20% 이내, 기대값 +)을
 *  통과한 설정 중 기대값 1위를 고르고 검증 성적을 확인.
 * 실행: node research/spo/run.js
 */
const fs = require("fs"), path = require("path");
const BT = require("../../assets/backtest.js");
const KST = 9 * 3600;
const toBars = (rows) => rows.map(([u, o, h, l, c, v]) => ({ t: u + KST, ms: u * 1000, day: new Date((u + KST) * 1000).toISOString().slice(0, 10), o, h, l, c, v }));

function groups() {
  const etf = (iv) => ["069500.KS", "122630.KS", "114800.KS", "252670.KS", "229200.KS", "233740.KS"].map((s) => {
    const j = JSON.parse(fs.readFileSync(path.join(__dirname, "../etf/data", `${s}_${iv}.json`)));
    return { sym: s, name: j.name, bars: toBars(j.bars), etf: true };
  });
  const stocks = (iv) => Object.entries(JSON.parse(fs.readFileSync(path.join(__dirname, "data", `stocks_${iv}.json`)))).map(([s, rows]) => ({ sym: s, name: s, bars: toBars(rows), etf: false }));
  return [
    { id: "etf_1h", label: "ETF 6종 · 1시간봉", sets: etf("60m"), minTr: 100, intraday: true },
    { id: "stk_1h", label: "대형주 59종 · 1시간봉", sets: stocks("60m"), minTr: 100, intraday: true },
    { id: "stk_1d", label: "대형주 60종 · 일봉 (2014~)", sets: stocks("1d").filter((x) => x.bars.length > 1500), minTr: 100, intraday: false },
    { id: "etf_5m", label: "ETF 6종 · 5분봉 (60일)", sets: etf("5m"), minTr: 50, intraday: true, fine: true },
  ];
}

function grid(fine, intraday) {
  const out = [];
  const risks = (fine ? [[0, 0], [1, 0], [1, 1]] : [[0, 0], [2, 0], [2, 2]]);
  const dcs = intraday ? [true, false] : [false];
  for (const fast of [5, 10, 20]) for (const slow of [30, 40, 60]) for (const [stopLoss, tp1Pct] of risks) for (const dayClose of (fine ? [true] : dcs)) {
    const o = { stopLoss, tp1Pct, tp1Frac: 50, dayClose };
    out.push({ p: { mode: "추세", fast, slow, th: 1, bandLen: 100, k: 2, strength: "일반", exitAt: "0선 회복" }, o });
    for (const th of [0.5, 1, 1.5]) for (const exitAt of ["0선 회복", "과매수 반락"])
      out.push({ p: { mode: "역추세", fast, slow, th, bandLen: 100, k: 2, strength: "일반", exitAt }, o });
    for (const exitAt of ["0선 회복", "과매수 반락"])
      out.push({ p: { mode: "역추세", fast, slow, th: 1, bandLen: 100, k: 2, strength: "강한 신호만", exitAt }, o });
  }
  return out;
}

function evalCfg(G, cfg) {
  const agg = { train: [], test: [] }, mdd = { train: [], test: [] }, rets = { train: [], test: [] };
  for (const x of G.sets) {
    const bars = x.bars, n = bars.length, k = Math.floor(n * 0.7);
    const o = { capital: 1e7, buyFee: 0.015, sellFee: x.etf ? 0.015 : 0.215, slip: x.etf ? 0.02 : 0.05, ...cfg.o, dayKey: (i) => bars[i].day };
    if (!G.intraday) o.dayClose = false;
    const r = BT.run(bars, "spo", cfg.p, o);
    for (const [seg, a, b] of [["train", 0, k], ["test", k, n]]) {
      agg[seg].push(...r.trades.filter((t) => t.exitIdx >= a && t.exitIdx < b));
      const start = a ? r.equity[a - 1] : 1e7;
      let pk = start, m = 0;
      for (let i = a; i < b; i++) { pk = Math.max(pk, r.equity[i]); m = Math.min(m, r.equity[i] / pk - 1); }
      mdd[seg].push(m * 100); rets[seg].push((r.equity[b - 1] / start - 1) * 100);
    }
  }
  const sum = (seg) => {
    const t = agg[seg], W = t.filter((z) => z.pnl > 0), L = t.filter((z) => z.pnl <= 0);
    const aw = W.length ? W.reduce((a, z) => a + z.ret, 0) / W.length : 0, al = L.length ? L.reduce((a, z) => a + z.ret, 0) / L.length : 0;
    const med = (a) => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; };
    return { trades: t.length, win: t.length ? W.length / t.length * 100 : 0, payoff: al < 0 ? aw / -al : aw > 0 ? 99 : 0,
      exp: t.length ? t.reduce((a, z) => a + z.ret, 0) / t.length : 0, mdd: med(mdd[seg]), ret: med(rets[seg]),
      pos: rets[seg].filter((v) => v > 0).length / rets[seg].length * 100 };
  };
  return { train: sum("train"), test: sum("test") };
}
const pass = (m, minTr) => m.trades >= minTr && m.win >= 50 && m.payoff >= 1.5 && m.mdd >= -20 && m.exp > 0;
const spear = (a, b) => {
  const rank = (arr) => { const idx = arr.map((v, i) => [v, i]).sort((x, y) => x[0] - y[0]); const r = []; for (let i = 0; i < idx.length;) { let j = i; while (j + 1 < idx.length && idx[j + 1][0] === idx[i][0]) j++; for (let q = i; q <= j; q++) r[idx[q][1]] = (i + j) / 2; i = j + 1; } return r; };
  const ra = rank(a), rb = rank(b), n = a.length, m = (n - 1) / 2; let nu = 0, da = 0, db = 0;
  for (let i = 0; i < n; i++) { nu += (ra[i] - m) * (rb[i] - m); da += (ra[i] - m) ** 2; db += (rb[i] - m) ** 2; }
  return nu / Math.sqrt(da * db);
};
const f = (v, d = 1) => (v == null || !isFinite(v) ? "—" : v.toFixed(d));
const desc = (c) => `${c.p.mode}${c.p.mode === "역추세" ? `(${c.p.strength === "강한 신호만" ? "밴드" : "±" + c.p.th}, 매도 ${c.p.exitAt})` : ""} SS${c.p.fast}/${c.p.slow} 손절${c.o.stopLoss} 1차익절${c.o.tp1Pct}${c.o.dayClose ? " 당일청산" : ""}`;
const line = (m) => `승률 ${f(m.win, 0)}% 손익비 ${f(m.payoff, 2)} 기대값 ${f(m.exp, 2)}% 거래 ${m.trades} · 종목 수익 중앙값 ${f(m.ret)}% 플러스 종목 ${f(m.pos, 0)}% MDD 중앙값 ${f(m.mdd)}%`;

const out = [];
for (const G of groups()) {
  const t0 = Date.now(), cfgs = grid(G.fine, G.intraday);
  const rows = cfgs.map((c) => ({ c, ...evalCfg(G, c) }));
  const n = G.sets[0].bars.length, k = Math.floor(n * 0.7);
  console.log(`\n=== ${G.label} · 학습 ~${G.sets[0].bars[k - 1].day} / 검증 ${G.sets[0].bars[k].day}~ · 설정 ${rows.length}개 · ${((Date.now() - t0) / 1000).toFixed(0)}s ===`);
  for (const mode of ["역추세", "추세"]) {
    const R = rows.filter((r) => r.c.p.mode === mode);
    const ok = R.filter((r) => pass(r.train, G.minTr)).sort((a, b) => b.train.exp - a.train.exp);
    const rho = spear(R.map((r) => r.train.exp), R.map((r) => r.test.exp));
    const testPos = R.filter((r) => r.test.exp > 0).length / R.length * 100;
    console.log(`[${mode}] 학습 목표통과 ${ok.length}/${R.length} · 그중 검증도 통과 ${ok.filter((r) => pass(r.test, Math.round(G.minTr * 0.3))).length} · 전체 설정 중 검증 기대값 플러스 ${f(testPos, 0)}% · 학습↔검증 순위상관 ${f(rho, 2)}`);
    const best = ok[0] || [...R].sort((a, b) => b.train.exp - a.train.exp)[0];
    console.log(`  ${ok[0] ? "학습 목표통과 1위" : "목표통과 없음 → 학습 기대값 1위"}: ${desc(best.c)}`);
    console.log(`    학습: ${line(best.train)}`);
    console.log(`    검증: ${line(best.test)}`);
    out.push({ group: G.id, mode, okTrain: ok.length, total: R.length, rho, testPos, best: { cfg: best.c, train: best.train, test: best.test } });
  }
}
fs.mkdirSync(path.join(__dirname, "results"), { recursive: true });
fs.writeFileSync(path.join(__dirname, "results", "spo_results.json"), JSON.stringify(out, null, 1));
