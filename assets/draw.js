/* =========================================================
 * 차트 그리기 도구
 *  추세선 · 연장선 · 수평선 · 수직선 · 박스 · 피보나치 · 측정 · 텍스트
 *  - 점은 {t: 시각(ms), p: 가격}으로 저장 → 봉 주기를 바꿔도 같은 자리에 그려짐
 *  - 종목별로 브라우저에 저장
 *  - 커서 모드에서 선을 클릭하면 선택, 끌어서 이동, 끝점 끌어서 수정, Delete 키로 삭제
 * ========================================================= */
const Draw = (() => {
  const TOOLS = {
    trend: { pts: 2, name: "추세선" },
    ray: { pts: 2, name: "연장선" },
    hline: { pts: 1, name: "수평선" },
    vline: { pts: 1, name: "수직선" },
    rect: { pts: 2, name: "박스" },
    fib: { pts: 2, name: "피보나치" },
    vp: { pts: 2, name: "POC" },
    pos: { pts: 2, name: "손절·익절" },
    measure: { pts: 2, name: "측정" },
    text: { pts: 1, name: "텍스트" },
  };
  const FIB = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
  // 손절·익절 박스: pts = [진입(시작 시각·진입가), 목표(끝 시각·목표가), 손절(끝 시각·손절가)] · 목표가 진입보다 위면 롱, 아래면 숏
  function posFix(d) {
    if (!d.pts[2]) { const e = d.pts[0].p, tg = d.pts[1].p; d.pts[2] = { t: d.pts[1].t, p: e - (tg - e) / 2 }; }   // 처음 손절은 손익비 2:1 자리
    if (d.pts[1].t < d.pts[0].t) { const t = d.pts[0].t; d.pts[0].t = d.pts[1].t; d.pts[1].t = t; }
    d.pts[2].t = d.pts[1].t;
  }
  function posResult(d) {                                  // 진입 뒤 박스 끝까지 목표·손절 중 먼저 닿은 것
    const B = CV.bars, e = d.pts[0].p, tg = d.pts[1].p, sl = d.pts[2].p, L = tg > e;
    let i = Math.max(0, Math.ceil(CV.msToLogical(d.pts[0].t))); const end = Math.min(B.length - 1, Math.floor(CV.msToLogical(d.pts[1].t)));
    for (; i <= end; i++) { const b = B[i]; if (b.l <= e && b.h >= e) break; }    // 진입가에 닿아야 체결
    if (i > end) return { k: "none" };
    for (; i <= end; i++) {
      const b = B[i], hitS = L ? b.l <= sl : b.h >= sl, hitT = L ? b.h >= tg : b.l <= tg;
      if (hitS) return { k: "stop", i }; if (hitT) return { k: "tgt", i };
    }
    return null;
  }
  // POC: 고른 기간의 가격대별 거래량 (봉 거래량을 저가~고가에 고르게 나눈 근사) · POC = 최다 거래 가격 · VAH/VAL = 거래량 70% 구간
  const VPROWS = 40, vpCache = new Map();
  function vprof(t0, t1) {
    const B = CV.bars; if (!B.length) return null;
    let a = Math.round(CV.msToLogical(Math.min(t0, t1))), b = Math.round(CV.msToLogical(Math.max(t0, t1)));
    a = Math.max(0, a); b = Math.min(B.length - 1, b); if (b - a < 1) return null;
    const key = [a, b, B.length, B[b].ms, B[b].v, B[b].c].join("|"); if (vpCache.has(key)) return vpCache.get(key);
    let lo = Infinity, hi = -Infinity, tot = 0;
    for (let i = a; i <= b; i++) { lo = Math.min(lo, B[i].l); hi = Math.max(hi, B[i].h); }
    if (!(hi > lo)) return null;
    const st = (hi - lo) / VPROWS, v = new Array(VPROWS).fill(0), up = new Array(VPROWS).fill(0);
    for (let i = a; i <= b; i++) {
      const k = B[i], vol = k.v || 0; if (!vol) continue; tot += vol;
      const r0 = Math.min(VPROWS - 1, Math.floor((k.l - lo) / st)), r1 = Math.min(VPROWS - 1, Math.floor((k.h - lo) / st)), span = k.h - k.l;
      for (let r = r0; r <= r1; r++) {
        const bl = lo + r * st, part = span > 0 ? vol * (Math.min(bl + st, k.h) - Math.max(bl, k.l)) / span : vol;
        v[r] += part; if (k.c >= k.o) up[r] += part;
      }
    }
    let P = null;
    if (tot) {
      let pr = 0; for (let r = 1; r < VPROWS; r++) if (v[r] > v[pr]) pr = r;
      let L = pr, H = pr, acc = v[pr];
      while (acc < 0.7 * tot && (L > 0 || H < VPROWS - 1)) { const d = L > 0 ? v[L - 1] : -1, u = H < VPROWS - 1 ? v[H + 1] : -1; if (u >= d) acc += v[++H]; else acc += v[--L]; }
      P = { a, b, lo, hi, st, v, up, pr, L, H, poc: lo + (pr + 0.5) * st, vah: lo + (H + 1) * st, val: lo + L * st };
    }
    if (vpCache.size > 50) vpCache.clear(); vpCache.set(key, P); return P;
  }
  const KEY = "tradingdesk.draw.";
  const HIT = 6;

  let host, cv, ctx, CV, onToolChange;
  let sym = "", tool = null, items = [], sel = -1, temp = null, drag = null, color = "#ffffff", magnet = true;
  let downAt = null, sig = "", dirty = true, hover = -1;

  // ---------- 저장 ----------
  const save = () => { try { localStorage.setItem(KEY + sym, JSON.stringify(items)); } catch (_) {} };
  const load = () => { try { items = JSON.parse(localStorage.getItem(KEY + sym) || "[]"); } catch (_) { items = []; } };

  // ---------- 좌표 ----------
  const ts = () => CV.chart.timeScale();
  function toXY(pt) {
    const x = ts().logicalToCoordinate(CV.msToLogical(pt.t));
    const y = CV.candle.priceToCoordinate(pt.p);
    return { x: x == null ? NaN : x, y: y == null ? NaN : y };
  }
  function fromXY(x, y, useMagnet = magnet) {
    let l = ts().coordinateToLogical(x);
    let p = CV.candle.coordinateToPrice(y);
    if (l == null || p == null) return null;
    if (useMagnet) {
      const i = Math.round(l), b = CV.bars[i];
      if (b) {
        const cand = [b.o, b.h, b.l, b.c].map((v) => [v, Math.abs(CV.candle.priceToCoordinate(v) - y)]).sort((a, c) => a[1] - c[1])[0];
        if (cand[1] < 24) { p = cand[0]; l = i; }
      }
    }
    return { t: CV.logicalToMs(l), p };
  }
  const plotW = () => CV.plotWidth();
  const plotH = () => CV.mainHeight();
  const inPlot = (x, y) => x >= 0 && y >= 0 && x <= plotW() && y <= plotH();

  // ---------- 그리기 ----------
  function resize() {
    const r = host.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    cv.width = Math.round(r.width * dpr); cv.height = Math.round(r.height * dpr);
    cv.style.width = r.width + "px"; cv.style.height = r.height + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    dirty = true;
  }
  function signature() {
    const r = ts().getVisibleLogicalRange();
    return [r && r.from, r && r.to, CV.candle.priceToCoordinate(CV.bars.length ? CV.bars[CV.bars.length - 1].c : 0), plotW(), plotH(), cv.width, cv.height].join("|");
  }
  function loop() {
    if (CV.bars.length) {
      const s = signature();
      if (s !== sig || dirty) { sig = s; dirty = false; render(); }
    }
    requestAnimationFrame(loop);
  }

  function label(text, x, y, bg, fg = "#000000", align = "left") {
    ctx.font = "600 11px Pretendard Variable, Pretendard, system-ui, sans-serif";
    const w = ctx.measureText(text).width + 10, h = 18;
    const lx = align === "right" ? x - w : align === "center" ? x - w / 2 : x;
    ctx.fillStyle = bg; roundRect(lx, y - h / 2, w, h, 4); ctx.fill();
    ctx.fillStyle = fg; ctx.textBaseline = "middle"; ctx.fillText(text, lx + 5, y + 0.5);
  }
  function roundRect(x, y, w, h, r) {
    ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }
  const alpha = (hex, a) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };

  function drawItem(d, selected) {
    const P = d.pts.map(toXY);
    if (P.some((q) => isNaN(q.x) || isNaN(q.y)) && d.type !== "vline" && d.type !== "hline") return;
    const c = d.color || color, W = plotW(), H = plotH();
    ctx.strokeStyle = c; ctx.fillStyle = c; ctx.lineWidth = selected ? 2 : 1.5; ctx.setLineDash([]);
    const seg = (a, b) => { ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); };
    switch (d.type) {
      case "trend": seg(P[0], P[1]); break;
      case "ray": {
        const dx = P[1].x - P[0].x, dy = P[1].y - P[0].y;
        const k = dx === 0 ? 0 : ((dx > 0 ? W : 0) - P[0].x) / dx;
        seg(P[0], dx === 0 ? { x: P[0].x, y: dy > 0 ? H : 0 } : { x: P[0].x + dx * k, y: P[0].y + dy * k });
        break;
      }
      case "hline": {
        if (isNaN(P[0].y)) return;
        seg({ x: 0, y: P[0].y }, { x: W, y: P[0].y });
        label(CV.fmt(d.pts[0].p), W - 2, P[0].y, c, "#000000", "right");
        break;
      }
      case "vline": if (!isNaN(P[0].x)) seg({ x: P[0].x, y: 0 }, { x: P[0].x, y: H }); break;
      case "rect": {
        const x = Math.min(P[0].x, P[1].x), y = Math.min(P[0].y, P[1].y), w = Math.abs(P[1].x - P[0].x), h = Math.abs(P[1].y - P[0].y);
        ctx.fillStyle = alpha(c, 0.12); ctx.fillRect(x, y, w, h); ctx.strokeRect(x, y, w, h);
        break;
      }
      case "fib": {
        const x1 = Math.min(P[0].x, P[1].x), x2 = Math.max(P[0].x, P[1].x, W);
        const [a, b] = [d.pts[0].p, d.pts[1].p];
        FIB.forEach((lv, k) => {
          const price = b + (a - b) * lv, y = CV.candle.priceToCoordinate(price);
          if (y == null) return;
          if (k < FIB.length - 1) {
            const y2 = CV.candle.priceToCoordinate(b + (a - b) * FIB[k + 1]);
            if (y2 != null) { ctx.fillStyle = alpha(c, k % 2 ? 0.05 : 0.1); ctx.fillRect(x1, Math.min(y, y2), x2 - x1, Math.abs(y2 - y)); }
          }
          ctx.strokeStyle = alpha(c, lv === 0 || lv === 1 ? 1 : 0.7); seg({ x: x1, y }, { x: x2, y });
          ctx.fillStyle = c; ctx.font = "600 11px Pretendard Variable, Pretendard, system-ui, sans-serif"; ctx.textBaseline = "bottom";
          ctx.fillText(`${lv} (${CV.fmt(price)})`, x1 + 4, y - 2);
        });
        ctx.setLineDash([4, 4]); ctx.strokeStyle = alpha(c, 0.6); seg(P[0], P[1]); ctx.setLineDash([]);
        break;
      }
      case "pos": {
        const pts = d.pts[2] ? d.pts : [d.pts[0], d.pts[1], { t: d.pts[1].t, p: d.pts[0].p - (d.pts[1].p - d.pts[0].p) / 2 }];
        const e = pts[0].p, tg = pts[1].p, sl = pts[2].p, L = tg >= e;
        const x1 = Math.min(P[0].x, P[1].x), x2 = Math.max(P[0].x, P[1].x), w = Math.max(2, x2 - x1);
        const ye = CV.candle.priceToCoordinate(e), yt = CV.candle.priceToCoordinate(tg), ys = CV.candle.priceToCoordinate(sl);
        if (ye == null || yt == null || ys == null) break;
        const G = "#26a65b", R = "#f0525c";
        ctx.fillStyle = alpha(G, 0.2); ctx.fillRect(x1, Math.min(ye, yt), w, Math.abs(yt - ye));
        ctx.fillStyle = alpha(R, 0.2); ctx.fillRect(x1, Math.min(ye, ys), w, Math.abs(ys - ye));
        ctx.lineWidth = 1; ctx.strokeStyle = alpha(G, 0.9); seg({ x: x1, y: yt }, { x: x2, y: yt });
        ctx.strokeStyle = alpha(R, 0.9); seg({ x: x1, y: ys }, { x: x2, y: ys });
        ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 1.5; seg({ x: x1, y: ye }, { x: x2, y: ye });
        const res = d.pts[2] ? posResult(d) : null;
        if (res && res.k !== "none") {                     // 실제로 먼저 닿은 쪽 표시
          const xr = ts().logicalToCoordinate(res.i);
          if (xr != null) { ctx.setLineDash([3, 3]); ctx.strokeStyle = res.k === "tgt" ? G : R; seg({ x: xr, y: ye }, { x: xr, y: res.k === "tgt" ? yt : ys }); ctx.setLineDash([]); }
        }
        const pc = (p) => ((p / e - 1) * 100), rr = Math.abs(tg - e) / Math.max(1e-12, Math.abs(e - sl));
        const mid = x1 + w / 2;
        label(`목표 ${CV.fmt(tg)} (${pc(tg) >= 0 ? "+" : ""}${pc(tg).toFixed(2)}%)`, mid, yt + (L ? -11 : 11), G, "#fff", "center");
        label(`손절 ${CV.fmt(sl)} (${pc(sl) >= 0 ? "+" : ""}${pc(sl).toFixed(2)}%)`, mid, ys + (L ? 11 : -11), R, "#fff", "center");
        label(`${L ? "롱" : "숏"} ${CV.fmt(e)} · 손익비 ${rr.toFixed(2)}${res ? (res.k === "tgt" ? " · 목표 도달 ✓" : res.k === "stop" ? " · 손절 ✗" : " · 진입가 미체결") : ""}`, mid, ye, "rgba(20,20,22,.92)", "#fff", "center");
        break;
      }
      case "vp": {
        const x1 = Math.min(P[0].x, P[1].x), x2 = Math.max(P[0].x, P[1].x), w = x2 - x1;
        const V = vprof(d.pts[0].t, d.pts[1].t);
        if (!V) { ctx.setLineDash([4, 4]); ctx.strokeStyle = alpha(c, 0.6); ctx.strokeRect(x1, Math.min(P[0].y, P[1].y), w, Math.abs(P[1].y - P[0].y)); ctx.setLineDash([]); break; }
        const Y = (p) => CV.candle.priceToCoordinate(p), yT = Y(V.hi), yB = Y(V.lo);
        if (yT == null || yB == null) break;
        ctx.fillStyle = alpha(c, 0.05); ctx.fillRect(x1, yT, w, yB - yT);
        ctx.setLineDash([3, 3]); ctx.strokeStyle = alpha(c, 0.35); ctx.lineWidth = 1; ctx.strokeRect(x1, yT, w, yB - yT); ctx.setLineDash([]);
        const mx = Math.max(...V.v), maxW = Math.max(20, w * 0.7);
        for (let r = 0; r < VPROWS; r++) {
          if (!V.v[r]) continue;
          const y1 = Y(V.lo + (r + 1) * V.st), y2 = Y(V.lo + r * V.st); if (y1 == null || y2 == null) continue;
          const len = (V.v[r] / mx) * maxW, ul = len * V.up[r] / V.v[r], hh = Math.max(1, y2 - y1 - 1);
          const al = r === V.pr ? 0.8 : r >= V.L && r <= V.H ? 0.45 : 0.2;
          ctx.fillStyle = `rgba(255,95,107,${al})`; ctx.fillRect(x1, y1, ul, hh);
          ctx.fillStyle = `rgba(78,163,255,${al})`; ctx.fillRect(x1 + ul, y1, len - ul, hh);
        }
        const yp = Y(V.poc);   // 글자표가 겹치지 않게 VAH는 위로, VAL은 아래로 밀기
        const lineAt = (p, lb, dash, lw) => {
          const y = Y(p); if (y == null) return;
          const ly = yp == null || lb === "POC" ? y : lb === "VAH" ? Math.min(y, yp - 19) : Math.max(y, yp + 19);
          ctx.setLineDash(dash); ctx.lineWidth = lw; ctx.strokeStyle = "#f5b942"; seg({ x: x1, y }, { x: x2, y }); ctx.setLineDash([]);
          label(`${lb} ${CV.fmt(p)}`, x2 + 110 > W ? x2 - 4 : x2 + 4, ly, lb === "POC" ? "#f5b942" : "rgba(245,185,66,.75)", "#000000", x2 + 110 > W ? "right" : "left");
        };
        lineAt(V.vah, "VAH", [4, 3], 1); lineAt(V.val, "VAL", [4, 3], 1); lineAt(V.poc, "POC", [], 2);
        break;
      }
      case "measure": {
        const up = d.pts[1].p >= d.pts[0].p, mc = up ? "#f0525c" : "#3d8bfd";
        const x = Math.min(P[0].x, P[1].x), y = Math.min(P[0].y, P[1].y), w = Math.abs(P[1].x - P[0].x), h = Math.abs(P[1].y - P[0].y);
        ctx.fillStyle = alpha(mc, 0.16); ctx.fillRect(x, y, w, h);
        ctx.strokeStyle = mc; seg({ x: P[0].x, y: P[0].y }, { x: P[0].x, y: P[1].y }); seg({ x: P[0].x, y: P[1].y }, { x: P[1].x, y: P[1].y });
        const diff = d.pts[1].p - d.pts[0].p, pct = (diff / d.pts[0].p) * 100;
        const nb = Math.round(CV.msToLogical(d.pts[1].t) - CV.msToLogical(d.pts[0].t));
        label(`${diff >= 0 ? "+" : ""}${CV.fmt(diff)} (${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%) · ${Math.abs(nb)}봉`, x + w / 2, up ? y - 12 : y + h + 12, mc, "#fff", "center");
        break;
      }
      case "text": label(d.text || "", P[0].x, P[0].y, alpha(c, 0.92)); break;
    }
    if (selected || d === temp) {
      d.pts.forEach((pt) => {
        const q = toXY(pt);
        let { x, y } = q;
        if (d.type === "hline") x = isNaN(x) ? W / 2 : Math.min(Math.max(x, 8), W - 8);
        if (d.type === "vline") y = plotH() / 2;
        if (isNaN(x) || isNaN(y)) return;
        ctx.fillStyle = "#000000"; ctx.strokeStyle = c; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      });
    }
  }

  function render() {
    const r = host.getBoundingClientRect();
    ctx.clearRect(0, 0, r.width, r.height);
    ctx.save();
    ctx.beginPath(); ctx.rect(0, 0, plotW(), plotH()); ctx.clip();
    items.forEach((d, i) => drawItem(d, i === sel || i === hover));
    if (temp) drawItem(temp, true);
    ctx.restore();
  }

  // ---------- 선택 판정 ----------
  function distSeg(px, py, a, b) {
    const dx = b.x - a.x, dy = b.y - a.y, L = dx * dx + dy * dy;
    let t = L ? ((px - a.x) * dx + (py - a.y) * dy) / L : 0;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(px - (a.x + t * dx), py - (a.y + t * dy));
  }
  function hitItem(x, y) {
    for (let i = items.length - 1; i >= 0; i--) {
      const d = items[i], P = d.pts.map(toXY), W = plotW();
      let hit = false;
      switch (d.type) {
        case "trend": hit = distSeg(x, y, P[0], P[1]) < HIT; break;
        case "ray": {
          const dx = P[1].x - P[0].x, dy = P[1].y - P[0].y, k = dx ? ((dx > 0 ? W : 0) - P[0].x) / dx : 0;
          hit = distSeg(x, y, P[0], { x: P[0].x + dx * k, y: P[0].y + dy * k }) < HIT; break;
        }
        case "hline": hit = Math.abs(y - P[0].y) < HIT; break;
        case "vline": hit = Math.abs(x - P[0].x) < HIT; break;
        case "rect": case "measure": {
          const x1 = Math.min(P[0].x, P[1].x), x2 = Math.max(P[0].x, P[1].x), y1 = Math.min(P[0].y, P[1].y), y2 = Math.max(P[0].y, P[1].y);
          hit = x >= x1 - HIT && x <= x2 + HIT && y >= y1 - HIT && y <= y2 + HIT; break;
        }
        case "pos": {
          if (!d.pts[2]) break;
          const x1 = Math.min(P[0].x, P[1].x), x2 = Math.max(P[0].x, P[1].x), ys = toXY(d.pts[2]).y;
          hit = x >= x1 - HIT && x <= x2 + HIT && y >= Math.min(P[1].y, ys) - HIT && y <= Math.max(P[1].y, ys) + HIT; break;
        }
        case "vp": {
          const V = vprof(d.pts[0].t, d.pts[1].t), x1 = Math.min(P[0].x, P[1].x), x2 = Math.max(P[0].x, P[1].x);
          const ya = V ? CV.candle.priceToCoordinate(V.hi) : Math.min(P[0].y, P[1].y), yb = V ? CV.candle.priceToCoordinate(V.lo) : Math.max(P[0].y, P[1].y);
          hit = x >= x1 - HIT && x <= x2 + HIT && y >= ya - HIT && y <= yb + HIT; break;
        }
        case "fib": {
          const x1 = Math.min(P[0].x, P[1].x), y1 = Math.min(P[0].y, P[1].y), y2 = Math.max(P[0].y, P[1].y);
          hit = x >= x1 - HIT && y >= y1 - HIT && y <= y2 + HIT; break;
        }
        case "text": hit = x >= P[0].x - 4 && x <= P[0].x + 8 + (d.text || "").length * 9 && Math.abs(y - P[0].y) < 12; break;
      }
      if (hit) return i;
    }
    return -1;
  }
  function hitHandle(x, y) {
    if (sel < 0) return -1;
    const d = items[sel];
    for (let k = 0; k < d.pts.length; k++) {
      const q = toXY(d.pts[k]);
      if (d.type === "hline" || d.type === "vline") continue;
      if (Math.hypot(x - q.x, y - q.y) < 9) return k;
    }
    return -1;
  }

  // ---------- 마우스/터치 ----------
  const pos = (e) => { const r = host.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
  const stop = (e) => { e.stopPropagation(); e.preventDefault(); };

  function finish() {
    if (!temp) return;
    if (temp.type === "text") {
      const t = window.prompt("표시할 글자를 입력하세요");
      if (!t) { temp = null; dirty = true; return; }
      temp.text = t;
    }
    if (temp.type === "pos") posFix(temp);
    items.push(temp); sel = items.length - 1; temp = null; save();
    setTool(null); dirty = true;
  }

  function onDown(e) {
    if (e.button !== undefined && e.button !== 0) return;
    const { x, y } = pos(e);
    if (!inPlot(x, y)) return;
    if (tool) {
      stop(e);
      const pt = fromXY(x, y);
      if (!pt) return;
      if (temp) { temp.pts[1] = pt; finish(); return; }
      temp = { type: tool, pts: TOOLS[tool].pts === 1 ? [pt] : [pt, { ...pt }], color };
      if (TOOLS[tool].pts === 1) { finish(); return; }
      downAt = { x, y };
      host.setPointerCapture && host.setPointerCapture(e.pointerId);
      dirty = true;
      return;
    }
    const h = hitHandle(x, y);
    if (h >= 0) { stop(e); drag = { mode: "handle", k: h, i: sel }; return; }
    const i = hitItem(x, y);
    if (i >= 0) {
      stop(e);
      sel = i;
      const start = fromXY(x, y, false);
      drag = { mode: "move", i, start, orig: items[i].pts.map((p) => ({ ...p })), ol: items[i].pts.map((p) => CV.msToLogical(p.t)), sl: ts().coordinateToLogical(x) };
      dirty = true;
      return;
    }
    if (sel >= 0) { sel = -1; dirty = true; }
  }

  function onMove(e) {
    const { x, y } = pos(e);
    if (temp) {
      const pt = fromXY(x, y);
      if (pt) { temp.pts[1] = pt; dirty = true; }
      stop(e); return;
    }
    if (drag) {
      stop(e);
      const d = items[drag.i];
      if (drag.mode === "handle") {
        const pt = fromXY(x, y); if (pt) d.pts[drag.k] = pt;
        if (d.type === "pos" && pt && drag.k > 0) d.pts[3 - drag.k].t = pt.t;   // 목표·손절은 같은 끝 시각
      } else {
        const now = fromXY(x, y, false), l = ts().coordinateToLogical(x);
        if (!now || l == null) return;
        const dp = now.p - drag.start.p, dl = l - drag.sl;
        d.pts = drag.orig.map((p, k) => ({ t: CV.logicalToMs(drag.ol[k] + dl), p: p.p + dp }));
      }
      dirty = true; return;
    }
    if (!tool && inPlot(x, y)) {
      const i = hitHandle(x, y) >= 0 ? sel : hitItem(x, y);
      if (i !== hover) { hover = i; dirty = true; }
      host.style.cursor = i >= 0 ? "pointer" : "";
    } else if (tool) host.style.cursor = "crosshair";
  }

  function onUp(e) {
    if (temp && downAt) {
      const { x, y } = pos(e);
      // 끌어서 그렸으면 바로 완료, 그냥 클릭이면 두 번째 클릭을 기다림
      if (Math.hypot(x - downAt.x, y - downAt.y) > 6) finish();
      downAt = null;
    }
    if (drag) { drag = null; save(); }
  }

  function onKey(e) {
    if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement && document.activeElement.tagName)) return;
    if ((e.key === "Delete" || e.key === "Backspace") && sel >= 0) { items.splice(sel, 1); sel = -1; save(); dirty = true; e.preventDefault(); }
    if (e.key === "Escape") { temp = null; setTool(null); sel = -1; dirty = true; }
  }

  // ---------- 공개 ----------
  function init(hostEl, chartView, cb) {
    host = hostEl; CV = chartView; onToolChange = cb || (() => {});
    cv = document.createElement("canvas");
    cv.className = "draw-layer";
    host.appendChild(cv);
    ctx = cv.getContext("2d");
    host.addEventListener("pointerdown", onDown, true);
    host.addEventListener("pointermove", onMove, true);
    window.addEventListener("pointerup", onUp, true);
    window.addEventListener("keydown", onKey);
    new ResizeObserver(resize).observe(host);
    resize();
    requestAnimationFrame(loop);
  }
  function setTool(t) {
    tool = t && TOOLS[t] ? t : null;
    temp = null;
    CV.chart.applyOptions({ handleScroll: !tool, handleScale: !tool });
    host.style.cursor = tool ? "crosshair" : "";
    onToolChange(tool);
  }
  function setSymbol(s) { sym = s; load(); sel = -1; temp = null; dirty = true; }
  function clearAll() { if (!items.length) return; items = []; sel = -1; save(); dirty = true; }
  function deleteSelected() { if (sel >= 0) { items.splice(sel, 1); sel = -1; save(); dirty = true; } }
  function setColor(c) { color = c; if (sel >= 0) { items[sel].color = c; save(); } dirty = true; }
  function setMagnet(on) { magnet = on; }

  return { TOOLS, init, setTool, setSymbol, clearAll, deleteSelected, setColor, setMagnet, redraw: () => (dirty = true),
    get count() { return items.length; }, get tool() { return tool; }, get magnet() { return magnet; } };
})();
