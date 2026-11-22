/* =========================================================
 * 볼륨 프로파일 · POC (11/22 형 요청: 차트 옆에 넣고, 기간을 찍어서 POC 확인)
 *  - 가격대별 거래량 막대를 차트 오른쪽에 그림
 *  - POC = 거래가 가장 많이 된 가격 (실선) · VAH/VAL = 거래량 70%가 몰린 구간의 위·아래 (점선)
 *  - 기본: 지금 화면에 보이는 봉 기준 / '기간 찍기' → 시작 봉·끝 봉을 차례로 누르면 그 기간만
 *  - 근사: 봉마다 거래량을 저가~고가에 고르게 나눔 (체결 데이터가 아니라 봉 데이터라서). 짧은 봉일수록 정확
 * ========================================================= */
const VP = (() => {
  const ROWS = 48, VA = 0.7;
  let host, cv, ctx, CV, on = false, mode = "view", pick = null, rng = null, lines = [], last = "", info, btn, prof = null;

  function calc(from, to) {
    const B = CV.bars; if (!B.length) return null;
    const a = Math.max(0, Math.floor(Math.min(from, to))), b = Math.min(B.length - 1, Math.ceil(Math.max(from, to)));
    if (b - a < 1) return null;
    let lo = Infinity, hi = -Infinity, tot = 0;
    for (let i = a; i <= b; i++) { lo = Math.min(lo, B[i].l); hi = Math.max(hi, B[i].h); }
    if (!(hi > lo)) return null;
    const step = (hi - lo) / ROWS, v = new Array(ROWS).fill(0), up = new Array(ROWS).fill(0);
    for (let i = a; i <= b; i++) {
      const k = B[i], vol = k.v || 0; if (!vol) continue; tot += vol;
      const r0 = Math.min(ROWS - 1, Math.floor((k.l - lo) / step)), r1 = Math.min(ROWS - 1, Math.floor((k.h - lo) / step));
      const span = Math.max(k.h - k.l, 1e-12);
      for (let r = r0; r <= r1; r++) {
        const bl = lo + r * step, bh = bl + step;
        const part = k.h === k.l ? vol : vol * (Math.min(bh, k.h) - Math.max(bl, k.l)) / span;
        v[r] += part; if (k.c >= k.o) up[r] += part;
      }
    }
    if (!tot) return null;
    let poc = 0; for (let r = 1; r < ROWS; r++) if (v[r] > v[poc]) poc = r;
    let L = poc, H = poc, acc = v[poc];                     // 가치 영역: POC에서 양옆 큰 쪽으로 넓혀 70%까지
    while (acc < VA * tot && (L > 0 || H < ROWS - 1)) {
      const dn = L > 0 ? v[L - 1] : -1, upv = H < ROWS - 1 ? v[H + 1] : -1;
      if (upv >= dn) acc += v[++H]; else acc += v[--L];
    }
    return { a, b, lo, step, v, up, poc: lo + (poc + 0.5) * step, vah: lo + (H + 1) * step, val: lo + L * step, pr: poc, L, H, tot };
  }

  function setLines(P) {
    lines.forEach((l) => { try { CV.candle.removePriceLine(l); } catch (_) {} }); lines = [];
    if (!P) return;
    const pl = (price, title, style, w) => lines.push(CV.candle.createPriceLine({ price, color: "#f5b942", lineWidth: w, lineStyle: style, axisLabelVisible: true, title }));
    pl(P.poc, "POC", 0, 2); pl(P.vah, "VAH", 2, 1); pl(P.val, "VAL", 2, 1);
  }

  function range() {
    if (rng) return rng;
    const r = CV.chart.timeScale().getVisibleLogicalRange(); if (!r) return null;
    return [Math.max(0, r.from), Math.min(CV.bars.length - 1, r.to)];
  }

  function resize() {
    const d = window.devicePixelRatio || 1, w = host.clientWidth, h = host.clientHeight;
    cv.width = w * d; cv.height = h * d; cv.style.width = w + "px"; cv.style.height = h + "px"; ctx.setTransform(d, 0, 0, d, 0, 0); last = "";
  }

  function loop() {
    requestAnimationFrame(loop);
    if (!on) { if (last !== "off") { ctx.clearRect(0, 0, cv.width, cv.height); setLines(null); last = "off"; } return; }
    const R = range(); if (!R) return;
    const y0 = CV.candle.priceToCoordinate(CV.bars.length ? CV.bars[CV.bars.length - 1].c : 0);
    const key = [R[0].toFixed(1), R[1].toFixed(1), CV.bars.length, CV.bars.length && CV.bars[CV.bars.length - 1].v, y0 && y0.toFixed(1), CV.plotWidth(), mode, pick, CV.sym, CV.iv].join("|");
    if (key === last) return; last = key;
    const k2 = [Math.round(R[0]), Math.round(R[1]), CV.bars.length, CV.sym, CV.iv].join("|");
    if (!prof || prof.k !== k2) { prof = calc(R[0], R[1]); if (prof) prof.k = k2; setLines(prof); showInfo(); }
    draw(prof);
  }

  function draw(P) {
    const w = host.clientWidth, h = host.clientHeight; ctx.clearRect(0, 0, w, h);
    const ts = CV.chart.timeScale();
    let box = null;
    if (rng || mode === "pick2") {                          // 고른 기간 음영
      const a = rng ? rng[0] : pick, b = rng ? rng[1] : pick;
      const lo = Math.min(a, b), hi = Math.max(a, b), c0 = ts.logicalToCoordinate(lo), c1 = ts.logicalToCoordinate(hi);   // v5는 소수 논리 좌표를 못 받음 → 봉 중심 ± 봉 간격/2
      const sp = c0 != null && ts.logicalToCoordinate(lo + 1) != null ? ts.logicalToCoordinate(lo + 1) - c0 : 6;
      const xa = c0 == null ? null : c0 - sp / 2, xb = c1 == null ? null : c1 + sp / 2;
      if (xa != null && xb != null) {
        ctx.fillStyle = "rgba(245,185,66,.07)"; ctx.fillRect(xa, 0, Math.max(1, xb - xa), CV.mainHeight());
        ctx.strokeStyle = "rgba(245,185,66,.55)"; ctx.setLineDash([4, 4]); ctx.lineWidth = 1;
        if (rng) box = [xa, xb];
        [xa, xb].forEach((x) => { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, CV.mainHeight()); ctx.stroke(); }); ctx.setLineDash([]);
      }
    }
    if (!P) return;
    // 고른 기간이면 그 기간 박스 안 왼쪽에서 오른쪽으로(트레이딩뷰 '고정 범위'처럼), 아니면 차트 오른쪽 끝에서 왼쪽으로
    const pw = CV.plotWidth(), inBox = box && box[1] - box[0] > 30;
    const maxW = inBox ? Math.min((box[1] - box[0]) * 0.7, 260) : Math.min(pw * (window.innerWidth < 640 ? 0.32 : 0.22), 220), right = pw - 2;
    const mx = Math.max(...P.v);
    for (let r = 0; r < ROWS; r++) {
      if (!P.v[r]) continue;
      const yT = CV.candle.priceToCoordinate(P.lo + (r + 1) * P.step), yB = CV.candle.priceToCoordinate(P.lo + r * P.step);
      if (yT == null || yB == null) continue;
      const hh = Math.max(1, yB - yT - 1), len = (P.v[r] / mx) * maxW, inVA = r >= P.L && r <= P.H, upLen = len * (P.up[r] / P.v[r]);
      const al = r === P.pr ? 0.75 : inVA ? 0.42 : 0.18;
      const x0 = inBox ? box[0] : right - len;
      ctx.fillStyle = `rgba(255,95,107,${al})`; ctx.fillRect(x0, yT, upLen, hh);              // 양봉 거래량
      ctx.fillStyle = `rgba(78,163,255,${al})`; ctx.fillRect(x0 + upLen, yT, len - upLen, hh);  // 음봉 거래량
      if (r === P.pr) { ctx.strokeStyle = "#f5b942"; ctx.lineWidth = 1; ctx.strokeRect(x0, yT, len, hh); }
    }
  }

  function showInfo() {
    if (!info) return;
    const P = prof, B = CV.bars, f = CV.fmt;
    const tm = (i) => { const b = B[i]; if (!b) return ""; return typeof b.t === "string" ? b.t.slice(5) : new Date(b.t * 1000).toISOString().slice(5, 16).replace("T", " ").replace("-", "/"); };
    if (mode === "pick1") info.innerHTML = `<b>기간 찍기</b> 시작 봉을 누르세요 <button class="float-btn" data-vp="cancel">취소</button>`;
    else if (mode === "pick2") info.innerHTML = `<b>기간 찍기</b> 끝 봉을 누르세요 <button class="float-btn" data-vp="cancel">취소</button>`;
    else if (!P) info.innerHTML = `거래량 자료가 없어 POC를 못 구해요`;
    else {
      const px = B.length ? B[B.length - 1].c : null, where = px == null ? "" : px > P.vah ? "가치 영역 위" : px < P.val ? "가치 영역 아래" : "가치 영역 안";
      info.innerHTML = `<span class="vp-k">${rng ? "고른 기간" : "화면 기준"} · ${tm(P.a)} ~ ${tm(P.b)} (${P.b - P.a + 1}봉)</span>
        <span><b class="vp-poc">POC ${f(P.poc)}</b> · VAH ${f(P.vah)} · VAL ${f(P.val)}${where ? `<i class="vp-w"> · 현재가 ${where}</i>` : ""}</span>
        <span class="vp-btns"><button class="float-btn" data-vp="pick">기간 찍기</button>${rng ? `<button class="float-btn" data-vp="reset">화면 기준으로</button>` : ""}</span>`;
    }
    info.hidden = !on; info.classList.toggle("picked", !!rng);
  }

  function onClick(p) {
    if (!on || (mode !== "pick1" && mode !== "pick2") || !p || p.logical == null) return;
    const l = Math.max(0, Math.min(CV.bars.length - 1, Math.round(p.logical)));
    if (mode === "pick1") { pick = l; mode = "pick2"; }
    else { rng = [Math.min(pick, l), Math.max(pick, l)]; if (rng[1] - rng[0] < 1) rng[1] = Math.min(CV.bars.length - 1, rng[0] + 1); mode = "view"; pick = null; prof = null; }
    last = ""; showInfo();
  }

  function init(hostEl, chartView) {
    host = hostEl; CV = chartView;
    cv = document.createElement("canvas"); cv.className = "vp-layer"; host.appendChild(cv); ctx = cv.getContext("2d");
    info = document.createElement("div"); info.className = "vp-info no-gloss"; info.hidden = true; host.appendChild(info);
    info.addEventListener("click", (e) => {
      const b = e.target.closest("[data-vp]"); if (!b) return; e.stopPropagation();
      const a = b.dataset.vp;
      if (a === "pick") { mode = "pick1"; pick = null; if (typeof Draw !== "undefined" && Draw.tool) Draw.setTool(null); }
      else if (a === "cancel") { mode = "view"; pick = null; }
      else if (a === "reset") { rng = null; prof = null; }
      last = ""; showInfo();
    });
    CV.chart.subscribeClick(onClick);
    new ResizeObserver(resize).observe(host); resize();
    requestAnimationFrame(loop);
  }
  function set(v) { on = !!v; if (!on) { mode = "view"; pick = null; } last = ""; prof = null; showInfo(); }
  function reset() { rng = null; mode = "view"; pick = null; prof = null; last = ""; showInfo(); }   // 종목·봉 주기 바뀌면 기간 해제
  return { init, set, reset, get on() { return on; } };
})();
