// 대형주 역추세 1위 설정의 실체 확인: 보유 기간, 노출, 보유 대비, 손절·최대보유를 넣으면?
const fs = require("fs"), path = require("path"), BT = require("../../assets/backtest.js");
const KST = 9 * 3600;
const toBars = (rows) => rows.map(([u, o, h, l, c, v]) => ({ t: u + KST, ms: u * 1000, day: new Date((u + KST) * 1000).toISOString().slice(0, 10), o, h, l, c, v }));
const P = { mode: "역추세", fast: 20, slow: 60, th: 1.5, bandLen: 100, k: 2, strength: "일반", exitAt: "과매수 반락" };
const med = (a) => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; };
for (const [iv, label, etf] of [["60m", "대형주 1시간봉", false], ["1d", "대형주 일봉", false], ["etf60m", "ETF 1시간봉", true]]) {
  let sets;
  if (etf) sets = ["069500.KS", "122630.KS", "114800.KS", "252670.KS", "229200.KS", "233740.KS"].map((s) => toBars(JSON.parse(fs.readFileSync(path.join(__dirname, "../etf/data", `${s}_60m.json`))).bars));
  else sets = Object.values(JSON.parse(fs.readFileSync(path.join(__dirname, "data", `stocks_${iv}.json`)))).map(toBars).filter((b) => b.length > (iv === "1d" ? 1500 : 500));
  console.log(`\n== ${label} (${sets.length}종목) · 역추세 ±1.5 · SS20/60 · 과매수 반락 매도 ==`);
  for (const [name, extra] of [["손절 없음", {}], ["손절 5%", { stopLoss: 5 }], ["손절 8%", { stopLoss: 8 }], ["손절 5% + 최대보유", { stopLoss: 5, maxHold: iv === "1d" ? 40 : 60 }]]) {
    const all = { train: [], test: [] }, bh = { train: [], test: [] }, ret = { train: [], test: [] }, hold = [], expo = [];
    for (const bars of sets) {
      const n = bars.length, k = Math.floor(n * 0.7);
      const r = BT.run(bars, "spo", P, { buyFee: 0.015, sellFee: etf ? 0.015 : 0.215, slip: etf ? 0.02 : 0.05, ...extra, dayKey: (i) => bars[i].day });
      [["train", 0, k], ["test", k, n]].forEach(([s, a, b]) => {
        all[s].push(...r.trades.filter((t) => t.exitIdx >= a && t.exitIdx < b));
        bh[s].push((bars[b - 1].c / bars[a].o - 1) * 100);
        ret[s].push((r.equity[b - 1] / (a ? r.equity[a - 1] : 1e7) - 1) * 100);
      });
      r.trades.forEach((t) => hold.push(t.bars)); expo.push(r.stats.exposure);
    }
    const s = (seg) => { const t = all[seg], W = t.filter((z) => z.pnl > 0), L = t.filter((z) => z.pnl <= 0); const aw = W.reduce((a, z) => a + z.ret, 0) / (W.length || 1), al = L.reduce((a, z) => a + z.ret, 0) / (L.length || 1);
      return `승률 ${(W.length / (t.length || 1) * 100).toFixed(0)}% 손익비 ${(al < 0 ? aw / -al : 0).toFixed(2)} 평균수익 ${aw.toFixed(1)}% 평균손실 ${al.toFixed(1)}% 거래 ${t.length} | 종목 수익 중앙값 ${med(ret[seg]).toFixed(1)}% vs 보유 ${med(bh[seg]).toFixed(1)}%`; };
    console.log(`  [${name}] 평균 보유 ${med(hold)}봉 · 시장 노출 ${med(expo).toFixed(0)}%`);
    console.log(`     학습: ${s("train")}`);
    console.log(`     검증: ${s("test")}`);
  }
}
