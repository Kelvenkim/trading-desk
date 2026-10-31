/*
 * ETF 단타 검증 — 사이트와 같은 엔진(assets/backtest.js) 사용
 *  - 앞 70% 기간(학습)에서 '내 목표 기준'을 통과한 설정 중 거래당 기대값 1위를 고르고
 *  - 뒤 30% 기간(검증)에서 그대로 통하는지 확인
 *  - 비용: ETF라 매도 세금 없음. 매수·매도 수수료 0.015%, 슬리피지 편도 0.02% (민감도: 0.05%)
 * 실행: node research/etf/run.js
 */
const fs = require("fs");
const path = require("path");
const BT = require("../../assets/backtest.js");

const D = path.join(__dirname, "data");
const KST = 9 * 3600;
const ETFS = ["069500.KS", "122630.KS", "114800.KS", "252670.KS", "229200.KS", "233740.KS"];
const GOAL = { winMin: 50, payoff: 1.5, mdd: -20 };
const TRAIN = 0.7;

function load(sym, iv) {
  const j = JSON.parse(fs.readFileSync(path.join(D, `${sym}_${iv}.json`)));
  const bars = j.bars.map(([u, o, h, l, c, v]) => {
    const ms = u * 1000;
    return { t: u + KST, ms, day: new Date(ms + KST * 1000).toISOString().slice(0, 10), o, h, l, c, v };
  });
  return { sym, name: j.name, bars };
}

// 구간 성과 (사이트 bt.js의 segStats와 같은 계산)
function seg(eq, ms, from, to, startVal, tr) {
  const n = to - from;
  if (n < 2) return null;
  let peak = startVal, mdd = 0, prev = startVal, s = 0, s2 = 0;
  const rets = [];
  for (let i = from; i < to; i++) { const r = eq[i] / prev - 1; prev = eq[i]; rets.push(r); s += r; if (eq[i] > peak) peak = eq[i]; mdd = Math.min(mdd, eq[i] / peak - 1); }
  const mean = s / n; rets.forEach((r) => (s2 += (r - mean) ** 2));
  const sd = Math.sqrt(s2 / n), years = Math.max((ms[to - 1] - ms[from]) / (365.25 * 86400000), 1 / 365);
  const W = tr.filter((t) => t.pnl > 0), L = tr.filter((t) => t.pnl <= 0);
  const aw = W.length ? W.reduce((a, t) => a + t.ret, 0) / W.length : 0, al = L.length ? L.reduce((a, t) => a + t.ret, 0) / L.length : 0;
  return {
    ret: (eq[to - 1] / startVal - 1) * 100, mdd: mdd * 100, sharpe: sd > 0 ? (mean / sd) * Math.sqrt(n / years) : 0,
    trades: tr.length, win: tr.length ? (W.length / tr.length) * 100 : 0,
    payoff: al < 0 ? aw / -al : aw > 0 ? 99 : 0, exp: tr.length ? tr.reduce((a, t) => a + t.ret, 0) / tr.length : 0,
  };
}
const pass = (m, minTr) => m && m.trades >= minTr && m.win >= GOAL.winMin && m.payoff >= GOAL.payoff && m.mdd >= GOAL.mdd && m.exp > 0;

function grid(strategy, iv) {
  const fine = iv === "5m";
  const stops = fine ? [0.5, 1] : [1, 2];
  const tp1s = fine ? [0, 0.5, 1] : [0, 1, 2];
  const trails = fine ? [0, 0.5, 1] : [0, 1, 2];
  const dcs = fine ? [true] : [true, false];
  const P = {
    breakout: [].concat(...[6, 12, 24].map((lb) => [1, 1.5, 2].map((vm) => [6, 12].map((ex) => ({ lookback: lb, volLen: 20, volMult: vm, exitLen: ex }))).flat())),
    rsi: [].concat(...[7, 14].map((pd) => [20, 30].map((lo) => [60, 70].map((hi) => ({ period: pd, low: lo, high: hi }))).flat())),
    bollinger: [].concat(...[1.5, 2, 2.5].map((k) => ["중심선", "상단"].map((ex) => ({ period: 20, k, exitAt: ex })))),
    ma_cross: [].concat(...[5, 10, 20].map((f) => [20, 40, 60].filter((sl) => sl > f).map((sl) => ({ type: "EMA", fast: f, slow: sl })))),
  }[strategy];
  const out = [];
  for (const p of P) for (const stopLoss of stops) for (const tp1Pct of tp1s) for (const trailing of trails) for (const dayClose of dcs)
    out.push({ p, o: { stopLoss, tp1Pct, tp1Frac: 50, trailing, dayClose } });
  return out;
}

function evaluate(x, cfg, sid, slip) {
  const { bars } = x, n = bars.length, k = Math.floor(n * TRAIN), ms = bars.map((b) => b.ms);
  const o = { capital: 1e7, buyFee: 0.015, sellFee: 0.015, slip, ...cfg.o, dayKey: (i) => bars[i].day };
  const r = BT.run(bars, sid, cfg.p, o);
  return {
    train: seg(r.equity, ms, 0, k, 1e7, r.trades.filter((t) => t.exitIdx < k)),
    test: seg(r.equity, ms, k, n, r.equity[k - 1], r.trades.filter((t) => t.exitIdx >= k)),
  };
}

function spearman(a, b) {
  const rank = (arr) => { const idx = arr.map((v, i) => [v, i]).sort((x, y) => x[0] - y[0]); const r = []; for (let i = 0; i < idx.length;) { let j = i; while (j + 1 < idx.length && idx[j + 1][0] === idx[i][0]) j++; for (let q = i; q <= j; q++) r[idx[q][1]] = (i + j) / 2; i = j + 1; } return r; };
  if (a.length < 5) return NaN;
  const ra = rank(a), rb = rank(b), n = a.length, m = (n - 1) / 2;
  let nu = 0, da = 0, db = 0;
  for (let i = 0; i < n; i++) { nu += (ra[i] - m) * (rb[i] - m); da += (ra[i] - m) ** 2; db += (rb[i] - m) ** 2; }
  return nu / Math.sqrt(da * db);
}

const results = [];
const t0 = Date.now();
for (const iv of ["60m", "5m"]) {
  const minTr = iv === "5m" ? 20 : 30;
  const sets = ETFS.map((s) => load(s, iv));
  for (const sid of ["breakout", "rsi", "bollinger", "ma_cross"]) {
    const cfgs = grid(sid, iv);
    for (const x of sets) {
      const rows = cfgs.map((cfg) => ({ cfg, ...evaluate(x, cfg, sid, 0.02) }));
      const ok = rows.filter((r) => pass(r.train, minTr));
      ok.sort((a, b) => b.train.exp - a.train.exp);
      const best = ok[0] || null;
      const valid = rows.filter((r) => r.train && r.test && r.train.trades >= minTr);
      const rho = spearman(valid.map((r) => r.train.exp), valid.map((r) => r.test.exp));
      let slip05 = null;
      if (best) slip05 = evaluate(x, best.cfg, sid, 0.05).test;
      results.push({
        iv, sid, sym: x.sym, name: x.name, combos: rows.length, trainPass: ok.length,
        testPassOfTrainPass: ok.filter((r) => pass(r.test, 0)).length,
        testPosOfTrainPass: ok.filter((r) => r.test && r.test.ret > 0).length,
        rho, best: best && { cfg: best.cfg, train: best.train, test: best.test, testSlip05: slip05 },
        bh: { train: (x.bars[Math.floor(x.bars.length * TRAIN) - 1].c / x.bars[0].o - 1) * 100, test: (x.bars[x.bars.length - 1].c / x.bars[Math.floor(x.bars.length * TRAIN)].o - 1) * 100 },
        period: { train: [x.bars[0].day, x.bars[Math.floor(x.bars.length * TRAIN) - 1].day], test: [x.bars[Math.floor(x.bars.length * TRAIN)].day, x.bars[x.bars.length - 1].day] },
      });
      process.stdout.write(".");
    }
  }
}
console.log(`\n${((Date.now() - t0) / 1000).toFixed(0)}s`);
fs.mkdirSync(path.join(__dirname, "results"), { recursive: true });
fs.writeFileSync(path.join(__dirname, "results", "etf_results.json"), JSON.stringify(results, null, 1));

// ---------- 요약 ----------
const f = (v, d = 1) => (v == null || !isFinite(v) ? "—" : v.toFixed(d));
for (const iv of ["60m", "5m"]) {
  const R = results.filter((r) => r.iv === iv);
  console.log(`\n=== ${iv === "60m" ? "1시간봉" : "5분봉"} · 학습 ${R[0].period.train.join("~")} / 검증 ${R[0].period.test.join("~")} ===`);
  for (const sid of ["breakout", "rsi", "bollinger", "ma_cross"]) {
    const S = R.filter((r) => r.sid === sid);
    const tp = S.reduce((a, r) => a + r.trainPass, 0), tpp = S.reduce((a, r) => a + r.testPassOfTrainPass, 0), tpos = S.reduce((a, r) => a + r.testPosOfTrainPass, 0);
    console.log(`\n[${sid}] 학습 목표통과 ${tp}개 → 검증에서도 통과 ${tpp}개 (${tp ? (tpp / tp * 100).toFixed(0) : 0}%), 검증 플러스 ${tp ? (tpos / tp * 100).toFixed(0) : 0}%`);
    for (const r of S) {
      if (!r.best) { console.log(`  ${r.name.padEnd(18)} 학습 통과 설정 없음 (${r.combos}개 중) · 순위상관 ${f(r.rho, 2)}`); continue; }
      const b = r.best, c = b.cfg;
      console.log(`  ${r.name.padEnd(18)} ${JSON.stringify(c.p)} 손절${c.o.stopLoss} 1차${c.o.tp1Pct} 트레일${c.o.trailing}${c.o.dayClose ? " 당일청산" : ""}`);
      console.log(`     학습: 승률 ${f(b.train.win, 0)}% 손익비 ${f(b.train.payoff, 2)} 기대값 ${f(b.train.exp, 2)}% 수익 ${f(b.train.ret)}% MDD ${f(b.train.mdd)}% 거래 ${b.train.trades} | 보유 ${f(r.bh.train)}%`);
      console.log(`     검증: 승률 ${f(b.test.win, 0)}% 손익비 ${f(b.test.payoff, 2)} 기대값 ${f(b.test.exp, 2)}% 수익 ${f(b.test.ret)}% MDD ${f(b.test.mdd)}% 거래 ${b.test.trades} | 보유 ${f(r.bh.test)}% | 슬리피지0.05% 수익 ${f(b.testSlip05.ret)}% · 순위상관 ${f(r.rho, 2)}`);
    }
  }
}
