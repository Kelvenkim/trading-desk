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

  /** 백테스트 실행. silent=true 면 오류를 화면 알림 대신 던짐 (대화창에서 사용) */
  async function runBT(silent = false) {
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
      return lastRun;
    } catch (err) {
      const msg = err.needProxy ? "이 종목은 ⚙ 설정에서 시세 중계 서버를 연결해야 백테스트할 수 있어요." : err.message;
      if (silent) throw new Error(msg);
      toast(esc(msg), true);
    } finally { btn.disabled = false; btn.textContent = "백테스트 실행"; }
  }

  // ================= 대화로 설정하기 =================
  const CHAT_KEY = "tradingdesk.chat";
  const chat = { history: [], busy: false };
  const chatCfg = () => store.get(CHAT_KEY, { model: "claude-sonnet-5-5", pass: "" });

  /** 지금 화면에 있는 백테스트 설정 */
  function currentSettings() {
    const sym = csv ? null : (btSym || cur.sym);
    return {
      symbol: sym ? `${Data.info(sym).name} (${sym})` : csv ? `CSV: ${csv.name}` : null,
      interval: $("#bt-interval").value, start: $("#bt-start").value || null, end: $("#bt-end").value || null,
      strategy: $("#bt-strategy").value, params: readParams(),
      stop_loss: +$("#bt-sl").value, take_profit: +$("#bt-tp").value, trailing: +$("#bt-trail").value,
      max_hold: +$("#bt-hold").value, day_close: $("#bt-dayclose").checked,
      capital: +$("#bt-capital").value, buy_fee: +$("#bt-buyfee").value, sell_fee: +$("#bt-sellfee").value, slippage: +$("#bt-slip").value,
    };
  }
  function summarize(run) {
    if (!run) return null;
    const s = run.result.stats, r2 = (v) => (v == null || !isFinite(v) ? null : Math.round(v * 100) / 100);
    const trades = run.result.trades;
    const reasons = trades.reduce((m, t) => ((m[t.reason] = (m[t.reason] || 0) + 1), m), {});
    return {
      target: run.title, period: `${run.label(0)} ~ ${run.label(run.bars.length - 1)}`, bars: run.bars.length,
      strategy: BT.STRATEGIES[run.sid].name, params: run.p,
      total_return_pct: r2(s.totalRet), buy_hold_pct: r2(s.buyHold), cagr_pct: r2(s.cagr), mdd_pct: r2(s.mdd),
      trades: s.trades, win_rate_pct: r2(s.winRate), avg_win_pct: r2(s.avgWin), avg_loss_pct: r2(s.avgLoss),
      profit_factor: r2(s.profitFactor), exposure_pct: r2(s.exposure), open_position: !!run.result.open, exit_reasons: reasons,
    };
  }

  /** 설정 적용 (AI 도구 호출과 간단 모드가 같이 씀). 반환: 바꾼 항목 설명 목록 */
  async function applySettings(a) {
    const done = [];
    const setNum = (id, v, label) => { if (v != null && isFinite(v)) { $(id).value = v; done.push(`${label} ${v}`); } };
    if (a.symbol_query) {
      const hit = (await Data.search(String(a.symbol_query), 1))[0];
      if (!hit) throw new Error(`'${a.symbol_query}' 종목을 찾지 못했어요.`);
      btSym = hit.symbol; csv = null; $("#bt-csv-name").textContent = ""; btSearch.set(hit.symbol);
      done.push(`종목 ${hit.name}`);
    }
    if (a.interval && Data.IV[a.interval]) {
      const changed = $("#bt-interval").value !== a.interval;
      $("#bt-interval").value = a.interval;
      if (changed) $("#bt-interval").dispatchEvent(new Event("change")); // 기간·당일청산 기본값 갱신
      done.push(`${Data.IV[a.interval].label}봉`);
    }
    if (a.start !== undefined) { $("#bt-start").value = a.start || ""; done.push(`시작 ${a.start || "처음부터"}`); }
    if (a.end !== undefined) { $("#bt-end").value = a.end || ""; done.push(`종료 ${a.end || "끝까지"}`); }
    if (a.strategy && BT.STRATEGIES[a.strategy]) {
      if ($("#bt-strategy").value !== a.strategy) { $("#bt-strategy").value = a.strategy; renderParams(); }
      done.push(`전략 ${BT.STRATEGIES[a.strategy].name}`);
    }
    if (a.params && typeof a.params === "object") {
      const S = BT.STRATEGIES[$("#bt-strategy").value];
      for (const [k, v] of Object.entries(a.params)) {
        const def = S.params.find((d) => d.key === k), el = $(`[data-p="${k}"]`);
        if (!def || !el) continue;
        el.value = def.type === "select" ? (def.options.includes(v) ? v : def.def) : Math.min(def.max ?? Infinity, Math.max(def.min ?? -Infinity, +v));
        done.push(`${def.label} ${el.value}`);
      }
    }
    setNum("#bt-sl", a.stop_loss, "손절 %"); setNum("#bt-tp", a.take_profit, "익절 %");
    setNum("#bt-trail", a.trailing, "트레일링 %"); setNum("#bt-hold", a.max_hold, "최대 보유 봉");
    if (typeof a.day_close === "boolean") { $("#bt-dayclose").checked = a.day_close; done.push(`장 마감 청산 ${a.day_close ? "켬" : "끔"}`); }
    setNum("#bt-capital", a.capital, "초기 자금"); setNum("#bt-buyfee", a.buy_fee, "매수 수수료 %");
    setNum("#bt-sellfee", a.sell_fee, "매도 수수료+세금 %"); setNum("#bt-slip", a.slippage, "슬리피지 %");
    return done;
  }

  // ---------- Claude에게 줄 설명 ----------
  function systemPrompt() {
    const strategies = Object.entries(BT.STRATEGIES).map(([k, s]) =>
      `- ${k} (${s.name}): ${s.desc}\n  파라미터: ${s.params.map((p) => `${p.key}=${p.label}${p.type === "select" ? `(${p.options.join("/")})` : `(${p.min}~${p.max}, 기본 ${p.def})`}`).join(", ")}`).join("\n");
    return `너는 개인 주식 연구 사이트 "Trading Desk"의 백테스트 탭 안에 있는 도우미야. 사용자는 한국 개인 투자자이고 한국어로 대화해.

할 수 있는 일
- configure_backtest 도구로 백테스트 설정(종목, 봉 주기, 기간, 전략, 파라미터, 손절·익절·트레일링·최대 보유, 장 마감 청산, 비용)을 바꾸고, run=true면 실행해서 결과를 받아.
- 사용자가 "해줘/바꿔줘/돌려줘"라고 하면 바로 도구를 써. 설정이 애매하면 합리적인 기본값을 쓰고 무엇을 골랐는지 말해.
- 추천을 부탁받으면 근거와 함께 제안하고, 필요하면 한 번에 2~4개 설정을 실행해서 비교해. 한 턴에 6번 넘게 실행하지 마.
- 결과를 해석할 때는 총 수익률을 "그냥 보유했을 때"와 비교하고, MDD·거래 수·승률·손익비를 같이 봐. 거래 수가 적으면(20회 미만) 우연일 수 있다고 말해.
- 같은 데이터로 설정을 계속 바꿔 가며 가장 좋은 값을 찾으면 과최적화가 된다는 점을 필요할 때 짚어줘. 앞 기간으로 고르고 뒤 기간으로 확인하는 방법을 권해.
- 수익을 장담하거나 특정 종목 매수·매도를 권하지 마. 연구용 도구라는 전제로 사실과 수치 중심으로 말해.

봉 주기 id: ${Data.INTERVALS.map((x) => `${x.id}(${x.label})`).join(", ")}
- 관심종목은 5분봉 이상 저장돼 있고, 그 외 종목이나 1분봉은 중계 서버로 받아. 분봉은 최근 60일(1시간봉은 약 2년), 1분봉은 최근 5일 정도만 있어.
- 분봉이면 day_close(장 마감 전 청산)를 보통 켜.

전략
${strategies}

엔진 규칙: 롱 전용, 신호가 나오면 자금 전액 진입. 신호는 봉 종가로 판단하고 다음 봉 시가에 체결. 손절·익절·트레일링은 봉 안에서 체결하고 같은 봉에 둘 다 닿으면 손절 우선. 비용 기본값은 매수 0.015%, 매도 수수료+세금 0.215%, 슬리피지 편도 0.05%.

이 사용자의 지난 연구 메모: 한국 대형주에서 같은 종목 박스권 롱숏 비중조절은 1시간봉·5분봉·일봉 모두 비용 후 우위가 없었고, 1시간봉에서는 박스 상단 돌파 후 추세가 이어지는 경향(+0.18~0.28%)이 있었어.

답변은 짧고 읽기 쉽게. 숫자는 퍼센트 소수 한두 자리로.`;
  }
  const TOOLS = () => [{
    name: "configure_backtest",
    description: "백테스트 탭의 설정을 바꾸고, run=true면 실행해서 결과 요약을 돌려준다. 바꾸지 않을 항목은 넣지 않는다.",
    input_schema: {
      type: "object",
      properties: {
        symbol_query: { type: "string", description: "종목명, 코드, 티커 (예: 삼성전자, 005930, NVDA)" },
        interval: { type: "string", enum: Data.INTERVALS.map((x) => x.id) },
        start: { type: "string", description: "YYYY-MM-DD, 빈 문자열이면 데이터 처음부터" },
        end: { type: "string", description: "YYYY-MM-DD, 빈 문자열이면 끝까지" },
        strategy: { type: "string", enum: Object.keys(BT.STRATEGIES) },
        params: { type: "object", description: "전략 파라미터 {key: 값}" },
        stop_loss: { type: "number", description: "손절 %, 0이면 사용 안 함" },
        take_profit: { type: "number", description: "익절 %, 0이면 사용 안 함" },
        trailing: { type: "number", description: "트레일링 스톱 %, 0이면 사용 안 함" },
        max_hold: { type: "integer", description: "최대 보유 봉 수, 0이면 사용 안 함" },
        day_close: { type: "boolean", description: "분봉에서 장 마감 전 청산" },
        capital: { type: "number" }, buy_fee: { type: "number" }, sell_fee: { type: "number" }, slippage: { type: "number" },
        run: { type: "boolean", description: "설정 후 바로 실행할지" },
      },
    },
  }];

  // ---------- 화면 ----------
  function md(s) {
    return esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/^[-•] (.*)$/gm, "<span class=\"li\">$1</span>").replace(/<\/span>\n/g, "</span>").replace(/\n/g, "<br/>");
  }
  function addMsg(role, html, cls = "") {
    const box = $("#chat-log");
    $(".chat-empty", box)?.remove();
    const el = document.createElement("div");
    el.className = `msg ${role} ${cls}`; el.innerHTML = html;
    box.appendChild(el); box.scrollTop = box.scrollHeight;
    return el;
  }
  const typing = () => addMsg("bot", `<span class="dots"><i></i><i></i><i></i></span>`, "typing");

  async function callClaude(messages) {
    const proxy = Data.getProxy();
    if (!proxy) { const e = new Error("no proxy"); e.code = "no_proxy"; throw e; }
    const cfg = chatCfg();
    const r = await fetch(proxy.replace(/\/+$/, "") + "/chat", {
      method: "POST",
      headers: { "content-type": "application/json", ...(cfg.pass ? { "x-td-pass": cfg.pass } : {}) },
      body: JSON.stringify({ model: cfg.model, max_tokens: 2000, system: systemPrompt(), tools: TOOLS(), messages }),
    });
    let j = null; try { j = await r.json(); } catch (_) {}
    if (!r.ok) {
      const e = new Error((j && j.error && j.error.message) || `AI 서버 오류 (${r.status})`);
      e.code = (j && j.error && j.error.type) || r.status; throw e;
    }
    return j;
  }

  async function sendChat(text) {
    if (chat.busy || !text.trim()) return;
    chat.busy = true; $("#chat-send").disabled = true;
    addMsg("me", md(text));
    const ctx = `[현재 설정]\n${JSON.stringify(currentSettings())}\n[최근 결과]\n${JSON.stringify(summarize(lastRun))}\n\n`;
    chat.history.push({ role: "user", content: [{ type: "text", text: ctx + text }] });
    let t = typing();
    try {
      for (let round = 0; round < 6; round++) {
        const res = await callClaude(chat.history);
        chat.history.push({ role: "assistant", content: res.content });
        const said = res.content.filter((b) => b.type === "text").map((b) => b.text).join("\n").trim();
        const calls = res.content.filter((b) => b.type === "tool_use");
        t.remove();
        if (said) addMsg("bot", md(said));
        if (res.stop_reason !== "tool_use" || !calls.length) break;
        const results = [];
        for (const c of calls) {
          try {
            const done = await applySettings(c.input || {});
            let out = { applied: done };
            if (c.input && c.input.run) {
              const run = await runBT(true);
              out.result = summarize(run);
              addMsg("bot", `<span class="chip-note">실행: ${esc(run.title)} · ${esc(BT.STRATEGIES[run.sid].name)} → 수익 <b class="${cls(run.result.stats.totalRet)}">${fmtPct(run.result.stats.totalRet)}</b>, MDD ${fmtPct(run.result.stats.mdd)}, 거래 ${run.result.stats.trades}회</span>`, "note");
            } else if (done.length) {
              addMsg("bot", `<span class="chip-note">설정 변경: ${esc(done.join(", "))}</span>`, "note");
            }
            results.push({ type: "tool_result", tool_use_id: c.id, content: JSON.stringify(out) });
          } catch (err) {
            addMsg("bot", `<span class="chip-note err">${esc(err.message)}</span>`, "note");
            results.push({ type: "tool_result", tool_use_id: c.id, content: err.message, is_error: true });
          }
        }
        chat.history.push({ role: "user", content: results });
        t = typing();
      }
    } catch (err) {
      t.remove();
      // 실패한 사용자 메시지는 기록에서 빼서 다음 대화가 꼬이지 않게
      while (chat.history.length && chat.history[chat.history.length - 1].role === "user") chat.history.pop();
      if (chat.history.length && chat.history[chat.history.length - 1].role === "assistant" && chat.history[chat.history.length - 1].content.some((b) => b.type === "tool_use")) chat.history.pop();
      if (err.code === "no_proxy" || err.code === "not_configured" || err.code === 404 || err.code === 405) {
        await localCommand(text, err.code);
      } else if (err.code === "bad_password") {
        addMsg("bot", `대화 비밀번호가 맞지 않아요. ⚙ 설정의 <b>대화 비밀번호</b>를 Cloudflare에 넣은 CHAT_PASSWORD와 같게 맞춰주세요.`, "warn");
      } else {
        addMsg("bot", `AI 응답을 받지 못했어요: ${esc(err.message)}`, "warn");
      }
    } finally {
      $("#chat-log .typing")?.remove();
      chat.busy = false; $("#chat-send").disabled = false;
      // 기록이 너무 길어지지 않게 (도구 호출 쌍이 깨지지 않도록 사용자 텍스트 메시지 경계에서 자름)
      if (chat.history.length > 40) {
        const i = chat.history.findIndex((m, k) => k > chat.history.length - 30 && m.role === "user" && m.content[0].type === "text");
        if (i > 0) chat.history = chat.history.slice(i);
      }
    }
  }

  // ---------- AI 연결 전 간단 모드 ----------
  async function localCommand(text, code) {
    const a = {}, q = text.replace(/\s+/g, " ");
    const num = (re) => { const m = q.match(re); return m ? +m[1] : undefined; };
    const ivMap = [["1분", "1m"], ["5분", "5m"], ["15분", "15m"], ["30분", "30m"], ["1시간", "1h"], ["60분", "1h"], ["시간봉", "1h"], ["일봉", "1d"], ["주봉", "1w"], ["월봉", "1M"]];
    for (const [k, v] of ivMap) if (q.includes(k)) { a.interval = v; break; }
    const stMap = [[/이동평균|이평|골든|크로스|ma/i, "ma_cross"], [/rsi/i, "rsi"], [/볼린저|박스/, "bollinger"], [/돌파|급등|거래량/, "breakout"]];
    for (const [re, v] of stMap) if (re.test(q)) { a.strategy = v; break; }
    a.stop_loss = num(/손절\s*(\d+(?:\.\d+)?)/); a.take_profit = num(/익절\s*(\d+(?:\.\d+)?)/); a.trailing = num(/트레일링\s*(\d+(?:\.\d+)?)/);
    const yrs = num(/(\d+)\s*년/), mons = num(/(\d+)\s*개월/);
    if (yrs || mons) { const d = new Date(); d.setMonth(d.getMonth() - (yrs ? yrs * 12 : mons)); a.start = d.toISOString().slice(0, 10); a.end = new Date().toISOString().slice(0, 10); }
    if (/당일|장\s*마감|단타/.test(q)) a.day_close = true;
    // 종목: 단어 중 검색되는 첫 번째
    for (const w of q.split(/[\s,.!?]+/).filter((x) => x.length >= 2 && !/봉|손절|익절|전략|해줘|돌려|테스트|백테스트|년|개월/.test(x))) {
      const hit = (await Data.search(w.replace(/(으로|로|을|를|이|가|은|는|에서|의)$/, ""), 1))[0];
      if (hit) { a.symbol_query = hit.symbol; break; }
    }
    Object.keys(a).forEach((k) => a[k] === undefined && delete a[k]);
    const why = code === "no_proxy" ? "중계 서버가 연결되지 않아서" : "AI가 아직 연결되지 않아서";
    if (!Object.keys(a).length) {
      addMsg("bot", `${why} 간단 모드로 동작 중이에요. 이런 식으로 말하면 알아들어요: <b>“삼성전자 5분봉 거래량 돌파 손절 2 실행”</b>, <b>“SK하이닉스 일봉 RSI 3년”</b>.<br/>자유롭게 대화하고 추천을 받으려면 README의 <b>대화 도우미 연결하기</b>를 따라 설정해주세요.`, "warn");
      return;
    }
    try {
      const done = await applySettings(a);
      let msg = `${why} 간단 모드로 처리했어요. 바꾼 설정: ${esc(done.join(", "))}`;
      if (/실행|돌려|테스트|해줘|보여/.test(q)) {
        const run = await runBT(true);
        const s = run.result.stats;
        msg += `<br/>결과: 수익 <b class="${cls(s.totalRet)}">${fmtPct(s.totalRet)}</b> (보유만 했을 때 ${fmtPct(s.buyHold)}), MDD ${fmtPct(s.mdd)}, 거래 ${s.trades}회, 승률 ${s.trades ? s.winRate.toFixed(1) + "%" : "—"}`;
      }
      addMsg("bot", msg);
    } catch (err) { addMsg("bot", esc(err.message), "warn"); }
  }

  function initChat() {
    const input = $("#chat-input");
    const send = () => { const v = input.value; input.value = ""; input.style.height = ""; sendChat(v); };
    $("#chat-send").addEventListener("click", send);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } });
    input.addEventListener("input", () => { input.style.height = ""; input.style.height = Math.min(input.scrollHeight, 140) + "px"; });
    $$("#chat-chips button").forEach((b) => b.addEventListener("click", () => sendChat(b.textContent)));
    $("#chat-clear").addEventListener("click", () => {
      chat.history = [];
      $("#chat-log").innerHTML = `<div class="chat-empty">대화를 지웠어요. 새로 물어보세요.</div>`;
    });
    const cfg = chatCfg();
    $("#chat-model").value = cfg.model; $("#chat-pass").value = cfg.pass || "";
    const saveCfg = () => store.set(CHAT_KEY, { model: $("#chat-model").value, pass: $("#chat-pass").value.trim() });
    $("#chat-model").addEventListener("change", saveCfg); $("#chat-pass").addEventListener("change", saveCfg);
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
    initChartTab(); initSettings(); initPF(); initBT(); initChat();
    const last = store.get(LAST_KEY, null);
    const first = (last && last.sym) || (Data.meta.symbols[0] && Data.meta.symbols[0].symbol);
    if (first) openSymbol(first, (last && last.iv) || "1d");
    const h = location.hash.slice(1);
    if (["portfolio", "backtest"].includes(h)) showTab(h);
  }
  init();
})();
