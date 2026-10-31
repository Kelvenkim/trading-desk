// ETF 1시간봉: VWAP 기울기(24봉 이동) 전략을 종목별로, 보유와 수익·MDD 비교
const fs = require("fs"), path = require("path"), BT = require("../../assets/backtest.js");
const KST = 9 * 3600;
const toBars = (rows) => rows.map(([u, o, h, l, c, v]) => ({ t: u + KST, ms: u * 1000, day: new Date((u + KST) * 1000).toISOString().slice(0, 10), o, h, l, c, v }));
const etfs = [["069500.KS", "KODEX 200"], ["122630.KS", "KODEX 레버리지"], ["229200.KS", "KODEX 코스닥150"], ["233740.KS", "코스닥150레버리지"], ["114800.KS", "KODEX 인버스"]];
const base = { kind: "N봉 이동", n: 24, mode: "기울기", buf: 0, confirm: 1, slopeN: 3, trendN: 240, noLate: 0 };
for (const [label, p, o] of [["기울기 24봉 · 손절 2%", { ...base, trend: "없음" }, { stopLoss: 2 }], ["기울기 24봉 + 큰 추세 필터 · 손절 2%", { ...base, trend: "이동 VWAP 위에서만 매수" }, { stopLoss: 2 }]]) {
  console.log(`\n${label}`);
  for (const [s, name] of etfs) {
    const b = toBars(JSON.parse(fs.readFileSync(path.join(__dirname, "../etf/data", `${s}_60m.json`))).bars), n = b.length, k = Math.floor(n * 0.7);
    const r = BT.run(b, "vwap", p, { buyFee: 0.015, sellFee: 0.015, slip: 0.02, ...o });
    const seg = (a, z) => { let pk = a ? r.equity[a - 1] : 1e7, m = 0; for (let i = a; i < z; i++) { pk = Math.max(pk, r.equity[i]); m = Math.min(m, r.equity[i] / pk - 1); }
      let bp = b[a].o, bm = 0; for (let i = a; i < z; i++) { bp = Math.max(bp, b[i].c); bm = Math.min(bm, b[i].c / bp - 1); }
      const t = r.trades.filter((x) => x.exitIdx >= a && x.exitIdx < z), W = t.filter((x) => x.pnl > 0), L = t.filter((x) => x.pnl <= 0);
      const aw = W.reduce((q, x) => q + x.ret, 0) / (W.length || 1), al = L.reduce((q, x) => q + x.ret, 0) / (L.length || 1);
      return `수익 ${((r.equity[z - 1] / (a ? r.equity[a - 1] : 1e7) - 1) * 100).toFixed(1).padStart(6)}% (보유 ${((b[z - 1].c / b[a].o - 1) * 100).toFixed(1)}%) · MDD ${(m * 100).toFixed(1)}% (보유 ${(bm * 100).toFixed(1)}%) · 승률 ${(W.length / (t.length || 1) * 100).toFixed(0)}% · 손익비 ${(al < 0 ? aw / -al : 0).toFixed(2)} · ${t.length}회`; };
    console.log(`  ${name.padEnd(12)} 노출 ${r.stats.exposure.toFixed(0)}%\n    학습: ${seg(0, k)}\n    검증: ${seg(k, n)}`);
  }
}
