/*
 * 실제 계좌처럼 운용: 하나의 계좌로 여러 종목, 동시 보유 최대 K개, 거래마다 계좌의 risk%만 위험
 *  셋업: 추세 눌림목 · 스윙 5 · 허용 0.3ATR · 여유 0.5ATR · 목표 3R · 코스피200이 200일선 위일 때만
 *  신호 다음 날 시가 매수, 장중 손절가·목표가 체결(같은 날 둘 다 닿으면 손절), 시가가 이미 손절가 아래/목표가 위면 건너뜀
 *  한 종목 비중은 계좌의 maxPos% 까지, 현금이 모자라면 남은 현금만큼만
 *  같은 날 신호가 여러 개면 시가총액 큰 종목부터 (중립 규칙)
 *  비용: 매수 0.015%+슬리피지 0.05%, 매도 0.215%+슬리피지 0.05%
 */
const fs = require("fs"), path = require("path");
const BT = require("../../assets/backtest.js");
const J = JSON.parse(fs.readFileSync(path.join(__dirname, "data/daily150.json")));
const KS = Object.entries(J.ks200).sort(), ksArr = KS.map(([, v]) => v), ksSma = BT.sma(ksArr, 200);
const ksUp = new Map(KS.map(([d], i) => [d, ksArr[i] > ksSma[i]]));
const ksPx = new Map(KS);

const P = { setup: "추세 눌림목", pivot: 5, window: 10, tol: 0.3, buf: 0.5, target: "3R", minRR: 2, maxStop: 15, filter: "없음" };
const codes = Object.keys(J.stocks);   // 시가총액 순
const S = codes.map((code) => {
  const bars = J.stocks[code].map(([d, o, h, l, c, v]) => ({ t: d, ms: Date.parse(d + "T00:00:00Z"), day: d, o, h, l, c, v }));
  let last = true; const mkt = bars.map((b) => { if (ksUp.has(b.day)) last = ksUp.get(b.day); return last; });
  const sg = BT.chartSetup(bars, { ...P, mkt });
  return { code, name: J.names[code], bars, idx: new Map(bars.map((b, i) => [b.day, i])), sg };
});
const DAYS = [...new Set(S.flatMap((s) => s.bars.map((b) => b.day)))].sort().filter((d) => d >= "2014-01-01");

// 주도주 점수: 6개월(126일) 수익률. rsTop>0 이면 그날 전체 종목 중 상위 rsTop 비율 안에 드는 종목만
S.forEach((s) => { s.m6 = s.bars.map((b, i) => (i >= 126 ? b.c / s.bars[i - 126].c - 1 : NaN)); s.hi52 = s.bars.map((b, i) => { if (i < 250) return NaN; let m = 0; for (let k = i - 250; k <= i; k++) m = Math.max(m, s.bars[k].h); return b.c / m; }); });
const rsCut = new Map();
for (const day of DAYS) { const v = S.map((s) => { const i = s.idx.get(day); return i == null ? NaN : s.m6[i]; }).filter((x) => isFinite(x)).sort((a, b) => b - a); rsCut.set(day, v); }
let ORDER = "cap", RS_TOP = 0, NEAR_HI = 0;
function simulate(maxN, risk, maxPos, from = "2014-01-01", to = "2099-01-01") {
  let cash = 1e7; const pos = new Map(); const eq = [], trades = [];
  const BUY = 1 + 0.00015 + 0.0005, SELL = 1 - 0.00215 - 0.0005;
  for (const day of DAYS) {
    if (day < from || day > to) continue;
    // 1) 오늘 시가 진입: 어제 신호
    const value = () => cash + [...pos.values()].reduce((a, p) => a + p.q * p.last, 0);
    const cands = [];
    for (const s of S) {
      const i = s.idx.get(day); if (i == null || i < 1 || pos.has(s.code)) continue;
      if (!s.sg.entry[i - 1]) continue;
      const sd = s.bars[i - 1].day, m6 = s.m6[i - 1];
      if (RS_TOP > 0) { const v = rsCut.get(sd) || []; const cut = v[Math.floor(v.length * RS_TOP)]; if (!(isFinite(m6) && m6 >= cut)) continue; }
      if (NEAR_HI > 0 && !(s.hi52[i - 1] >= 1 - NEAR_HI)) continue;
      cands.push({ s, i, plan: s.sg.plan[i - 1], m6 });
    }
    if (ORDER === "rs") cands.sort((a, b) => (b.m6 || -9) - (a.m6 || -9));
    for (const c of cands) {
      if (pos.size >= maxN) break;
      const b = c.s.bars[c.i], px = b.o * BUY, { stop, target } = c.plan;
      if (b.o <= stop || b.o >= target) continue;
      const eqNow = value();
      const perShareRisk = px - stop * SELL;
      let q = (eqNow * risk) / perShareRisk;
      q = Math.min(q, (eqNow * maxPos) / px, cash / px);
      if (q * px < eqNow * 0.01) continue;
      cash -= q * px;
      pos.set(c.s.code, { s: c.s, q, entry: px, stop, target, ent: day, last: b.o, riskCash: q * perShareRisk });
    }
    // 2) 장중 손절·목표
    for (const [code, p] of [...pos]) {
      const i = p.s.idx.get(day); if (i == null) continue;
      const b = p.s.bars[i];
      let exitPx = null, why = "";
      if (b.l <= p.stop) { exitPx = Math.min(b.o, p.stop); why = "손절"; }
      else if (b.h >= p.target) { exitPx = Math.max(b.o, p.target); why = "목표"; }
      p.last = b.c;
      if (exitPx != null) {
        const got = p.q * exitPx * SELL; cash += got;
        trades.push({ code, name: p.s.name, ent: p.ent, exit: day, r: (got - p.q * p.entry) / p.riskCash, ret: got / (p.q * p.entry) - 1, why });
        pos.delete(code);
      }
    }
    eq.push([day, cash + [...pos.values()].reduce((a, p) => a + p.q * p.last, 0), [...pos.values()].reduce((a, p) => a + p.q * p.last, 0)]);
  }
  return { eq, trades };
}
const stats = (eq, trades) => {
  const v = eq.map((e) => e[1]), yrs = (Date.parse(eq[eq.length - 1][0]) - Date.parse(eq[0][0])) / 31557600000;
  let pk = v[0], mdd = 0; v.forEach((x) => { pk = Math.max(pk, x); mdd = Math.min(mdd, x / pk - 1); });
  const W = trades.filter((t) => t.r > 0);
  return { cagr: (Math.pow(v[v.length - 1] / v[0], 1 / yrs) - 1) * 100, mdd: mdd * 100, n: trades.length, win: trades.length ? W.length / trades.length * 100 : 0,
    avgR: trades.length ? trades.reduce((a, t) => a + t.r, 0) / trades.length : 0, expo: eq.reduce((a, e) => a + e[2] / e[1], 0) / eq.length * 100 };
};
const yearly = (eq) => { const y = {}; let prev = eq[0][1]; eq.forEach(([d, v], k) => { const yr = d.slice(0, 4); if (k + 1 === eq.length || eq[k + 1][0].slice(0, 4) !== yr) { y[yr] = (v / prev - 1) * 100; prev = v; } }); return y; };
const ksYearly = () => { const y = {}; let prev = null, prevY = null; for (const [d, v] of KS) { const yr = d.slice(0, 4); if (yr < "2014") { prev = v; continue; } if (prevY && yr !== prevY) { y[prevY] = (last / prev - 1) * 100; prev = last; } prevY = yr; var last = v; } y[prevY] = (last / prev - 1) * 100; return y; };

const f = (v, d = 1) => v.toFixed(d);
console.log("코스피200 지수(배당 제외) 같은 기간: 2014~2026 연", f((Math.pow(ksPx.get(KS[KS.length - 1][0]) / ksPx.get(DAYS[0]), 1 / ((Date.parse(KS[KS.length - 1][0]) - Date.parse(DAYS[0])) / 31557600000)) - 1) * 100), "%");
console.log("\n동시 보유·위험 크기별 (2014-01 ~ 2026-10)");
for (const [n, r, mp] of [[5, 0.01, 0.25], [8, 0.01, 0.2], [10, 0.01, 0.15], [5, 0.02, 0.3], [10, 0.015, 0.2]]) {
  const { eq, trades } = simulate(n, r, mp);
  const a = stats(eq, trades);
  const tr = simulate(n, r, mp, "2014-01-01", "2021-12-31"), te = simulate(n, r, mp, "2022-01-01");
  const A = stats(tr.eq, tr.trades), B = stats(te.eq, te.trades);
  console.log(`  최대 ${String(n).padStart(2)}종목 · 1회 위험 ${r * 100}% · 종목당 최대 ${mp * 100}%  → 전체 연 ${f(a.cagr)}% MDD ${f(a.mdd)}% 거래 ${a.n} 승률 ${f(a.win, 0)}% 평균 ${f(a.avgR, 2)}R 평균 투자비중 ${f(a.expo, 0)}% | 학습(14~21) 연 ${f(A.cagr)}% MDD ${f(A.mdd)}% | 검증(22~26) 연 ${f(B.cagr)}% MDD ${f(B.mdd)}%`);
}
console.log("\n신호 고르는 방식 (최대 8종목 · 위험 1% · 종목당 20%)");
let best = null;
for (const [o, rs, hi, name] of [["cap", 0, 0, "시가총액 큰 순 (기본)"], ["rs", 0, 0, "6개월 수익률 높은 순"], ["rs", 0.3, 0, "주도주(6개월 수익 상위 30%)만"], ["rs", 0.2, 0, "주도주(상위 20%)만"], ["rs", 0, 0.1, "52주 고점 10% 이내만"], ["rs", 0.3, 0.15, "주도주 30% + 52주 고점 15% 이내"]]) {
  ORDER = o; RS_TOP = rs; NEAR_HI = hi;
  const a = stats(...Object.values(simulate(8, 0.01, 0.2))), A = stats(...Object.values(simulate(8, 0.01, 0.2, "2014-01-01", "2021-12-31"))), B = stats(...Object.values(simulate(8, 0.01, 0.2, "2022-01-01")));
  console.log(`  ${name.padEnd(26)} 전체 연 ${f(a.cagr)}% MDD ${f(a.mdd)}% 거래 ${a.n} 승률 ${f(a.win, 0)}% 평균 ${f(a.avgR, 2)}R | 학습 연 ${f(A.cagr)}% (${f(A.avgR, 2)}R) | 검증 연 ${f(B.cagr)}% (${f(B.avgR, 2)}R)`);
}
ORDER = "rs"; RS_TOP = 0.3; NEAR_HI = 0;
const { eq, trades } = simulate(8, 0.01, 0.2);
const Y = yearly(eq), K = ksYearly();
console.log("\n연도별 (주도주 30% · 최대 8종목 · 위험 1%) vs 코스피200");
Object.keys(Y).forEach((y) => console.log(`  ${y}: 전략 ${f(Y[y]).padStart(6)}%  코스피200 ${f(K[y] ?? NaN).padStart(6)}%  거래 ${trades.filter((t) => t.exit.startsWith(y)).length}회 승률 ${f(trades.filter((t) => t.exit.startsWith(y) && t.r > 0).length / Math.max(1, trades.filter((t) => t.exit.startsWith(y)).length) * 100, 0)}%`));
fs.writeFileSync(path.join(__dirname, "results/portfolio_trades.json"), JSON.stringify(trades));
