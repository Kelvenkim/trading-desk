/* 내 투자 — 보유 종목 관리(브라우저에만 저장) + 모의 투자 기록(data/us/paper.json) */
const InvestUI = (() => {
  const { $, $$, esc, store, toast, attachSearch, download, LC_OPTS } = U;
  const KEY = "tradingdesk.holdings.us";
  const has = (v) => v != null && isFinite(v);
  const pct = (v, d = 1) => (has(v) ? (v > 0 ? "+" : "") + (v * 100).toFixed(d) + "%" : "—");
  const cls = (v) => (!has(v) ? "" : v > 0 ? "up" : v < 0 ? "down" : "");
  const usd = (v, d = 2) => (has(v) ? (v < 0 ? "-" : "") + "$" + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }) : "—");
  const won = (v) => (has(v) ? Math.round(v).toLocaleString("ko-KR") + "원" : "—");
  const get = async (p) => { const r = await fetch(p + "?t=" + Date.now()); if (!r.ok) throw new Error(p); return r.json(); };
  const load = () => store.get(KEY, { holdings: [], cash: 0 });
  const save = (x) => store.set(KEY, x);
  // 장기 손익비 (기댓값 = G×pG + L×pL) — 종목별 값은 브라우저에만 저장
  const EVKEY = "tradingdesk.ev.us";
  const evLoad = () => store.get(EVKEY, {});
  const evSave = (x) => store.set(EVKEY, x);
  // Claude 시나리오(11/19, 2029년 기준) — 아이온큐만 미리 채워 둠. 확률은 형이 정하는 값 — 보수적으로 30%에서 시작
  const EV_PRESET = { IONQ: { g: 120, l: 7.5, pg: 30, note: "Claude 2029 시나리오: 아주 강세 $120 · 약세 $5~10 (강세 $65, 기본 $20)" } };
  const daysTo = (d) => Math.round((new Date(d + "T12:00:00") - new Date()) / 864e5);

  let ctx = null, inited = false, acctSel = "basket", pchart = null, seq = 0;
  const prof = {}, anal = {};

  async function context() {
    if (ctx) return ctx;
    const [mk, rank, theme] = await Promise.all(["data/us/market.json", "data/us/rank.json", "data/us/theme.json"].map((p) => get(p).catch(() => null)));
    const fx = mk && (mk.assets || []).find((a) => a.t === "KRW=X");
    const themeOf = {};
    if (theme) theme.rows.forEach((r) => (r.stocks || []).forEach((s) => { (themeOf[s.code] = themeOf[s.code] || []).push(r.name); }));
    ctx = { fx: fx ? fx.last : null, rank, themeOf, regime: mk && mk.regime };
    return ctx;
  }
  async function profile(t) {
    if (t in prof) return prof[t];
    try { prof[t] = await get(`data/us/profile/${encodeURIComponent(t)}.json`); } catch (_) { prof[t] = null; }
    return prof[t];
  }

  // 종목 하나 분석: 일봉으로 추세·변동·이탈선
  async function analyze(t) {
    if (anal[t]) return anal[t];
    let b;
    try { b = await Data.getBars(t, "1d"); } catch (_) { try { b = await Data.getBars(t, "1d", { fresh: true }); } catch (e) { return (anal[t] = { err: e.message }); } }
    if (!b || b.length < 25) return (anal[t] = { err: "시세가 짧아요" });
    const c = b.map((x) => x.c), n = b.length, px = c[n - 1];
    const ma = (k) => (n >= k ? c.slice(-k).reduce((s, x) => s + x, 0) / k : null);
    let N = 0;
    for (let i = n - 20; i < n; i++) { const p = b[i - 1].c; N += Math.max(b[i].h - b[i].l, Math.abs(b[i].h - p), Math.abs(b[i].l - p)); }
    N /= 20;
    const lo20 = Math.min(...b.slice(-21, -1).map((x) => x.l)), hi20 = Math.max(...b.slice(-21, -1).map((x) => x.h));
    const y = b.slice(-252), hi52 = Math.max(...y.map((x) => x.h)), lo52 = Math.min(...y.map((x) => x.l));
    return (anal[t] = { px, prev: c[n - 2], day: b[n - 1].day, ma50: ma(50), ma200: ma(200), N, lo20, hi20, hi52, lo52, n, short: n < 200 });
  }

  async function onShow() {
    if (!inited) init();
    renderHold();
    renderPaper();
  }

  function init() {
    inited = true;
    const s = attachSearch($("#hd-sym").closest(".search"), () => $("#hd-qty").focus());
    $("#hd-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const t = $("#hd-sym").dataset.sym;
      if (!t) { toast("종목을 검색해서 목록에서 골라주세요.", true); return; }
      if (Data.isKR(t)) { toast("미국 주식만 넣을 수 있어요.", true); return; }
      const qty = +$("#hd-qty").value, avg = +$("#hd-avg").value;
      const x = load(), i = x.holdings.findIndex((h) => h.t === t);
      if (!qty) { if (i >= 0) x.holdings.splice(i, 1); }
      else if (i >= 0) x.holdings[i] = { t, qty, avg };
      else x.holdings.push({ t, qty, avg });
      save(x); e.target.reset(); delete $("#hd-sym").dataset.sym; renderHold(); toast("저장했어요.");
    });
    $("#hd-cash").addEventListener("change", () => { const x = load(); x.cash = +$("#hd-cash").value || 0; save(x); renderHold(); });
    $("#hd-export").addEventListener("click", () => download("my-holdings.json", JSON.stringify(load(), null, 2), "application/json"));
    $("#hd-import").addEventListener("change", async (e) => {
      const f = e.target.files[0]; if (!f) return;
      try { const j = JSON.parse(await f.text()); if (!Array.isArray(j.holdings)) throw 0; save(j); renderHold(); toast("가져왔어요."); }
      catch (_) { toast("파일 형식이 맞지 않아요. 내보내기로 만든 파일을 골라주세요.", true); }
      e.target.value = "";
    });
    $("#tab-portfolio").addEventListener("change", (e) => {
      const inp = e.target.closest(".ev-in input"); if (!inp) return;
      const box = inp.closest(".ev-in"), t = box.dataset.ev, st = evLoad();
      const v = {}; box.querySelectorAll("input").forEach((x) => (v[x.dataset.k] = +x.value));
      if (!(v.g > 0) || !(v.l >= 0) || !(v.pg >= 0 && v.pg <= 100)) { toast("가격은 0보다 크게, 확률은 0~100 사이로 넣어 주세요.", true); return; }
      st[t] = { ...v, note: "직접 넣은 값이에요." }; evSave(st); renderHold();
    });
    $("#tab-portfolio").addEventListener("click", (e) => {
      const rs = e.target.closest("[data-evreset]");
      if (rs) { e.preventDefault(); const st = evLoad(); delete st[rs.dataset.evreset]; evSave(st); renderHold(); return; }
      const ed = e.target.closest("[data-edit]");
      if (ed) { const h = load().holdings.find((x) => x.t === ed.dataset.edit); if (h) { s.set(h.t); $("#hd-qty").value = h.qty; $("#hd-avg").value = h.avg; $("#hd-qty").focus(); } return; }
      const del = e.target.closest("[data-del]");
      if (del) { const x = load(); x.holdings = x.holdings.filter((h) => h.t !== del.dataset.del); save(x); renderHold(); return; }
      const sy = e.target.closest("[data-sym]");
      if (sy) App.openChart(sy.dataset.sym);
      const ac = e.target.closest("[data-acct]");
      if (ac) { acctSel = ac.dataset.acct; renderPaper(); }
    });
  }

  // ================= 보유 종목 =================
  async function renderHold() {
    const my = ++seq, x = load(), C = await context();
    $("#hd-cash").value = x.cash || "";
    if (!x.holdings.length) {
      $("#hd-summary").innerHTML = "";
      $("#hd-list").innerHTML = `<p class="muted">아직 보유 종목이 없어요. 오른쪽에서 종목·수량·평균 단가(달러)를 넣으면 손절선·실적 일정·쏠림을 같이 봐 드려요.</p>`;
      $("#hd-warn").innerHTML = ""; return;
    }
    $("#hd-list").innerHTML = `<p class="muted">불러오는 중…</p>`;
    const rows = await Promise.all(x.holdings.map(async (h) => ({ ...h, a: await analyze(h.t), p: await profile(h.t) })));
    if (my !== seq) return;
    rows.forEach((r) => {
      r.px = r.a.px ?? (r.p && r.p.val.price); r.val = has(r.px) ? r.px * r.qty : r.avg * r.qty; r.cost = r.avg * r.qty;
      r.pl = r.cost ? r.val / r.cost - 1 : null; r.day = has(r.a.prev) ? r.a.px / r.a.prev - 1 : null;
      r.beta = r.p && has(r.p.val.beta) ? r.p.val.beta : null;
      r.themes = C.themeOf[r.t] || [];
      r.group = r.themes[0] || (r.p && (r.p.industry || r.p.sector)) || "기타";
      r.name = (r.p && (r.p.ko || r.p.name)) || Data.info(r.t).name || r.t;
    });
    const stock = rows.reduce((s, r) => s + r.val, 0), cost = rows.reduce((s, r) => s + r.cost, 0), cash = +x.cash || 0, total = stock + cash;
    const dayUsd = rows.reduce((s, r) => s + (has(r.day) ? r.val - r.val / (1 + r.day) : 0), 0);
    rows.forEach((r) => (r.w = total ? r.val / total : 0));
    rows.sort((a, b) => b.val - a.val);
    const fx = C.fx;
    $("#hd-summary").innerHTML = [
      ["평가액", usd(stock), fx ? won(stock * fx) : "", ""],
      ["손익", `<span class="${cls(stock - cost)}">${usd(stock - cost)}</span>`, `<span class="${cls(stock - cost)}">${pct(cost ? stock / cost - 1 : 0)}</span>`, ""],
      ["오늘", `<span class="${cls(dayUsd)}">${usd(dayUsd)}</span>`, rows[0] && rows[0].a.day ? `${rows[0].a.day} 종가` : "", ""],
      ["현금", usd(cash), total ? `비중 ${Math.round((cash / total) * 100)}%` : "", ""],
    ].map(([k, v, s]) => `<div class="hd-stat"><span class="k">${k}</span><b>${v}</b><span class="s">${s}</span></div>`).join("");
    $("#hd-warn").innerHTML = warnings(rows, total, cash, C);
    $("#hd-list").innerHTML = rows.map((r) => card(r, C)).join("");
  }

  function warnings(rows, total, cash, C) {
    const out = [];
    const top = rows[0];
    if (top && top.w > 0.4) out.push(["neg", `<b>${esc(top.name)}</b>가 계좌의 <b>${Math.round(top.w * 100)}%</b>예요. 한 종목이 40%를 넘으면 그 종목 하나에 계좌 전체가 흔들려요.`]);
    const g = {};
    rows.forEach((r) => (g[r.group] = (g[r.group] || 0) + r.w));
    const gt = Object.entries(g).sort((a, b) => b[1] - a[1]);
    if (gt.length && gt[0][1] > 0.6 && rows.length > 1) out.push(["neg", `<b>${esc(gt[0][0])}</b> 쪽이 ${Math.round(gt[0][1] * 100)}%예요. 같은 테마·업종은 같이 오르고 같이 빠져요.`]);
    const bw = rows.filter((r) => has(r.beta));
    if (bw.length) {
      const B = bw.reduce((s, r) => s + r.beta * r.w, 0) / Math.max(1e-9, bw.reduce((s, r) => s + r.w, 0)) * (1 - cash / total);
      out.push([B > 1.5 ? "neg" : "", `계좌 전체 베타 약 <b>${B.toFixed(1)}</b> — S&P500이 10% 빠지면 평균적으로 약 <b>${Math.round(B * 10)}%</b> 빠지는 구성이에요${B > 1.5 ? " (시장보다 훨씬 크게 출렁)" : ""}.`]);
    }
    const soon = rows.filter((r) => r.p && r.p.earn && r.p.earn.next && daysTo(r.p.earn.next) >= 0 && daysTo(r.p.earn.next) <= 14);
    soon.forEach((r) => out.push(["warn", `<b>${esc(r.name)}</b> 실적 발표 <b>${daysTo(r.p.earn.next) === 0 ? "오늘" : "D-" + daysTo(r.p.earn.next)}</b> (${r.p.earn.next}) — 발표 전후로 크게 움직일 수 있어요.`]));
    const broke = rows.filter((r) => has(r.a.lo20) && r.px < r.a.lo20);
    broke.forEach((r) => out.push(["neg", `<b>${esc(r.name)}</b>가 20일 최저가(${usd(r.a.lo20)})를 깼어요 — 추세 추종 기준으론 이탈 신호예요.`]));
    if (C.regime) out.push([C.regime.up ? "" : "neg", `시장: S&P500이 200일선 ${C.regime.up ? "위" : "아래"} (${pct(C.regime.sp_vs200)}).`]);
    return out.length ? `<ul class="hd-warn">${out.map(([c, t]) => `<li class="${c}">${t}</li>`).join("")}</ul>` : "";
  }

  function card(r, C) {
    const a = r.a, p = r.p, out = [];
    if (a.err) out.push(["", `시세를 못 받았어요 (${esc(a.err)})`]);
    else {
      if (has(a.ma200)) out.push([r.px > a.ma200 ? "pos" : "neg", `200일선 ${usd(a.ma200)} ${r.px > a.ma200 ? "위 — 장기 상승 추세" : "아래 — 장기 하락 추세"} (${pct(r.px / a.ma200 - 1)})`]);
      else if (has(a.ma50)) out.push([r.px > a.ma50 ? "pos" : "neg", `상장 ${a.n}일이라 200일선 없음 · 50일선 ${usd(a.ma50)} ${r.px > a.ma50 ? "위" : "아래"}`]);
      out.push(["", `52주 최고 ${usd(a.hi52)} 대비 ${pct(r.px / a.hi52 - 1, 0)} · 최저 ${usd(a.lo52)} 대비 ${pct(r.px / a.lo52 - 1, 0)}`]);
    }
    if (p && p.earn && p.earn.next) { const d = daysTo(p.earn.next); if (d >= -1) out.push([d <= 14 ? "warn" : "", `다음 실적 발표 ${p.earn.next} (${d <= 0 ? "오늘" : "D-" + d})`]); }
    if (p && p.analyst && has(p.analyst.mean) && has(r.px)) out.push(["", `월가 ${p.analyst.n || ""}명 평균 목표가 ${usd(p.analyst.mean)} (${pct(p.analyst.mean / r.px - 1, 0)})`]);
    const ch = p && (p.changes || [])[0];
    if (ch) out.push([ch.Action === "down" || ch.priceTargetAction === "Lowers" ? "neg" : ch.Action === "up" || ch.priceTargetAction === "Raises" ? "pos" : "",
      `최근 의견: ${esc(ch.GradeDate.slice(5))} ${esc(ch.Firm)} ${esc(ch.ToGrade)}${ch.currentPriceTarget ? ` · 목표가 ${usd(ch.currentPriceTarget, 0)}${ch.priorPriceTarget && ch.priorPriceTarget !== ch.currentPriceTarget ? ` ← ${usd(ch.priorPriceTarget, 0)}` : ""}` : ""}`]);
    const lines = a.err ? "" : `<div class="hd-lines">
        <div><span class="k">하루 평균 변동 (N)</span><b>${usd(a.N)}</b><span class="s">${pct(a.N / r.px)}</span></div>
        <div><span class="k">2N 아래</span><b>${usd(r.px - 2 * a.N)}</b><span class="s">${pct(-2 * a.N / r.px)} · 변동폭(N)의 2배</span></div>
        <div><span class="k">20일 최저 (추세 이탈선)</span><b class="${r.px < a.lo20 ? "down" : ""}">${usd(a.lo20)}</b><span class="s">${pct(a.lo20 / r.px - 1)}</span></div>
        <div><span class="k">20일 최고 (돌파선)</span><b>${usd(a.hi20)}</b><span class="s">${pct(a.hi20 / r.px - 1)}</span></div>
      </div>`;
    return `<div class="hd-card">
      <div class="hd-top">
        <button class="tt-sym" data-sym="${esc(r.t)}"><b>${esc(r.name)}</b><span class="muted">${esc(r.t)} · ${r.qty}주 · 평단 ${usd(r.avg)}${r.themes.length ? " · " + esc(r.themes.join(", ")) : ""}</span></button>
        <div class="hd-val"><b>${usd(r.val)}</b><span class="${cls(r.pl)}">${pct(r.pl)} (${usd(r.val - r.cost)})</span><span class="muted small">비중 ${Math.round(r.w * 100)}% · 오늘 <span class="${cls(r.day)}">${pct(r.day)}</span></span></div>
      </div>
      ${lines}
      <ul class="hd-notes">${out.map(([c, t]) => `<li class="${c}">${t}</li>`).join("")}</ul>
      ${evBox(r)}
      <div class="hd-btns"><button class="link-btn" data-edit="${esc(r.t)}">수정</button><button class="link-btn" data-del="${esc(r.t)}">삭제</button></div>
    </div>`;
  }

  // ---------- 장기 손익비 ----------
  function evDefault(r) {
    const pre = EV_PRESET[r.t]; if (pre) return { ...pre };
    const hi = r.p && r.p.analyst && r.p.analyst.high;
    return { g: has(hi) ? Math.round(hi * 100) / 100 : Math.round(r.px * 2 * 100) / 100, l: Math.round(r.px * 0.5 * 100) / 100, pg: 50, note: "기본값(월가 최고 목표가 · 반토막)이에요. 직접 바꿔 주세요." };
  }
  function evCalc(px, e) {
    const G = e.g / px - 1, L = e.l / px - 1, pG = e.pg / 100, pL = 1 - pG;
    const ev = G * pG + L * pL, ratio = L < 0 ? G / -L : null, be = (G - L) > 0 ? -L / (G - L) : null;
    const ideal = G >= 3 && L >= -0.5;        // 상방 4배(+300%) 이상 & 하방 반토막(−50%) 이내
    const grade = ev <= 0 ? ["neg", "기댓값 마이너스 — 이 가정이면 사면 손해예요"] : ideal ? ["pos", "이상적: 상방 4배↑ · 하방 반토막 이내"] :
      ratio >= 4 ? ["pos", "좋음: 이익이 손실의 4배 이상"] : ratio >= 2 ? ["", "보통: 이익이 손실의 2~4배"] : ["warn", "약함: 이익이 손실의 2배 미만"];
    return { G, L, pG, pL, ev, ratio, be, grade };
  }
  function evBox(r) {
    if (!has(r.px)) return "";
    const st = evLoad(), e = st[r.t] || evDefault(r), c = evCalc(r.px, e), ca = has(r.avg) && r.avg > 0 ? evCalc(r.avg, e) : null;
    const w = (v) => Math.min(100, Math.abs(v) * 100 / 5);   // 막대: +500%를 꽉 찬 길이로
    return `<details class="ev-box" ${st[r.t] ? "open" : ""}><summary><b>장기 손익비</b> <span class="muted small">기댓값 = G×pG + L×pL</span>
        <span class="ev-sum ${c.grade[0]}">${pct(c.ev, 0)} · ${c.ratio == null ? "—" : c.ratio.toFixed(1) + " : 1"}</span></summary>
      <div class="ev-in" data-ev="${esc(r.t)}">
        <label>잘 풀리면 가격 <span class="muted">G</span><input type="number" step="0.01" data-k="g" value="${e.g}"></label>
        <label>안 풀리면 가격 <span class="muted">L</span><input type="number" step="0.01" data-k="l" value="${e.l}"></label>
        <label>잘 풀릴 확률 <span class="muted">pG %</span><input type="number" step="1" min="0" max="100" data-k="pg" value="${e.pg}"></label>
        <button class="link-btn" data-evreset="${esc(r.t)}">기본값</button>
      </div>
      <div class="ev-bars"><div class="ev-bar"><span class="k">상방 G</span><i class="up-bg" style="width:${w(c.G)}%"></i><b class="up">${pct(c.G, 0)}</b><span class="s">${(1 + c.G).toFixed(1)}배</span></div>
        <div class="ev-bar"><span class="k">하방 L</span><i class="down-bg" style="width:${w(c.L)}%"></i><b class="down">${pct(c.L, 0)}</b><span class="s">${(1 + c.L).toFixed(2)}배</span></div></div>
      <ul class="hd-notes">
        <li class="${c.grade[0]}"><b>지금 가격 ${usd(r.px)}에서 사면:</b> 기댓값 <b class="${cls(c.ev)}">${pct(c.ev, 0)}</b> = (${pct(c.G, 0)} × ${Math.round(c.pG * 100)}%) + (${pct(c.L, 0)} × ${Math.round(c.pL * 100)}%) · 손익비 <b>${c.ratio == null ? "—" : c.ratio.toFixed(1) + " : 1"}</b> · ${c.grade[1]}</li>
        <li>본전이 되는 확률: 잘 풀릴 확률이 <b>${c.be == null ? "—" : Math.round(c.be * 100) + "%"}</b>만 넘으면 기댓값이 플러스예요.</li>
        ${ca ? `<li class="muted">내 평단 ${usd(r.avg)} 기준이면: 기댓값 ${pct(ca.ev, 0)} · 상방 ${pct(ca.G, 0)} · 하방 ${pct(ca.L, 0)}</li>` : ""}
        <li class="muted small">${esc(e.note || "직접 넣은 값이에요.")} 이상적인 기준: 상방 4~5배(+300~400%), 하방 반토막(−50%).</li>
      </ul></details>`;
  }

  // ================= 모의 투자 =================
  let P = null;
  const ACCT = { basket: ["추천 바구니", "오늘의 순위 바구니 20종목, 5거래일마다 교체"], spy: ["S&P500 보유", "비교 기준"] };
  async function renderPaper() {
    if (!P) { try { P = await get("data/us/paper.json"); } catch (_) { $("#pp-cards").innerHTML = `<p class="muted">아직 모의 투자 기록이 없어요.</p>`; return; } }
    const days = P.acct.spy.eq.length;
    $("#pp-sub").textContent = `${P.start} 시작 · ${P.date} 종가까지 · ${days}거래일 · 각 $${P.cash0.toLocaleString()} · ${P.cost}`;
    $("#pp-cards").innerHTML = Object.entries(ACCT).map(([k, [nm, ds]]) => {
      const a = P.acct[k], e = a.eq[a.eq.length - 1][1], r = e / P.cash0 - 1;
      return `<button class="pp-card ${k === acctSel ? "on" : ""}" data-acct="${k}"><span class="k">${nm}</span><b>${usd(e, 0)}</b><span class="${cls(r)}">${pct(r, 2)}</span><span class="s">${ds}</span></button>`;
    }).join("");
    const a = P.acct[acctSel];
    const st = a.stats;
    $("#pp-stats").innerHTML = acctSel === "spy" ? "" : `끝난 거래 ${st.n}건${st.n ? ` · 이긴 비율 ${Math.round(st.win * 100)}% · 평균 이익 ${pct(st.avg_win)} · 평균 손실 ${pct(st.avg_loss)}` : ""} · 보유 ${a.pos.length}종목 · 현금 ${usd(a.cash, 0)}`;
    $("#pp-pos").innerHTML = a.pos.map((x) => `<tr><td><button class="tt-sym" data-sym="${esc(x.t)}"><b>${esc(x.name || x.t)}</b><span class="muted">${esc(x.t)} · ${esc(x.since.slice(5))}부터${x.units ? ` · ${x.units}유닛` : ""}</span></button></td>
      <td class="num">${usd(x.avg)}</td><td class="num">${usd(x.px)}</td><td class="num ${cls(x.pl)}">${pct(x.pl)}</td><td class="num">${usd(x.val, 0)}</td><td class="num">${x.stop ? usd(x.stop) : "—"}</td></tr>`).join("")
      || `<tr class="empty-row"><td colspan="6">${days <= 1 ? "첫 주문이 다음 거래일 시가에 체결돼요." : "보유 종목이 없어요."}</td></tr>`;
    $("#pp-orders").innerHTML = a.orders.length ? `<div class="co-sub">내일 주문 ${a.orders.length}건</div><div class="pp-chips">${a.orders.map((o) =>
      `<span>${o.side === "sell" ? "매도" : "매수"} <b>${esc(o.t)}</b>${o.trigger ? ` ${usd(o.trigger)} 넘으면` : o.usd ? ` ${usd(o.usd, 0)}` : ""}</span>`).join("")}</div>` : "";
    const lg = a.log.slice(0, 60);
    const K = { buy: ["매수", "up"], sell: ["매도", "down"], kill: ["걸러냄", "muted"], skip: ["건너뜀", "muted"], note: ["", "muted"] };
    $("#pp-log").innerHTML = lg.map((l) => `<li><span class="muted">${esc(l.d.slice(5))}</span> <span class="${K[l.k][1]}">${K[l.k][0]}</span> ${l.t ? `<b>${esc(l.t)}</b>` : ""} ${l.px ? usd(l.px) : ""} ${has(l.pl) ? `<span class="${cls(l.pl)}">${pct(l.pl)}</span>` : ""} <span class="muted">${esc(l.why || "")}</span></li>`).join("")
      || `<li class="muted">기록이 없어요.</li>`;
    drawPaper();
  }

  function drawPaper() {
    const el = $("#pp-chart"); if (!el || typeof LightweightCharts === "undefined") return;
    if (pchart) { pchart.remove(); pchart = null; }
    if (P.acct.spy.eq.length < 2) { el.innerHTML = `<p class="muted small pp-wait">곡선은 이틀째부터 그려져요.</p>`; return; }
    el.innerHTML = "";
    const LC = LightweightCharts;
    pchart = LC.createChart(el, { ...LC_OPTS(), layout: { ...LC_OPTS().layout, attributionLogo: false }, handleScroll: false, handleScale: false, rightPriceScale: { borderVisible: false }, timeScale: { borderVisible: false } });
    [["spy", "#9a9aa2"], ["basket", "#ffffff"]].forEach(([k, c]) => {
      const s = pchart.addSeries(LC.LineSeries, { color: c, lineWidth: k === acctSel ? 3 : 2, priceLineVisible: false, lastValueVisible: true });
      s.setData(P.acct[k].eq.map(([d, v]) => ({ time: d, value: v })));
    });
    pchart.timeScale().fitContent();
  }

  return { onShow };
})();
