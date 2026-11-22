/* AI 트레이딩 데스크 — 6명 에이전트 + 대화방 (data/us/ai_paper.json) */
const DeskUI = (() => {
  const { $, esc } = U;
  const has = (v) => v != null && isFinite(v);
  const pct = (v, d = 1) => (has(v) ? (v > 0 ? "+" : "") + (v * 100).toFixed(d) + "%" : "—");
  const cls = (v) => (!has(v) ? "" : v > 0 ? "up" : v < 0 ? "down" : "");
  const usd = (v, d = 2) => (has(v) ? "$" + v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }) : "—");
  const AG = {
    scout: ["Scout", "S", "#4fd1a5", "시장 탐색", "순위 바구니·급등·거래량 급증에서 후보를 찾아요"],
    filter: ["Filter", "F", "#b8b8be", "걸러내기", "실적 임박·거래대금 부족·$5 미만·과열·시장 이상을 빼요"],
    analyst: ["Analyst", "A", "#7aa2ff", "분석", "추세·RSI·MACD·거래량·상대강도·목표가로 0~1점, 0.6 미만 탈락"],
    risk: ["Risk", "R", "#f0525c", "위험 관리", "손절 필수, 손실 ≤ 계좌 2%, +15%부터 추적 손절, 급락 땐 신규 중단"],
    executor: ["Executor", "E", "#ffffff", "주문 실행", "지정가·스톱 주문, 중복 방지, 30분마다 체결 확인"],
    logger: ["Logger", "L", "#c792ea", "기록·성과", "승률·손익비·최대 낙폭·누적 수익을 기록해요"],
    claude: ["Claude", "C", "#f5c26b", "총괄", "매일 아침 뉴스·이벤트를 보고 판단을 더하고 직접 주문도 내요"],
  };
  let A = null, loaded = false;

  // ---------- 한눈에 보기: 계좌 성적 · 지금 보유 · 사고 판 기록 ----------
  const ACC = {                                        // 이름, 색, 설명, 펼칠 상세, 종류 — 탭 순서도 이 순서 (11/21 사용자 지정)
    ai: ["주식", "#2fa36b", "주식 · 며칠~몇 주 보유", "more-ai", "stock"],
    coin: ["코인", "#9b6bd8", "BTC·ETH · AMD + 오더블록(완화판) · 레버리지 없음 · 한 번 손절 시 계좌 −1%/−0.25% (11/22부터, 그 전엔 50일선)", "", "coin"],
    lev: ["코인 10배", "#d86bb4", "BTC 1시간봉 AMD + 오더블록(완화판) · 한 번 손절 시 계좌 −2%/−0.5% · 노출 최대 10배 (11/22부터, 그 전엔 50일선)", "", "coin"],
    day: ["데이트레이딩", "#e5484d", "주식 · 그날 사서 그날 팔기", "more-day", "stock"],
    tr10: ["코인 10배 단타", "#e07040", "BTC·ETH·SOL 1시간봉 추세 눌림 · 1회 손실 계좌 0.25% · 노출 최대 10배 (11/22 새로 시작)", "", "coin"],
    ob: ["코인 오더블록", "#3fb6c9", "BTC·ETH·SOL 1시간봉 오더블록 · 1회 손실 계좌 1% · 횟수 제한 없음", "", "coin"],
    amd: ["코인 AMD", "#f5b942", "BTC·ETH·SOL 1시간봉 매집→조작→분산 · POC 진입 · 1회 손실 계좌 0.5% (11/22 시작)", "", "coin"],
    c50: ["코인 50일선", "#7a8cff", "BTC·ETH 일봉 · 50일선 위면 롱, 아래면 숏 · 레버리지 없음 (11/14부터, 11/22 형 결정으로 계속)", "more-coin", "coin"],
    l50: ["코인 10배 50일선", "#c77dff", "BTC 일봉 50일선 롱·숏 · 변동성 맞춤 크기 · 추적 손절 · 증거금 10배 (11/15부터, 11/22 형 결정으로 계속)", "more-coin", "coin"],
  };
  // 공식 피드백방: 계좌 → 그 계좌가 쓰는 공식 (scripts/coach.py → data/us/coach.json)
  const ROOMS = { coin: ["amd", "ob"], lev: ["amd", "ob"], ob: ["ob"], amd: ["amd"], tr10: ["tr10"] };
  const COACH_C = { wyckoff: "#8bc34a", ict: "#3fb6c9", livermore: "#f5b942", minervini: "#e07040", seykota: "#9b6bd8", ptj: "#d86bb4", judge: "#f5c26b" };
  function renderCoach(K) {                            // 공식 점검표 (11/22 형: 캐릭터·채팅 대신 보기 쉬운 표)
    const el = $("#coach-room"); if (!el) return;
    const rooms = ROOMS[SM.acct];
    if (!K || !K.rooms || !rooms) { el.hidden = true; return; }
    el.hidden = false;
    const tm = new Date(K.made).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });
    const R2 = (x) => (x >= 0 ? "+" : "") + x.toFixed(2) + "R";
    const logs = (K.log || []).filter((x) => rooms.includes(x.formula)).slice(-5).reverse();
    const short = (why) => (why || "").split(" · ")[0].replace("좋아진 폭 0.05R 미만", "좋아진 폭이 너무 작음").replace("계좌 기준(수익÷낙폭)은 안 좋아짐", "계좌 전체로는 안 좋아짐");
    el.innerHTML = `<div class="tt-head"><h3>공식 점검 <span class="muted small">매일 아침 2년치로 시험 → 좋아지는 것만 자동 반영</span></h3><span class="muted small">${tm}</span></div>
      ${logs.length ? `<div class="ck-log"><b>최근 바뀐 것</b>${logs.map((x) => `<div>${md(x.at.slice(0, 10))} · ${esc((K.rooms[x.formula] || {}).name || x.formula)} · ${x.kind === "remove" ? "뺌" : x.kind === "param" ? "숫자 바꿈" : "추가"}: <b>${esc(x.change)}</b> <span class="muted">(${R2(x.R[0])} → ${R2(x.R[1])})</span></div>`).join("")}</div>` : ""}
      ${rooms.map((r) => { const R = K.rooms[r]; if (!R) return "";
        const rows = R.msgs.filter((m) => m.res && m.res.ac0).sort((a, b) => (b.ok ? 1 : 0) - (a.ok ? 1 : 0) || b.res.dR - a.res.dR);
        return `<div class="ck-card"><div class="ck-head"><b>${esc(R.name)}</b>
          <span class="muted small">2년 시험 ${R.n ?? "—"}번 · 승률 ${R.win != null ? Math.round(R.win * 100) + "%" : "—"} · 거래당 ${R2(R.base)}${R.perday != null ? ` · BTC·ETH 하루 ${R.perday}번` : ""}</span></div>
          <div class="ck-now">지금 붙은 조건: <b>${esc(R.active || "없음 (기본 규칙)")}</b></div>
          <details><summary>시험한 것 ${rows.length}개 보기 (통과 ${rows.filter((m) => m.ok).length}개)</summary>
          <div class="tbl-wrap"><table class="tt-tbl ck-tbl"><thead><tr><th>시험한 것</th><th class="hide-sm">분야</th><th class="num">거래당</th><th class="num hide-sm">수익÷낙폭</th><th>결과</th></tr></thead><tbody>
          ${rows.map((m) => `<tr class="${m.ok ? "ok" : ""}"><td>${esc(m.idea)}<span class="s">거래 ${m.res.n0} → ${m.res.n}번${m.ok ? "" : " · " + esc(short(m.res.why))}</span></td><td class="hide-sm muted">${esc((K.coach[m.who] || [m.who])[0])}</td>
            <td class="num">${R2(m.res.R0)} → <b class="${m.res.dR > 0 ? "up" : "down"}">${R2(m.res.R)}</b></td><td class="num hide-sm">${m.res.ac0[2].toFixed(1)} → ${m.res.ac[2].toFixed(1)}</td>
            <td class="ck-res">${m.ok ? "✅" : `<span class="muted">✗</span>`}</td></tr>`).join("")}
          </tbody></table></div></details>
          <div class="muted small ck-live">${(R.live || []).map(esc).join("<br>")}</div></div>`; }).join("")}
      <p class="muted small">통과 기준: 거래 60번↑ · 거래당 +0.05R↑ · 앞 1년·뒤 1년 둘 다 좋아짐 · 코인 3개 중 2개↑ · 계좌 전체(수익÷낙폭)도 좋아짐. 공식마다 이틀에 한 번, 조건은 최대 3개까지.</p>`;
  }
  let SM = { log: [], acct: (() => { try { return localStorage.getItem("tradingdesk.acct") || "ai"; } catch (_) { return "ai"; } })() };
  const getj = async (u) => { try { const r = await fetch(u + "?t=" + Date.now()); return r.ok ? await r.json() : null; } catch (_) { return null; } };
  const nameOf = (t) => { try { const n = Data.info(t).name; return n && n !== t ? n : ""; } catch (_) { return ""; } };
  const md = (d) => (d || "").slice(5, 10).replace("-", "/");
  const tag = (k) => `<span class="sm-tag" style="--c:${ACC[k][1]}">${ACC[k][0]}</span>`;
  const sideTxt = (sd) => sd < 0 ? `<span class="sm-side down">숏</span>` : "";
  const px$ = (v) => !has(v) ? "—" : usd(v, v >= 1000 ? 0 : 2);

  async function renderReports() {
    const el = $("#rp-list"); if (!el) return;
    try {
      const L = await (await fetch("reports/pdf/index.json?t=" + Date.now())).json();
      el.innerHTML = L.map((r) => `<a class="rp-item" href="reports/pdf/${encodeURIComponent(r.file)}" target="_blank" rel="noopener"><b>${esc(r.date)}</b><span>${esc(r.n)} · ${esc(r.kind)}</span><span class="rp-dl">PDF ↓</span></a>`).join("") || `<p class="muted">아직 없어요.</p>`;
    } catch (_) { el.innerHTML = `<p class="muted">목록을 못 불러왔어요.</p>`; }
  }
  // 공식 그림 크게 보기 — 새 창 대신 화면 안 창 (앱·폰에서 새 창으로 열면 돌아올 버튼이 없어서, 11/22)
  function fmView() {
    const dlg = $("#fm-view"); if (!dlg || dlg._init) return dlg; dlg._init = 1;
    const img = $("#fm-view-img");
    const close = () => { if (dlg.open) dlg.close(); };
    $("#fm-back").addEventListener("click", () => { if (history.state && history.state.fm) history.back(); else close(); });
    img.addEventListener("click", () => img.classList.toggle("zoom"));
    dlg.addEventListener("click", (e) => { if (e.target === dlg) $("#fm-back").click(); });
    dlg.addEventListener("cancel", (e) => { e.preventDefault(); $("#fm-back").click(); });       // Esc
    window.addEventListener("popstate", close);                                                    // 폰 뒤로 가기
    document.addEventListener("click", (e) => {
      const a = e.target.closest && e.target.closest("[data-fm-view]"); if (!a) return;
      e.preventDefault(); img.src = a.dataset.fmView; img.classList.remove("zoom"); $("#fm-view-title").textContent = a.dataset.fmTitle || "";
      dlg.showModal(); try { history.pushState({ fm: 1 }, ""); } catch (_) {}
    });
    return dlg;
  }
  async function renderFormulas() {
    fmView();                    // 매매 공식 그림 보관함 (formulas/index.json, 11/22 형 요청) + 성적 바 (쓸모없으면 폐기·수정 판단용)
    const el = $("#fm-list"); if (!el) return;
    let L; try { L = await (await fetch("formulas/index.json?t=" + Date.now())).json(); } catch (_) { el.innerHTML = `<p class="muted">목록을 못 불러왔어요.</p>`; return; }
    const NEED = 30;                                    // 평가에 필요한 끝난 거래 수
    const live = await Promise.all(L.map((f) => f.live ? getj(f.live.file) : null));
    const stat = (f, J) => {
      if (!f.live) return null;
      if (!J) return { n: 0, R: [], ret: null };
      const R = f.live.type === "ob" ? (J.journal || []).filter((j) => j.exit != null).map((j) => j.R)
        : f.live.type === "pl" ? (J.trades || []).filter((t) => !f.live.since || (t.in || "") >= f.live.since).map((t) => t.pl * 100) : (J.trades || []).map((t) => t.R);   // pl: 주식 계좌는 거래당 수익률(%)로
      return { n: R.length, R, ret: f.live.since ? null : J.eq_now != null ? J.eq_now / 10000 - 1 : null };   // since: 규칙 시작 뒤 거래만 보므로 계좌 전체 수익률은 숨김
    };
    const card = (f, S) => {
      const bt = f.bt;
      let body;
      if (!S) body = `<div class="fm-verdict wait">시험 전 — 규칙 확정 뒤 과거 데이터 시험 · 모의 계좌 시작</div>`;
      else {
        const n = S.n, win = n ? S.R.filter((r) => r > 0).length / n : null, avgR = n ? S.R.reduce((a, r) => a + r, 0) / n : null;
        const aw = S.R.filter((r) => r > 0), al = S.R.filter((r) => r <= 0);
        // 본전 승률 = 평균 손실 / (평균 이익 + 평균 손실) — 이 승률보다 높아야 돈을 범. 표본 적으면 시험 값으로
        const mW = aw.length >= 5 ? aw.reduce((a, r) => a + r, 0) / aw.length : bt && bt.aw, mL = al.length >= 5 ? -al.reduce((a, r) => a + r, 0) / al.length : bt && -bt.al;
        const be = mW && mL ? mL / (mW + mL) : null;
        const pctU = f.live.type === "pl", good = pctU ? 1 : 0.1;          // 주식: 거래당 평균 +1% 넘으면 유지
        const v = n < NEED ? ["wait", `표본 부족 (${n}/${NEED}) — 계속 관찰`] : avgR > good ? ["good", "유지 — 기대값 플러스"] : avgR > 0 ? ["mid", "고치기 검토 — 남는 게 너무 적음"] : ["bad", "폐기 검토 — 기대값 마이너스"];
        const pctW = (x) => x == null ? "—" : (x * 100).toFixed(0) + "%";
        const sR = (x) => x == null ? "—" : (x >= 0 ? "+" : "") + x.toFixed(2) + (pctU ? "%" : "R");
        body = `<div class="fm-stats">
          <div class="fm-row"><span>평가까지</span><div class="fm-bar"><i style="width:${Math.min(100, n / NEED * 100)}%"></i></div><b>${n}/${NEED}번</b></div>
          <div class="fm-row"><span>승률</span><div class="fm-bar win"><i class="${win != null && be != null && win < be ? "lo" : ""}" style="width:${win == null ? 0 : win * 100}%"></i>${be != null ? `<em style="left:${be * 100}%" title="본전 승률"></em>` : ""}${bt ? `<u style="left:${bt.win * 100}%" title="과거 시험 승률"></u>` : ""}</div><b>${pctW(win)}</b></div>
          <div class="fm-nums"><span>수익률 <b class="${cls(S.ret)}">${S.ret == null ? "—" : pct(S.ret, 2)}</b></span><span>평균 <b class="${cls(avgR)}">${sR(avgR)}</b></span>${bt ? `<span class="muted">과거 시험 ${bt.n}번 · 승률 ${pctW(bt.win)} · ${sR(bt.avgR)}</span>` : ""}</div>
          <div class="fm-key muted small">${be != null ? `흰 선 = 본전 승률 ${pctW(be)} (이보다 높아야 이익)` : ""}${bt ? ` · 점선 = 과거 시험 승률` : ""} · ${esc(f.live.acct)} 계좌 기준</div>
          <div class="fm-verdict ${v[0]}">${v[1]}</div></div>`;
      }
      return `<div class="fm-item"><a href="${esc(f.img)}" data-fm-view="${esc(f.img)}" data-fm-title="${esc(f.title)}"><img src="${esc(f.img)}" alt="${esc(f.title)}" loading="lazy"></a>
        <b>${esc(f.title)}</b><span class="muted small">${esc(f.date)} · ${esc(f.status)}</span><span class="small">${esc(f.desc)}</span>${body}</div>`;
    };
    el.innerHTML = L.map((f, i) => [f, stat(f, live[i])]).reverse().map(([f, S]) => card(f, S)).join("") || `<p class="muted">아직 없어요.</p>`;
  }
  async function renderSummary() {
    renderReports(); renderFormulas();
    const [A, D, C, L, Q0] = await Promise.all(["data/us/ai_paper.json", "data/us/day_desk.json", "data/us/crypto_paper.json", "data/us/crypto_lev.json", "data/us/trend10.json"].map(getj));
    const O = await getj("data/us/ob_paper.json"), M = await getj("data/us/amd_paper.json");
    // 11/22: 코인·코인 10배는 AMD 칸 + 오더블록 칸(돈을 반씩)을 합쳐서 한 계좌로 보여줌
    const mergeAcct = (A_, B_) => {
      if (!A_ || !B_) return null;
      const tag = (X, nm) => (X.journal || []).map((j) => ({ ...j, tag: nm }));
      return { start: A_.start, eq_now: (A_.eq_now ?? A_.cash) + (B_.eq_now ?? B_.cash), eq: A_.eq, n_trades: (A_.n_trades || 0) + (B_.n_trades || 0), old: A_.old, parts: [["AMD", A_], ["오더블록", B_]],
        chat: [...(A_.chat || []).map((m) => ({ ...m, text: "[AMD] " + m.text })), ...(B_.chat || []).map((m) => ({ ...m, text: "[오더블록] " + m.text }))].sort((x, y) => (x.at < y.at ? -1 : 1)),
        journal: [...tag(A_, "AMD"), ...tag(B_, "오더블록")].sort((x, y) => ((x.in_at || "") < (y.in_at || "") ? -1 : 1)), skips: B_.skips, rule: `AMD 칸: ${A_.rule} / 오더블록 칸: ${B_.rule}` };
    };
    const LV = mergeAcct(await getj("data/us/lev10.json"), await getj("data/us/lev10_ob.json")) || await getj("data/us/lev10.json");
    const CX = mergeAcct(await getj("data/us/coin_amd.json"), await getj("data/us/coin_ob.json"));
    const Q = Q0;
    getj("data/us/coach.json").then(renderCoach);                                       // 10배 단타 (추세 눌림, 11/22 새로 시작 — 예전 평균 회귀 단타는 접음)
    // 1) 계좌 탭 (토스증권처럼 위에 계좌, 고르면 아래가 그 계좌로 바뀜)
    const cards = {};
    const card = (k, eq, base, start, extra) => (cards[k] = { k, eq, r: eq == null ? null : eq / base - 1, start, extra });
    if (A) card("ai", A.eq_now, A.cash0, A.start, `보유 ${A.pos.length}종목 · 같은 기간 S&P500 ${pct(A.bench, 2)} (${A.bench == null ? "—" : pct(A.eq_now / A.cash0 - 1 - A.bench, 1) + "p"})`);
    if (CX) card("coin", CX.eq_now, 10000, "2026-11-14", `새 방식 끝난 매매 ${CX.n_trades}번 · AMD 칸 ${usd(CX.parts[0][1].eq_now ?? CX.parts[0][1].cash, 0)} · 오더블록 칸 ${usd(CX.parts[1][1].eq_now ?? CX.parts[1][1].cash, 0)} · 50일선 방식(11/14~22) ${C ? pct(C.eq_now / 10000 - 1, 1) : ""}`);
    else if (C) card("coin", C.eq_now, 10000, C.start, `같은 기간 비트코인 ${pct(C.btc_ret, 1)}`);
    if (LV && LV.eq && LV.eq.length) card("lev", LV.eq_now ?? LV.cash, 10000, LV.start, `새 방식 끝난 매매 ${LV.n_trades || 0}번${LV.parts ? ` · AMD 칸 ${usd(LV.parts[0][1].eq_now ?? LV.parts[0][1].cash, 0)} · 오더블록 칸 ${usd(LV.parts[1][1].eq_now ?? LV.parts[1][1].cash, 0)}` : ""} · 50일선 방식(11/15~22) ${LV.old ? pct(LV.old.end_eq / 10000 - 1, 1) : ""}`);
    else if (L) card("lev", L.eq_now, 10000, L.start, `강제 청산 ${L.liq_n}번`);
    if (C) card("c50", C.eq_now, 10000, C.start, `규칙 ${C.rule_txt || "50일선"} · 같은 기간 비트코인 ${pct(C.btc_ret, 1)}`);
    if (L) card("l50", L.eq_now, 10000, L.start, `강제 청산 ${L.liq_n}번 · 같은 기간 비트코인 ${pct(L.btc_ret, 1)}`);
    if (D && D.eq && D.eq.length) card("day", D.eq[D.eq.length - 1][1], 10000, D.start, `매매 ${(D.trades || []).length}번`); else cards.day = { k: "day", off: "시작 전", extra: "월요일(11/23) 미국장부터 시작" };
    if (Q && Q.eq && Q.eq.length) card("tr10", Q.eq_now, 10000, Q.start, `끝난 매매 ${(Q.trades || []).length}번 · 보유 ${Object.keys(Q.pos || {}).length}개 · 수수료 포함`); else cards.tr10 = { k: "tr10", off: "시작 전", extra: "1시간마다 자동 실행" };
    if (O && O.eq) card("ob", O.eq_now, 10000, O.start, `끝난 매매 ${O.n_trades || 0}번 · 대기 ${Object.values(O.pend || {}).reduce((a, x) => a + x.length, 0)}개 · 수수료 포함`); else cards.ob = { k: "ob", off: "시작 전", extra: "1시간마다 자동 실행" };
    if (M && M.eq && M.eq.length) card("amd", M.eq_now, 10000, M.start, `끝난 매매 ${M.n_trades || 0}번 · POC 대기 ${Object.keys(M.pend || {}).length}개 · 수수료 포함`); else cards.amd = { k: "amd", off: "시작 전", extra: "1시간마다 자동 실행" };
    if (!ACC[SM.acct]) SM.acct = "ai";
    $("#sm-accts").innerHTML = Object.keys(ACC).map((k) => { const c = cards[k] || { off: "—" };
      return `<button class="acct-tab ${k === SM.acct ? "on" : ""}" data-acct="${k}" style="--c:${ACC[k][1]}"><span class="nm">${ACC[k][0]}</span><span class="ret ${c.off ? "muted" : cls(c.r)}">${c.off ? c.off : pct(c.r, 2)}</span></button>`; }).join("");
    { const c = cards[SM.acct] || { off: "—" }, [nm, col, how, more] = ACC[SM.acct];
      const chatSrc = SM.acct === "tr10" && Q ? Q.chat : SM.acct === "ob" && O ? O.chat : SM.acct === "amd" && M ? M.chat : SM.acct === "lev" && LV ? LV.chat : SM.acct === "coin" && CX ? CX.chat : SM.acct === "c50" && C ? C.chat : SM.acct === "l50" && L ? L.chat : null;
      $("#sm-hero").innerHTML = `<div class="hero-top" style="--c:${col}"><div><span class="nm">${nm}</span><span class="how">${how}</span></div>
        <span class="ret ${c.off ? "" : cls(c.r)}">${c.off ? c.off : pct(c.r, 2)}</span></div>
        <div class="hero-sub">${c.off ? "" : `<b>${usd(c.eq, 0)}</b> · 가상 $10,000 · ${md(c.start)}부터`}${c.extra ? ` · ${c.extra}` : ""}</div>
        ${more ? `<button class="link-btn hero-more" data-open="${more}">대화방·규칙 자세히 ↓</button>` : ""}
        ${chatSrc && chatSrc.length ? `<ul class="hero-chat">${chatSrc.slice(-6).reverse().map((m) => `<li><span class="muted small">${new Date(m.at).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false })}</span> ${esc(m.text)}</li>`).join("")}</ul>` : ""}`;
      document.querySelectorAll("#tab-desk .dk-more").forEach((d) => { d.hidden = d.id !== more; });
    }
    // 2) 지금 들고 있는 것
    let rows = [];
    if (A) for (const p of A.pos) rows.push({ k: "ai", sym: p.sym, side: 1, since: p.since, entry: p.avg, now: p.px, pl: p.pl, stop: p.stop, target: p.target, why: p.why });
    if (D && D.pos) for (const [sym, p] of Object.entries(D.pos)) rows.push({ k: "day", sym, side: 1, since: D.today && D.today.day, entry: p.entry, now: null, pl: null, stop: p.stop, target: p.target, why: (p.sig || []).join(" · ") });
    if (C) for (const p of C.pos) rows.push({ k: "c50", sym: p.sym, nm: p.name, side: p.side, since: p.since, entry: p.entry, now: p.now, pl: p.pl, stop: null, target: null, why: "50일선 " + (p.side < 0 ? "아래 → 숏" : "위 → 롱") + " (종가 기준, 50일선 반대로 넘으면 정리)" });
    for (const [k, X] of [["lev", LV], ["coin", CX]]) if (X && X.parts) for (const [nm, P] of X.parts) for (const [sym, p] of Object.entries(P.pos || {})) { const now = (P.px || {})[sym], J = (P.journal || [])[p.jid] || {}, e = p.fill ?? p.entry; rows.push({ k, sym, nm: COINNM[sym] || sym, side: p.side, since: (p.at || "").slice(0, 16).replace("T", " "), entry: e, now, pl: now ? p.side * (now / e - 1) : null, stop: p.stop, stopLbl: nm === "AMD" ? "조작 꼬리 끝" : p.be ? "본전 손절" : "오더블록 꼬리 끝", target: p.target ?? (p.be ? null : p.wave), why: `[${nm}] ` + (J.why_in || []).join(" · ") }); }
    if (LV && !LV.parts && LV.pos) for (const [sym, p] of Object.entries(LV.pos)) { const now = (LV.px || {})[sym], J = (LV.journal || [])[p.jid] || {}; rows.push({ k: "lev", sym, nm: COINNM[sym] || sym, side: p.side, since: (p.at || "").slice(0, 16).replace("T", " "), entry: p.fill, now, pl: now ? p.side * (now / p.fill - 1) * (p.qty * p.fill / (LV.cash || 1)) : null, stop: p.stop, stopLbl: "조작 꼬리 끝 (계좌 −2%)", target: p.target, why: (J.why_in || []).join(" · ") + " · 수익률은 계좌 대비" }); }
    if (L && L.pos) { const p = L.pos; rows.push({ k: "l50", sym: "BTC-USD", nm: "비트코인", side: p.side, since: p.since, entry: p.entry, now: L.now, pl: p.pl, stop: p.stop, stopLbl: `추적 손절 · 청산 ${px$(p.liq)}`, target: null, why: `계좌의 ${(p.expo || 0).toFixed(2)}배 노출 (증거금 × ${L.lev}배, 변동성 맞춤) · 수익률은 계좌 대비` }); }
    if (Q && Q.pos) for (const [sym, p] of Object.entries(Q.pos)) { const now = (Q.px || {})[sym]; rows.push({ k: "tr10", sym, nm: COINNM[sym] || sym, side: p.side, since: (p.at || "").slice(0, 16).replace("T", " "), entry: p.entry, now, pl: now ? p.side * (now / p.entry - 1) * (p.expo || 1) : null, stop: p.stop, stopLbl: p.trailed ? "추적 손절 (ATR×5)" : "첫 손절 (ATR×1.5)", target: null, why: `${p.why} · 계좌의 ${p.expo}배 노출, 수익률은 계좌 대비` }); }
    if (O && O.pos) for (const [sym, p] of Object.entries(O.pos)) { const now = (O.px || {})[sym]; rows.push({ k: "ob", sym, nm: COINNM[sym] || sym, side: p.side, since: (p.at || "").slice(0, 16).replace("T", " "), entry: p.fill, now, pl: now ? p.side * (now / p.fill - 1) : null, stop: p.stop, stopLbl: p.be ? "본전 손절 (절반 익절 뒤)" : "오더블록 꼬리 끝", target: p.be ? null : p.wave, why: (O.journal[p.jid] || {}).why_in ? O.journal[p.jid].why_in.join(" · ") : "" }); }
    if (M && M.pos) for (const [sym, p] of Object.entries(M.pos)) { const now = (M.px || {})[sym], J = (M.journal || [])[p.jid] || {}; rows.push({ k: "amd", sym, nm: COINNM[sym] || sym, side: p.side, since: (p.at || "").slice(0, 16).replace("T", " "), entry: p.fill, now, pl: now ? p.side * (now / p.fill - 1) : null, stop: p.stop, stopLbl: "조작 꼬리 끝", target: p.target, why: (J.why_in || []).join(" · ") }); }
    SM.rows = rows;
    const allRows = rows;
    rows = allRows.filter((r) => r.k === SM.acct);
    rows.sort((a, b) => (b.pl ?? -9) - (a.pl ?? -9));
    $("#sm-pos-sub").textContent = rows.length ? `${rows.length}개 · 수익률은 산 가격 대비 (수수료 전)` : "";
    $("#sm-pos").innerHTML = rows.map((r) => `<tr class="open">
      <td><button class="tt-sym" data-sym="${esc(r.sym)}"><b>${esc(r.nm || r.sym)}${sideTxt(r.side)}</b><span class="muted">${esc(r.nm ? r.sym : nameOf(r.sym))} · ${md(r.since)} 매수</span></button></td>
      <td class="num">${px$(r.entry)} → <b>${px$(r.now)}</b></td>
      <td class="num pl ${cls(r.pl)}">${pct(r.pl, 1)}</td>
      <td class="num hide-sm">${r.stop ? px$(r.stop) : "—"}<span class="s">${r.stopLbl ? r.stopLbl : r.target ? "목표 " + px$(r.target) : ""}</span></td>
      <td class="hide-sm"><span class="why" title="${esc(r.why || "")}">${esc(r.why || "")}</span></td></tr>`).join("")
      || `<tr class="empty-row"><td colspan="5">지금 들고 있는 것 없음</td></tr>`;
    $("#sm-orders").innerHTML = SM.acct === "ai" && A && A.orders.length ? `<div class="sm-orders">대기 주문: ${A.orders.map((o) => `<b>${esc(o.desc)}</b>`).join(" · ")}</div>` : "";
    // 3) 사고 판 기록 (끝난 것 + 들고 있는 것의 매수)
    const log = [];
    if (A) for (const t of A.trades) log.push({ k: "ai", d: t.out, sym: t.sym, side: 1, a: t.avg, b: t.px, din: t.in, pl: t.pl, why: `팜: ${t.why} · 산 이유: ${t.entry_why || ""}` });
    if (D) for (const t of D.trades || []) log.push({ k: "day", d: t.day, sym: t.sym, side: 1, a: t.entry, b: t.exit, din: t.day, pl: t.pl, why: t.why });
    if (C) for (const t of C.trades || []) log.push({ k: "c50", d: t.out, sym: t.sym, nm: t.sym.startsWith("BTC") ? "비트코인" : "이더리움", side: t.side, a: t.entry, b: t.exit, din: t.in, pl: t.pl, why: (t.why || "50일선 반대로 넘어가서 정리") });
    if (L) for (const t of L.trades || []) log.push({ k: "l50", d: t.out, sym: "BTC-USD", nm: "비트코인", side: t.side, a: t.entry, b: t.exit, din: t.in, pl: t.pl, why: (t.liq ? "💥 강제 청산 (증거금 전부 손실)" : t.why || "50일선 반대로 넘어가서 정리") });
    if (Q) for (const t of (Q.trades || []).slice(-300)) log.push({ k: "tr10", d: (t.out || "").slice(0, 16).replace("T", " "), sym: t.sym, nm: COINNM[t.sym] || t.sym, side: t.side, a: t.entry, b: t.exit, din: (t.in || "").slice(0, 16).replace("T", " "), pl: t.acct, why: `팜: ${t.why} (${t.R >= 0 ? "+" : ""}${t.R}R) · 산 이유: ${t.entry_why} · 수익률은 계좌 대비` });
    if (O) for (const j of O.journal || []) if (j.exit != null) log.push({ k: "ob", d: (j.out_at || "").slice(0, 16).replace("T", " "), sym: j.sym, nm: COINNM[j.sym] || j.sym, side: j.side === "숏" ? -1 : 1, a: j.fill, b: j.exit, din: (j.in_at || "").slice(0, 16).replace("T", " "), pl: j.pnl / 10000, why: `${j.why_out} · ${j.R >= 0 ? "+" : ""}${j.R}R · 수익률은 계좌 대비` });
    for (const [k, X] of [["lev", LV], ["coin", CX]]) if (X && X.parts) for (const j of X.journal) if (j.exit != null) log.push({ k, d: (j.out_at || "").slice(0, 16).replace("T", " "), sym: j.sym, nm: COINNM[j.sym] || j.sym, side: j.side === "숏" ? -1 : 1, a: j.fill, b: j.exit, din: (j.in_at || "").slice(0, 16).replace("T", " "), pl: j.pnl / 10000, why: `[${j.tag}] ${j.why_out} · ${j.R >= 0 ? "+" : ""}${j.R}R · 수익률은 계좌 대비` });
    if (LV && !LV.parts) for (const j of LV.journal || []) if (j.exit != null) log.push({ k: "lev", d: (j.out_at || "").slice(0, 16).replace("T", " "), sym: j.sym, nm: COINNM[j.sym] || j.sym, side: j.side === "숏" ? -1 : 1, a: j.fill, b: j.exit, din: (j.in_at || "").slice(0, 16).replace("T", " "), pl: j.pnl / 10000, why: `${j.why_out} · ${j.R >= 0 ? "+" : ""}${j.R}R · 수익률은 계좌 대비` });
    if (M) for (const j of M.journal || []) if (j.exit != null) log.push({ k: "amd", d: (j.out_at || "").slice(0, 16).replace("T", " "), sym: j.sym, nm: COINNM[j.sym] || j.sym, side: j.side === "숏" ? -1 : 1, a: j.fill, b: j.exit, din: (j.in_at || "").slice(0, 16).replace("T", " "), pl: j.pnl / 10000, why: `${j.why_out} · ${j.R >= 0 ? "+" : ""}${j.R}R · 수익률은 계좌 대비` });
    for (const r of allRows) log.push({ k: r.k, d: r.since, sym: r.sym, nm: r.nm, side: r.side, a: r.entry, b: null, din: r.since, pl: r.pl, open: true, why: r.why });
    log.sort((x, y) => (y.d || "").localeCompare(x.d || "") || (y.open ? 1 : 0) - (x.open ? 1 : 0));
    SM.log = log; renderLog();
    renderJournal(SM.acct === "amd" ? M : SM.acct === "lev" ? LV : SM.acct === "coin" ? CX : O);
    const tm = (x) => x ? new Date(x).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }) : "";
    $("#sm-made").textContent = `주식 ${A && A.eq.length ? md(A.eq[A.eq.length - 1][0]) + " 마감" : "—"} · 코인 ${C ? tm(C.made) : "—"} 기준`;
  }
  const COINNM = { "BTC-USD": "비트코인", "ETH-USD": "이더리움", "SOL-USD": "솔라나" };
  function renderJournal(O) {                          // 오더블록 매매일지: 진입 이유 · 손절/익절 이유 · 피드백
    const el = $("#ob-journal"); if (!el) return;
    el.hidden = !["ob", "amd", "lev", "coin"].includes(SM.acct) || !O; if (el.hidden) return;
    const J = ((O && O.journal) || []).slice().reverse();
    const done = J.filter((j) => j.exit != null), w = done.filter((j) => j.R > 0).length, avgR = done.length ? done.reduce((a, j) => a + j.R, 0) / done.length : null;
    const mt = done.filter((j) => j.mtf), mR = mt.length ? mt.reduce((a, j) => a + j.R, 0) / mt.length : null;
    const tm = (x) => x ? new Date(x).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }) : "";
    el.innerHTML = `<div class="tt-head"><h3>매매일지</h3><span class="muted small">${done.length ? `끝난 ${done.length}번 · 승 ${w} · 평균 ${avgR >= 0 ? "+" : ""}${avgR.toFixed(2)}R${mt.length ? ` · 4시간 OB 겹친 거래 ${mt.length}번 평균 ${mR >= 0 ? "+" : ""}${mR.toFixed(2)}R` : ""}` : `아직 끝난 매매 없음 — ${SM.acct === "ob" ? "오더블록 자리" : "AMD 자리(박스 가짜 이탈 뒤 POC 복귀)"}가 나오면 기록돼요`}</span></div>
      <p class="muted small">규칙: ${esc((O && O.rule) || "")}</p>
      ${J.map((j) => `<details class="ob-j ${j.exit == null ? "open-pos" : j.R > 0 ? "win" : "loss"}"><summary>
          <span class="ob-j-t"><b>${j.tag ? `<span class="sm-tag">${esc(j.tag)}</span> ` : ""}${esc(COINNM[j.sym] || j.sym)} ${esc(j.side)}</b> <span class="muted small">${tm(j.in_at)} 진입</span></span>
          <span class="ob-j-r ${j.exit == null ? "" : j.R > 0 ? "up" : "down"}">${j.exit == null ? "보유 중" : `${j.R >= 0 ? "+" : ""}${j.R}R`}</span></summary>
        <div class="ob-j-b">
          <p class="small">진입 ${j.fill} · 손절 ${j.stop} (${j.risk_pct}%) · 목표 ${j.target} · $${Math.round(j.size).toLocaleString()}어치${j.mtf ? " · <b>4시간 OB 겹침</b>" : ""}</p>
          <h5>진입 이유</h5><ul>${(j.why_in || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
          ${(j.partial || []).map((x) => `<h5>부분 익절</h5><p class="small">${tm(x.at)} · ${x.px} · ${esc(x.why)} · ${x.pnl >= 0 ? "+" : ""}$${x.pnl}</p>`).join("")}
          ${j.exit != null ? `<h5>${j.R > 0 ? "익절" : "손절"} 이유</h5><p class="small">${tm(j.out_at)} · ${j.exit} · ${esc(j.why_out)} · ${j.pnl >= 0 ? "+" : ""}$${j.pnl} · ${j.bars}봉 보유 · 최대 유리 +${j.mfe}% / 최대 불리 −${j.mae}%</p>
          <h5>피드백</h5><ul>${(j.feedback || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
        </div></details>`).join("")}
      ${(O && O.skips && O.skips.length) ? `<details class="ob-j"><summary><span class="ob-j-t"><b>진입 안 한 자리 ${O.skips.length}개</b> <span class="muted small">구간에 안 닿음 · 무효화 · 손익비 부족</span></span></summary><div class="ob-j-b"><ul>${O.skips.slice(-30).reverse().map((x) => `<li class="small">${esc(COINNM[x.sym] || x.sym)} ${esc(x.side)} ${x.entry} — ${esc(x.why)}</li>`).join("")}</ul></div></details>` : ""}`;
  }
  function renderLog() {
    const all = SM.log.filter((r) => r.k === SM.acct), L = all.slice(0, 60);
    const done = all.filter((r) => !r.open);
    $("#sm-log-sub").textContent = done.length ? `끝난 매매 ${done.length}번 · 이긴 것 ${done.filter((r) => r.pl > 0).length}번` : "끝난 매매 아직 없음";
    $("#sm-log").innerHTML = L.map((r) => `<tr class="${r.open ? "open" : ""}"><td class="small hide-sm">${md(r.d)}</td>
      <td><button class="tt-sym" data-sym="${esc(r.sym)}"><b>${esc(r.nm || r.sym)}${sideTxt(r.side)}</b><span class="muted">${esc(r.nm ? r.sym : nameOf(r.sym))}</span></button></td>
      <td class="num">${r.open ? `${px$(r.a)} → <span class="muted">보유 중</span>` : `${px$(r.a)} → ${px$(r.b)}`}<span class="s">${r.open ? md(r.din) + " 매수" : md(r.din) + " 매수 · " + md(r.d) + " 매도"}</span></td>
      <td class="num pl ${cls(r.pl)}">${pct(r.pl, 1)}${r.open ? `<span class="s">평가</span>` : ""}</td>
      <td class="hide-sm"><span class="why" title="${esc(r.why || "")}">${esc(r.why || "")}</span></td></tr>`).join("")
      || `<tr class="empty-row"><td colspan="5">기록 없음</td></tr>`;
  }

  async function onShow() {
    renderSummary();
    try { const r = await fetch("data/us/ai_paper.json?t=" + Date.now()); if (!r.ok) throw 0; A = await r.json(); }
    catch (_) { $("#dk-chat").innerHTML = `<p class="muted">아직 데스크가 열리지 않았어요.</p>`; return; }
    if (!loaded) {
      loaded = true;
      $("#tab-desk").addEventListener("click", (e) => {
        const o = e.target.closest("[data-open]");
        if (o) { if (o.dataset.open) { const d = $("#" + o.dataset.open); d.open = true; d.scrollIntoView({ behavior: "smooth", block: "start" }); } else App.go && App.go("portfolio"); return; }
        const ac = e.target.closest("[data-acct]");
        if (ac) { SM.acct = ac.dataset.acct; try { localStorage.setItem("tradingdesk.acct", SM.acct); } catch (_) {} renderSummary(); return; }
        const b = e.target.closest("[data-sym]"); if (b) App.openChart(b.dataset.sym);
      });
    }
    render();
    renderDay();
    renderCoin();
  }

  // ---------- 코인 계좌 (data/us/crypto_paper.json) ----------
  async function renderCoin() {
    let C = null; try { const r = await fetch("data/us/crypto_paper.json?t=" + Date.now()); if (r.ok) C = await r.json(); } catch (_) {}
    if (!C) { $("#cx-stats").innerHTML = `<p class="muted">아직 시작 전이에요.</p>`; return; }
    const r = C.eq_now / 10000 - 1, tr = C.trades || [], w = tr.filter((t) => t.pl > 0).length;
    $("#cx-sub").textContent = `${C.start} 시작 · ${new Date(C.made).toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false })} 갱신`;
    $("#cx-stats").innerHTML = [
      ["계좌", usd(C.eq_now, 0), `<span class="${cls(r)}">${pct(r, 2)}</span>`],
      ["같은 기간 비트코인", `<span class="${cls(C.btc_ret)}">${pct(C.btc_ret, 2)}</span>`, `차이 <b class="${cls(r - C.btc_ret)}">${pct(r - C.btc_ret, 2)}</b>`],
      ["현금", usd(C.cash, 0), `보유 ${C.pos.length}개`],
      ["끝난 매매", `${tr.length}번`, tr.length ? `승률 ${Math.round(w / tr.length * 100)}%` : "아직 없음"],
      ["최대 낙폭", pct(C.mdd, 1), "고점 대비"],
      ["지금 규칙", esc(C.rule_txt), (C.history || []).length ? `${C.history.length}번 바뀜` : "시작 규칙 그대로"],
    ].map(([k, v, s_]) => `<div class="hd-stat"><span class="k">${k}</span><b>${v}</b><span class="s">${s_}</span></div>`).join("");
    const P = Object.fromEntries(C.pos.map((p) => [p.sym, p]));
    $("#cx-watch").innerHTML = C.watch.map((x) => { const p = P[x.sym], g = x.ma50 ? x.close / x.ma50 - 1 : null;
      return `<tr><td><button class="tt-sym" data-sym="${esc(x.sym)}"><b>${esc(x.name)}</b><span class="muted">${esc(x.sym)}</span></button></td><td class="num">${usd(x.now, x.now > 1000 ? 0 : 2)}</td><td class="num">${usd(x.ma50, 0)}<span class="s">${usd(x.ma200, 0)}</span></td>
        <td class="small">${p ? (p.side < 0 ? `<b class="down">숏</b> ${pct(p.pl)}` : `<b class="up">롱</b> ${pct(p.pl)}`) : `현금 대기`}<span class="s">어제 종가가 50일선 ${pct(g)}</span></td></tr>`; }).join("");
    const nm = { ma50: "50일선", ma200: "200일선", gold: "50>200 + 50일선", don: "돈치안 20/10", hold: "그냥 보유", ls50: "롱+숏 (50일선)", ls_bear: "롱+숏 (약세장만 숏)", vote: "선 4개 투표", ens_vt: "★ 추세 10개 묶음+변동성" };
    $("#cx-shadow").innerHTML = Object.entries(C.shadow || {}).sort((a, b) => b[1].ret - a[1].ret).map(([k, v]) => `<tr><td>${k === C.rule ? "<b>▶ " : ""}${esc(nm[k] || k)}${k === C.rule ? "</b>" : ""}<span class="s">${esc(v.name)}</span></td><td class="num ${cls(v.ret)}">${pct(v.ret, 2)}</td><td class="num">${pct(v.mdd, 1)}</td></tr>`).join("");
    $("#cx-trades").innerHTML = tr.slice(-10).reverse().map((t) => `<tr><td><b>${esc(t.sym.replace("-USD", ""))}</b> ${t.side < 0 ? "숏" : "롱"}<span class="s">${esc(t.in.slice(5))} → ${esc(t.out.slice(5))}</span></td><td class="num ${cls(t.pl)}">${pct(t.pl, 2)}</td></tr>`).join("") || `<tr class="empty-row"><td colspan="2">아직 없음</td></tr>`;
    const NM = { scout: ["Scout", "S", "#4fd1a5"], risk: ["Risk", "R", "#f0525c"], executor: ["Executor", "E", "#ffffff"], logger: ["Logger", "L", "#c792ea"], analyst: ["Analyst", "A", "#7aa2ff"], claude: ["Claude", "C", "#f5c26b"] };
    $("#cx-chat").innerHTML = (C.chat || []).map((c) => {
      const [n_, ini, col] = NM[c.who] || [c.who, "?", "#888"];
      const t = new Date(c.at).toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
      return c.text.startsWith("──") ? `<div class="dk-meet">${esc(c.text)}</div>` : `<div class="dk-msg"><span class="dk-av" style="--c:${col}">${ini}</span><div class="dk-bub"><div class="dk-who"><b style="color:${col}">${n_}</b><span class="muted small">${t}</span></div><div>${esc(c.text)}</div></div></div>`;
    }).join("");
    const box = $("#cx-chat"); box.scrollTop = box.scrollHeight;
    let V = null; try { const r2 = await fetch("data/us/crypto_lev.json?t=" + Date.now()); if (r2.ok) V = await r2.json(); } catch (_) {}
    if (V) {
      const rv = V.eq_now / 10000 - 1, p = V.pos, last = (V.chat || []).slice(-3);
      $("#cx-lev").innerHTML = `<div class="pp-chips"><span>계좌 <b>${usd(V.eq_now, 0)}</b> <b class="${cls(rv)}">${pct(rv, 2)}</b></span><span>최대 낙폭 <b>${pct(V.mdd, 1)}</b></span><span>강제 청산 <b class="${V.liq_n ? "down" : ""}">${V.liq_n}번</b></span></div>
        <p class="small">${p ? `${p.side < 0 ? "<b class='down'>숏</b>" : "<b class='up'>롱</b>"} @ ${usd(p.entry, 0)} · 계좌의 ${(p.expo || 0).toFixed(2)}배 노출 · 계좌 대비 <b class="${cls(p.pl)}">${pct(p.pl, 1)}</b><br>추적 손절 ${usd(p.stop, 0)} · 강제 청산 ${usd(p.liq, 0)}` : V.block ? `추적 손절 뒤 대기 — 50일선 신호가 바뀌면 다시 진입` : `현금 대기 — 다음 일봉 마감 때 50일선 위면 롱, 아래면 숏`}</p>
        <ul class="ai-orders">${last.map((c) => `<li class="small">${esc(c.text)}</li>`).join("")}</ul>`;
    }
  }

  // ---------- 데이트레이딩 계좌 (중계 서버에서 실시간, 없으면 저장본) ----------
  async function renderDay() {
    let S = null, live = false;
    const px = Data.getProxy && Data.getProxy();
    if (px) { try { const r = await fetch(px.replace(/\/$/, "") + "/day", { cache: "no-store" }); if (r.ok) { S = await r.json(); live = !!S.eq; } } catch (_) {} }
    if (!S || !S.eq) { try { const r = await fetch("data/us/day_desk.json?t=" + Date.now()); if (r.ok) S = await r.json(); } catch (_) {} }
    let P = null; try { const r = await fetch("data/us/day_params.json?t=" + Date.now()); if (r.ok) P = await r.json(); } catch (_) {}
    if (!S || !S.eq || !S.eq.length) {
      $("#dd-stats").innerHTML = `<p class="muted">아직 시작 전이에요. 중계 서버에 예약 실행(5분마다)과 저장소(KV)를 연결하면 미국장 시간에 혼자 매매를 시작해요.</p>`;
      $("#dd-chat").innerHTML = ""; renderParams(P); return;
    }
    const e = S.eq[S.eq.length - 1][1], r = e / 10000 - 1, tr = S.trades || [];
    const td = tr.filter((t) => t.day === (S.today || {}).day), w = tr.filter((t) => t.pl > 0).length;
    const sp = S.spy0 && S.spy_now ? S.spy_now / S.spy0 - 1 : null;
    const R = tr.length ? tr.reduce((a, t) => a + (t.R || 0), 0) / tr.length : null;
    $("#dd-sub").textContent = `${S.start} 시작 · ${live ? "실시간" : "저장본"} · 뉴욕 ${S.ny || ""} 갱신`;
    $("#dd-stats").innerHTML = [
      ["계좌", usd(e, 0), `<span class="${cls(r)}">${pct(r, 2)}</span>`],
      ["같은 기간 S&P500", sp == null ? "—" : `<span class="${cls(sp)}">${pct(sp, 2)}</span>`, sp == null ? "" : `차이 <b class="${cls(r - sp)}">${pct(r - sp, 2)}</b>`],
      ["오늘 매매", `${td.length}번`, `하루 최대 ${(P && P.max_trades) || 5}번`],
      ["전체 매매", `${tr.length}번`, tr.length ? `승률 ${Math.round(w / tr.length * 100)}%` : "—"],
      ["평균 R", R == null ? "—" : (R >= 0 ? "+" : "") + R.toFixed(2) + "R", "거래당 손익 ÷ 처음 손절 폭"],
      ["상태", S.halt ? `<b class="down">신규 중단</b>` : "정상", `지금 보유 ${Object.keys(S.pos || {}).length}종목`],
    ].map(([k, v, s_]) => `<div class="hd-stat"><span class="k">${k}</span><b>${v}</b><span class="s">${s_}</span></div>`).join("");
    $("#dd-pos").innerHTML = Object.entries(S.pos || {}).map(([s_, p]) => `<tr><td><button class="tt-sym" data-sym="${esc(s_)}"><b>${esc(s_)}</b></button></td><td class="num">${usd(p.entry)}</td><td class="num">${usd(p.stop)}<span class="s">${usd(p.target)}</span></td><td class="small">${esc((p.sig || []).join("·"))}</td></tr>`).join("")
      || `<tr class="empty-row"><td colspan="4">없음</td></tr>`;
    $("#dd-trades").innerHTML = tr.slice(-15).reverse().map((t) => `<tr><td><b>${esc(t.sym)}</b><span class="s">${esc(t.day.slice(5))} · ${esc((t.sig || []).join("·"))}</span></td><td class="num ${cls(t.pl)}">${pct(t.pl, 2)}</td><td class="num ${cls(t.R)}">${(t.R >= 0 ? "+" : "") + (t.R || 0).toFixed(1)}</td><td class="small">${esc(t.why)}</td></tr>`).join("")
      || `<tr class="empty-row"><td colspan="4">아직 없음</td></tr>`;
    const NM = { scout: ["Scout", "S", "#4fd1a5"], risk: ["Risk", "R", "#f0525c"], executor: ["Executor", "E", "#ffffff"], logger: ["Logger", "L", "#c792ea"], analyst: ["Analyst", "A", "#7aa2ff"], claude: ["Claude", "C", "#f5c26b"] };
    $("#dd-chat").innerHTML = (S.chat || []).slice(-200).map((c) => {
      const [nm, ini, col] = NM[c.who] || [c.who, "?", "#888"];
      const t = new Date(c.at).toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
      return c.text.startsWith("──") ? `<div class="dk-meet">${esc(c.text)}</div>` : `<div class="dk-msg"><span class="dk-av" style="--c:${col}">${ini}</span><div class="dk-bub"><div class="dk-who"><b style="color:${col}">${nm}</b><span class="muted small">${t}</span></div><div>${esc(c.text)}</div></div></div>`;
    }).join("");
    const box = $("#dd-chat"); box.scrollTop = box.scrollHeight;
    renderParams(P);
  }
  function renderParams(P) {
    if (!P) { $("#dd-params").innerHTML = ""; return; }
    const on = Object.entries(P.on || {}).map(([k, v]) => `${{ orb: "개장 범위 돌파", vwap: "VWAP 회복", rs: "상대강도" }[k] || k} ${v ? "켬" : "<b class='down'>끔</b>"}`).join(" · ");
    const wt = Object.entries(P.w || {}).map(([k, v]) => `<span>${{ orb: "돌파", vwap: "VWAP", rs: "강도", rv: "거래", mom: "모멘텀" }[k] || k} <b>${v.toFixed(2)}</b></span>`).join("");
    $("#dd-params").innerHTML = `<p class="small">설정 v${P.v || 1} · 진입 기준 ${P.min_score} · 신호: ${on}</p><div class="pp-chips">${wt}</div>
      ${(P.history || []).length ? `<ul class="ai-orders">${P.history.slice(-6).reverse().map((h) => `<li class="small"><span class="muted">${esc(h.day)} v${h.v}</span> ${esc(h.changes.join(" / "))}</li>`).join("")}</ul>` : `<p class="small muted">아직 바꾼 것 없음 — 신호별로 15건 넘게 쌓이면 금요일마다 성적 보고 조정해요.</p>`}
      <p class="small muted">감시 ${(P.watch || []).length}종목: ${(P.watch || []).slice(0, 14).map(esc).join(", ")}…</p>`;
  }

  function render() {
    const m = A.stats || {}, r = A.eq_now / A.cash0 - 1, inv = A.pos.reduce((s, p) => s + (p.val || 0), 0);
    $("#dk-date").textContent = `${A.start} 시작 · ${(A.agents || {}).day ? A.agents.day + " 회의까지" : ""}`;
    $("#dk-rules").textContent = "규칙: " + A.rules;
    const st = [
      ["계좌", usd(A.eq_now, 0), `<span class="${cls(r)}">${pct(r, 2)}</span>`],
      ["같은 기간 S&P500", A.bench == null ? "첫 체결 뒤" : `<span class="${cls(A.bench)}">${pct(A.bench, 2)}</span>`, A.bench == null ? "" : `차이 <b class="${cls(r - A.bench)}">${pct(r - A.bench, 2)}</b>`],
      ["투자 / 현금", `${usd(inv, 0)}`, `현금 ${usd(A.cash, 0)}`],
      ["끝난 거래", `${m.n || 0}건`, m.n ? `승률 ${Math.round(m.win * 100)}%` : "아직 없음"],
      ["손익비", has(m.payoff) ? m.payoff.toFixed(2) : "—", "평균 이익 ÷ 평균 손실"],
      ["최대 낙폭", pct(m.mdd, 1), A.halt ? `<b class="down">🚨 신규 매수 중단 중</b>` : "고점 대비 최대 하락"],
    ];
    $("#dk-stats").innerHTML = st.map(([k, v, s]) => `<div class="hd-stat"><span class="k">${k}</span><b>${v}</b><span class="s">${s}</span></div>`).join("");
    const ag = A.agents || {};
    $("#dk-agents").innerHTML = ["scout", "filter", "analyst", "risk", "executor", "logger"].map((k, i) => {
      const [nm, ini, col, role, desc] = AG[k];
      return `${i ? `<span class="dk-arrow">→</span>` : ""}<div class="dk-agent" title="${esc(desc)}">
        <span class="dk-av" style="--c:${col}">${ini}</span><div><b>${nm}</b><span class="muted small">${role}</span><span class="dk-st">${esc(ag[k] || "대기")}</span></div></div>`;
    }).join("");
    renderChat();
    $("#dk-pos").innerHTML = A.pos.map((p) => `<tr><td><button class="tt-sym" data-sym="${esc(p.sym)}"><b>${esc(p.sym)}</b><span class="muted">${usd(p.val, 0)} · ${esc(p.since.slice(5))}부터</span></button></td>
      <td class="num ${cls(p.pl)}">${pct(p.pl)}</td><td class="num">${usd(p.stop)}<span class="s">${p.target ? usd(p.target) : "—"}</span></td></tr>`).join("")
      || `<tr class="empty-row"><td colspan="3">아직 없음 — 대기 주문이 체결되면 떠요.</td></tr>`;
    $("#dk-orders").innerHTML = A.orders.map((o) => `<li><b>${esc(o.desc)}</b><span class="muted small">${esc(o.why)}</span></li>`).join("") || `<li class="muted">없음</li>`;
    $("#dk-cands").innerHTML = (A.cands || []).slice(0, 8).map((c) => `<div class="dk-cand"><button class="tt-sym" data-sym="${esc(c.t)}"><b>${esc(c.name)}</b><span class="muted">${esc(c.t)} · ${esc(c.src)}</span></button>
      <div class="dk-bar"><i style="width:${Math.round(c.score * 100)}%" class="${c.score >= 0.6 ? "ok" : ""}"></i><span>${c.score.toFixed(2)}</span></div><span class="muted small">${esc(c.why)}</span></div>`).join("") || `<p class="muted small">회의 뒤에 채워져요.</p>`;
    const adj = A.adj || { src: {}, sig: {} }, rv = A.review;
    const chips = [...Object.entries(adj.src || {}).map(([k, v]) => [k, v]), ...Object.entries(adj.sig || {}).map(([k, v]) => ["장중·" + k, v])].filter(([, v]) => v);
    $("#dk-fb").innerHTML = `
      <div class="pp-chips">${chips.length ? chips.map(([k, v]) => `<span>${esc(k)} <b class="${cls(v)}">${v > 0 ? "+" : ""}${v.toFixed(2)}</b></span>`).join("") : `<span class="muted">아직 보정 없음</span>`}</div>
      ${rv ? `<p class="small muted" style="margin:8px 0 4px">${esc(rv.day)} 성적표 · 끝난 거래 ${rv.n}건</p><ul class="ai-orders">${(rv.lines || []).slice(0, 8).map((l) => `<li class="small">${esc(l)}</li>`).join("")}</ul>` : `<p class="small muted">첫 성적표는 금요일 마감 회의 때 나와요.</p>`}
      ${(A.adj_log || []).length ? `<div class="co-sub">조정 이력</div><ul class="ai-orders">${A.adj_log.slice(0, 10).map((a) => `<li class="small"><span class="muted">${esc(a.day)}</span> ${esc(a.text)}</li>`).join("")}</ul>` : ""}`;
    $("#dk-trades").innerHTML = A.trades.slice(0, 15).map((t) => `<li><b>${esc(t.sym)}</b> <span class="${cls(t.pl)}">${pct(t.pl)}</span><span class="muted small">${esc(t.in.slice(5))} → ${esc(t.out.slice(5))} · ${esc(t.why)}${t.src ? " · " + esc(t.src) : ""}</span></li>`).join("") || `<li class="muted">아직 없음</li>`;
  }

  function renderChat() {
    const box = $("#dk-chat"), msgs = A.chat || [];
    $("#dk-chat-sub").textContent = `${msgs.length}개 메시지`;
    let lastDay = "";
    box.innerHTML = msgs.map((c) => {
      const [nm, ini, col] = AG[c.who] || [c.who, "?", "#888"];
      const d = c.at.slice(0, 10);
      const sep = d !== lastDay ? `<div class="dk-day">${d}</div>` : ""; lastDay = d;
      if (c.sep) return sep + `<div class="dk-meet">${esc(c.text)}</div>`;
      const txt = esc(c.text).replace(/@(Scout|Filter|Analyst|Risk|Executor|Logger|Claude)/g, '<span class="dk-at">@$1</span>');
      return sep + `<div class="dk-msg"><span class="dk-av" style="--c:${col}">${ini}</span><div class="dk-bub"><div class="dk-who"><b style="color:${col}">${nm}</b><span class="muted small">${esc(c.at.slice(11))}</span></div><div>${txt}</div></div></div>`;
    }).join("") || `<p class="muted">아직 대화가 없어요.</p>`;
    box.scrollTop = box.scrollHeight;
  }

  return { onShow };
})();
