/* =========================================================
 * 공통 도구 (모든 화면에서 사용)
 * ========================================================= */
const U = (() => {
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
  function download(name, text, type) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  const LC_OPTS = () => ({
    autoSize: true,
    layout: { background: { color: "transparent" }, textColor: "#8d98b3", fontSize: 11, fontFamily: "Pretendard Variable, Pretendard, system-ui, sans-serif" },
    grid: { vertLines: { color: "rgba(141,152,179,.07)" }, horzLines: { color: "rgba(141,152,179,.07)" } },
    rightPriceScale: { borderColor: "#253049" },
    timeScale: { borderColor: "#253049", timeVisible: true, secondsVisible: false },
    crosshair: { mode: 0 }, localization: { locale: "ko-KR" },
  });
  return { $, $$, esc, krw, fmtPx, fmtWon, fmtPct, fmtVol, cls, store, toast, attachSearch, download, LC_OPTS };
})();
