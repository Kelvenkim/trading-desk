/* =========================================================
 * Trading Desk — 화면 연결
 * ========================================================= */
(() => {
  const { $, $$, esc, krw, fmtPx, fmtWon, fmtPct, fmtVol, cls, store, toast, attachSearch, download } = U;
  const LAST_KEY = "tradingdesk.last", FAV_KEY = "tradingdesk.favs", PF_KEY = "tradingdesk.portfolio.v1";

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

    // 전체 화면: 차트 영역을 화면 가득 (아이폰 사파리도 되도록 CSS 방식)
    const center = $("#chart-wrap").closest(".center");
    const setFull = (on) => {
      center.classList.toggle("full", on); document.body.classList.toggle("no-scroll", on);
      $("#full-close").hidden = !on; $("#fit-btn").title = on ? "전체 화면 닫기" : "전체 화면 (Esc로 닫기)";
    };
    $("#fit-btn").addEventListener("click", () => setFull(!center.classList.contains("full")));
    $("#full-close").addEventListener("click", () => setFull(false));
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && center.classList.contains("full")) setFull(false); });
    $("#lines-btn").addEventListener("click", () => ChartView.setLines(!ChartView.linesOn));
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
        ? `저장된 시세 · ${Data.meta.updated} 기준`
        : Data.fromRank(sym) ? "순위 화면 자료 · 최근 6개월 일봉 (더 긴 기간·분봉은 ⚙ 설정에서 중계 서버 연결)" : "중계 서버로 받은 시세 (최대 몇 분 지연될 수 있어요)";
      $("#chart-foot").textContent = `${src} · ${bars.length.toLocaleString("ko-KR")}개 봉`;
      if (opts.fresh) toast("최신 시세로 바꿨어요.");
    } catch (e) {
      if (seq !== cur.seq) return;
      // 분봉이 안 되면(중계 서버 없음·연결 실패) 일봉으로 자동 전환 — 다음에 열 때도 일봉
      if (!Data.IV[cur.iv].daily && !opts.noFallback) {
        toast(e.needProxy ? "분봉은 중계 서버가 있어야 볼 수 있어요. 일봉으로 보여드려요." : "분봉 시세를 받지 못해서 일봉으로 보여드려요.", true);
        return openSymbol(sym, "1d", { ...opts, noFallback: true });
      }
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


  // ================= 탭 =================
  function showTab(name) {
    $$(".tab").forEach((x) => x.classList.toggle("active", x.dataset.tab === name));
    $$(".panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + name));
    if (location.hash !== "#" + name) history.replaceState(null, "", "#" + name);
    if (name === "portfolio") renderPF();
    if (name === "backtest") { try { BTUI.onShow(cur.sym); } catch (_) {} }
    if (name === "rank") { try { RankUI.onShow(); } catch (e) { console.error(e); } }
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
    // 한 화면에서 오류가 나도 다른 화면은 동작하도록 따로 시작
    const safe = (name, fn) => { try { fn(); } catch (e) { console.error(name, e); toast(`${name} 화면을 여는 중 문제가 생겼어요. 새로고침(Ctrl+Shift+R)을 해보세요.`, true); } };
    safe("차트", initChartTab); safe("설정", initSettings); safe("포트폴리오", initPF);
    safe("백테스트", () => BTUI.init({ current: () => cur.sym }));
    safe("순위", () => RankUI.init());
    window.App = { openChart: (sym) => { showTab("chart"); openSymbol(sym, "1d"); } };
    const last = store.get(LAST_KEY, null);
    const first = (last && last.sym) || (Data.meta.symbols[0] && Data.meta.symbols[0].symbol);
    if (first) openSymbol(first, (last && last.iv) || "1d");
    const h = location.hash.slice(1);
    if (["portfolio", "backtest", "rank"].includes(h)) showTab(h);
  }
  init();
})();
