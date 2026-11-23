/* 장기 투자 리서치 — data/us/longterm/*.json (매크로 → 산업 → 공급망 → 상장사 → 회사 검증 → 시나리오 → 분류) */
const LongUI = (() => {
  const { $, esc } = U;
  const has = (v) => v != null && isFinite(v);
  const pct = (v, d = 0) => (has(v) ? (v > 0 ? "+" : "") + (v * 100).toFixed(d) + "%" : "—");
  const big = (v, cur = "USD") => { if (!has(v)) return "—"; const s = ({ JPY: "¥", GBp: "£", EUR: "€", KRW: "₩", GBP: "£" })[cur] || "$";
    const x = cur === "GBp" ? v / 100 : v; return x >= 1e12 ? s + (x / 1e12).toFixed(2) + "조" : x >= 1e10 ? s + Math.round(x / 1e8).toLocaleString() + "억" : x >= 1e8 ? s + (x / 1e8).toFixed(1) + "억" : x >= 1e4 ? s + Math.round(x / 1e4).toLocaleString() + "만" : s + Math.round(x).toLocaleString(); };
  const KIND = { "사실": "lt-f", "추정": "lt-e", "모름": "lt-u" };
  const tag = (k) => `<span class="lt-k ${KIND[k] || ""}">${esc(k)}</span>`;
  const item = ([t, k, src]) => `<li>${tag(k)} ${esc(t)}${src ? ` <a href="${esc(src)}" target="_blank" rel="noopener" class="lt-src">출처</a>` : ""}</li>`;
  const NECK = { "매우 강함": "n5", "강함": "n4", "보통": "n3", "약함": "n2", "단순 테마": "n1", "모름": "n0" };
  let I = null, R = null, cur = null, inited = false, TH = new Map();

  const FORMULAS = [
    ["장기 손익비 (기댓값)", "G×pG + L×pL", "잘 풀리면 G, 안 풀리면 L, 확률 pG. 이상적인 자리 = 상방 4~5배 · 하방 반토막(−50%) 이내", "형 공식 (11/19)"],
    ["200일선 필터", "주가 > 200일 평균", "S&P500 2000~2026: 200일선 위에서만 보유 → 최대 낙폭 −57% → −26% (수익은 +440% → +226%로 줄어듦)", "검증"],
    ["이미 많이 오른 자리 피하기", "50일선 +8%↑ & RSI 65↑", "주식 5만 건(2015~2026): 이 자리에서 산 경우 평균 +0.07R로 최하위, 앞·뒤 기간 모두", "검증"],
    ["덜 오른 자리", "50일선 0~5% 위 · RSI≤65 · MACD↑", "같은 5만 건: +0.19R vs 나머지 +0.14R, 앞·뒤 기간 모두 같은 방향", "검증"],
    ["12-1 모멘텀", "1년 전→1달 전 수익", "2016~2026: 상위 종목 20일 뒤 평균 +1.65% (살아남은 종목 기준이라 실제보다 좋을 수 있음)", "검증(참고)"],
    ["분할 매수", "이벤트 뒤 · 50일선 회복 · 실적 확인", "한 번에 사지 않고 조건마다 나눠 사기 — 바닥을 맞히지 못해도 후회를 줄이는 규칙", "규칙(미검증)"],
  ];

  async function onShow() {
    if (!inited) {
      inited = true;
      document.querySelectorAll(".lt-tab").forEach((b) => b.addEventListener("click", () => pane(b.dataset.lt)));
      $("#lt-root").addEventListener("click", (e) => {
        const c = e.target.closest("[data-co]"); if (c) { openCo(c.dataset.co); return; }
        const sy = e.target.closest("#lt-body [data-sym]"); if (sy) { App.openChart(sy.dataset.sym); return; }
        const ind = e.target.closest("[data-ind]"); if (ind) { load(ind.dataset.ind); ind.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" }); return; }
        const mo = e.target.closest("[data-more]"); if (mo) { const el = $("#lt-sum"); el.classList.toggle("clamp"); mo.textContent = el.classList.contains("clamp") ? "더 보기" : "접기"; return; }
      });
      $("#lt-dialog").addEventListener("click", (e) => {
        const g = e.target.closest(".gl-t");
        if (g) return;                                   // 용어 풀이는 사이트 공통 말풍선(gloss.js)이 띄움
        if (e.target.closest("[data-close]") || e.target.id === "lt-dialog") $("#lt-dialog").close(); const s = e.target.closest("[data-sym]"); if (s) { $("#lt-dialog").close(); App.openChart(s.dataset.sym); } });
      $("#lt-dialog").addEventListener("input", (e) => { if (e.target.id === "lt-pg") evDraw(); });
    }
    try { I = await (await fetch("data/us/longterm/index.json?t=" + Date.now())).json(); } catch (_) { $("#lt-body").innerHTML = `<p class="muted">아직 리서치가 없어요.</p>`; return; }
    let themes = [];
    try { themes = (await (await fetch("data/us/theme.json?t=" + Date.now())).json()).rows; } catch (_) {}
    TH = new Map(themes.map((r) => [r.key, r]));         // 11/23 형: 리서치와 테마 점수를 한 화면으로 — 테마 점수 순으로 정렬, 고르면 전체 종목까지
    const done = new Map(I.industries.map((x) => [x.key, x]));
    const sc = (k) => (TH.get(k) || {}).score ?? -1;
    const all = [...I.industries, ...themes.filter((t) => !done.has(t.key))].sort((a, b) => sc(b.key) - sc(a.key));
    $("#lt-progress").textContent = `장기 테마 ${themes.length || all.length}개 중 ${I.industries.length}개 완료`;
    const VC = { "우호": "v-good", "중립": "v-mid", "비우호": "v-bad" };
    $("#lt-inds").innerHTML = all.map((x) => done.has(x.key)
      ? `<button class="lt-ind" data-ind="${esc(x.key)}"><i class="lt-vd ${VC[x.verdict] || ""}"></i>${esc(x.name)}${TH.get(x.key) ? ` <span class="lt-sc">${Math.round(TH.get(x.key).score)}</span>` : ""}</button>`
      : `<button class="lt-ind todo" disabled>${esc(x.name)} · 예정</button>`).join("");
    $("#lt-formulas").innerHTML = FORMULAS.map(([n, f, w, s]) => `<li><b>${esc(n)}</b> <code>${esc(f)}</code> <span class="lt-k ${s.startsWith("검증") ? "lt-f" : "lt-e"}">${esc(s)}</span><span class="muted small">${esc(w)}</span></li>`).join("");
    if (!R && I.industries[0]) load(([...I.industries].sort((x, y) => sc(y.key) - sc(x.key))[0]).key);   // 처음엔 테마 점수 1위
  }

  async function load(key) {
    try { R = await (await fetch(`data/us/longterm/${key}.json?t=` + Date.now())).json(); } catch (_) { return; }
    document.querySelectorAll(".lt-ind").forEach((b) => b.classList.toggle("on", b.dataset.ind === key));
    const M = R.macro, N = R.narrative;
    const pdf = `reports/longterm/${key}/industry.pdf`;
    const VC = { "우호": "v-good", "중립": "v-mid", "비우호": "v-bad" };
    const clsTone = (x) => /핵심/.test(x) ? "c-core" : /투기|부적합/.test(x) ? "c-spec" : /병목/.test(x) ? "c-neck" : "c-watch";
    const card = (c) => { const m = c.m || {}; const dd = has(m.px) && has(m.hi52) ? m.px / m.hi52 - 1 : null;
      return `<button class="lt-card" data-co="${esc(c.t)}"><div class="lt-card-top"><b>${esc(c.name)}</b><span class="muted small">${esc(c.t)}</span></div>
        <span class="lt-cls ${clsTone(c.cls)}">${esc(c.cls.split(" — ")[0])}</span>
        <p class="lt-edge">${esc((c.about && c.about.edge) || c.layer)}</p>
        <div class="lt-card-num"><span>시총 <b>${big(m.mcap, m.cur)}</b></span><span>고점 대비 <b class="${dd != null && dd < 0 ? "down" : ""}">${pct(dd)}</b></span></div></button>`; };
    const sec = (title, sub, body) => `<details class="lt-acc"><summary><b>${title}</b><span class="muted small">${sub}</span></summary><div class="lt-acc-b">${body}</div></details>`;
    const order = ["핵심", "관찰", "병목", "투기", "부적합"];
    const cos = [...R.companies].sort((x, y) => order.findIndex((o) => x.cls.includes(o)) - order.findIndex((o) => y.cls.includes(o)));
    const T_ = TH.get(key), pp = (v) => v == null ? "—" : `<b class="${v >= 0 ? "up" : "down"}">${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%p</b>`;
    const resSet = new Set(R.companies.map((c) => c.t));
    const thLine = T_ ? `<div class="lt-thline"><span>테마 점수 <b>${Math.round(T_.score)}</b>/100 · ${T_.rank}위 · <b>${esc(T_.status || "")}</b></span><span>S&P500 대비 3개월 ${pp(T_.r3)} · 6개월 ${pp(T_.r6)}</span></div>` : "";
    const allTbl = T_ && T_.stocks ? `<h4 class="lt-h">테마 전체 종목 ${T_.stocks.length}개 <span class="muted small">3개월 수익률 순 · <span class="lt-rs">리서치</span> = 위 카드에 분석 있음</span></h4>
      <div class="tbl-wrap"><table class="tt-tbl lt-all"><thead><tr><th>종목</th><th class="num">3개월</th><th class="num hide-sm">월가 목표 여력</th><th></th></tr></thead><tbody>${[...T_.stocks].sort((a, b) => (b.r3 ?? -9) - (a.r3 ?? -9)).map((s) => `<tr>
        <td><b>${esc(s.ko || s.name || s.code)}</b> <span class="muted small">${esc(s.code)}</span>${resSet.has(s.code) ? ` <span class="lt-rs">리서치</span>` : ""}</td>
        <td class="num ${s.r3 >= 0 ? "up" : "down"}">${pct(s.r3)}</td><td class="num hide-sm">${s.up != null ? pct(s.up) : "—"}</td>
        <td class="num"><button class="btn small" data-sym="${esc(s.code)}">차트</button></td></tr>`).join("")}</tbody></table></div>` : "";
    $("#lt-body").innerHTML = `
      <div class="lt-hero">
        <div class="lt-hero-top"><h3>${esc(R.name)}</h3><span class="lt-verdict ${VC[M.verdict] || ""}">매크로 ${esc(M.verdict)}</span></div>
        <p class="lt-sum clamp" id="lt-sum">${esc(R.summary)}</p>
        <div class="lt-hero-foot"><button class="lt-more" data-more>더 보기</button><span class="muted small">${esc(R.asof)} 리서치 · 숫자 ${esc((R.metrics_at || "").slice(5, 10).replace("-", "/"))}</span><a class="lt-pdf sm" href="${pdf}" target="_blank" rel="noopener">산업 PDF</a></div>
      </div>
      ${thLine}
      <h4 class="lt-h">리서치한 회사 ${R.companies.length}곳 <span class="muted small">눌러서 소개·검증·시나리오 보기</span></h4>
      <div class="lt-cards">${cos.map(card).join("")}</div>
      ${allTbl}
      <h4 class="lt-h">자세히 보기 <span class="muted small">7단계 리서치 원문</span></h4>
      ${sec("매크로 환경", esc(M.verdict_why), `
        <div class="lt-2"><div><h5>우호 요인</h5><ul class="lt-ul">${M.good.map(item).join("")}</ul></div><div><h5>비우호 요인</h5><ul class="lt-ul">${M.bad.map(item).join("")}</ul></div>
        <div><h5>유동성</h5><ul class="lt-ul">${M.liquidity.map(item).join("")}</ul></div><div><h5>지정학</h5><ul class="lt-ul">${M.geo.map(item).join("")}</ul></div></div>`)}
      ${sec("산업 이야기", esc(N.mega), `
        <div class="tbl-wrap"><table class="tt-tbl"><thead><tr><th>축</th><th>뒷받침</th><th>근거</th></tr></thead><tbody>${N.axes.map(([a, s2, t, src]) => `<tr><td><b>${esc(a)}</b></td><td>${esc(s2)}</td><td>${esc(t)} ${src ? `<a class="lt-src" href="${esc(src)}" target="_blank" rel="noopener">출처</a>` : ""}</td></tr>`).join("")}</tbody></table></div>
        <div class="lt-priced"><span>시장 선반영</span>${[0, 50, 75].map((p) => `<b class="${N.priced === p ? "on" : ""}">${p}%</b>`).join("")}<span class="muted small">${tag(N.priced_why[1])} ${esc(N.priced_why[0])}</span></div>
        <div class="lt-2"><div><h5>강화 시나리오</h5><ul class="lt-ul">${N.up.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div><div><h5>약화 시나리오</h5><ul class="lt-ul">${N.down.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div></div>`)}
      ${sec("공급망 병목", R.chain.filter((c) => /매우 강함/.test(c.neck)).map((c) => esc(c.layer)).join(" · ") || "병목 강도별 층", `
        <div class="lt-chain">${R.chain.map((c) => `<div class="lt-chain-i"><div><b>${esc(c.layer)}</b> <span class="lt-neck ${NECK[c.neck] || ""}">${esc(c.neck)}</span></div>
          <span class="muted small">${esc(c.desc)} · 발생 ${esc(c.when)} · 유지 ${esc(c.dur)}</span><p class="small">${tag(c.why[1])} ${esc(c.why[0])}${c.note ? ` <span class="muted">※ ${esc(c.note)}</span>` : ""}</p></div>`).join("")}</div>`)}
      ${sec("상장사 비교표", "시총·거래대금·등급·공식", `
        <div class="tbl-wrap"><table class="tt-tbl lt-cos"><thead><tr><th>회사</th><th class="num">시가총액</th><th class="num">20일 거래대금</th><th class="num">매출 대비</th><th>등급</th><th>공식</th><th>최근 성장</th></tr></thead><tbody>
        ${R.companies.map((c) => { const m = c.m || {}; const F = m.formulas || [];
          return `<tr data-co="${esc(c.t)}" class="lt-row"><td><b>${esc(c.name)}</b><span class="s">${esc(c.t)}</span></td>
          <td class="num">${big(m.mcap, m.cur)}</td><td class="num">${big(m.adv, m.cur)}</td><td class="num">${has(m.ps) ? m.ps.toFixed(0) + "배" : "—"}</td>
          <td><span class="lt-grade g${esc(c.v.grade)}">${esc(c.v.grade)}</span></td><td>${F.map((f) => `<span class="lt-dot ${f.ok ? "ok" : "no"}" title="${esc(f.t)}"></span>`).join("")}</td>
          <td class="small lt-grow">${tag(c.growth[1])} ${esc(c.growth[0])}</td></tr>`; }).join("")}</tbody></table></div>
        <p class="muted small">공식 점: 초록 = 조건 충족 / 빨강 = 미충족 (200일선 · 많이 오른 자리 아님 · 덜 오른 자리 · 12-1 모멘텀). 등급 A 공식 고객·반복 매출 / B 대형 고객 확인 / C 구조상 가능 / D 협약·시험 / E 소문</p>`)}
      ${sec("최종 분류", "지금 조건에서의 위치", R.final.map(([n, ts, w]) => `<div class="lt-final"><b>${esc(n)}</b><span>${ts.map((t) => `<button class="lt-chip" data-co="${esc(t)}">${esc((R.companies.find((c) => c.t === t) || {}).name || t)}</button>`).join("")}</span><span class="muted small">${esc(w)}</span></div>`).join(""))}
      ${sec("제외한 곳 · 출처", `제외 ${R.excluded.length} · 출처 ${R.sources.length}`, `<ul class="lt-ul">${R.excluded.map(([n, w, k, s2]) => `<li>${tag(k)} <b>${esc(n)}</b> — ${esc(w)}</li>`).join("")}</ul>
        <ul class="lt-ul small lt-srcs">${R.sources.map((x) => `<li><a href="${esc(x)}" target="_blank" rel="noopener">${esc(x.replace(/^https?:\/\/(www\.)?/, "").slice(0, 70))}</a></li>`).join("")}</ul>`)}`;
  }

  function gl(txt) {                                // 어려운 말에 밑줄 → 누르면 풀이
    const G = (R && R.gloss) || {}; let h = esc(txt);
    const keys = Object.keys(G).sort((a, b) => b.length - a.length).filter((k) => txt.includes(k));
    const used = [];
    for (const k of keys) {
      if (used.some((u) => u.includes(k))) continue;
      const ek = esc(k), i = h.indexOf(ek);
      if (i < 0 || h.slice(0, i).lastIndexOf("<") > h.slice(0, i).lastIndexOf(">")) continue;
      h = h.slice(0, i) + `<button class="gl-t" data-gl="${ek}">${ek}</button>` + h.slice(i + ek.length); used.push(k);
    }
    return h;
  }
  function openCo(t) {
    const c = R && R.companies.find((x) => x.t === t); if (!c) return;
    cur = c; const v = c.v, sc = c.sc, m = c.m || {};
    const row = (n, q, x) => `<tr><td><b>${n}</b><span class="s">${q}</span></td><td>${tag(x[1])} ${esc(x[0])}</td></tr>`;
    $("#lt-dlg-body").innerHTML = `
      <div class="lt-dhead"><div><h3>${esc(c.name)} <span class="muted">${esc(c.t)} · ${esc(c.exch)}</span></h3><span class="muted small">${esc(c.layer)} · ${esc(R.name)} 리서치 ${esc(R.asof)}</span></div>
        <div class="lt-dbtn"><a class="lt-pdf" href="reports/longterm/${esc(R.key)}/${esc(c.t)}.pdf" target="_blank" rel="noopener">분석표 PDF</a><button class="lt-pdf" data-sym="${esc(c.t)}">차트</button><button class="icon-btn" data-close>✕</button></div></div>
      ${c.about ? `<div class="lt-about">
        <div class="lt-ab"><span class="k">사업 정의</span><p>${gl(c.about.what)}</p></div>
        <div class="lt-ab"><span class="k">제품·매출원</span><p>${gl(c.about.makes)}</p></div>
        <div class="lt-ab"><span class="k">왜 필요한가</span><p>${gl(c.about.why)}</p></div>
        ${c.about.edge ? `<p class="lt-like"><b>핵심 한 줄</b> — ${gl(c.about.edge)}</p>` : ""}
        <p class="muted small">밑줄 친 말을 누르면 뜻이 나와요. 투자 논지·쟁점·재무 추세·동종 비교·역산 밸류에이션·리스크까지는 위의 <b>분석표 PDF</b>에서.</p></div>` : ""}
      <div class="lt-kpi">${[["주가", has(m.px) ? m.px.toLocaleString() + " " + (m.cur || "") : "—"], ["시가총액", big(m.mcap, m.cur)], ["20일 거래대금", big(m.adv, m.cur)], ["매출 대비 몸값", has(m.ps) ? m.ps.toFixed(1) + "배" : "—"], ["200일선", has(m.ma200) ? m.ma200.toLocaleString() : "—"], ["52주 범위", has(m.lo52) ? `${m.lo52.toLocaleString()} ~ ${m.hi52.toLocaleString()}` : "—"]].map(([k, x]) => `<div class="hd-stat"><span class="k">${k}</span><b>${x}</b></div>`).join("")}</div>
      <p class="small"><b>주요 제품</b> ${esc(c.products)}<br><b>주요 고객</b> ${esc(c.customers)}<br><b>최근 성장</b> ${tag(c.growth[1])} ${esc(c.growth[0])}</p>
      <details class="lt-acc"><summary><b>회사 검증 8항목</b><span class="muted small">공급망 지위 · 고객 ${esc(v.grade)}등급 · 재무 · 희석 · 몸값</span></summary><div class="lt-acc-b">
      <table class="tt-tbl lt-ver"><tbody>
        ${row("① 공급망 지위", "없으면 고객 생산·성능에 문제가 생기나", v.pos)}
        ${row("　대체 가능성", "대체 비용·기간", v.sub)}
        <tr><td><b>② 고객 검증 등급</b><span class="s">A~E</span></td><td><span class="lt-grade g${esc(v.grade)}">${esc(v.grade)}</span> ${esc(v.grade_why)}</td></tr>
        ${row("③ 생산 능력 확장", "장비·공장·인허가·인력 제약", v.capa)}
        ${row("④ 재무 건전성", "현금·부채·현금흐름", v.fin)}
        ${row("⑤ 희석 위험", "증자·전환사채·ATM", v.dil)}
        ${row("⑥ 경영진·실행력", "CEO·실행 이력", v.mgmt)}
        ${row("⑦ 지정학·규제", "수출 통제·정부 지분", v.geo)}
        ${row("⑧ 밸류에이션", "몸값", v.val)}
      </tbody></table></div></details>
      <details class="lt-acc"><summary><b>시나리오</b><span class="muted small">최고 ${sc.best.mult}배 · 기본 ${sc.base.mult}배 · 최악 ${sc.worst.mult}배</span></summary><div class="lt-acc-b">
      <div class="lt-sc">
        <div class="lt-sc1"><h5 class="up">최고 · 약 ${sc.best.mult}배</h5><p><b>핵심 가정</b> ${esc(sc.best.assume)}</p><p><b>가장 강한 근거</b> ${esc(sc.best.evidence)}</p><p><b>가장 큰 약점</b> ${esc(sc.best.weak)}</p><p><b>재평가 조건</b> ${esc(sc.best.rerate)}</p></div>
        <div class="lt-sc1"><h5>기본 · 약 ${sc.base.mult}배</h5><p><b>핵심 가정</b> ${esc(sc.base.assume)}</p><p><b>가장 강한 근거</b> ${esc(sc.base.evidence)}</p><p><b>주가가 부진할 수 있는 이유</b> ${esc(sc.base.why_weak)}</p></div>
        <div class="lt-sc1"><h5 class="down">최악 · 약 ${sc.worst.mult}배</h5><p><b>핵심 가정</b> ${esc(sc.worst.assume)}</p><p><b>위험</b> ${esc(sc.worst.risks)}</p><p><b>가장 강한 근거</b> ${esc(sc.worst.evidence)}</p><p><b>손실 경로</b> ${esc(sc.worst.loss)}</p></div>
      </div>
      <p class="muted small">배수는 리서치 시점 주가 대비 2029년 무렵을 가정한 추정이에요(사실 아님). 근거가 바뀌면 같이 바뀌어요.</p></div></details>
      <h4>장기 손익비 · 검증된 공식</h4>
      <div class="lt-ev"><label>잘 풀릴 확률 pG <input id="lt-pg" type="range" min="0" max="100" value="${c.ev.pg}"><b id="lt-pgv"></b></label><div id="lt-evout"></div></div>
      <ul class="hd-notes">${(m.formulas || []).map((f) => `<li class="${f.ok ? "pos" : "neg"}"><b>${esc(f.t)}</b> <span class="muted small">— ${esc(f.why)}</span></li>`).join("") || "<li>숫자 아직 없음</li>"}</ul>
      <h4>7단계 · 분류</h4>
      <div class="lt-final"><b>${esc(c.cls)}</b></div>
      <ul class="hd-notes"><li class="pos"><b>좋은 투자가 되는 조건</b> ${esc(c.good_if)}</li><li class="neg"><b>가설이 무너지는 조건</b> ${esc(c.break_if)}</li></ul>
      ${c.src.length ? `<p class="small">출처: ${c.src.map((s, i) => `<a href="${esc(s)}" target="_blank" rel="noopener">[${i + 1}]</a>`).join(" ")}</p>` : ""}
      <p class="muted small">투자 권유가 아니라 판단 재료예요. 사실 = 공시·보도로 확인 / 추정 = 제 판단 / 모름 = 확인 못 함.</p>`;
    evDraw();
    $("#lt-dialog").showModal();
  }
  function evDraw() {
    const c = cur; if (!c) return;
    const pg = +$("#lt-pg").value / 100, G = c.ev.g - 1, L = c.ev.l - 1, ev = G * pg + L * (1 - pg), ratio = L < 0 ? G / -L : null, be = -L / (G - L);
    const ideal = G >= 3 && L >= -0.5;
    $("#lt-pgv").textContent = Math.round(pg * 100) + "%";
    $("#lt-evout").innerHTML = `<p>기댓값 <b class="${ev > 0 ? "up" : "down"}">${pct(ev)}</b> = (${pct(G)} × ${Math.round(pg * 100)}%) + (${pct(L)} × ${Math.round((1 - pg) * 100)}%) · 손익비 <b>${ratio ? ratio.toFixed(1) + " : 1" : "—"}</b> · 본전 확률 <b>${Math.round(be * 100)}%</b></p>
      <p class="small ${ideal ? "up" : "muted"}">${ideal ? "이상적 자리: 상방 4배↑ · 하방 반토막 이내" : `이상적 기준(상방 4~5배 · 하방 −50% 이내)과 비교: 상방 ${(1 + G).toFixed(1)}배 · 하방 ${pct(L)}`}</p>`;
  }
  function pane(k) {                                 // 11/23: 탭 없앰 — 'th'는 아래 접힌 테마 순위 칸을 펼침
    if (k === "th") { const d = document.querySelector(".lt-thall"); if (d) { d.open = true; d.scrollIntoView({ behavior: "smooth" }); } }
  }
  async function openTicker(key, t) {               // 차트 화면에서 '장기 리서치' 바로가기
    await onShow();                                  // 버튼(닫기·용어) 연결이 안 된 채 열리는 문제 방지
    pane("res");
    if (!R || R.key !== key) await load(key);
    openCo(t);
  }
  return { onShow, pane, openTicker };
})();
