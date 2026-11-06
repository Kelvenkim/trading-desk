/* =========================================================
 * 메인 차트 (lightweight-charts v5)
 *  - 캔들 + 거래량 + 이동평균/볼린저 (메인 창)
 *  - RSI / MACD (아래 보조 창)
 *  - 커서 위치 OHLC 범례
 * ========================================================= */
const ChartView = (() => {
  const LC = LightweightCharts;
  const COL = {
    up: "#f0525c", down: "#3d8bfd", grid: "rgba(160, 160, 168,.07)", line: "#2a2a2e", text: "#9a9aa2",
    gold: "#ffffff", upA: "rgba(240,82,92,.32)", downA: "rgba(61,139,253,.32)",
  };
  const MA = [[5, "#8a8a92"], [20, "#ffffff"], [60, "#7aa2ff"], [120, "#c792ea"]];
  const IND_KEY = "tradingdesk.indicators";
  const DEFAULT_IND = { ma: true, bb: false, vol: true, rsi: false, macd: false, spo: false, vwap: false, plan: true };

  let chart, candle, vol, legendEl, markersApi;
  let bars = [], idxByTime = new Map(), sym = "", ivId = "1d", fmt = (v) => String(v);
  let main = [], sub = [], planDraw = null, planSeq = 0, planA = null, planPart = null;
  let linesOn = true;
  try { linesOn = localStorage.getItem("tradingdesk.planlines") !== "off"; } catch (_) {}
  function drawLines() {
    if (planDraw) { planDraw.remove(); planDraw = null; }
    if (planA && linesOn) planDraw = Levels.draw(chart, candle, planPart.map((b) => b.t), planA, (mk) => markersApi.setMarkers(mk));
    const btn = document.getElementById("lines-btn");
    if (btn) { btn.hidden = !planA; btn.textContent = linesOn ? "선 숨기기" : "선 보이기"; btn.classList.toggle("off", !linesOn); }
  }
  function setLines(on) {
    linesOn = on;
    try { localStorage.setItem("tradingdesk.planlines", on ? "on" : "off"); } catch (_) {}
    drawLines();
  }
  let ind = { ...DEFAULT_IND };
  try { ind = { ...DEFAULT_IND, ...JSON.parse(localStorage.getItem(IND_KEY) || "{}") }; } catch (_) {}

  const lineOpts = (color, w = 1) => ({ color, lineWidth: w, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });

  function baseOptions() {
    return {
      autoSize: true,
      layout: {
        background: { color: "transparent" }, textColor: COL.text, fontSize: 11,
        fontFamily: "Pretendard Variable, Pretendard, system-ui, sans-serif",
        panes: { separatorColor: COL.line, separatorHoverColor: "rgba(255, 255, 255,.25)", enableResize: true },
      },
      grid: { vertLines: { color: COL.grid }, horzLines: { color: COL.grid } },
      rightPriceScale: { borderColor: COL.line },
      timeScale: { borderColor: COL.line, timeVisible: true, secondsVisible: false, rightOffset: 8, barSpacing: 8 },
      crosshair: {
        mode: 0,
        vertLine: { color: "rgba(255, 255, 255,.35)", labelBackgroundColor: "#2a2a2e" },
        horzLine: { color: "rgba(255, 255, 255,.35)", labelBackgroundColor: "#2a2a2e" },
      },
      localization: { locale: "ko-KR" },
    };
  }

  function create(el, legend) {
    legendEl = legend;
    chart = LC.createChart(el, baseOptions());
    candle = chart.addSeries(LC.CandlestickSeries, {
      upColor: COL.up, downColor: COL.down, borderUpColor: COL.up, borderDownColor: COL.down,
      wickUpColor: COL.up, wickDownColor: COL.down,
    });
    markersApi = LC.createSeriesMarkers(candle, []);
    chart.subscribeCrosshairMove((p) => {
      const i = p && p.time !== undefined ? idxByTime.get(p.time) : undefined;
      updateLegend(i === undefined ? bars.length - 1 : i);
    });
    return chart;
  }

  function setPriceFormat(isKRW) {
    const pf = isKRW ? { type: "price", precision: 0, minMove: 1 } : { type: "price", precision: 2, minMove: 0.01 };
    candle.applyOptions({ priceFormat: pf });
    fmt = (v) => v == null || isNaN(v) ? "—" : isKRW ? Math.round(v).toLocaleString("ko-KR")
      : v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  // 축·십자선 표기: 가격은 천 단위 쉼표, 시간은 봉 주기에 맞게
  const p2 = (n) => String(n).padStart(2, "0");
  function axisFormat(isKRW, daily) {
    chart.applyOptions({
      timeScale: { timeVisible: !daily },
      localization: {
        locale: "ko-KR",
        priceFormatter: (v) => Math.abs(v) < 100 && !Number.isInteger(v) ? v.toFixed(2)
          : isKRW ? Math.round(v).toLocaleString("ko-KR") : v.toLocaleString("en-US", { maximumFractionDigits: 2 }),
        timeFormatter: (t) => {
          if (typeof t === "string") return t;
          if (typeof t === "object") return `${t.year}-${p2(t.month)}-${p2(t.day)}`;
          const d = new Date(t * 1000);
          return `${d.getUTCFullYear()}-${p2(d.getUTCMonth() + 1)}-${p2(d.getUTCDate())} ${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())}`;
        },
      },
    });
  }

  const line = (arr) => bars.map((b, i) => ({ time: b.t, value: arr[i] })).filter((p) => p.value != null && isFinite(p.value));

  function clearSeries(list) { list.forEach((s) => { try { chart.removeSeries(s); } catch (_) {} }); list.length = 0; }

  // 지지·저항·추세선·매매 계획 (일봉만, 최근 6개월로 계산)
  async function renderPlan() {
    const seq = ++planSeq;
    planA = null; drawLines();
    const box = document.getElementById("chart-plan");
    const krStock = !/^\^|=|-USD$/.test(sym);   // 지수·환율·코인 빼고 주식이면
    if (!ind.plan || ivId !== "1d" || !krStock || bars.length < 60 || typeof Levels === "undefined") {
      if (box) box.innerHTML = ind.plan && ivId !== "1d" && krStock ? `<p class="hint">지지·저항·매매 계획은 일봉에서 보여요.</p>` : "";
      return;
    }
    const off = Math.max(0, bars.length - Levels.WINDOW), part = bars.slice(off);
    const up = await Levels.marketUp();
    if (seq !== planSeq) return;
    let A = null;
    try { A = Levels.analyze(part, { marketUp: up }); } catch (e) { console.error(e); }
    if (!A) { if (box) box.innerHTML = ""; return; }
    planA = A; planPart = part; drawLines();
    if (box) box.innerHTML = Levels.planHTML(A);
  }

  function renderIndicators() {
    clearSeries(main); clearSeries(sub);
    if (vol) { try { chart.removeSeries(vol); } catch (_) {} vol = null; }
    if (!bars.length) return;
    const closes = bars.map((b) => b.c);

    if (ind.vol) {
      vol = chart.addSeries(LC.HistogramSeries, { priceScaleId: "vol", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
      chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 }, visible: false });
      vol.setData(bars.map((b) => ({ time: b.t, value: b.v, color: b.c >= b.o ? COL.upA : COL.downA })));
    }
    candle.priceScale().applyOptions({ scaleMargins: { top: 0.06, bottom: ind.vol ? 0.2 : 0.06 } });

    if (ind.ma) MA.forEach(([n, c]) => {
      if (bars.length < n) return;
      const s = chart.addSeries(LC.LineSeries, lineOpts(c)); s.setData(line(BT.sma(closes, n))); s._label = `MA${n}`; s._calc = BT.sma(closes, n); main.push(s);
    });
    if (ind.bb && bars.length >= 20) {
      const mid = BT.sma(closes, 20), sd = BT.stdev(closes, 20);
      [[mid.map((m, i) => m + 2 * sd[i]), "rgba(160, 160, 168,.8)"], [mid, "rgba(255, 255, 255,.7)"], [mid.map((m, i) => m - 2 * sd[i]), "rgba(160, 160, 168,.8)"]]
        .forEach(([arr, c]) => { const s = chart.addSeries(LC.LineSeries, { ...lineOpts(c), lineStyle: 0 }); s.setData(line(arr)); main.push(s); });
    }

    if (ind.vwap) {
      // 분봉: 당일 VWAP(굵게) + 주간 VWAP, 일봉 이상: 20봉 이동 VWAP
      const daily = ["1d", "1w", "1M"].includes(ivId);
      const parts = daily ? [["rolling", 20, "#4fd1a5", 2, "VWAP 20"]] : [["session", 0, "#4fd1a5", 2, "VWAP"], ["week", 0, "rgba(79,209,165,.45)", 1, "주간 VWAP"]];
      parts.forEach(([k, nn, col, w, lb]) => {
        const s2 = chart.addSeries(LC.LineSeries, { ...lineOpts(col, w), lineType: 0 });
        const arr = BT.vwapCalc(bars, k, nn).vwap;
        s2.setData(line(arr)); s2._label = lb; s2._calc = arr; main.push(s2);
      });
    }
    let pane = 1;
    if (ind.rsi) {
      const r = BT.rsi(closes, 14);
      const s = chart.addSeries(LC.LineSeries, { ...lineOpts("#c792ea", 2), lastValueVisible: true }, pane);
      s.setData(line(r));
      [70, 30].forEach((v) => s.createPriceLine({ price: v, color: "rgba(160, 160, 168,.45)", lineWidth: 1, lineStyle: 2, axisLabelVisible: false }));
      sub.push(s); pane++;
    }
    if (ind.macd) {
      const e12 = BT.ema(closes, 12), e26 = BT.ema(closes, 26);
      const m = e12.map((v, i) => v - e26[i]);
      const firstValid = m.findIndex((v) => !isNaN(v));
      const sigPart = firstValid >= 0 ? BT.ema(m.slice(firstValid), 9) : [];
      const sig = m.map((_, i) => (i < firstValid ? NaN : sigPart[i - firstValid]));
      const h = chart.addSeries(LC.HistogramSeries, { priceLineVisible: false, lastValueVisible: false, priceFormat: { type: "price", precision: 2, minMove: 0.01 } }, pane);
      h.setData(bars.map((b, i) => ({ time: b.t, value: m[i] - sig[i], color: m[i] - sig[i] >= 0 ? COL.upA : COL.downA })).filter((p) => isFinite(p.value)));
      const ml = chart.addSeries(LC.LineSeries, lineOpts("#ffffff", 2), pane); ml.setData(line(m));
      const sl = chart.addSeries(LC.LineSeries, lineOpts("#7aa2ff", 2), pane); sl.setData(line(sig));
      sub.push(h, ml, sl); pane++;
    }
    if (ind.spo) {
      const r = BT.spoCalc(bars, 10, 40, 100, 2);
      const o = chart.addSeries(LC.LineSeries, { ...lineOpts("#4fd1a5", 2), lastValueVisible: true, priceFormat: { type: "price", precision: 2, minMove: 0.01 } }, pane);
      o.setData(line(r.osc));
      [1, -1].forEach((v) => o.createPriceLine({ price: v, color: "rgba(160, 160, 168,.45)", lineWidth: 1, lineStyle: 2, axisLabelVisible: false }));
      o.createPriceLine({ price: 0, color: "rgba(160, 160, 168,.25)", lineWidth: 1, lineStyle: 0, axisLabelVisible: false });
      const up = chart.addSeries(LC.LineSeries, lineOpts("rgba(240,82,92,.7)"), pane); up.setData(line(r.upper));
      const lo = chart.addSeries(LC.LineSeries, lineOpts("rgba(61,139,253,.7)"), pane); lo.setData(line(r.lower));
      sub.push(o, up, lo); pane++;
    }
    const panes = chart.panes();
    panes.forEach((p, i) => p.setStretchFactor(i === 0 ? 3.2 : 1));
    renderPlan();
  }

  function updateLegend(i) {
    if (!legendEl) return;
    const b = bars[i];
    if (!b) { legendEl.innerHTML = ""; return; }
    const p = bars[i - 1];
    const chg = p ? (b.c / p.c - 1) * 100 : 0;
    const cls = chg > 0 ? "up" : chg < 0 ? "down" : "";
    const v = b.v >= 1e8 ? (b.v / 1e8).toFixed(2) + "억" : b.v >= 1e4 ? (b.v / 1e4).toFixed(1) + "만" : b.v.toLocaleString("ko-KR");
    const ma = main.filter((s) => s._label).map((s) => {
      const val = s._calc[i];
      return isFinite(val) ? `<span style="color:${s.options().color}">${s._label} ${fmt(val)}</span>` : "";
    }).join("");
    legendEl.innerHTML =
      `<span class="lg-time">${typeof b.t === "string" ? b.t : new Date(b.ms + 9 * 3600e3).toISOString().slice(0, 16).replace("T", " ")}</span>` +
      `<span>시 <b class="${cls}">${fmt(b.o)}</b></span><span>고 <b class="${cls}">${fmt(b.h)}</b></span>` +
      `<span>저 <b class="${cls}">${fmt(b.l)}</b></span><span>종 <b class="${cls}">${fmt(b.c)}</b></span>` +
      `<span class="${cls}">${chg > 0 ? "+" : ""}${chg.toFixed(2)}%</span><span>거래량 <b>${v}</b></span>` +
      (ma ? `<div class="lg-ma">${ma}</div>` : "");
  }

  function setData(newBars, newSym, newIv, isKRW) {
    bars = newBars; sym = newSym; ivId = newIv;
    idxByTime = new Map(bars.map((b, i) => [b.t, i]));
    setPriceFormat(isKRW);
    axisFormat(isKRW, ["1d", "1w", "1M"].includes(ivId));
    candle.setData(bars.map((b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c })));
    markersApi.setMarkers([]);
    renderIndicators();
    const show = { "1m": 240, "5m": 300, "15m": 260, "30m": 220, "1h": 200, "1d": 180, "1w": 156, "1M": 120 }[ivId] || 200;
    chart.timeScale().setVisibleLogicalRange({ from: Math.max(-2, bars.length - show), to: bars.length + 8 });
    updateLegend(bars.length - 1);
  }

  // 실시간 갱신: 보고 있던 구간을 유지한 채 막대만 바꿈
  function refresh(newBars) {
    if (!newBars || !newBars.length) return;
    const range = chart.timeScale().getVisibleLogicalRange();
    const atEnd = range && range.to >= bars.length - 3;
    const grow = newBars.length - bars.length;
    bars = newBars;
    idxByTime = new Map(bars.map((b, i) => [b.t, i]));
    candle.setData(bars.map((b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c })));
    renderIndicators();
    if (range) chart.timeScale().setVisibleLogicalRange(atEnd ? { from: range.from + grow, to: range.to + grow } : range);
    updateLegend(bars.length - 1);
  }

  function setIndicator(key, on) {
    ind[key] = on;
    try { localStorage.setItem(IND_KEY, JSON.stringify(ind)); } catch (_) {}
    renderIndicators();
    updateLegend(bars.length - 1);
  }

  // ---------- 그리기 도구용 좌표 변환 ----------
  function step() {
    if (bars.length < 2) return 86400000;
    const d = [];
    for (let i = Math.max(1, bars.length - 60); i < bars.length; i++) d.push(bars[i].ms - bars[i - 1].ms);
    d.sort((a, b) => a - b);
    return d[Math.floor(d.length / 2)] || 86400000;
  }
  function msToLogical(ms) {
    const n = bars.length;
    if (!n) return 0;
    const st = step();
    if (ms <= bars[0].ms) return (ms - bars[0].ms) / st;
    if (ms >= bars[n - 1].ms) return n - 1 + (ms - bars[n - 1].ms) / st;
    let lo = 0, hi = n - 1;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (bars[mid].ms <= ms) lo = mid; else hi = mid; }
    return lo + (ms - bars[lo].ms) / (bars[hi].ms - bars[lo].ms);
  }
  function logicalToMs(l) {
    const n = bars.length;
    if (!n) return 0;
    const st = step();
    if (l <= 0) return bars[0].ms + l * st;
    if (l >= n - 1) return bars[n - 1].ms + (l - (n - 1)) * st;
    const i = Math.floor(l), f = l - i;
    return bars[i].ms + f * (bars[i + 1].ms - bars[i].ms);
  }

  return {
    create, setData, refresh, setIndicator, msToLogical, logicalToMs, setLines, get linesOn() { return linesOn; },
    get chart() { return chart; }, get candle() { return candle; }, get bars() { return bars; },
    get ind() { return { ...ind }; }, get sym() { return sym; }, get iv() { return ivId; },
    fmt: (v) => fmt(v),
    mainHeight: () => (chart ? chart.paneSize(0).height : 0),
    plotWidth: () => (chart ? chart.paneSize(0).width : 0),
    setMarkers: (m) => markersApi.setMarkers(m),
  };
})();
