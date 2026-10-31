/* =========================================================
 * Trading Desk — 화면 로직
 * ========================================================= */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const KST_OFFSET = 9 * 3600;
  const UP = "#f04452", DOWN = "#3485fa", MUTED = "#8b8fa3", ACCENT = "#f5b642";

  const state = { meta: null, bySymbol: {}, cache: {}, sel: null, iv: "1d", csv: null, lastRun: null };

  // ---------- 포맷 ----------
  const isKRW = (sym) => !sym || /\.(KS|KQ)$/.test(sym) || (state.bySymbol[sym]?.currency === "KRW");
  const fmtPx = (v, sym) => v == null || isNaN(v) ? "—" :
    isKRW(sym) ? Math.round(v).toLocaleString("ko-KR") : v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fmtWon = (v) => v == null || isNaN(v) ? "—" : Math.round(v).toLocaleString("ko-KR") + "원";
  const fmtPct = (v, d = 2) => v == null || isNaN(v) || !isFinite(v) ? "—" : (v > 0 ? "+" : "") + v.toFixed(d) + "%";
  const cls = (v) => (v > 0 ? "up" : v < 0 ? "down" : "");
  const fmtNum = (v, d = 2) => v == null || isNaN(v) ? "—" : !isFinite(v) ? "∞" : v.toFixed(d);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const kstDay = (ms) => new Date(ms + KST_OFFSET * 1000).toISOString().slice(0, 10);
  const kstTime = (ms) => new Date(ms + KST_OFFSET * 1000).toISOString().slice(0, 16).replace("T", " ");

  function banner(msg) { const b = $("#banner"); b.innerHTML = msg; b.classList.remove("hidden"); }

  // ---------- 데이터 ----------
  async function getJSON(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(`${url} (${r.status})`);
    return r.json();
  }
  // 원본 [t,o,h,l,c,v] → {t(차트용), ms, day, o,h,l,c,v}
  function normalize(raw, intraday) {
    return raw.map(([t, o, h, l, c, v]) => {
      if (intraday) { const ms = t * 1000; return { t: t + KST_OFFSET, ms, day: kstDay(ms), o, h, l, c, v }; }
      return { t, ms: Date.parse(t + "T00:00:00Z"), day: t, o, h, l, c, v };
    });
  }
  async function loadBars(sym, iv) {
    const key = sym + "|" + iv;
    if (state.cache[key]) return state.cache[key];
    const m = state.bySymbol[sym];
    const dir = iv === "5m" ? "intraday" : "daily";
    const j = await getJSON(`data/${dir}/${m.file}`);
    return (state.cache[key] = normalize(j.bars, iv === "5m"));
  }

  // ---------- 차트 공통 ----------
  const chartOpts = (el) => ({
    autoSize: true,
    layout: { background: { color: "transparent" }, textColor: MUTED, fontFamily: "Pretendard Variable, Pretendard, system-ui, sans-serif" },
    grid: { vertLines: { color: "#1c202b" }, horzLines: { color: "#1c202b" } },
    rightPriceScale: { borderColor: "#262b38" },
    timeScale: { borderColor: "#262b38", timeVisible: true, secondsVisible: false },
    crosshair: { mode: 0 },
    localization: { locale: "ko-KR" },
  });
  const candleOpts = { upColor: UP, downColor: DOWN, borderUpColor: UP, borderDownColor: DOWN, wickUpColor: UP, wickDownColor: DOWN };
  // 원화는 소수점 없이, 달러는 소수 둘째 자리
  const pxFormat = (sym) => isKRW(sym)
    ? { priceFormat: { type: "price", precision: 0, minMove: 1 } }
    : { priceFormat: { type: "price", precision: 2, minMove: 0.01 } };
  const toLine = (bars, arr) => bars.map((b, i) => ({ time: b.t, value: arr[i] })).filter((p) => p.value != null && !isNaN(p.value));

  // ================= 현황 =================
  let mkt = null;
  function initMarketChart() {
    const chart = LightweightCharts.createChart($("#market-chart"), chartOpts());
    const candles = chart.addCandlestickSeries(candleOpts);
    const vol = chart.addHistogramSeries({ priceScaleId: "vol", priceFormat: { type: "volume" } });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    candles.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.25 } });
    const mas = [[20, ACCENT], [60, "#7aa2ff"], [120, "#c792ea"]].map(([n, color]) => ({
      n, s: chart.addLineSeries({ color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }),
    }));
    mkt = { chart, candles, vol, mas };
  }

  function sparkSVG(closes) {
    if (!closes || closes.length < 2) return "";
    const w = 200, h = 36, mn = Math.min(...closes), mx = Math.max(...closes), rg = mx - mn || 1;
    const pts = closes.map((c, i) => `${(i / (closes.length - 1)) * w},${h - 2 - ((c - mn) / rg) * (h - 4)}`).join(" ");
    const col = closes[closes.length - 1] >= closes[0] ? UP : DOWN;
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline fill="none" stroke="${col}" stroke-width="1.5" points="${pts}" vector-effect="non-scaling-stroke"/></svg>`;
  }

  function renderCards() {
    const el = $("#cards");
    el.innerHTML = state.meta.symbols.map((s) => {
      const pos = s.high52 > s.low52 ? ((s.close - s.low52) / (s.high52 - s.low52)) * 100 : 50;
      return `<div class="card" data-sym="${esc(s.symbol)}">
        <div class="nm">${esc(s.name)}</div><div class="sym">${esc(s.symbol)} · ${esc(s.date)}</div>
        <div class="px">${fmtPx(s.close, s.symbol)}</div>
        <div class="chg ${cls(s.changePct)}">${s.change > 0 ? "▲" : s.change < 0 ? "▼" : ""} ${fmtPx(Math.abs(s.change), s.symbol)} (${fmtPct(s.changePct)})</div>
        <div class="spark-wrap" data-spark="${esc(s.symbol)}"></div>
        <div class="range"><div class="bar"><span class="dot" style="left:${Math.max(0, Math.min(100, pos))}%"></span></div>
          <div class="lbl"><span>52주 ${fmtPx(s.low52, s.symbol)}</span><span>${fmtPx(s.high52, s.symbol)}</span></div></div>
      </div>`;
    }).join("");
    $$(".card", el).forEach((c) => c.addEventListener("click", () => selectSymbol(c.dataset.sym)));
    // 스파크라인은 일봉을 받은 뒤 채움 (최근 60거래일)
    state.meta.symbols.forEach(async (s) => {
      try {
        const bars = await loadBars(s.symbol, "1d");
        $(`[data-spark="${CSS.escape(s.symbol)}"]`).innerHTML = sparkSVG(bars.slice(-60).map((b) => b.c));
      } catch (_) {}
    });
  }

  async function selectSymbol(sym) {
    state.sel = sym;
    const m = state.bySymbol[sym];
    $$(".card").forEach((c) => c.classList.toggle("sel", c.dataset.sym === sym));
    const b5 = $('#interval-seg [data-iv="5m"]');
    b5.disabled = !m.intraday;
    if (!m.intraday && state.iv === "5m") state.iv = "1d";
    $$("#interval-seg button").forEach((b) => b.classList.toggle("on", b.dataset.iv === state.iv));
    $("#chart-title").textContent = `${m.name} (${m.symbol})`;
    $("#chart-sub").textContent = state.iv === "5m" ? "5분봉 · 최근 60거래일 · 시간은 한국시간" : "일봉 · 최근 10년";
    try {
      const bars = await loadBars(sym, state.iv);
      mkt.candles.applyOptions(pxFormat(sym));
      mkt.candles.setData(bars.map((b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c })));
      mkt.vol.setData(bars.map((b) => ({ time: b.t, value: b.v, color: b.c >= b.o ? "rgba(240,68,82,.35)" : "rgba(52,133,250,.35)" })));
      const closes = bars.map((b) => b.c);
      mkt.mas.forEach(({ n, s }) => s.setData(toLine(bars, BT.sma(closes, n))));
      const ts = mkt.chart.timeScale();
      const show = state.iv === "5m" ? 75 * 5 : 250;   // 5분봉 약 5일 / 일봉 약 1년
      ts.setVisibleLogicalRange({ from: Math.max(0, bars.length - show), to: bars.length + 3 });
    } catch (e) { banner(`차트 데이터를 불러오지 못했어요: ${esc(e.message)}`); }
  }

  // ================= 포트폴리오 =================
  const PF_KEY = "tradingdesk.portfolio.v1";
  const loadPF = () => { try { return JSON.parse(localStorage.getItem(PF_KEY)) || { holdings: [], cash: 0 }; } catch (_) { return { holdings: [], cash: 0 }; } };
  const savePF = (pf) => { try { localStorage.setItem(PF_KEY, JSON.stringify(pf)); } catch (_) { banner("이 브라우저에서는 저장이 안 돼요 (시크릿 모드 등)."); } };

  function renderPF() {
    const pf = loadPF();
    const rows = pf.holdings.map((h) => {
      const m = state.bySymbol[h.symbol];
      const px = m ? m.close : null;
      const cost = h.qty * h.avg, val = px != null ? h.qty * px : null;
      return { ...h, name: m ? m.name : h.symbol, px, cost, val, pnl: val != null ? val - cost : null, ret: val != null && cost ? (val / cost - 1) * 100 : null, dayPct: m ? m.changePct : null, dayChg: m ? m.change * h.qty : 0 };
    });
    const invested = rows.reduce((s, r) => s + r.cost, 0);
    const value = rows.reduce((s, r) => s + (r.val ?? r.cost), 0);
    const total = value + (+pf.cash || 0);
    const pnl = value - invested;
    const day = rows.reduce((s, r) => s + (r.dayChg || 0), 0);

    $("#pf-summary").innerHTML = [
      ["총 자산", fmtWon(total), ""],
      ["주식 평가액", fmtWon(value), ""],
      ["평가 손익", `${pnl > 0 ? "+" : ""}${fmtWon(pnl)}`, cls(pnl)],
      ["수익률", fmtPct(invested ? (pnl / invested) * 100 : 0), cls(pnl)],
      ["오늘 변동", `${day > 0 ? "+" : ""}${fmtWon(day)}`, cls(day)],
      ["예수금", fmtWon(+pf.cash || 0), ""],
    ].map(([k, v, c]) => `<div class="stat"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`).join("");

    const tb = $("#pf-table tbody");
    if (!rows.length) {
      tb.innerHTML = `<tr class="empty-row"><td colspan="9">아직 보유 종목이 없어요. 오른쪽에서 추가해보세요.</td></tr>`;
    } else {
      rows.sort((a, b) => (b.val ?? b.cost) - (a.val ?? a.cost));
      tb.innerHTML = rows.map((r) => {
        const w = total ? ((r.val ?? r.cost) / total) * 100 : 0;
        return `<tr>
          <td><b>${esc(r.name)}</b><div class="sub">${esc(r.symbol)}${r.px == null ? " · 시세 없음 (watchlist에 추가 필요)" : ""}</div></td>
          <td class="r">${r.qty.toLocaleString("ko-KR")}</td>
          <td class="r">${fmtPx(r.avg, r.symbol)}</td>
          <td class="r">${fmtPx(r.px, r.symbol)}<div class="sub ${cls(r.dayPct)}">${fmtPct(r.dayPct)}</div></td>
          <td class="r">${fmtWon(r.val)}</td>
          <td class="r ${cls(r.pnl)}">${r.pnl == null ? "—" : (r.pnl > 0 ? "+" : "") + fmtWon(r.pnl)}</td>
          <td class="r ${cls(r.ret)}">${fmtPct(r.ret)}</td>
          <td class="r">${w.toFixed(1)}%<span class="wbar"><b style="width:${w}%"></b></span></td>
          <td><button class="del" data-del="${esc(r.symbol)}" title="삭제">✕</button></td>
        </tr>`;
      }).join("");
      $$("[data-del]", tb).forEach((b) => b.addEventListener("click", () => {
        const p = loadPF(); p.holdings = p.holdings.filter((h) => h.symbol !== b.dataset.del); savePF(p); renderPF();
      }));
      $$("tr", tb).forEach((tr, i) => tr.addEventListener("dblclick", () => {
        const r = rows[i]; $("#pf-symbol").value = r.symbol; $("#pf-qty").value = r.qty; $("#pf-avg").value = r.avg;
      }));
    }
    $("#pf-cash").value = pf.cash || "";
  }

  function initPF() {
    $("#symbol-list").innerHTML = state.meta.symbols.map((s) => `<option value="${esc(s.symbol)}">${esc(s.name)}</option>`).join("");
    $("#pf-form").addEventListener("submit", (e) => {
      e.preventDefault();
      let sym = $("#pf-symbol").value.trim().toUpperCase();
      // 이름으로 입력해도 찾아주기
      const byName = state.meta.symbols.find((s) => s.name.toUpperCase() === sym);
      if (byName) sym = byName.symbol;
      const qty = +$("#pf-qty").value, avg = +$("#pf-avg").value;
      if (!sym || !(qty >= 0) || !(avg >= 0)) return;
      const pf = loadPF();
      const i = pf.holdings.findIndex((h) => h.symbol === sym);
      if (qty === 0) { if (i >= 0) pf.holdings.splice(i, 1); }
      else if (i >= 0) pf.holdings[i] = { symbol: sym, qty, avg };
      else pf.holdings.push({ symbol: sym, qty, avg });
      savePF(pf); e.target.reset(); renderPF();
    });
    $("#cash-form").addEventListener("submit", (e) => { e.preventDefault(); const pf = loadPF(); pf.cash = +$("#pf-cash").value || 0; savePF(pf); renderPF(); });
    $("#pf-export").addEventListener("click", () => download("portfolio.json", JSON.stringify(loadPF(), null, 2), "application/json"));
    $("#pf-import").addEventListener("change", async (e) => {
      const f = e.target.files[0]; if (!f) return;
      try { const j = JSON.parse(await f.text()); if (!Array.isArray(j.holdings)) throw 0; savePF(j); renderPF(); }
      catch (_) { banner("포트폴리오 파일 형식이 맞지 않아요."); }
      e.target.value = "";
    });
    renderPF();
  }

  function download(name, text, type) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type }));
    a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  // ================= 백테스트 =================
  let btc = null;
  function initBT() {
    const symSel = $("#bt-symbol");
    symSel.innerHTML = state.meta.symbols.map((s) => `<option value="${esc(s.symbol)}">${esc(s.name)} (${esc(s.symbol)})</option>`).join("");
    const stSel = $("#bt-strategy");
    stSel.innerHTML = Object.entries(BT.STRATEGIES).map(([k, s]) => `<option value="${k}">${s.name}</option>`).join("");

    const syncInterval = () => {
      const m = state.bySymbol[symSel.value];
      const o5 = $('#bt-interval option[value="5m"]');
      o5.disabled = !(m && m.intraday);
      if (o5.disabled && $("#bt-interval").value === "5m") $("#bt-interval").value = "1d";
      setDefaultDates();
    };
    const setDefaultDates = () => {
      const iv = $("#bt-interval").value;
      const end = new Date();
      const start = new Date(end);
      if (iv === "5m") start.setDate(end.getDate() - 90); else start.setFullYear(end.getFullYear() - 5);
      $("#bt-start").value = start.toISOString().slice(0, 10);
      $("#bt-end").value = end.toISOString().slice(0, 10);
      $("#bt-dayclose").checked = iv === "5m";
    };
    symSel.addEventListener("change", () => { state.csv = null; $("#bt-csv-name").textContent = ""; syncInterval(); });
    $("#bt-interval").addEventListener("change", setDefaultDates);
    stSel.addEventListener("change", renderParams);
    syncInterval(); renderParams();

    $("#bt-csv").addEventListener("change", async (e) => {
      const f = e.target.files[0]; if (!f) return;
      try {
        state.csv = { name: f.name.replace(/\.[^.]+$/, ""), ...parseCSV(await f.text()) };
        const first = state.csv.bars[0], last = state.csv.bars[state.csv.bars.length - 1];
        $("#bt-csv-name").textContent = `${f.name} · ${state.csv.bars.length}개 봉 · ${state.csv.intraday ? "분봉" : "일봉"} (종목 선택 시 해제)`;
        $("#bt-start").value = new Date(first.ms).toISOString().slice(0, 10);
        $("#bt-end").value = new Date(last.ms + 86400000).toISOString().slice(0, 10);
        $("#bt-dayclose").checked = state.csv.intraday;
      } catch (err) { banner(`CSV를 읽지 못했어요: ${esc(err.message)}`); }
      e.target.value = "";
    });

    $("#bt-run").addEventListener("click", runBT);
    $("#bt-pine").addEventListener("click", showPine);
    $("#pine-close").addEventListener("click", () => $("#pine-dialog").close());
    $("#pine-copy").addEventListener("click", async () => {
      try { await navigator.clipboard.writeText($("#pine-code").textContent); $("#pine-copy").textContent = "복사됨"; setTimeout(() => ($("#pine-copy").textContent = "복사"), 1500); }
      catch (_) { banner("클립보드 접근이 막혀 있어요. 코드를 직접 선택해서 복사하세요."); }
    });
    $("#bt-trades-csv").addEventListener("click", () => {
      const r = state.lastRun; if (!r) return;
      const lines = ["no,entry_time,entry_price,exit_time,exit_price,bars,return_pct,reason"];
      r.result.trades.forEach((t, i) => lines.push([i + 1, r.label(t.entryIdx), t.entryPx, r.label(t.exitIdx), t.exitPx, t.bars, t.ret.toFixed(3), t.reason].join(",")));
      download("trades.csv", "﻿" + lines.join("\n"), "text/csv");
    });

    // 차트
    const pc = LightweightCharts.createChart($("#bt-price"), chartOpts());
    const ec = LightweightCharts.createChart($("#bt-equity"), chartOpts());
    btc = { pc, ec, candles: pc.addCandlestickSeries(candleOpts), lines: [],
      eq: ec.addLineSeries({ color: ACCENT, lineWidth: 2, priceLineVisible: false, priceFormat: { type: "price", precision: 0, minMove: 1 } }),
      bh: ec.addLineSeries({ color: MUTED, lineWidth: 1, priceLineVisible: false, lineStyle: 2, priceFormat: { type: "price", precision: 0, minMove: 1 } }) };
    // 두 차트 시간축 동기화
    let syncing = false;
    const link = (a, b) => a.timeScale().subscribeVisibleLogicalRangeChange((r) => {
      if (syncing || !r) return; syncing = true; b.timeScale().setVisibleLogicalRange(r); syncing = false;
    });
    link(pc, ec); link(ec, pc);
  }

  function renderParams() {
    const S = BT.STRATEGIES[$("#bt-strategy").value];
    $("#bt-desc").textContent = S.desc;
    $("#bt-params").innerHTML = S.params.map((p) => p.type === "select"
      ? `<label>${p.label}<select data-p="${p.key}">${p.options.map((o) => `<option ${o === p.def ? "selected" : ""}>${o}</option>`).join("")}</select></label>`
      : `<label>${p.label}<input type="number" data-p="${p.key}" value="${p.def}" min="${p.min ?? ""}" max="${p.max ?? ""}" step="${p.step ?? 1}"></label>`).join("");
  }

  function readParams() {
    const S = BT.STRATEGIES[$("#bt-strategy").value];
    const p = {};
    S.params.forEach((d) => { const el = $(`[data-p="${d.key}"]`); p[d.key] = d.type === "select" ? el.value : +el.value; });
    return p;
  }
  const readOpt = () => ({
    capital: +$("#bt-capital").value || 10000000,
    buyFee: +$("#bt-buyfee").value || 0, sellFee: +$("#bt-sellfee").value || 0, slip: +$("#bt-slip").value || 0,
    stopLoss: +$("#bt-sl").value || 0, takeProfit: +$("#bt-tp").value || 0, trailing: +$("#bt-trail").value || 0,
    maxHold: Math.floor(+$("#bt-hold").value || 0), dayClose: $("#bt-dayclose").checked,
  });

  function parseCSV(text) {
    const lines = text.trim().split(/\r?\n/).filter(Boolean);
    const head = lines[0].split(/[,;\t]/).map((h) => h.trim().replace(/^"|"$/g, "").toLowerCase());
    const find = (...names) => head.findIndex((h) => names.includes(h));
    const it = find("time", "date", "datetime", "timestamp", "날짜", "일자"), io = find("open", "시가"),
      ih = find("high", "고가"), il = find("low", "저가"), ic = find("close", "종가", "adj close"), iv = find("volume", "거래량", "vol");
    if ([it, io, ih, il, ic].some((x) => x < 0)) throw new Error("time/open/high/low/close 열이 필요해요");
    const raw = lines.slice(1).map((ln) => {
      const c = ln.split(/[,;\t]/).map((x) => x.trim().replace(/^"|"$/g, ""));
      let ms;
      if (/^\d+(\.\d+)?$/.test(c[it])) { ms = +c[it]; if (ms < 1e12) ms *= 1000; }
      else ms = Date.parse(c[it].includes("T") || c[it].includes(" ") ? c[it] : c[it] + "T00:00:00Z");
      return { ms, o: +c[io], h: +c[ih], l: +c[il], c: +c[ic], v: iv >= 0 ? +c[iv] || 0 : 0 };
    }).filter((b) => !isNaN(b.ms) && !isNaN(b.c)).sort((a, b) => a.ms - b.ms);
    if (raw.length < 30) throw new Error("데이터가 너무 적어요 (30봉 이상 필요)");
    const gaps = raw.slice(1, 200).map((b, i) => b.ms - raw[i].ms).sort((a, b) => a - b);
    const intraday = gaps[Math.floor(gaps.length / 2)] < 86400000 * 0.9;
    const bars = raw.map((b) => intraday
      ? { ...b, t: Math.floor(b.ms / 1000) + KST_OFFSET, day: kstDay(b.ms) }
      : { ...b, t: new Date(b.ms).toISOString().slice(0, 10), day: new Date(b.ms).toISOString().slice(0, 10) });
    // 같은 시간 중복 제거 (차트 라이브러리 요구사항)
    const uniq = bars.filter((b, i) => i === 0 || b.t !== bars[i - 1].t);
    return { bars: uniq, intraday };
  }

  async function runBT() {
    const btn = $("#bt-run"); btn.disabled = true; btn.textContent = "계산 중…";
    try {
      let all, intraday, title;
      if (state.csv) { all = state.csv.bars; intraday = state.csv.intraday; title = state.csv.name; }
      else {
        const sym = $("#bt-symbol").value, iv = $("#bt-interval").value;
        all = await loadBars(sym, iv); intraday = iv === "5m"; title = state.bySymbol[sym].name;
      }
      const s = Date.parse($("#bt-start").value + "T00:00:00Z") - KST_OFFSET * 1000;
      const e = Date.parse($("#bt-end").value + "T23:59:59Z") - KST_OFFSET * 1000;
      const bars = all.filter((b) => (isNaN(s) || b.ms >= s) && (isNaN(e) || b.ms <= e));
      if (bars.length < 30) throw new Error("선택한 기간의 봉이 30개 미만이에요. 기간을 늘려주세요.");

      const sid = $("#bt-strategy").value, p = readParams(), opt = readOpt();
      opt.dayKey = intraday ? (i) => bars[i].day : null;
      if (!intraday) opt.dayClose = false;
      const result = BT.run(bars, sid, p, opt);
      const label = (i) => intraday ? kstTime(bars[i].ms) : bars[i].day;
      state.lastRun = { sym: state.csv ? null : $("#bt-symbol").value, sid, p, opt, title: `${title} · ${BT.STRATEGIES[sid].name}`, result, bars, label };
      renderResult(state.lastRun, intraday);
    } catch (err) { banner(esc(err.message)); }
    finally { btn.disabled = false; btn.textContent = "백테스트 실행"; }
  }

  function renderResult(run, intraday) {
    const { result: r, bars, opt, label, sym } = run, st = r.stats;
    $("#banner").classList.add("hidden");
    const m = [
      ["총 수익률", fmtPct(st.totalRet), cls(st.totalRet), "hero"],
      ["최종 자산", fmtWon(st.final), "", ""],
      ["보유만 했을 때", fmtPct(st.buyHold), cls(st.buyHold), ""],
      ["연환산 (CAGR)", st.cagr == null ? "—" : fmtPct(st.cagr), cls(st.cagr), ""],
      ["최대 낙폭 (MDD)", fmtPct(st.mdd), "down", ""],
      ["거래 수", st.trades + (r.open ? " (+보유중 1)" : ""), "", ""],
      ["승률", st.trades ? st.winRate.toFixed(1) + "%" : "—", "", ""],
      ["평균 수익 / 손실", `${fmtPct(st.avgWin, 1)} / ${fmtPct(st.avgLoss, 1)}`, "", ""],
      ["손익비 (PF)", fmtNum(st.profitFactor), "", ""],
      ["시장 노출", st.exposure.toFixed(1) + "%", "", ""],
    ];
    $("#bt-metrics").innerHTML = m.map(([k, v, c, x]) => `<div class="stat ${x}"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`).join("");
    $("#bt-range").textContent = `${label(0)} ~ ${label(bars.length - 1)} · ${bars.length.toLocaleString()}개 봉`;

    // 가격 차트
    btc.candles.applyOptions(pxFormat(sym));
    btc.candles.setData(bars.map((b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c })));
    btc.lines.forEach((s) => btc.pc.removeSeries(s));
    btc.lines = r.lines.map((ln) => {
      const s = btc.pc.addLineSeries({ color: ln.color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      s.setData(toLine(bars, ln.data)); return s;
    });
    const marks = [];
    r.trades.forEach((t) => {
      marks.push({ time: bars[t.entryIdx].t, position: "belowBar", color: UP, shape: "arrowUp", text: "매수" });
      marks.push({ time: bars[t.exitIdx].t, position: "aboveBar", color: DOWN, shape: "arrowDown", text: `${t.ret >= 0 ? "+" : ""}${t.ret.toFixed(1)}%` });
    });
    if (r.open) marks.push({ time: bars[r.open.entryIdx].t, position: "belowBar", color: UP, shape: "arrowUp", text: "매수(보유중)" });
    marks.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
    btc.candles.setMarkers(marks);

    // 자산 곡선
    btc.eq.setData(bars.map((b, i) => ({ time: b.t, value: r.equity[i] })));
    const base = bars[0].o;
    btc.bh.setData(bars.map((b) => ({ time: b.t, value: (opt.capital * b.c) / base })));
    btc.pc.timeScale().fitContent(); btc.ec.timeScale().fitContent();

    // 거래 내역
    const tb = $("#bt-trades tbody");
    const rows = r.trades.map((t, i) => `<tr><td>${i + 1}</td><td>${label(t.entryIdx)}</td><td class="r">${fmtPx(t.entryPx, sym)}</td>
      <td>${label(t.exitIdx)}</td><td class="r">${fmtPx(t.exitPx, sym)}</td><td class="r">${t.bars}봉</td>
      <td class="r ${cls(t.ret)}">${fmtPct(t.ret)}</td><td>${t.reason}</td></tr>`);
    if (r.open) rows.push(`<tr><td>—</td><td>${label(r.open.entryIdx)}</td><td class="r">${fmtPx(r.open.entryPx, sym)}</td><td class="sub">보유 중</td>
      <td class="r">${fmtPx(r.open.lastPx, sym)}</td><td class="r">—</td><td class="r ${cls(r.open.ret)}">${fmtPct(r.open.ret)}</td><td>평가</td></tr>`);
    tb.innerHTML = rows.length ? rows.reverse().join("") : `<tr class="empty-row"><td colspan="8">이 기간에는 매매 신호가 없었어요.</td></tr>`;
  }

  function showPine() {
    const sid = $("#bt-strategy").value, p = readParams(), opt = readOpt();
    $("#pine-code").textContent = BT.pine(sid, p, opt, `TD - ${BT.STRATEGIES[sid].name}`);
    $("#pine-dialog").showModal();
  }

  // ================= 탭 =================
  function initTabs() {
    $$(".tab").forEach((t) => t.addEventListener("click", () => {
      $$(".tab").forEach((x) => x.classList.toggle("active", x === t));
      $$(".panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + t.dataset.tab));
      if (location.hash !== "#" + t.dataset.tab) history.replaceState(null, "", "#" + t.dataset.tab);
    }));
    const h = location.hash.slice(1);
    if (h) $(`.tab[data-tab="${h}"]`)?.click();
    $$("#interval-seg button").forEach((b) => b.addEventListener("click", () => {
      if (b.disabled) return; state.iv = b.dataset.iv; if (state.sel) selectSymbol(state.sel);
    }));
  }

  // ================= 시작 =================
  async function init() {
    initTabs();
    if (typeof LightweightCharts === "undefined") { banner("차트 라이브러리를 불러오지 못했어요. 인터넷 연결을 확인하세요."); return; }
    try { state.meta = await getJSON("data/meta.json"); }
    catch (e) {
      $("#updated").textContent = "데이터 없음";
      banner(location.protocol === "file:"
        ? "파일을 직접 열면 데이터를 읽을 수 없어요. 폴더에서 <code>python -m http.server</code> 실행 후 <code>http://localhost:8000</code>으로 열어주세요."
        : "data/meta.json이 없어요. GitHub Actions의 <b>시세 데이터 갱신</b>을 한 번 실행하거나 <code>python scripts/fetch_data.py</code>를 실행하세요.");
      return;
    }
    state.meta.symbols.forEach((s) => (state.bySymbol[s.symbol] = s));
    $("#updated").textContent = `시세 기준 ${state.meta.updated}`;
    initMarketChart(); renderCards(); initPF(); initBT();
    if (state.meta.symbols.length) selectSymbol(state.meta.symbols[0].symbol);
  }
  init();
})();
