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
    measure: { pts: 2, name: "측정" },
    text: { pts: 1, name: "텍스트" },
  };
  const FIB = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
  const KEY = "tradingdesk.draw.";
  const HIT = 6;

  let host, cv, ctx, CV, onToolChange;
  let sym = "", tool = null, items = [], sel = -1, temp = null, drag = null, color = "#f2b84b", magnet = true;
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

  function label(text, x, y, bg, fg = "#0e1422", align = "left") {
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
        label(CV.fmt(d.pts[0].p), W - 2, P[0].y, c, "#0e1422", "right");
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
        ctx.fillStyle = "#0e1422"; ctx.strokeStyle = c; ctx.lineWidth = 2;
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
