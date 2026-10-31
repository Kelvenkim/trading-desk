// 돌파 + 추세 필터(종가 > EMA N) — 승률이 올라가는지, 학습/검증 둘 다 확인
const fs = require("fs"), path = require("path"), BT = require("../../assets/backtest.js");
const KST = 9 * 3600, D = path.join(__dirname, "data");
const load = (s) => { const j = JSON.parse(fs.readFileSync(path.join(D, `${s}_60m.json`))); return { name: j.name, bars: j.bars.map(([u, o, h, l, c, v]) => ({ t: u + KST, ms: u * 1000, day: new Date((u + KST) * 1000).toISOString().slice(0, 10), o, h, l, c, v })) }; };
const rules = (ema, tp1) => ({ entry: { logic: "AND", rules: [
  { a: { ind: "close" }, op: ">", b: { ind: "hh", n: 24 } },
  { a: { ind: "volume" }, op: ">", b: { ind: "vol_sma", n: 20 }, mult: 1.5 },
  ...(ema ? [{ a: { ind: "close" }, op: ">", b: { ind: "ema", n: ema } }, { a: { ind: "ema", n: 20 }, op: ">", b: { ind: "ema", n: ema } }] : []),
] }, exit: { logic: "OR", rules: [{ a: { ind: "close" }, op: "<", b: { ind: "ll", n: 12 } }] } });
const seg = (r, bars, a, b) => {
  const t = r.trades.filter((z) => z.exitIdx >= a && z.exitIdx < b), W = t.filter((z) => z.pnl > 0), L = t.filter((z) => z.pnl <= 0);
  const aw = W.length ? W.reduce((s, z) => s + z.ret, 0) / W.length : 0, al = L.length ? L.reduce((s, z) => s + z.ret, 0) / L.length : 0;
  let pk = r.equity[a > 0 ? a - 1 : 0], mdd = 0; for (let i = a; i < b; i++) { pk = Math.max(pk, r.equity[i]); mdd = Math.min(mdd, r.equity[i] / pk - 1); }
  return `수익 ${((r.equity[b - 1] / (a ? r.equity[a - 1] : 1e7) - 1) * 100).toFixed(1).padStart(6)}% 승률 ${(t.length ? W.length / t.length * 100 : 0).toFixed(0).padStart(3)}% 손익비 ${(al < 0 ? aw / -al : 0).toFixed(2)} 거래 ${String(t.length).padStart(2)} MDD ${(mdd * 100).toFixed(1)}%`;
};
for (const sym of ["069500.KS", "122630.KS", "229200.KS", "233740.KS"]) {
  const x = load(sym), n = x.bars.length, k = Math.floor(n * 0.7);
  const bhT = (x.bars[k - 1].c / x.bars[0].o - 1) * 100, bhV = (x.bars[n - 1].c / x.bars[k].o - 1) * 100;
  console.log(`\n${x.name}  (보유: 학습 ${bhT.toFixed(1)}% / 검증 ${bhV.toFixed(1)}%)`);
  for (const [ema, tp1, label] of [[0, 0, "필터 없음"], [120, 0, "추세 필터 EMA120"], [120, 2, "추세 필터 + 2%에서 절반 익절"], [240, 2, "추세 필터 EMA240 + 절반 익절"]]) {
    const r = BT.run(x.bars, "custom", { rules: rules(ema, tp1) }, { buyFee: 0.015, sellFee: 0.015, slip: 0.02, stopLoss: 2, tp1Pct: tp1, tp1Frac: 50, dayKey: (i) => x.bars[i].day });
    console.log(`  ${label.padEnd(24)} 학습: ${seg(r, x.bars, 0, k)}  |  검증: ${seg(r, x.bars, k, n)}`);
  }
}
