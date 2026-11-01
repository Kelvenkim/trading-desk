/*
 * 종합 점수(여러 조건 합의) 검증 — 사이트와 같은 엔진
 *  ① 매수 점수(동의 조건 수)를 4→8로 올리면 승률이 오르는가
 *  ② 청산 방식(1차 익절)으로 승률을 얼마나 올릴 수 있는가
 *  ③ 전체 탐색: 학습에서 목표 기준 통과 설정 → 검증
 *  ④ 조건별 기여: 진입 순간 각 조건이 맞았을 때 vs 아니었을 때 승률
 * 학습 70% / 검증 30%. 설정 하나를 묶음 전체 종목에 똑같이 적용하고 거래를 모아서 평가.
 * 실행: node research/confluence/run.js
 */
const fs = require("fs"), path = require("path");
const BT = require("../../assets/backtest.js");
const KST = 9 * 3600;
const toBars = (rows) => rows.map(([u, o, h, l, c, v]) => ({ t: u + KST, ms: u * 1000, day: new Date((u + KST) * 1000).toISOString().slice(0, 10), o, h, l, c, v }));
BT.STRATEGIES._pre = { params: [], signals: (b, p) => ({ entry: p.entry, exit: p.exit, lines: [] }) };
const ETF6 = ["069500.KS", "122630.KS", "114800.KS", "252670.KS", "229200.KS", "233740.KS"];
const KEYS = BT.CONF_LIST.map((x) => x.key);

const GROUPS = [
  { id: "etf_1h", label: "ETF 6종 · 1시간봉", short: 24, long: 240, etf: true, minTr: 60,
    load: () => ETF6.map((s) => toBars(JSON.parse(fs.readFileSync(path.join(__dirname, "../etf/data", `${s}_60m.json`))).bars)),
    stops: [2, 3], tp1s: [0, 2, 4], trails: [0, 3], baseStop: 2 },
  { id: "stk_1h", label: "대형주 59종 · 1시간봉", short: 24, long: 240, etf: false, minTr: 100,
    load: () => Object.values(JSON.parse(fs.readFileSync(path.join(__dirname, "../spo/data/stocks_60m.json")))).map(toBars),
    stops: [2, 3], tp1s: [0, 2, 4], trails: [0, 3], baseStop: 2 },
  { id: "stk_1d", label: "대형주 55종 · 일봉 (2014~)", short: 20, long: 200, etf: false, minTr: 100,
    load: () => Object.values(JSON.parse(fs.readFileSync(path.join(__dirname, "../spo/data/stocks_1d.json")))).map(toBars).filter((b) => b.length > 1500),
    stops: [5, 8], tp1s: [0, 5, 10], trails: [0, 10], baseStop: 5 },
];
const f = (v, d = 1) => (v == null || !isFinite(v) ? "—" : v.toFixed(d));
const med = (a) => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; };

for (const G of GROUPS) {
  const t0 = Date.now();
  const sets = G.load().map((bars) => {
    const cf = BT.confluence(bars, G.short, G.long), n = bars.length;
    const score = new Array(n).fill(0).map((_, i) => KEYS.reduce((s, k) => s + (cf[k][i] ? 1 : 0), 0));
    return { bars, cf, score, n, k: Math.floor(n * 0.7) };
  });
  const sig = (x, buy, sell) => ({
    entry: x.score.map((s, i) => i > 0 && s >= buy && x.score[i - 1] < buy),
    exit: x.score.map((s) => s <= sell),
  });
  // 설정 하나 → 묶음 평가
  const evalCfg = (buy, sell, risk, keepTrades) => {
    const A = { train: { t: [], ret: [], mdd: [] }, test: { t: [], ret: [], mdd: [] } };
    sets.forEach((x) => {
      const bars = x.bars;
      const r = BT.run(bars, "_pre", sig(x, buy, sell), { buyFee: 0.015, sellFee: G.etf ? 0.015 : 0.215, slip: G.etf ? 0.02 : 0.05, tp1Frac: 50, ...risk });
      const eq = r.equity;
      for (const [seg, a, b] of [["train", 0, x.k], ["test", x.k, x.n]]) {
        const start = a ? eq[a - 1] : 1e7;
        const tr = r.trades.filter((t) => t.exitIdx >= a && t.exitIdx < b);
        if (keepTrades) tr.forEach((t) => (t.cond = KEYS.map((key) => x.cf[key][Math.max(0, t.entryIdx - 1)])));
        A[seg].t.push(...tr);
        A[seg].ret.push((eq[b - 1] / start - 1) * 100);
        let pk = start, m = 0; for (let i = a; i < b; i++) { pk = Math.max(pk, eq[i]); m = Math.min(m, eq[i] / pk - 1); }
        A[seg].mdd.push(m * 100);
      }
    });
    const sum = (S) => {
      const W = S.t.filter((z) => z.pnl > 0), L = S.t.filter((z) => z.pnl <= 0);
      const aw = W.length ? W.reduce((q, z) => q + z.ret, 0) / W.length : 0, al = L.length ? L.reduce((q, z) => q + z.ret, 0) / L.length : 0;
      return { trades: S.t.length, win: S.t.length ? W.length / S.t.length * 100 : 0, payoff: al < 0 ? aw / -al : aw > 0 ? 99 : 0,
        exp: S.t.length ? S.t.reduce((q, z) => q + z.ret, 0) / S.t.length : 0, ret: S.ret.reduce((q, v) => q + v, 0) / S.ret.length, mdd: med(S.mdd), tradesList: keepTrades ? S.t : null };
    };
    return { train: sum(A.train), test: sum(A.test) };
  };
  const line = (m) => `승률 ${f(m.win, 0).padStart(3)}% · 손익비 ${f(m.payoff, 2)} · 기대값 ${f(m.exp, 2).padStart(5)}% · 거래 ${String(m.trades).padStart(4)} · 수익 ${f(m.ret).padStart(6)}% · MDD ${f(m.mdd)}%`;
  const bh = (seg) => sets.reduce((s, x) => { const [a, b] = seg === "train" ? [0, x.k] : [x.k, x.n]; return s + (x.bars[b - 1].c / x.bars[a].o - 1) * 100; }, 0) / sets.length;

  console.log(`\n==================== ${G.label} (${sets.length}종목) · 보유 수익 학습 ${f(bh("train"))}% / 검증 ${f(bh("test"))}% ====================`);
  // ① 동의 개수별 승률
  console.log(`\n① 매수 점수(동의 조건 수)별 · 매도 점수 3 이하 · 손절 ${G.baseStop}%`);
  for (let buy = 4; buy <= 8; buy++) {
    const m = evalCfg(buy, 3, { stopLoss: G.baseStop });
    console.log(`  ${buy}개 이상  학습: ${line(m.train)}\n           검증: ${line(m.test)}`);
  }
  // ② 청산 방식
  console.log(`\n② 매수 점수 6 · 청산 방식별`);
  for (const [name, sell, risk] of [
    ["점수 3 이하 매도 · 손절", 3, { stopLoss: G.baseStop }],
    ["점수 4 이하 매도(빨리 팔기) · 손절", 4, { stopLoss: G.baseStop }],
    [`+ 1차 익절 ${G.tp1s[1]}%에서 절반`, 3, { stopLoss: G.baseStop, tp1Pct: G.tp1s[1] }],
    [`+ 1차 익절 ${G.tp1s[2]}%에서 절반`, 3, { stopLoss: G.baseStop, tp1Pct: G.tp1s[2] }],
    [`+ 1차 익절 ${G.tp1s[1]}% · 트레일링 ${G.trails[1]}%`, 3, { stopLoss: G.baseStop, tp1Pct: G.tp1s[1], trailing: G.trails[1] }],
  ]) {
    const m = evalCfg(6, sell, risk);
    console.log(`  ${name}\n     학습: ${line(m.train)}\n     검증: ${line(m.test)}`);
  }
  // ③ 전체 탐색
  const rows = [];
  for (let buy = 4; buy <= 8; buy++) for (let sell = 1; sell <= Math.min(5, buy - 1); sell++)
    for (const stopLoss of G.stops) for (const tp1Pct of G.tp1s) for (const trailing of G.trails)
      rows.push({ buy, sell, risk: { stopLoss, tp1Pct, trailing }, ...evalCfg(buy, sell, { stopLoss, tp1Pct, trailing }) });
  const pass = (m, minTr) => m.trades >= minTr && m.win >= 50 && m.payoff >= 1.5 && m.exp > 0 && m.mdd >= -20;
  const ok = rows.filter((r) => pass(r.train, G.minTr)).sort((a, b) => b.train.ret - a.train.ret);
  const desc = (r) => `매수 ${r.buy}개↑ · 매도 ${r.sell}개↓ · 손절 ${r.risk.stopLoss}% · 1차익절 ${r.risk.tp1Pct || "없음"} · 트레일링 ${r.risk.trailing || "없음"}`;
  console.log(`\n③ 전체 탐색 ${rows.length}개 설정 → 학습에서 목표 기준(승률 50%+·손익비 1.5+·기대값+·MDD -20% 이내·거래 ${G.minTr}+) 통과 ${ok.length}개 → 검증도 통과 ${ok.filter((r) => pass(r.test, Math.round(G.minTr * 0.3))).length}개`);
  ok.slice(0, 3).forEach((r, i) => console.log(`  ${i + 1}. ${desc(r)}\n     학습: ${line(r.train)}\n     검증: ${line(r.test)}`));
  const wins = rows.map((r) => r.train.win), winsT = rows.map((r) => r.test.win);
  console.log(`  참고: 전체 설정 학습 승률 범위 ${f(Math.min(...wins), 0)}~${f(Math.max(...wins), 0)}%, 검증 ${f(Math.min(...winsT), 0)}~${f(Math.max(...winsT), 0)}%`);
  // ④ 조건별 기여
  const m = evalCfg(5, 3, { stopLoss: G.baseStop }, true);
  console.log(`\n④ 조건별 기여 (매수 점수 5 · 매도 3 · 손절 ${G.baseStop}% · 진입 순간 그 조건이 맞았을 때 vs 아니었을 때 승률)`);
  KEYS.forEach((key, j) => {
    const part = (T) => { const on = T.filter((t) => t.cond[j]), off = T.filter((t) => !t.cond[j]); const w = (a) => (a.length ? a.filter((t) => t.pnl > 0).length / a.length * 100 : NaN);
      return `맞음 ${f(w(on), 0)}% (${on.length}) / 아님 ${f(w(off), 0)}% (${off.length})`; };
    console.log(`  ${BT.CONF_LIST[j].label.padEnd(26)} 학습 ${part(m.train.tradesList)} · 검증 ${part(m.test.tradesList)}`);
  });
  console.log(`  (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
}
