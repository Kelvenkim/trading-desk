/* =========================================================
 * Trading Desk — 화면 연결
 * ========================================================= */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const LC = LightweightCharts;
  const UP = "#f0525c", DOWN = "#3d8bfd", GOLD = "#f2b84b", MUTED = "#8d98b3";
  const LAST_KEY = "tradingdesk.last", FAV_KEY = "tradingdesk.favs", PF_KEY = "tradingdesk.portfolio.v1";

  // ---------- 공통 ----------
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const krw = (sym) => !sym || Data.isKR(sym);
  const fmtPx = (v, sym) => v == null || !isFinite(v) ? "—" : krw(sym) ? Math.round(v).toLocaleString("ko-KR")
    : v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fmtWon = (v) => v == null || !isFinite(v) ? "—" : Math.round(v).toLocaleString("ko-KR") + "원";
  const fmtPct = (v, d = 2) => v == null || !isFinite(v) ? "—" : (v > 0 ? "+" : "") + v.toFixed(d) + "%";
  const fmtVol = (v) => v >= 1e8 ? (v / 1e8).toFixed(2) + "억" : v >= 1e4 ? (v / 1e4).toFixed(1) + "만" : (v || 0).toLocaleString("ko-KR");
  const cls = (v) => (v > 0 ? "up" : v < 0 ? "down" : "");
  const store = {
    get: (k, d) => { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (_) { return d; } },
    set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) {} },
  };
  let toastTimer;
  function toast(msg, err) {
    const t = $("#toast"); t.innerHTML = msg; t.classList.toggle("err", !!err); t.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.hidden = true), err ? 6000 : 3000);
  }

  // ---------- 검색 상자 ----------
  function attachSearch(wrap, onPick) {
    const input = $("input", wrap), list = $(".suggest", wrap);
    let items = [], on = -1, timer;
    const close = () => { list.hidden = true; on = -1; };
    const render = () => {
      list.innerHTML = items.length
        ? items.map((s, i) => `<li data-i="${i}" class="${i === on ? "on" : ""}" role="option"><span class="nm">${esc(s.name)}</span><span class="mk">${esc(s.market)}</span><span class="cd">${esc(s.symbol)}</span></li>`).join("")
        : `<li class="none">검색 결과가 없어요. 종목명이나 코드를 다시 확인해주세요.</li>`;
      list.hidden = false;
    };
    const pick = (s) => { input.value = wrap.classList.contains("mini") ? `${s.name} (${s.symbol})` : ""; input.dataset.sym = s.symbol; close(); input.blur(); onPick(s.symbol); };
    input.addEventListener("input", () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (!q) { close(); return; }
      timer = setTimeout(async () => { items = await Data.search(q); on = items.length ? 0 : -1; render(); }, 70);
    });
    input.addEventListener("keydown", (e) => {
      if (list.hidden) return;
      if (e.key === "ArrowDown") { on = Math.min(items.length - 1, on + 1); render(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { on = Math.max(0, on - 1); render(); e.preventDefault(); }
      else if (e.key === "Enter") { if (items[on]) pick(items[on]); e.preventDefault(); }
      else if (e.key === "Escape") { close(); input.blur(); }
    });
    list.addEventListener("mousedown", (e) => { const li = e.target.closest("li[data-i]"); if (li) { e.preventDefault(); pick(items[+li.dataset.i]); } });
    input.addEventListener("blur", () => setTimeout(close, 120));
    input.addEventListener("focus", () => { if (input.value.trim() && items.length && !wrap.classList.contains("mini")) render(); });
    return { set: (sym) => { input.dataset.sym = sym; const i = Data.info(sym); input.value = `${i.name} (${sym})`; } };
  }

  // ================= 차트 탭 =================
  const cur = { sym: null, iv: "1d", seq: 0 };
  const favs = () => store.get(FAV_KEY, []);
  const quoteCache = {};

  function initChartTab() {
    ChartView.create($("#chart"), $("#legend"));
    Draw.init($("#chart-wrap"), ChartView, (tool) => {
      $$("#toolbar .tool[data-tool]").forEach((b) => b.classList.toggle("on", (b.dataset.tool || null) === tool));
    });

    // 봉 주기
    $("#iv-seg").innerHTML = Data.INTERVALS.map((x) => `<button data-iv="${x.id}">${x.label}</button>`).join("");
    $$("#iv-seg button").forEach((b) => b.addEventListener("click", () => openSymbol(cur.sym, b.dataset.iv)));

    // 지표
    const ind = ChartView.ind;
    $$("#ind-chips button").forEach((b) => {
      b.classList.toggle("on", !!ind[b.dataset.ind]);
      b.addEventListener("click", () => { const on = !b.classList.contains("on"); b.classList.toggle("on", on); ChartView.setIndicator(b.dataset.ind, on); });
    });

    // 그리기 도구
    $$("#toolbar .tool[data-tool]").forEach((b) => b.addEventListener("click", () => Draw.setTool(b.dataset.tool || null)));
    $$("#swatches button").forEach((b) => b.addEventListener("click", () => {
      $$("#swatches button").forEach((x) => x.classList.toggle("on", x === b)); Draw.setColor(b.dataset.color);
    }));
    $("#magnet").addEventListener("click", (e) => { const on = !Draw.magnet; Draw.setMagnet(on); e.currentTarget.classList.toggle("on", on); });
    $("#clear-draw").addEventListener("click", () => {
      if (!Draw.count) { toast("지울 그림이 없어요."); return; }
      if (confirm(`이 종목에 그린 ${Draw.count}개를 모두 지울까요?`)) Draw.clearAll();
    });

    $("#fit-btn").addEventListener("click", () => ChartView.chart.timeScale().fitContent());
    $("#fresh-btn").addEventListener("click", () => {
      if (!Data.getProxy()) { toast("최신 시세를 받으려면 ⚙ 설정에서 시세 중계 서버 주소를 넣어주세요.", true); return; }
      openSymbol(cur.sym, cur.iv, { fresh: true });
    });
    $("#fav-btn").addEventListener("click", () => {
      const f = favs(), i = f.indexOf(cur.sym);
      if (i >= 0) f.splice(i, 1); else f.push(cur.sym);
      store.set(FAV_KEY, f); renderWatchlist(); updateFav();
      toast(i >= 0 ? "관심종목에서 뺐어요." : "관심종목에 추가했어요.");
    });

    attachSearch($("#search"), (sym) => { showTab("chart"); openSymbol(sym); });
    document.addEventListener("keydown", (e) => {
      if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) { e.preventDefault(); $("#search-input").focus(); }
    });
    renderWatchlist();
  }

  const updateFav = () => {
    const on = favs().includes(cur.sym) || Data.isLocal(cur.sym);
    const b = $("#fav-btn"); b.classList.toggle("on", on);
    b.disabled = Data.isLocal(cur.sym) && !favs().includes(cur.sym);
    b.title = Data.isLocal(cur.sym) ? "watchlist.json에 있는 기본 관심종목이에요" : on ? "관심종목에서 빼기" : "관심종목에 추가";
  };

  function chartMsg(html) {
    const m = $("#chart-msg");
    if (!html) { m.hidden = true; return; }
    m.innerHTML = `<div class="inner">${html}</div>`; m.hidden = false;
    const b = $("[data-open-settings]", m); if (b) b.addEventListener("click", () => $("#settings").showModal());
  }

  async function openSymbol(sym, iv, opts = {}) {
    if (!sym) return;
    const seq = ++cur.seq;
    const changed = sym !== cur.sym;
    cur.sym = sym; cur.iv = iv || cur.iv;
    store.set(LAST_KEY, { sym, iv: cur.iv });
    const info = Data.info(sym);
    $("#q-title").textContent = info.name;
    $("#q-code").textContent = `${sym.replace(/\.(KS|KQ)$/, "")} · ${info.market}`;
    document.title = `${info.name} · Trading Desk`;
    $$("#iv-seg button").forEach((b) => b.classList.toggle("on", b.dataset.iv === cur.iv));
    $$("#watchlist li").forEach((li) => li.classList.toggle("on", li.dataset.sym === sym));
    updateFav();
    if (changed) { Draw.setSymbol(sym); $("#q-price").textContent = "—"; $("#q-change").textContent = ""; $("#q-range").innerHTML = ""; }
    chartMsg(`<div>시세를 불러오는 중…</div>`);

    try {
      const bars = await Data.getBars(sym, cur.iv, opts);
      if (seq !== cur.seq) return;
      if (!bars.length) throw new Error("표시할 시세가 없어요.");
      ChartView.setData(bars, sym, cur.iv, krw(sym));
      Draw.redraw();
      chartMsg(null);
      const src = Data.isLocal(sym) && !opts.fresh && (Data.IV[cur.iv].daily || (Data.hasLocalIntraday(sym) && Data.IV[cur.iv].min >= 5))
        ? `저장된 시세 · ${Data.meta.updated} 기준` : "중계 서버로 받은 시세 (최대 몇 분 지연될 수 있어요)";
      $("#chart-foot").textContent = `${src} · ${bars.length.toLocaleString("ko-KR")}개 봉`;
      if (opts.fresh) toast("최신 시세로 바꿨어요.");
    } catch (e) {
      if (seq !== cur.seq) return;
      if (e.needProxy) {
        chartMsg(`<div><b>${esc(info.name)}</b> 시세는 아직 볼 수 없어요.<br/>관심종목 외 종목이나 1분봉은 시세 중계 서버를 설정하면 볼 수 있어요.</div>
          <p><button class="btn primary" data-open-settings>중계 서버 설정</button></p>`);
      } else chartMsg(`<div>시세를 불러오지 못했어요.<br/><span class="small">${esc(e.message)}</span></div>`);
      $("#chart-foot").textContent = "";
    }
    renderQuote(sym, seq);
  }

  async function renderQuote(sym, seq) {
    try {
      const d = await Data.getBars(sym, "1d");
      if (seq !== cur.seq || d.length < 2) return;
      const last = d[d.length - 1], prev = d[d.length - 2], y = d.slice(-252);
      const chg = last.c - prev.c, pct = (last.c / prev.c - 1) * 100;
      const h52 = Math.max(...y.map((b) => b.h)), l52 = Math.min(...y.map((b) => b.l));
      const pos = last.h > last.l ? ((last.c - last.l) / (last.h - last.l)) * 100 : 50;
      $("#q-price").textContent = fmtPx(last.c, sym);
      $("#q-price").className = "px " + cls(chg);
      $("#q-change").className = "chg " + cls(chg);
      $("#q-change").textContent = `${chg > 0 ? "▲" : chg < 0 ? "▼" : ""} ${fmtPx(Math.abs(chg), sym)} (${fmtPct(pct)})`;
      $("#q-range").innerHTML =
        `<span>${esc(last.day)}</span>` +
        `<span>당일<b>${fmtPx(last.l, sym)} ~ ${fmtPx(last.h, sym)}</b><span class="daybar"><i style="left:${pos}%"></i></span></span>` +
        `<span>52주<b>${fmtPx(l52, sym)} ~ ${fmtPx(h52, sym)}</b></span>` +
        `<span>거래량<b>${fmtVol(last.v)}</b></span>`;
      quoteCache[sym] = { close: last.c, changePct: pct, change: chg };
    } catch (_) { /* 시세 없음: 차트 영역에서 안내 */ }
  }

  function renderWatchlist() {
    const base = Data.meta.symbols.map((s) => s.symbol);
    const all = [...base, ...favs().filter((s) => !base.includes(s))];
    $("#wl-count").textContent = all.length;
    $("#watchlist").innerHTML = all.map((sym) => {
      const m = Data.meta.symbols.find((x) => x.symbol === sym) || quoteCache[sym];
      const info = Data.info(sym);
      return `<li data-sym="${esc(sym)}" class="${sym === cur.sym ? "on" : ""}">
        <span class="nm">${esc(info.name)}</span><span class="px">${m ? fmtPx(m.close, sym) : "—"}</span>
        <span class="cd">${esc(sym.replace(/\.(KS|KQ)$/, ""))}</span><span class="pc ${m ? cls(m.changePct) : ""}">${m ? fmtPct(m.changePct) : ""}</span></li>`;
    }).join("");
    $$("#watchlist li").forEach((li) => li.addEventListener("click", () => openSymbol(li.dataset.sym)));
    // 직접 추가한 종목은 중계 서버로 현재가 채우기
    if (Data.getProxy()) all.filter((s) => !base.includes(s) && !quoteCache[s]).forEach(async (s) => {
      try { const q = await Data.quote(s); quoteCache[s] = q; renderWatchlist(); } catch (_) { quoteCache[s] = { close: NaN, changePct: NaN }; }
    });
  }

  // ================= 설정 =================
  function initSettings() {
    $$("dialog [data-close]").forEach((b) => b.addEventListener("click", () => b.closest("dialog").close()));
    $("#open-settings").addEventListener("click", () => { $("#proxy-input").value = Data.getProxy(); $("#proxy-status").textContent = ""; $("#settings").showModal(); });
    $("#proxy-save").addEventListener("click", async () => {
      let v = $("#proxy-input").value.trim();
      if (v && !/^https?:\/\//.test(v)) v = "https://" + v;
      v = v.replace(/\/+$/, "");
      Data.setProxy(v);
      const st = $("#proxy-status");
      if (!v) { st.textContent = "중계 서버를 사용하지 않아요."; return; }
      st.textContent = "연결 확인 중…";
      try {
        const b = await Data.getBars("005930.KS", "1d", { fresh: true });
        st.textContent = `연결됐어요. 삼성전자 ${b[b.length - 1].day} 종가 ${fmtPx(b[b.length - 1].c, "005930.KS")}원`;
        renderWatchlist(); if (cur.sym) openSymbol(cur.sym, cur.iv);
      } catch (e) { st.textContent = `연결하지 못했어요: ${e.message}. 주소를 다시 확인해주세요.`; }
    });
  }

  // ================= 포트폴리오 =================
  const loadPF = () => store.get(PF_KEY, { holdings: [], cash: 0 });
  const savePF = (pf) => store.set(PF_KEY, pf);
  const pfQuote = (sym) => Data.meta.symbols.find((x) => x.symbol === sym) || quoteCache[sym];

  function renderPF() {
    const pf = loadPF();
    const rows = pf.holdings.map((h) => {
      const q = pfQuote(h.symbol);
      const px = q && isFinite(q.close) ? q.close : null;
      const cost = h.qty * h.avg, val = px != null ? h.qty * px : null;
      return { ...h, name: Data.info(h.symbol).name, px, cost, val, pnl: val != null ? val - cost : null,
        ret: val != null && cost ? (val / cost - 1) * 100 : null, dayPct: q ? q.changePct : null, dayChg: q && isFinite(q.change) ? q.change * h.qty : 0 };
    });
    const invested = rows.reduce((s, r) => s + r.cost, 0);
    const value = rows.reduce((s, r) => s + (r.val ?? r.cost), 0);
    const total = value + (+pf.cash || 0), pnl = value - invested;
    const day = rows.reduce((s, r) => s + (r.dayChg || 0), 0);
    $("#pf-summary").innerHTML = [
      ["총 자산", fmtWon(total), "", "hero"],
      ["주식 평가액", fmtWon(value), "", ""],
      ["평가 손익", `${pnl > 0 ? "+" : ""}${fmtWon(pnl)}`, cls(pnl), ""],
      ["수익률", fmtPct(invested ? (pnl / invested) * 100 : 0), cls(pnl), ""],
      ["오늘 변동", `${day > 0 ? "+" : ""}${fmtWon(day)}`, cls(day), ""],
      ["예수금", fmtWon(+pf.cash || 0), "", ""],
    ].map(([k, v, c, x]) => `<div class="stat ${x}"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`).join("");

    const tb = $("#pf-table tbody");
    if (!rows.length) tb.innerHTML = `<tr class="empty-row"><td colspan="9">아직 보유 종목이 없어요. 오른쪽에서 종목을 검색해 추가하세요.</td></tr>`;
    else {
      rows.sort((a, b) => (b.val ?? b.cost) - (a.val ?? a.cost));
      tb.innerHTML = rows.map((r) => {
        const w = total ? ((r.val ?? r.cost) / total) * 100 : 0;
        return `<tr data-sym="${esc(r.symbol)}">
          <td><b>${esc(r.name)}</b><div class="sub">${esc(r.symbol)}${r.px == null ? " · 현재가 없음" : ""}</div></td>
          <td class="r">${r.qty.toLocaleString("ko-KR")}</td><td class="r">${fmtPx(r.avg, r.symbol)}</td>
          <td class="r">${fmtPx(r.px, r.symbol)}<div class="sub ${cls(r.dayPct)}">${fmtPct(r.dayPct)}</div></td>
          <td class="r">${fmtWon(r.val)}</td>
          <td class="r ${cls(r.pnl)}">${r.pnl == null ? "—" : (r.pnl > 0 ? "+" : "") + fmtWon(r.pnl)}</td>
          <td class="r ${cls(r.ret)}">${fmtPct(r.ret)}</td>
          <td class="r">${w.toFixed(1)}%<span class="wbar"><b style="width:${w}%"></b></span></td>
          <td><button class="del" data-del="${esc(r.symbol)}" title="삭제">✕</button></td></tr>`;
      }).join("");
      $$("[data-del]", tb).forEach((b) => b.addEventListener("click", () => { const p = loadPF(); p.holdings = p.holdings.filter((h) => h.symbol !== b.dataset.del); savePF(p); renderPF(); }));
      $$("tr[data-sym]", tb).forEach((tr) => tr.addEventListener("dblclick", () => {
        const h = loadPF().holdings.find((x) => x.symbol === tr.dataset.sym); if (!h) return;
        pfSearch.set(h.symbol); $("#pf-qty").value = h.qty; $("#pf-avg").value = h.avg;
      }));
    }
    $("#pf-cash").value = pf.cash || "";
    // 관심종목 밖 종목은 중계 서버로 현재가 받아서 다시 그리기
    const missing = pf.holdings.filter((h) => !pfQuote(h.symbol)).map((h) => h.symbol);
    if (missing.length && Data.getProxy()) Promise.allSettled(missing.map(async (s) => (quoteCache[s] = await Data.quote(s)))).then((r) => { if (r.some((x) => x.status === "fulfilled")) renderPF(); });
  }

  let pfSearch;
  function initPF() {
    pfSearch = attachSearch($("#pf-symbol").closest(".search"), () => $("#pf-qty").focus());
    $("#pf-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const sym = $("#pf-symbol").dataset.sym;
      if (!sym) { toast("종목을 검색해서 목록에서 골라주세요.", true); return; }
      const qty = +$("#pf-qty").value, avg = +$("#pf-avg").value;
      const pf = loadPF(), i = pf.holdings.findIndex((h) => h.symbol === sym);
      if (qty === 0) { if (i >= 0) pf.holdings.splice(i, 1); }
      else if (i >= 0) pf.holdings[i] = { symbol: sym, qty, avg };
      else pf.holdings.push({ symbol: sym, qty, avg });
      savePF(pf); e.target.reset(); delete $("#pf-symbol").dataset.sym; renderPF(); toast("저장했어요.");
    });
    $("#cash-form").addEventListener("submit", (e) => { e.preventDefault(); const pf = loadPF(); pf.cash = +$("#pf-cash").value || 0; savePF(pf); renderPF(); toast("예수금을 저장했어요."); });
    $("#pf-export").addEventListener("click", () => download("portfolio.json", JSON.stringify(loadPF(), null, 2), "application/json"));
    $("#pf-import").addEventListener("change", async (e) => {
      const f = e.target.files[0]; if (!f) return;
      try { const j = JSON.parse(await f.text()); if (!Array.isArray(j.holdings)) throw 0; savePF(j); renderPF(); toast("가져왔어요."); }
      catch (_) { toast("포트폴리오 파일 형식이 맞지 않아요. 내보내기로 만든 파일을 골라주세요.", true); }
      e.target.value = "";
    });
    renderPF();
  }

  function download(name, text, type) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  // ================= 백테스트 =================
  let btc = null, btSearch, btSym = null, csv = null, lastRun = null;

  function chartOpts() {
    return {
      autoSize: true,
      layout: { background: { color: "transparent" }, textColor: MUTED, fontSize: 11, fontFamily: "Pretendard Variable, Pretendard, system-ui, sans-serif" },
      grid: { vertLines: { color: "rgba(141,152,179,.07)" }, horzLines: { color: "rgba(141,152,179,.07)" } },
      rightPriceScale: { borderColor: "#253049" },
      timeScale: { borderColor: "#253049", timeVisible: true, secondsVisible: false },
      crosshair: { mode: 0 }, localization: { locale: "ko-KR" },
    };
  }

  function initBT() {
    btSearch = attachSearch($("#bt-symbol").closest(".search"), (sym) => { btSym = sym; csv = null; $("#bt-csv-name").textContent = ""; });
    $("#bt-interval").innerHTML = Data.INTERVALS.map((x) => `<option value="${x.id}" ${x.id === "1d" ? "selected" : ""}>${x.label}봉</option>`).join("");
    $("#bt-strategy").innerHTML = Object.entries(BT.STRATEGIES).map(([k, s]) => `<option value="${k}">${s.name}</option>`).join("");
    const setDates = () => {
      const iv = Data.IV[$("#bt-interval").value];
      const end = new Date(), start = new Date(end);
      if (iv.daily) start.setFullYear(end.getFullYear() - 5);
      $("#bt-start").value = iv.daily ? start.toISOString().slice(0, 10) : "";
      $("#bt-end").value = end.toISOString().slice(0, 10);
      $("#bt-dayclose").checked = !iv.daily;
    };
    $("#bt-interval").addEventListener("change", setDates);
    $("#bt-strategy").addEventListener("change", renderParams);
    setDates(); renderParams();

    $("#bt-csv").addEventListener("change", async (e) => {
      const f = e.target.files[0]; if (!f) return;
      try {
        csv = { name: f.name.replace(/\.[^.]+$/, ""), ...parseCSV(await f.text()) };
        $("#bt-csv-name").textContent = `${f.name} · ${csv.bars.length.toLocaleString()}개 봉 (${csv.intraday ? "분봉" : "일봉"}) · 종목을 다시 고르면 해제돼요`;
        $("#bt-start").value = ""; $("#bt-end").value = "";
        $("#bt-dayclose").checked = csv.intraday;
      } catch (err) { toast(`CSV를 읽지 못했어요: ${esc(err.message)}`, true); }
      e.target.value = "";
    });

    $("#bt-run").addEventListener("click", runBT);
    $("#bt-pine").addEventListener("click", () => {
      const sid = $("#bt-strategy").value;
      $("#pine-code").textContent = BT.pine(sid, readParams(), readOpt(), `TD - ${BT.STRATEGIES[sid].name}`);
      $("#pine-dialog").showModal();
    });
    $("#pine-copy").addEventListener("click", async () => {
      try { await navigator.clipboard.writeText($("#pine-code").textContent); toast("복사했어요. TradingView Pine 에디터에 붙여넣으세요."); }
      catch (_) { toast("클립보드를 쓸 수 없어요. 코드를 직접 선택해서 복사해주세요.", true); }
    });
    $("#bt-trades-csv").addEventListener("click", () => {
      if (!lastRun) { toast("먼저 백테스트를 실행해주세요."); return; }
      const lines = ["no,entry_time,entry_price,exit_time,exit_price,bars,return_pct,reason"];
      lastRun.result.trades.forEach((t, i) => lines.push([i + 1, lastRun.label(t.entryIdx), t.entryPx, lastRun.label(t.exitIdx), t.exitPx, t.bars, t.ret.toFixed(3), t.reason].join(",")));
      download("trades.csv", "﻿" + lines.join("\n"), "text/csv");
    });

    const pc = LC.createChart($("#bt-price"), chartOpts()), ec = LC.createChart($("#bt-equity"), chartOpts());
    const candles = pc.addSeries(LC.CandlestickSeries, { upColor: UP, downColor: DOWN, borderUpColor: UP, borderDownColor: DOWN, wickUpColor: UP, wickDownColor: DOWN });
    btc = { pc, ec, candles, marks: LC.createSeriesMarkers(candles, []), lines: [],
      eq: ec.addSeries(LC.LineSeries, { color: GOLD, lineWidth: 2, priceLineVisible: false, priceFormat: { type: "price", precision: 0, minMove: 1 } }),
      bh: ec.addSeries(LC.LineSeries, { color: MUTED, lineWidth: 1, lineStyle: 2, priceLineVisible: false, priceFormat: { type: "price", precision: 0, minMove: 1 } }) };
    let syncing = false;
    const link = (a, b) => a.timeScale().subscribeVisibleLogicalRangeChange((r) => { if (syncing || !r) return; syncing = true; b.timeScale().setVisibleLogicalRange(r); syncing = false; });
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
    const S = BT.STRATEGIES[$("#bt-strategy").value], p = {};
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
    const find = (...n) => head.findIndex((h) => n.includes(h));
    const it = find("time", "date", "datetime", "timestamp", "날짜", "일자"), io = find("open", "시가"), ih = find("high", "고가"),
      il = find("low", "저가"), ic = find("close", "종가", "adj close"), iv = find("volume", "거래량", "vol");
    if ([it, io, ih, il, ic].some((x) => x < 0)) throw new Error("time, open, high, low, close 열이 필요해요");
    const raw = lines.slice(1).map((ln) => {
      const c = ln.split(/[,;\t]/).map((x) => x.trim().replace(/^"|"$/g, ""));
      let ms;
      if (/^\d+(\.\d+)?$/.test(c[it])) { ms = +c[it]; if (ms < 1e12) ms *= 1000; }
      else ms = Date.parse(/[T ]/.test(c[it]) ? c[it] : c[it] + "T00:00:00Z");
      return { ms, o: +c[io], h: +c[ih], l: +c[il], c: +c[ic], v: iv >= 0 ? +c[iv] || 0 : 0 };
    }).filter((b) => !isNaN(b.ms) && !isNaN(b.c)).sort((a, b) => a.ms - b.ms);
    if (raw.length < 30) throw new Error("데이터가 너무 적어요 (30봉 이상 필요)");
    const gaps = raw.slice(1, 200).map((b, i) => b.ms - raw[i].ms).sort((a, b) => a - b);
    const intraday = gaps[Math.floor(gaps.length / 2)] < 86400000 * 0.9;
    const bars = raw.map((b) => intraday ? { ...b, t: Math.floor(b.ms / 1000) + Data.KST, day: Data.kstDay(b.ms) }
      : { ...b, t: new Date(b.ms).toISOString().slice(0, 10), day: new Date(b.ms).toISOString().slice(0, 10) });
    return { bars: bars.filter((b, i) => i === 0 || b.t !== bars[i - 1].t), intraday };
  }

  async function runBT() {
    const btn = $("#bt-run"); btn.disabled = true; btn.textContent = "계산 중…";
    try {
      let all, intraday, title, sym = null;
      if (csv) { all = csv.bars; intraday = csv.intraday; title = csv.name; }
      else {
        sym = btSym || cur.sym;
        if (!sym) throw new Error("종목을 골라주세요.");
        const ivId = $("#bt-interval").value;
        all = await Data.getBars(sym, ivId); intraday = !Data.IV[ivId].daily; title = Data.info(sym).name;
      }
      const s = Date.parse($("#bt-start").value + "T00:00:00Z") - Data.KST * 1000;
      const e = Date.parse($("#bt-end").value + "T23:59:59Z") - Data.KST * 1000;
      const bars = all.filter((b) => (isNaN(s) || b.ms >= s) && (isNaN(e) || b.ms <= e));
      if (bars.length < 30) throw new Error("선택한 기간의 봉이 30개 미만이에요. 기간을 늘려주세요.");
      const sid = $("#bt-strategy").value, p = readParams(), opt = readOpt();
      opt.dayKey = intraday ? (i) => bars[i].day : null;
      if (!intraday) opt.dayClose = false;
      const result = BT.run(bars, sid, p, opt);
      const label = (i) => intraday ? new Date(bars[i].ms + Data.KST * 1000).toISOString().slice(0, 16).replace("T", " ") : bars[i].day;
      lastRun = { sym, sid, p, opt, title, result, bars, label };
      renderResult(lastRun);
    } catch (err) {
      toast(err.needProxy ? "이 종목은 ⚙ 설정에서 시세 중계 서버를 연결해야 백테스트할 수 있어요." : esc(err.message), true);
    } finally { btn.disabled = false; btn.textContent = "백테스트 실행"; }
  }

  function renderResult(run) {
    const { result: r, bars, opt, label, sym } = run, st = r.stats;
    const m = [
      ["총 수익률", fmtPct(st.totalRet), cls(st.totalRet), "hero"],
      ["최종 자산", fmtWon(st.final), "", ""],
      ["보유만 했을 때", fmtPct(st.buyHold), cls(st.buyHold), ""],
      ["연환산 (CAGR)", st.cagr == null ? "—" : fmtPct(st.cagr), cls(st.cagr), ""],
      ["최대 낙폭 (MDD)", fmtPct(st.mdd), "down", ""],
      ["거래 수", st.trades + (r.open ? " (+보유 중 1)" : ""), "", ""],
      ["승률", st.trades ? st.winRate.toFixed(1) + "%" : "—", "", ""],
      ["평균 수익 / 손실", `${fmtPct(st.avgWin, 1)} / ${fmtPct(st.avgLoss, 1)}`, "", ""],
      ["손익비 (PF)", !isFinite(st.profitFactor) ? "∞" : st.profitFactor.toFixed(2), "", ""],
      ["시장 노출", st.exposure.toFixed(1) + "%", "", ""],
    ];
    $("#bt-metrics").innerHTML = m.map(([k, v, c, x]) => `<div class="stat ${x}"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`).join("");
    $("#bt-range").textContent = `${run.title} · ${label(0)} ~ ${label(bars.length - 1)} · ${bars.length.toLocaleString()}개 봉`;

    const pf = krw(sym) ? { type: "price", precision: 0, minMove: 1 } : { type: "price", precision: 2, minMove: 0.01 };
    btc.candles.applyOptions({ priceFormat: pf });
    const pfmt = (v) => krw(sym) ? Math.round(v).toLocaleString("ko-KR") : v.toLocaleString("en-US", { maximumFractionDigits: 2 });
    btc.pc.applyOptions({ localization: { locale: "ko-KR", priceFormatter: pfmt }, timeScale: { timeVisible: !!run.opt.dayKey } });
    btc.ec.applyOptions({ localization: { locale: "ko-KR", priceFormatter: (v) => Math.round(v).toLocaleString("ko-KR") }, timeScale: { timeVisible: !!run.opt.dayKey } });
    btc.candles.setData(bars.map((b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c })));
    btc.lines.forEach((s) => btc.pc.removeSeries(s));
    btc.lines = r.lines.map((ln) => {
      const s = btc.pc.addSeries(LC.LineSeries, { color: ln.color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      s.setData(bars.map((b, i) => ({ time: b.t, value: ln.data[i] })).filter((x) => isFinite(x.value))); return s;
    });
    const marks = [];
    r.trades.forEach((t) => {
      marks.push({ time: bars[t.entryIdx].t, position: "belowBar", color: UP, shape: "arrowUp", text: "매수" });
      marks.push({ time: bars[t.exitIdx].t, position: "aboveBar", color: DOWN, shape: "arrowDown", text: `${t.ret >= 0 ? "+" : ""}${t.ret.toFixed(1)}%` });
    });
    if (r.open) marks.push({ time: bars[r.open.entryIdx].t, position: "belowBar", color: UP, shape: "arrowUp", text: "매수 (보유 중)" });
    marks.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
    btc.marks.setMarkers(marks);
    btc.eq.setData(bars.map((b, i) => ({ time: b.t, value: r.equity[i] })));
    btc.bh.setData(bars.map((b) => ({ time: b.t, value: (opt.capital * b.c) / bars[0].o })));
    btc.pc.timeScale().fitContent(); btc.ec.timeScale().fitContent();

    const rows = r.trades.map((t, i) => `<tr><td>${i + 1}</td><td>${label(t.entryIdx)}</td><td class="r">${fmtPx(t.entryPx, sym)}</td>
      <td>${label(t.exitIdx)}</td><td class="r">${fmtPx(t.exitPx, sym)}</td><td class="r">${t.bars}봉</td>
      <td class="r ${cls(t.ret)}">${fmtPct(t.ret)}</td><td>${t.reason}</td></tr>`);
    if (r.open) rows.push(`<tr><td>—</td><td>${label(r.open.entryIdx)}</td><td class="r">${fmtPx(r.open.entryPx, sym)}</td><td class="sub">보유 중</td>
      <td class="r">${fmtPx(r.open.lastPx, sym)}</td><td class="r">—</td><td class="r ${cls(r.open.ret)}">${fmtPct(r.open.ret)}</td><td>평가</td></tr>`);
    $("#bt-trades tbody").innerHTML = rows.length ? rows.reverse().join("") : `<tr class="empty-row"><td colspan="8">이 기간에는 매매 신호가 없었어요. 기간을 늘리거나 설정을 바꿔보세요.</td></tr>`;
  }

  // ================= 탭 =================
  function showTab(name) {
    $$(".tab").forEach((x) => x.classList.toggle("active", x.dataset.tab === name));
    $$(".panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + name));
    if (location.hash !== "#" + name) history.replaceState(null, "", "#" + name);
    if (name === "portfolio") renderPF();
    if (name === "backtest" && !btSym && cur.sym) { btSym = cur.sym; btSearch.set(cur.sym); }
  }

  // ================= 시작 =================
  async function init() {
    $$(".tab").forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));
    if (typeof LightweightCharts === "undefined") { toast("차트 라이브러리를 불러오지 못했어요. 인터넷 연결을 확인하고 새로고침해주세요.", true); return; }
    try { await Data.init(); }
    catch (e) {
      toast(location.protocol === "file:"
        ? "파일을 직접 열면 시세를 읽을 수 없어요. 폴더에서 python -m http.server 실행 후 http://localhost:8000 으로 열어주세요."
        : "data/meta.json이 없어요. GitHub Actions에서 '시세 데이터 갱신'을 한 번 실행해주세요.", true);
    }
    Data.loadSymbols();
    initChartTab(); initSettings(); initPF(); initBT();
    const last = store.get(LAST_KEY, null);
    const first = (last && last.sym) || (Data.meta.symbols[0] && Data.meta.symbols[0].symbol);
    if (first) openSymbol(first, (last && last.iv) || "1d");
    const h = location.hash.slice(1);
    if (["portfolio", "backtest"].includes(h)) showTab(h);
  }
  init();
})();
