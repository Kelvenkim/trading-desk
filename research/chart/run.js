/*
 * 차트 매매 셋업 검증 — 사이트와 같은 엔진(assets/backtest.js)
 *  시총 상위 149종목 일봉 2013~2026: 학습 ~2021-12 / 검증 2022-01~ (2022 하락장 포함)
 *  매 거래 위험 = 손절까지 거리, 결과를 R(손절 폭 대비 배수)로 평가
 *  비용: 매수 0.015%, 매도 0.215%(세금 포함), 슬리피지 0.05%
 * 실행: node research/chart/run.js
 */
const fs = require("fs"), path = require("path");
const BT = require("../../assets/backtest.js");
const J = JSON.parse(fs.readFileSync(path.join(__dirname, "data/daily150.json")));
const SPLIT = "2022-01-01";
const KS = Object.entries(J.ks200).sort();
const ksMap = new Map(), ksArr = KS.map(([, v]) => v);
const ksSma = BT.sma(ksArr, 200);
KS.forEach(([d], i) => ksMap.set(d, ksArr[i] > ksSma[i]));

const sets = Object.entries(J.stocks).map(([code, rows]) => {
  const bars = rows.map(([d, o, h, l, c, v]) => ({ t: d, ms: Date.parse(d + "T00:00:00Z"), day: d, o, h, l, c, v }));
  let last = true;
  const mkt = bars.map((b) => { if (ksMap.has(b.day)) last = ksMap.get(b.day); return last; });
  return { code, name: J.names[code], bars, mkt, k: bars.findIndex((b) => b.day >= SPLIT) };
}).filter((x) => x.k > 300);
const yrsTrain = (Date.parse(SPLIT) - Date.parse("2014-01-01")) / 31557600000, yrsTest = (Date.parse("2026-10-30") - Date.parse(SPLIT)) / 31557600000;

const prod = (...arrs) => arrs.reduce((acc, a) => acc.flatMap((x) => a.map((y) => [...x, y])), [[]]);
const TGT = [["다음 저항", 1.5], ["다음 저항", 2], ["2R", 2], ["3R", 3]];
const SIG = prod(["돌파 후 되돌림", "추세 눌림목", "지지선 반등"], [3, 5, 8], [0.3, 0.6], [0.2, 0.5], TGT, ["없음", "200일선 위에서만", "시장 상승장만"])
  .map(([setup, pivot, tol, buf, [target, minRR], filter]) => ({ setup, pivot, tol, buf, target, minRR, filter, window: 10, maxStop: 15 }));
const BE = [0, 1];

BT.STRATEGIES._pre = { params: [], signals: (b, p) => p.sig };
const f = (v, d = 2) => (v == null || !isFinite(v) ? "—" : v.toFixed(d));
const t0 = Date.now();
const rows = [];
let done = 0;
for (const s of SIG) {
  const sigs = sets.map((x) => BT.chartSetup(x.bars, { ...s, filter: s.filter === "시장 상승장만" ? "없음" : s.filter, mkt: s.filter === "시장 상승장만" ? x.mkt : null }));
  for (const be of BE) {
    const T = { train: [], test: [] };
    let conc = new Map();
    sets.forEach((x, j) => {
      const r = BT.run(x.bars, "_pre", { sig: { entry: sigs[j].entry, exit: sigs[j].exit, plan: sigs[j].plan, lines: [] } },
        { sizing: "risk", riskPct: 1, beAfterR: be, buyFee: 0.015, sellFee: 0.215, slip: 0.05 });
      r.trades.forEach((t) => {
        (t.entryIdx < x.k ? T.train : T.test).push(t);
        for (let i = t.entryIdx; i <= t.exitIdx; i++) { const d = x.bars[i].day; conc.set(d, (conc.get(d) || 0) + 1); }
      });
    });
    const sum = (arr, yrs) => {
      const rs = arr.map((t) => t.r).filter((v) => isFinite(v));
      const W = rs.filter((v) => v > 0), L = rs.filter((v) => v <= 0);
      const aw = W.length ? W.reduce((a, v) => a + v, 0) / W.length : 0, al = L.length ? L.reduce((a, v) => a + v, 0) / L.length : 0;
      const hold = arr.map((t) => t.bars).sort((a, b) => a - b);
      return { n: rs.length, win: rs.length ? W.length / rs.length * 100 : 0, avgR: rs.length ? rs.reduce((a, v) => a + v, 0) / rs.length : 0,
        payoff: al < 0 ? aw / -al : 0, rPerYear: rs.reduce((a, v) => a + v, 0) / yrs, hold: hold[Math.floor(hold.length / 2)] || 0 };
    };
    const cv = [...conc.values()].sort((a, b) => a - b);
    rows.push({ ...s, be, train: sum(T.train, yrsTrain), test: sum(T.test, yrsTest), concMed: cv[Math.floor(cv.length / 2)] || 0, concP95: cv[Math.floor(cv.length * 0.95)] || 0 });
  }
  if (++done % 50 === 0) console.error(`${done}/${SIG.length} ${((Date.now() - t0) / 1000).toFixed(0)}s`);
}
fs.mkdirSync(path.join(__dirname, "results"), { recursive: true });
fs.writeFileSync(path.join(__dirname, "results/grid_daily.json"), JSON.stringify(rows));

const desc = (r) => `${r.setup} · 스윙 ${r.pivot} · 허용 ${r.tol}ATR · 여유 ${r.buf}ATR · 목표 ${r.target}${r.target === "다음 저항" ? `(손익비 ${r.minRR}↑)` : ""} · 필터 ${r.filter}${r.be ? " · 1R에 본전" : ""}`;
const line = (m) => `거래 ${String(m.n).padStart(5)} · 승률 ${f(m.win, 0).padStart(3)}% · 평균 ${f(m.avgR).padStart(5)}R · 손익비 ${f(m.payoff)} · 연 ${f(m.rPerYear, 0)}R · 보유 중앙값 ${m.hold}일`;
console.log(`=== 시총 상위 ${sets.length}종목 일봉 · 학습 2014~2021 (${yrsTrain.toFixed(1)}년) / 검증 2022~2026.10 (${yrsTest.toFixed(1)}년) · 설정 ${rows.length}개 · ${((Date.now() - t0) / 1000).toFixed(0)}s ===`);
const spear = (a, b) => {
  const rank = (arr) => { const idx = arr.map((v, i) => [v, i]).sort((x, y) => x[0] - y[0]); const r = []; for (let i = 0; i < idx.length;) { let j = i; while (j + 1 < idx.length && idx[j + 1][0] === idx[i][0]) j++; for (let q = i; q <= j; q++) r[idx[q][1]] = (i + j) / 2; i = j + 1; } return r; };
  const ra = rank(a), rb = rank(b), n = a.length, m = (n - 1) / 2; let nu = 0, da = 0, db = 0;
  for (let i = 0; i < n; i++) { nu += (ra[i] - m) * (rb[i] - m); da += (ra[i] - m) ** 2; db += (rb[i] - m) ** 2; }
  return nu / Math.sqrt(da * db);
};
const ok = rows.filter((r) => r.train.n >= 200 && r.test.n >= 50);
console.log(`거래 충분한 설정 ${ok.length}개 · 검증 평균R 플러스 ${(ok.filter((r) => r.test.avgR > 0).length / ok.length * 100).toFixed(0)}% · 학습↔검증 평균R 순위상관 ${f(spear(ok.map((r) => r.train.avgR), ok.map((r) => r.test.avgR)))}`);
const group = (key) => {
  const g = {};
  ok.forEach((r) => { const k = key(r); (g[k] = g[k] || []).push(r); });
  return Object.entries(g).map(([k, v]) => `  ${k.padEnd(22)} 학습 평균 ${f(v.reduce((a, r) => a + r.train.avgR, 0) / v.length)}R (승률 ${f(v.reduce((a, r) => a + r.train.win, 0) / v.length, 0)}%) → 검증 ${f(v.reduce((a, r) => a + r.test.avgR, 0) / v.length)}R (승률 ${f(v.reduce((a, r) => a + r.test.win, 0) / v.length, 0)}%) · 검증 플러스 ${(v.filter((r) => r.test.avgR > 0).length / v.length * 100).toFixed(0)}%`).join("\n");
};
console.log("\n셋업별"); console.log(group((r) => r.setup));
console.log("\n추세 필터별"); console.log(group((r) => r.filter));
console.log("\n목표가별"); console.log(group((r) => r.target + (r.target === "다음 저항" ? " " + r.minRR : "")));
console.log("\n1R 본전 손절"); console.log(group((r) => (r.be ? "1R에 본전" : "본전 이동 없음")));
console.log("\n학습 평균R 상위 5 → 검증");
ok.sort((a, b) => b.train.avgR - a.train.avgR).slice(0, 5).forEach((r, i) => console.log(`${i + 1}. ${desc(r)}\n   학습: ${line(r.train)}\n   검증: ${line(r.test)} · 동시 보유 중앙값 ${r.concMed}개 (상위5% ${r.concP95}개)`));
console.log("\n승률 50~60% 이면서 학습 평균R 상위 5 → 검증");
ok.filter((r) => r.train.win >= 50 && r.train.win <= 60).sort((a, b) => b.train.avgR - a.train.avgR).slice(0, 5).forEach((r, i) => console.log(`${i + 1}. ${desc(r)}\n   학습: ${line(r.train)}\n   검증: ${line(r.test)}`));
