// 1시간봉 거래량 돌파: 고르지 않은 '모든 설정'의 검증 성과 분포 + 기본 설정 하나
const fs = require("fs"), path = require("path"), BT = require("../../assets/backtest.js");
const KST = 9 * 3600, D = path.join(__dirname, "data");
const load = (s) => { const j = JSON.parse(fs.readFileSync(path.join(D, `${s}_60m.json`))); return { name: j.name, bars: j.bars.map(([u, o, h, l, c, v]) => ({ t: u + KST, ms: u * 1000, day: new Date((u + KST) * 1000).toISOString().slice(0, 10), o, h, l, c, v })) }; };
const q = (a, p) => { const s = [...a].sort((x, y) => x - y); return s[Math.floor((s.length - 1) * p)]; };
for (const sym of ["069500.KS", "122630.KS", "229200.KS", "233740.KS"]) {
  const x = load(sym), n = x.bars.length, k = Math.floor(n * 0.7), test = x.bars.slice(k);
  const bh = (test[test.length - 1].c / test[0].o - 1) * 100;
  const rets = [], wins = [], pays = [], exps = [];
  for (const lb of [6, 12, 24]) for (const vm of [1, 1.5, 2]) for (const ex of [6, 12]) for (const sl of [1, 2]) for (const tp1 of [0, 1, 2]) for (const tr of [0, 1, 2]) for (const dc of [true, false]) {
    // 검증 구간만 따로 돌림 (앞쪽 지표 계산용으로 50봉 앞에서 시작)
    const bars = x.bars.slice(k - 50);
    const r = BT.run(bars, "breakout", { lookback: lb, volLen: 20, volMult: vm, exitLen: ex }, { buyFee: 0.015, sellFee: 0.015, slip: 0.02, stopLoss: sl, tp1Pct: tp1, tp1Frac: 50, trailing: tr, dayClose: dc, dayKey: (i) => bars[i].day });
    const eq = r.equity, ret = (eq[eq.length - 1] / eq[49] - 1) * 100, t = r.trades.filter((t) => t.entryIdx >= 50);
    rets.push(ret); exps.push(t.length ? t.reduce((a, z) => a + z.ret, 0) / t.length : 0);
    const W = t.filter((z) => z.pnl > 0), L = t.filter((z) => z.pnl <= 0);
    wins.push(t.length ? W.length / t.length * 100 : 0);
    const aw = W.length ? W.reduce((a, z) => a + z.ret, 0) / W.length : 0, al = L.length ? L.reduce((a, z) => a + z.ret, 0) / L.length : 0;
    pays.push(al < 0 ? aw / -al : 0);
  }
  const plain = (() => { const bars = x.bars.slice(k - 50); const r = BT.run(bars, "breakout", { lookback: 24, volLen: 20, volMult: 1.5, exitLen: 12 }, { buyFee: 0.015, sellFee: 0.015, slip: 0.02, stopLoss: 2, dayKey: (i) => bars[i].day }); return { ret: (r.equity[r.equity.length - 1] / r.equity[49] - 1) * 100, st: r.stats }; })();
  console.log(`${x.name.padEnd(16)} 검증 ${test[0].day}~ 보유 ${bh.toFixed(1)}% | 648개 설정 검증수익: 플러스 ${(rets.filter((v) => v > 0).length / rets.length * 100).toFixed(0)}%, 중앙값 ${q(rets, 0.5).toFixed(1)}%, 하위25% ${q(rets, 0.25).toFixed(1)}%, 상위25% ${q(rets, 0.75).toFixed(1)}% | 승률 중앙값 ${q(wins, 0.5).toFixed(0)}% 손익비 중앙값 ${q(pays, 0.5).toFixed(2)} 기대값 중앙값 ${q(exps, 0.5).toFixed(2)}%`);
  console.log(`   기본 설정(24봉 돌파·거래량1.5배·12봉 이탈·손절2%): 수익 ${plain.ret.toFixed(1)}% 승률 ${plain.st.winRate.toFixed(0)}% 손익비 ${plain.st.payoff.toFixed(2)} 거래 ${plain.st.trades} MDD ${plain.st.mdd.toFixed(1)}% 노출 ${plain.st.exposure.toFixed(0)}%`);
}
