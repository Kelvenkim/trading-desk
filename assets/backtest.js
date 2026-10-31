/* =========================================================
 * 백테스트 엔진
 *  - 롱 온리, 전액 진입/청산
 *  - 신호는 봉 종가 기준으로 판단, 체결은 다음 봉 시가 (미래 참조 방지)
 *  - 손절/익절/트레일링은 봉 안에서 체결 (같은 봉에 둘 다 닿으면 손절 우선 = 보수적)
 * bars: [{t, o, h, l, c, v}]
 * ========================================================= */
const BT = (() => {
  // ---------- 지표 ----------
  const sma = (a, n) => {
    const out = new Array(a.length).fill(NaN);
    let s = 0;
    for (let i = 0; i < a.length; i++) {
      s += a[i];
      if (i >= n) s -= a[i - n];
      if (i >= n - 1) out[i] = s / n;
    }
    return out;
  };
  const ema = (a, n) => {
    const out = new Array(a.length).fill(NaN);
    const k = 2 / (n + 1);
    let prev = NaN;
    for (let i = 0; i < a.length; i++) {
      if (i === n - 1) {
        let s = 0;
        for (let j = 0; j < n; j++) s += a[j];
        prev = s / n;
        out[i] = prev;
      } else if (i >= n) {
        prev = a[i] * k + prev * (1 - k);
        out[i] = prev;
      }
    }
    return out;
  };
  // Wilder RSI (TradingView ta.rsi 와 동일한 방식)
  const rsi = (a, n) => {
    const out = new Array(a.length).fill(NaN);
    let ag = 0, al = 0;
    for (let i = 1; i < a.length; i++) {
      const d = a[i] - a[i - 1];
      const g = Math.max(d, 0), l = Math.max(-d, 0);
      if (i <= n) {
        ag += g / n; al += l / n;
        if (i === n) out[i] = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
      } else {
        ag = (ag * (n - 1) + g) / n;
        al = (al * (n - 1) + l) / n;
        out[i] = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
      }
    }
    return out;
  };
  // 모표준편차 (TradingView ta.stdev 와 동일)
  const stdev = (a, n) => {
    const m = sma(a, n);
    const out = new Array(a.length).fill(NaN);
    for (let i = n - 1; i < a.length; i++) {
      let s = 0;
      for (let j = i - n + 1; j <= i; j++) s += (a[j] - m[i]) ** 2;
      out[i] = Math.sqrt(s / n);
    }
    return out;
  };
  // 직전 n개 봉(현재 봉 제외)의 최고/최저
  const prevHighest = (a, n) => a.map((_, i) => (i < n ? NaN : Math.max(...a.slice(i - n, i))));
  const prevLowest = (a, n) => a.map((_, i) => (i < n ? NaN : Math.min(...a.slice(i - n, i))));
  const shift1 = (a) => a.map((_, i) => (i === 0 ? NaN : a[i - 1]));

  // ---------- 전략 정의 ----------
  // signals(bars, p) → { entry: bool[], exit: bool[], lines: [{name, data, color}] }
  const STRATEGIES = {
    ma_cross: {
      name: "이동평균 크로스",
      desc: "단기선이 장기선을 위로 뚫으면 매수, 아래로 뚫으면 매도. 추세 추종의 기본형.",
      params: [
        { key: "type", label: "이평 종류", type: "select", options: ["SMA", "EMA"], def: "SMA" },
        { key: "fast", label: "단기", def: 20, min: 2, max: 200 },
        { key: "slow", label: "장기", def: 60, min: 3, max: 400 },
      ],
      signals(b, p) {
        const c = b.map((x) => x.c), f = p.type === "EMA" ? ema : sma;
        const fa = f(c, p.fast), sl = f(c, p.slow);
        const entry = c.map((_, i) => i > 0 && fa[i - 1] <= sl[i - 1] && fa[i] > sl[i]);
        const exit = c.map((_, i) => i > 0 && fa[i - 1] >= sl[i - 1] && fa[i] < sl[i]);
        return { entry, exit, lines: [
          { name: `${p.type}${p.fast}`, data: fa, color: "#f5b642" },
          { name: `${p.type}${p.slow}`, data: sl, color: "#7aa2ff" },
        ] };
      },
    },
    rsi: {
      name: "RSI 역추세",
      desc: "RSI가 과매도선을 아래에서 위로 올라오면 매수, 과매수선을 넘으면 매도.",
      params: [
        { key: "period", label: "기간", def: 14, min: 2, max: 100 },
        { key: "low", label: "과매도", def: 30, min: 1, max: 50 },
        { key: "high", label: "과매수", def: 70, min: 50, max: 99 },
      ],
      signals(b, p) {
        const r = rsi(b.map((x) => x.c), p.period);
        const entry = r.map((v, i) => i > 0 && r[i - 1] <= p.low && v > p.low);
        const exit = r.map((v, i) => i > 0 && r[i - 1] <= p.high && v > p.high);
        return { entry, exit, lines: [] };
      },
    },
    bollinger: {
      name: "볼린저 박스권",
      desc: "종가가 하단 밴드 아래로 내려가면 매수, 중심선(또는 상단)을 넘으면 매도. 박스권 종목용.",
      params: [
        { key: "period", label: "기간", def: 20, min: 5, max: 200 },
        { key: "k", label: "표준편차 배수", def: 2, min: 0.5, max: 4, step: 0.1 },
        { key: "exitAt", label: "매도 기준", type: "select", options: ["중심선", "상단"], def: "중심선" },
      ],
      signals(b, p) {
        const c = b.map((x) => x.c);
        const mid = sma(c, p.period), sd = stdev(c, p.period);
        const up = mid.map((m, i) => m + p.k * sd[i]), lo = mid.map((m, i) => m - p.k * sd[i]);
        const tgt = p.exitAt === "상단" ? up : mid;
        return {
          entry: c.map((v, i) => v < lo[i]),
          exit: c.map((v, i) => v > tgt[i]),
          lines: [
            { name: "상단", data: up, color: "#8b8fa3" },
            { name: "중심", data: mid, color: "#f5b642" },
            { name: "하단", data: lo, color: "#8b8fa3" },
          ],
        };
      },
    },
    breakout: {
      name: "거래량 돌파 (급등 포착)",
      desc: "종가가 최근 N봉 최고가를 넘고, 거래량이 평균의 X배 이상이면 매수. 최근 M봉 최저가를 깨면 매도.",
      params: [
        { key: "lookback", label: "돌파 기준 봉 수", def: 20, min: 2, max: 250 },
        { key: "volLen", label: "거래량 평균 기간", def: 20, min: 2, max: 250 },
        { key: "volMult", label: "거래량 배수", def: 2, min: 1, max: 20, step: 0.1 },
        { key: "exitLen", label: "이탈 기준 봉 수", def: 10, min: 2, max: 250 },
      ],
      signals(b, p) {
        const h = b.map((x) => x.h), l = b.map((x) => x.l), c = b.map((x) => x.c), v = b.map((x) => x.v);
        const hh = prevHighest(h, p.lookback), ll = prevLowest(l, p.exitLen);
        const va = shift1(sma(v, p.volLen));
        return {
          entry: c.map((x, i) => x > hh[i] && v[i] > va[i] * p.volMult),
          exit: c.map((x, i) => x < ll[i]),
          lines: [
            { name: `${p.lookback}봉 최고`, data: hh, color: "#ef5350" },
            { name: `${p.exitLen}봉 최저`, data: ll, color: "#42a5f5" },
          ],
        };
      },
    },
  };

  // ---------- 엔진 ----------
  /**
   * opt: { capital, buyFee, sellFee, slip (모두 %), stopLoss, takeProfit, trailing (%; 0=사용안함),
   *        maxHold (봉; 0=사용안함), dayClose (bool), dayKey (i → 'YYYY-MM-DD') }
   */
  function run(bars, strategyId, p, opt) {
    const S = STRATEGIES[strategyId];
    const sig = S.signals(bars, p);
    const n = bars.length;
    const buyCost = (opt.buyFee + opt.slip) / 100;
    const sellCost = (opt.sellFee + opt.slip) / 100;

    let cash = opt.capital, qty = 0, entryPx = 0, entryIdx = -1, peak = 0, entryCash = 0;
    let pendingEntry = false, pendingExit = false;
    const equity = new Array(n), trades = [];

    const sell = (i, px, reason) => {
      const proceeds = qty * px * (1 - sellCost);
      trades.push({
        entryIdx, exitIdx: i, entryPx, exitPx: px, bars: i - entryIdx,
        pnl: proceeds - entryCash, ret: (proceeds / entryCash - 1) * 100, reason,
      });
      cash += proceeds; qty = 0; entryIdx = -1;
    };

    for (let i = 0; i < n; i++) {
      const b = bars[i];
      // 1) 직전 봉에서 나온 신호를 이번 봉 시가에 체결
      if (pendingExit && qty > 0) sell(i, b.o, "신호");
      if (pendingEntry && qty === 0) {
        entryCash = cash;
        qty = cash / (b.o * (1 + buyCost));
        cash = 0; entryPx = b.o; entryIdx = i;
        peak = b.o; // 진입 봉 고가는 봉 내 순서를 알 수 없어 체크 후에 반영
      }
      pendingEntry = pendingExit = false;

      // 2) 보유 중이면 봉 안에서 손절/트레일링/익절 체크
      if (qty > 0) {
        const slPx = opt.stopLoss > 0 ? entryPx * (1 - opt.stopLoss / 100) : -Infinity;
        const trPx = opt.trailing > 0 ? peak * (1 - opt.trailing / 100) : -Infinity;
        const stopPx = Math.max(slPx, trPx);
        const tpPx = opt.takeProfit > 0 ? entryPx * (1 + opt.takeProfit / 100) : null;
        if (stopPx > -Infinity && b.l <= stopPx) {
          sell(i, Math.min(b.o, stopPx), trPx > slPx ? "트레일링" : "손절");
        } else if (tpPx !== null && b.h >= tpPx) {
          sell(i, Math.max(b.o, tpPx), "익절");
        }
        if (qty > 0) peak = Math.max(peak, b.h);
      }

      // 3) 보유기간 초과 / 당일 청산 (봉 종가)
      if (qty > 0 && opt.maxHold > 0 && i - entryIdx >= opt.maxHold) sell(i, b.c, "보유기간");
      const lastOfDay = opt.dayClose && opt.dayKey && (i === n - 1 || opt.dayKey(i) !== opt.dayKey(i + 1));
      if (qty > 0 && lastOfDay) sell(i, b.c, "당일청산");

      // 4) 이번 봉 종가 기준 신호 → 다음 봉에서 체결
      if (i < n - 1) {
        if (qty > 0 && sig.exit[i]) pendingExit = true;
        // 당일 청산 모드에서는 마지막 봉 신호로 다음날 진입하지 않음
        if (qty === 0 && sig.entry[i] && !lastOfDay) pendingEntry = true;
      }
      equity[i] = cash + qty * b.c;
    }
    // 마지막까지 보유 중이면 평가만 하고 미청산으로 표시
    let open = null;
    if (qty > 0) {
      const last = bars[n - 1];
      open = { entryIdx, entryPx, lastPx: last.c, ret: ((qty * last.c * (1 - sellCost)) / entryCash - 1) * 100 };
    }
    return { equity, trades, open, lines: sig.lines, stats: stats(bars, equity, trades, opt, open) };
  }

  function stats(bars, eq, trades, opt, open) {
    const n = bars.length;
    const final = eq[n - 1];
    let peak = -Infinity, mdd = 0;
    for (const v of eq) { peak = Math.max(peak, v); mdd = Math.min(mdd, v / peak - 1); }
    const wins = trades.filter((t) => t.pnl > 0), losses = trades.filter((t) => t.pnl <= 0);
    const gw = wins.reduce((s, t) => s + t.pnl, 0), gl = -losses.reduce((s, t) => s + t.pnl, 0);
    const days = (bars[n - 1].ms - bars[0].ms) / 86400000;
    const years = days / 365.25;
    const totalRet = final / opt.capital - 1;
    const held = trades.reduce((s, t) => s + t.bars + 1, 0) + (open ? n - open.entryIdx : 0);
    return {
      totalRet: totalRet * 100,
      cagr: years >= 0.25 ? (Math.pow(final / opt.capital, 1 / years) - 1) * 100 : null,
      mdd: mdd * 100,
      trades: trades.length,
      winRate: trades.length ? (wins.length / trades.length) * 100 : 0,
      avgWin: wins.length ? wins.reduce((s, t) => s + t.ret, 0) / wins.length : 0,
      avgLoss: losses.length ? losses.reduce((s, t) => s + t.ret, 0) / losses.length : 0,
      profitFactor: gl > 0 ? gw / gl : (gw > 0 ? Infinity : 0),
      buyHold: (bars[n - 1].c / bars[0].o - 1) * 100,
      exposure: (held / n) * 100,
      final,
    };
  }

  // ---------- Pine Script 생성 ----------
  function pine(strategyId, p, opt, title) {
    const perSide = ((opt.buyFee + opt.sellFee) / 2 + opt.slip).toFixed(4);
    const L = [];
    L.push("//@version=5");
    L.push(`strategy("${title.replace(/"/g, "'")}", overlay=true, initial_capital=${opt.capital},`);
    L.push(`     default_qty_type=strategy.percent_of_equity, default_qty_value=100,`);
    L.push(`     commission_type=strategy.commission.percent, commission_value=${perSide})`);
    L.push("");
    L.push("// ===== 리스크 설정 (0 = 사용 안 함) =====");
    L.push(`stopPct   = input.float(${opt.stopLoss}, "손절 %", minval=0)`);
    L.push(`tpPct     = input.float(${opt.takeProfit}, "익절 %", minval=0)`);
    L.push(`trailPct  = input.float(${opt.trailing}, "트레일링 %", minval=0)`);
    L.push(`maxHold   = input.int(${opt.maxHold}, "최대 보유 봉 수", minval=0)`);
    L.push(`dayClose  = input.bool(${opt.dayClose ? "true" : "false"}, "장 마감 전 청산 (분봉)")`);
    L.push("");
    L.push("// ===== 전략 =====");
    let entry = "", exit = "";
    if (strategyId === "ma_cross") {
      const f = p.type === "EMA" ? "ta.ema" : "ta.sma";
      L.push(`fastLen = input.int(${p.fast}, "단기")`);
      L.push(`slowLen = input.int(${p.slow}, "장기")`);
      L.push(`fast = ${f}(close, fastLen)`);
      L.push(`slow = ${f}(close, slowLen)`);
      L.push(`plot(fast, "단기", color.orange)`);
      L.push(`plot(slow, "장기", color.blue)`);
      entry = "ta.crossover(fast, slow)"; exit = "ta.crossunder(fast, slow)";
    } else if (strategyId === "rsi") {
      L.push(`len = input.int(${p.period}, "RSI 기간")`);
      L.push(`lo  = input.float(${p.low}, "과매도")`);
      L.push(`hi  = input.float(${p.high}, "과매수")`);
      L.push(`r = ta.rsi(close, len)`);
      entry = "ta.crossover(r, lo)"; exit = "ta.crossover(r, hi)";
    } else if (strategyId === "bollinger") {
      L.push(`len = input.int(${p.period}, "기간")`);
      L.push(`mult = input.float(${p.k}, "표준편차 배수")`);
      L.push(`basis = ta.sma(close, len)`);
      L.push(`dev = mult * ta.stdev(close, len)`);
      L.push(`upper = basis + dev`);
      L.push(`lower = basis - dev`);
      L.push(`plot(upper, "상단", color.gray)`);
      L.push(`plot(basis, "중심", color.orange)`);
      L.push(`plot(lower, "하단", color.gray)`);
      entry = "close < lower"; exit = p.exitAt === "상단" ? "close > upper" : "close > basis";
    } else if (strategyId === "breakout") {
      L.push(`lookback = input.int(${p.lookback}, "돌파 기준 봉 수")`);
      L.push(`volLen   = input.int(${p.volLen}, "거래량 평균 기간")`);
      L.push(`volMult  = input.float(${p.volMult}, "거래량 배수")`);
      L.push(`exitLen  = input.int(${p.exitLen}, "이탈 기준 봉 수")`);
      L.push(`hh = ta.highest(high, lookback)[1]`);
      L.push(`ll = ta.lowest(low, exitLen)[1]`);
      L.push(`va = ta.sma(volume, volLen)[1]`);
      L.push(`plot(hh, "돌파선", color.red)`);
      L.push(`plot(ll, "이탈선", color.blue)`);
      entry = "close > hh and volume > va * volMult"; exit = "close < ll";
    }
    L.push("");
    L.push("lastBar = dayClose and timeframe.isintraday and session.islastbar_regular");
    L.push(`if (${entry}) and strategy.position_size == 0 and not lastBar`);
    L.push(`    strategy.entry("L", strategy.long)`);
    L.push(`if (${exit}) and strategy.position_size > 0`);
    L.push(`    strategy.close("L", comment="신호")`);
    L.push("");
    L.push("if strategy.position_size > 0");
    L.push("    ep = strategy.position_avg_price");
    L.push("    sl = stopPct > 0 ? ep * (1 - stopPct / 100) : na");
    L.push("    tp = tpPct > 0 ? ep * (1 + tpPct / 100) : na");
    L.push("    trailTicks = trailPct > 0 ? ep * trailPct / 100 / syminfo.mintick : na");
    L.push(`    strategy.exit("R", "L", stop=sl, limit=tp, trail_points=trailPct > 0 ? 0 : na, trail_offset=trailTicks)`);
    L.push("    if maxHold > 0 and bar_index - strategy.opentrades.entry_bar_index(0) >= maxHold");
    L.push(`        strategy.close("L", comment="보유기간", immediately=true)`);
    L.push("    if lastBar");
    L.push(`        strategy.close("L", comment="당일청산", immediately=true)`);
    return L.join("\n");
  }

  return { STRATEGIES, run, pine, sma, ema, rsi, stdev };
})();
