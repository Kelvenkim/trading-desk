const fs = require("fs"), path = require("path"), BT = require("../../assets/backtest.js");
const KST = 9 * 3600;
const toBars = (rows) => rows.map(([u, o, h, l, c, v]) => ({ t: u + KST, ms: u * 1000, day: new Date((u + KST) * 1000).toISOString().slice(0, 10), o, h, l, c, v }));
const etfs = [["069500.KS", "KODEX 200"], ["122630.KS", "KODEX 레버리지"], ["229200.KS", "KODEX 코스닥150"]];
const cfgs = [
  ["전체기간 1위: 추세 SS5/90 · 손절3 · 트레일링10", { mode: "추세", fast: 5, slow: 90 }, { stopLoss: 3, trailing: 10 }],
  ["학습 1위: 추세 SS20/90 · 손절3 · 익절40", { mode: "추세", fast: 20, slow: 90 }, { stopLoss: 3, takeProfit: 40 }],
];
for (const [label, p, r] of cfgs) {
  console.log(`\n${label}`);
  for (const [s, name] of etfs) {
    const b = toBars(JSON.parse(fs.readFileSync(path.join(__dirname, "../etf/data", `${s}_60m.json`))).bars), n = b.length, k = Math.floor(n * 0.7);
    const res = BT.run(b, "spo", { ...p, th: 1, bandLen: 100, k: 2, strength: "일반", exitAt: "0선 회복" }, { buyFee: 0.015, sellFee: 0.015, slip: 0.02, ...r });
    const seg = (a, z) => { let pk = a ? res.equity[a - 1] : 1e7, m = 0; for (let i = a; i < z; i++) { pk = Math.max(pk, res.equity[i]); m = Math.min(m, res.equity[i] / pk - 1); }
      const t = res.trades.filter((x) => x.exitIdx >= a && x.exitIdx < z), W = t.filter((x) => x.pnl > 0), L = t.filter((x) => x.pnl <= 0);
      const aw = W.reduce((q, x) => q + x.ret, 0) / (W.length || 1), al = L.reduce((q, x) => q + x.ret, 0) / (L.length || 1);
      let bpk = b[a].o, bm = 0; for (let i = a; i < z; i++) { bpk = Math.max(bpk, b[i].c); bm = Math.min(bm, b[i].c / bpk - 1); }
      return `수익 ${((res.equity[z - 1] / (a ? res.equity[a - 1] : 1e7) - 1) * 100).toFixed(1)}% (보유 ${((b[z - 1].c / b[a].o - 1) * 100).toFixed(1)}%) · MDD ${(m * 100).toFixed(1)}% (보유 ${(bm * 100).toFixed(1)}%) · 승률 ${(W.length / (t.length || 1) * 100).toFixed(0)}% · 손익비 ${(al < 0 ? aw / -al : 0).toFixed(2)} · ${t.length}회`; };
    console.log(`  ${name.padEnd(14)} 노출 ${res.stats.exposure.toFixed(0)}%\n     학습: ${seg(0, k)}\n     검증: ${seg(k, n)}`);
  }
}
