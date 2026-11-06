/* 뉴스 탭 — data/news/latest.json */
const NewsUI = (() => {
  const { $, esc } = U;
  let J = null, loaded = false, who = "trump";
  const f = { kind: "all", theme: "", q: "" };
  const ago = (at) => { if (!at) return ""; const m = (Date.now() - Date.parse(at.replace(" ", "T") + ":00+09:00")) / 60000; return m < 60 ? `${Math.max(1, Math.round(m))}분 전` : m < 1440 ? `${Math.round(m / 60)}시간 전` : at.slice(5, 10).replace("-", "/"); };

  async function load() {
    try { J = await (await fetch("data/news/latest.json?t=" + Date.now())).json(); }
    catch (_) { $("#nw-list").innerHTML = `<p class="muted">아직 뉴스 자료가 없어요.</p>`; return; }
    loaded = true;
    $("#nw-made").textContent = `${J.made} 갱신 · 30분마다`;
    $("#nw-theme").innerHTML = `<option value="">모든 테마</option>` + Object.entries(J.themes || {}).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
    renderList(); renderPeople();
  }

  function renderList() {
    const q = f.q.trim();
    const L = J.news.filter((n) => (f.kind === "all" || (f.kind === "pol" && n.pol) || (f.kind === "up" && n.s > 0) || (f.kind === "down" && n.s < 0) || (f.kind === "who" && n.who.length)) &&
      (!f.theme || n.themes.includes(f.theme)) && (!q || n.t.includes(q) || (n.b || "").includes(q)));
    $("#nw-count").textContent = `${L.length}건`;
    $("#nw-list").innerHTML = L.map((n) => `<div class="nw">
      <div class="nw-meta"><span>${ago(n.at)}</span><span>${esc(n.o || "")}</span>${n.pol ? `<span class="tag pol">정책</span>` : ""}${n.s > 0 ? `<span class="up">▲ 호재 단어</span>` : n.s < 0 ? `<span class="down">▼ 악재 단어</span>` : ""}</div>
      <a class="nw-t" href="${esc(n.u)}" target="_blank" rel="noopener">${esc(n.t)}</a>
      ${n.b ? `<div class="nw-b">${esc(n.b)}…</div>` : ""}
      <div class="nw-tags">${n.themes.map((k) => `<button class="rk-theme" data-theme="${k}">${esc(J.themes[k] || k)}</button>`).join("")}
        ${n.stocks.map(([nm, cd]) => `<button class="nw-stock" data-code="${cd}">${esc(nm)}</button>`).join("")}
        ${n.who.map((k) => `<span class="nw-who">${esc((J.people.find((p) => p.key === k) || {}).name || k)}</span>`).join("")}</div>
    </div>`).join("") || `<p class="muted">조건에 맞는 뉴스가 없어요.</p>`;
  }

  let span = 30;
  function words(list, showChg) {
    if (!list || !list.length) return `<p class="small muted">이 기간에 시장 관련 단어가 거의 없었어요.</p>`;
    const mx = Math.max(...list.map((w) => w.n), 1);
    return `<div class="wl">${list.map((w) => {
      const chg = !showChg ? "" : w.prev === 0 ? `<span class="new">새로</span>` : `<span class="${w.n > w.prev ? "up" : w.n < w.prev ? "down" : "muted"}">${w.n > w.prev ? "▲" : w.n < w.prev ? "▼" : "–"} ${w.prev}→${w.n}</span>`;
      const ex = (w.ex || []).map((e) => `<li><a href="${esc(e.u)}" target="_blank" rel="noopener">${esc(e.t)}</a> <span class="sub">${ago(e.at)}</span></li>`).join("");
      return `<details class="w-item"><summary class="w"><span class="w-name">${esc(w.w)}</span>
        <span class="w-bar"><i style="width:${w.n / mx * 100}%"></i></span><span class="w-n">${w.n}</span><span class="w-chg">${chg}</span>
        <span class="w-th">${(w.themes || []).map((k) => `<button class="rk-theme" data-theme="${k}">${esc(J.themes[k] || k)}</button>`).join("")}</span></summary>
        ${ex ? `<ul class="news w-ex">${ex}</ul>` : ""}</details>`;
    }).join("")}</div>`;
  }

  function renderPeople() {
    $("#nw-people").innerHTML = J.people.map((p) => `<button class="${p.key === who ? "on" : ""}" data-who="${p.key}">${esc(p.name)}</button>`).join("");
    const p = J.people.find((x) => x.key === who) || J.people[0];
    const wk = (d) => d && (Date.now() - Date.parse(d)) / 864e5 >= 14;
    const own = p.own_market ? `
      <div class="nw-sub"><h3>본인이 직접 쓴 글 <span class="muted small">Truth Social</span></h3>
        <div class="seg small" id="nw-span"><button data-span="7" class="${span === 7 ? "on" : ""}">7일</button><button data-span="30" class="${span === 30 ? "on" : ""}">30일</button></div></div>
      <p class="small muted">${span === 7 ? `최근 7일 글 ${p.n_posts}개 중 선거 지지·여론조사 같은 정치 글 ${p.n_skip}개는 빼고 셌어요.` : `최근 30일 글 ${p.n_posts30}개 (정치 글 제외하고 셈)`} 단어를 누르면 실제 글이 나와요.</p>
      ${words(span === 7 ? p.own_market : p.own_market30, span === 7)}
      ${p.wh_market && p.wh_market.length ? `<h4 class="muted small">백악관 발표에 나온 시장 단어</h4>${words(p.wh_market, false)}` : ""}` : "";
    $("#nw-person").innerHTML = `<div class="nw-role muted small">${esc(p.role)}</div>${own}
      <h3>국내 기사에서 함께 나온 시장 단어 <span class="muted small">최근 7일 기사 ${p.n_heads}건</span></h3>
      ${words(p.ko_market, wk(p.since))}
      <p class="hint">AI·반도체·관세·금리·에너지처럼 주식시장에 영향을 주는 단어 사전(약 45개 묶음)에 있는 것만 세요. 한 글·기사에서 같은 단어는 한 번만 셌어요. 많이 나온다고 오른다는 뜻은 아니에요 — 지금 무엇이 이야기되는지 보는 용도예요.</p>`;
  }

  function init() {
    $("#tab-news").addEventListener("click", (e) => {
      const k = e.target.closest("[data-kind]"); if (k) { f.kind = k.dataset.kind; document.querySelectorAll("#nw-kinds button").forEach((b) => b.classList.toggle("on", b === k)); renderList(); return; }
      const w = e.target.closest("[data-who]"); if (w) { who = w.dataset.who; renderPeople(); return; }
      const sp = e.target.closest("[data-span]"); if (sp) { span = +sp.dataset.span; renderPeople(); return; }
      const th = e.target.closest("[data-theme]"); if (th) { e.preventDefault(); window.App && App.showTheme(th.dataset.theme); return; }
      const st = e.target.closest("[data-code]");
      if (st) { const code = st.dataset.code; Data.loadSymbols().then((l) => { const h = l.find((x) => x.symbol.startsWith(code + ".")); window.App && App.openChart(h ? h.symbol : code + ".KS"); }); }
    });
    $("#nw-theme").addEventListener("change", (e) => { f.theme = e.target.value; renderList(); });
    $("#nw-q").addEventListener("input", (e) => { f.q = e.target.value; renderList(); });
  }
  return { init, onShow: () => { if (!loaded) load(); } };
})();
