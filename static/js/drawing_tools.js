/**
 * TradingView-Style Interactive Drawing Tools Manager (v2.0)
 * Supports:
 * - Tools: Pointer, Horizontal Line, 2-Point Trendline, Shaded Zone Box, Long/Short RR Tool, Clear All
 * - Full Interactivity: Click to Select, Drag Body to Move, Drag Anchor Handles to Reshape,
 *   Floating Object Edit Toolbar (Color, Line Width, Dashed/Solid, Label, Delete),
 *   Keyboard Delete/Backspace, and localStorage persistence.
 */
class DrawingToolsManager {
  constructor(chartManager) {
    this.cm = chartManager;
    this.activeTool = 'pointer';
    this.pendingPoint = null;
    this.selected = null; // { key, id }
    this.dragState = null; // { key, id, mode: 'move'|'p1'|'p2'|'entry'|'sl'|'tp'|'top'|'bot', startX, startY, orig }
    this.svgs = {};
    this.drawings = this.loadFromStorage();

    this.initSvgOverlays();
    this.initFloatingToolbar();
    this.bindToolbar();
    this.bindChartEvents();
    this.startSyncLoop();
  }

  getTargets() {
    return [
      { key: 'H4', container: this.cm.containerH4, chart: this.cm.chartH4, series: this.cm.seriesH4 },
      { key: 'TF2', container: this.cm.containerTF2, chart: this.cm.chartTF2, series: this.cm.seriesTF2 },
      { key: 'M15', container: this.cm.containerM15, chart: this.cm.chartM15, series: this.cm.seriesM15 }
    ].filter(t => t.container && t.chart && t.series);
  }

  getTarget(key) {
    return this.getTargets().find(t => t.key === key) || null;
  }

  loadFromStorage() {
    try {
      const raw = JSON.parse(localStorage.getItem('tvDrawings_v2') || 'null');
      if (raw && typeof raw === 'object') {
        return {
          H4: Array.isArray(raw.H4) ? raw.H4 : [],
          TF2: Array.isArray(raw.TF2) ? raw.TF2 : [],
          M15: Array.isArray(raw.M15) ? raw.M15 : []
        };
      }
    } catch (e) {}
    return { H4: [], TF2: [], M15: [] };
  }

  saveToStorage() {
    try {
      localStorage.setItem('tvDrawings_v2', JSON.stringify(this.drawings));
    } catch (e) {}
  }

  initSvgOverlays() {
    const ns = 'http://www.w3.org/2000/svg';
    this.getTargets().forEach(({ key, container }) => {
      let svg = container.querySelector(`.tv-draw-svg[data-key="${key}"]`);
      if (!svg) {
        svg = document.createElementNS(ns, 'svg');
        svg.setAttribute('class', 'tv-draw-svg');
        svg.setAttribute('data-key', key);
        container.appendChild(svg);
      }
      this.svgs[key] = svg;
    });
  }

  initFloatingToolbar() {
    let tb = document.getElementById('tvDrawFloatingToolbar');
    if (!tb) {
      tb = document.createElement('div');
      tb.id = 'tvDrawFloatingToolbar';
      tb.className = 'tv-draw-toolbar-float';
      tb.innerHTML = `
        <span class="tv-dtb-title" id="tvDtbTitle">Object</span>
        <div class="tv-dtb-sep"></div>
        <div class="tv-dtb-colors" id="tvDtbColors">
          <button class="tv-dtb-swatch" data-color="#38bdf8" style="background:#38bdf8;" title="Xanh dương"></button>
          <button class="tv-dtb-swatch" data-color="#f59e0b" style="background:#f59e0b;" title="Vàng cam"></button>
          <button class="tv-dtb-swatch" data-color="#10b981" style="background:#10b981;" title="Xanh lá"></button>
          <button class="tv-dtb-swatch" data-color="#ef4444" style="background:#ef4444;" title="Đỏ"></button>
          <button class="tv-dtb-swatch" data-color="#a855f7" style="background:#a855f7;" title="Tím"></button>
          <button class="tv-dtb-swatch" data-color="#f8fafc" style="background:#f8fafc;" title="Trắng"></button>
        </div>
        <div class="tv-dtb-sep"></div>
        <button class="tv-dtb-btn" data-width="1" title="Nét mảnh 1px">1px</button>
        <button class="tv-dtb-btn" data-width="2" title="Nét vừa 2px">2px</button>
        <button class="tv-dtb-btn" data-width="3" title="Nét đậm 3px">3px</button>
        <div class="tv-dtb-sep"></div>
        <button class="tv-dtb-btn" id="tvDtbDash" title="Đổi nét liền / nét đứt">━ / ╌</button>
        <button class="tv-dtb-btn" id="tvDtbEditLabel" title="Sửa nhãn văn bản">🏷️</button>
        <div class="tv-dtb-sep"></div>
        <button class="tv-dtb-btn del" id="tvDtbDelete" title="Xóa object đang chọn (Delete)">🗑️ Xóa</button>
      `;
      document.body.appendChild(tb);
    }
    this.floatingToolbar = tb;

    tb.addEventListener('mousedown', (e) => e.stopPropagation());
    tb.querySelectorAll('.tv-dtb-swatch').forEach(btn => {
      btn.addEventListener('click', () => {
        const obj = this.getSelectedObject();
        if (!obj) return;
        obj.color = btn.getAttribute('data-color');
        this.saveToStorage();
        this.renderAll();
        this.updateFloatingToolbar();
      });
    });
    tb.querySelectorAll('.tv-dtb-btn[data-width]').forEach(btn => {
      btn.addEventListener('click', () => {
        const obj = this.getSelectedObject();
        if (!obj) return;
        obj.lineWidth = parseInt(btn.getAttribute('data-width'), 10) || 2;
        this.saveToStorage();
        this.renderAll();
        this.updateFloatingToolbar();
      });
    });
    tb.querySelector('#tvDtbDash')?.addEventListener('click', () => {
      const obj = this.getSelectedObject();
      if (!obj) return;
      obj.dashed = !obj.dashed;
      this.saveToStorage();
      this.renderAll();
      this.updateFloatingToolbar();
    });
    tb.querySelector('#tvDtbEditLabel')?.addEventListener('click', () => {
      const obj = this.getSelectedObject();
      if (!obj) return;
      const next = prompt('Nhập nhãn hiển thị cho object:', obj.label || '');
      if (next !== null) {
        obj.label = next.trim();
        this.saveToStorage();
        this.renderAll();
      }
    });
    tb.querySelector('#tvDtbDelete')?.addEventListener('click', () => {
      this.deleteSelected();
    });
  }

  getSelectedObject() {
    if (!this.selected) return null;
    const list = this.drawings[this.selected.key] || [];
    return list.find(d => d.id === this.selected.id) || null;
  }

  selectObject(key, id) {
    this.selected = (key && id) ? { key, id } : null;
    this.updateFloatingToolbar();
    this.renderAll();
  }

  updateFloatingToolbar() {
    const tb = this.floatingToolbar;
    if (!tb) return;
    const obj = this.getSelectedObject();
    if (!obj) {
      tb.classList.remove('open');
      return;
    }
    const typeNames = {
      hline: 'H-Line',
      trendline: 'Trendline',
      zone: 'Zone Box',
      rr_long: 'Long RR',
      rr_short: 'Short RR'
    };
    const titleEl = tb.querySelector('#tvDtbTitle');
    if (titleEl) titleEl.innerText = `${typeNames[obj.type] || obj.type} (${this.selected.key})`;
    tb.querySelectorAll('.tv-dtb-btn[data-width]').forEach(b => {
      b.classList.toggle('active', parseInt(b.getAttribute('data-width'), 10) === (obj.lineWidth || 2));
    });
    const dashBtn = tb.querySelector('#tvDtbDash');
    if (dashBtn) dashBtn.classList.toggle('active', !!obj.dashed);
    tb.classList.add('open');
  }

  deleteSelected() {
    if (!this.selected) return;
    const { key, id } = this.selected;
    this.drawings[key] = (this.drawings[key] || []).filter(d => d.id !== id);
    this.selected = null;
    this.saveToStorage();
    this.updateFloatingToolbar();
    this.renderAll();
    if (this.cm.showToast) this.cm.showToast('🗑️ Đã xóa object đang chọn');
  }

  bindToolbar() {
    const btns = document.querySelectorAll('.tv-draw-btn[data-tool]');
    btns.forEach(btn => {
      btn.addEventListener('click', () => {
        const tool = btn.getAttribute('data-tool');
        if (tool === 'clear') {
          this.clearAllDrawings();
          return;
        }
        this.setTool(tool);
      });
    });

    window.addEventListener('keydown', (e) => {
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
      if (e.key === 'Escape') {
        if (this.activeTool !== 'pointer') this.setTool('pointer');
        else if (this.selected) this.selectObject(null, null);
      } else if ((e.key === 'Delete' || e.key === 'Backspace') && this.selected) {
        e.preventDefault();
        this.deleteSelected();
      }
    });
  }

  setTool(tool) {
    this.activeTool = tool;
    this.pendingPoint = null;
    if (tool !== 'pointer') this.selectObject(null, null);
    document.querySelectorAll('.tv-draw-btn[data-tool]').forEach(b => {
      b.classList.toggle('active', b.getAttribute('data-tool') === tool);
    });

    const cursor = tool === 'pointer' ? '' : 'crosshair';
    this.getTargets().forEach(t => {
      if (t.container) t.container.style.cursor = cursor;
    });

    const labels = {
      pointer: 'Con trỏ (Click object để chọn / kéo thả / Delete để xóa)',
      hline: 'Đường Ngang (H-Line): Click lên chart để đặt cản',
      trendline: 'Trendline: Click điểm 1, sau đó click điểm 2',
      zone: 'Vùng Cản (Zone): Click góc 1, sau đó click góc 2',
      rr_long: 'Long Position RR (1:2): Click điểm Entry trên chart',
      rr_short: 'Short Position RR (1:2): Click điểm Entry trên chart'
    };
    if (tool !== 'pointer' && this.cm.showToast) {
      this.cm.showToast(`✏️ ${labels[tool] || tool}`);
    }
  }

  // Coordinate helpers supporting both historical bars & future right margin
  getCandles(key) {
    if (key === 'H4') return this.cm.rawCandlesH4 || [];
    if (key === 'TF2') return this.cm.rawCandlesTF2 || [];
    return this.cm.rawCandlesM15 || [];
  }

  getTfStepSec(key) {
    const arr = this.getCandles(key);
    if (arr.length >= 2) {
      const diff = arr[arr.length - 1].time - arr[arr.length - 2].time;
      if (diff > 0) return diff;
    }
    return key === 'H4' ? 14400 : (key === 'TF2' ? 3600 : 900);
  }

  xToLogical(target, x) {
    try {
      const l = target.chart.timeScale().coordinateToLogical(x);
      if (l !== null && !isNaN(l)) return l;
    } catch (e) {}
    return null;
  }

  xToTime(target, x) {
    const arr = this.getCandles(target.key);
    if (!arr.length) return Math.floor(Date.now() / 1000);
    const l = this.xToLogical(target, x);
    if (l === null) return arr[arr.length - 1].time;
    const idx = Math.round(l);
    const step = this.getTfStepSec(target.key);
    if (idx < 0) return arr[0].time + idx * step;
    if (idx >= arr.length) return arr[arr.length - 1].time + (idx - (arr.length - 1)) * step;
    return arr[idx].time;
  }

  timeToX(target, time) {
    try {
      const direct = target.chart.timeScale().timeToCoordinate(time);
      if (direct !== null && !isNaN(direct)) return direct;
    } catch (e) {}
    const arr = this.getCandles(target.key);
    if (!arr.length) return null;
    const step = this.getTfStepSec(target.key);
    const lastIdx = arr.length - 1;
    let logical = lastIdx;
    if (time >= arr[lastIdx].time) {
      logical = lastIdx + (time - arr[lastIdx].time) / step;
    } else if (time <= arr[0].time) {
      logical = (time - arr[0].time) / step;
    } else {
      // Binary search nearest candle
      let lo = 0, hi = lastIdx;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        if (arr[mid].time === time) { logical = mid; break; }
        if (arr[mid].time < time) { logical = mid; lo = mid + 1; }
        else hi = mid - 1;
      }
    }
    try {
      const coord = target.chart.timeScale().logicalToCoordinate(logical);
      if (coord !== null && !isNaN(coord)) return coord;
    } catch (e) {}
    return null;
  }

  bindChartEvents() {
    this.getTargets().forEach(target => {
      const { key, chart, series, container } = target;

      // Re-render SVG whenever user pans or zooms
      chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
        this.renderChart(key);
      });

      // Handle creating new drawings & deselecting on empty canvas click
      chart.subscribeClick((param) => {
        if (window.app && window.app.replayController && window.app.replayController.barCutActive) return;
        if (this.dragState) return;
        if (this.activeTool === 'pointer') {
          if (this.selected) this.selectObject(null, null);
          return;
        }
        if (!param || !param.point) return;

        const price = series.coordinateToPrice(param.point.y);
        if (price === null || isNaN(price)) return;
        const time = param.time || this.xToTime(target, param.point.x);
        const id = `d_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

        if (this.activeTool === 'hline') {
          this.drawings[key].push({
            id, type: 'hline', price, color: '#38bdf8', lineWidth: 2, dashed: false, label: ''
          });
          this.saveToStorage();
          this.setTool('pointer');
          this.selectObject(key, id);
        } else if (this.activeTool === 'trendline') {
          if (!this.pendingPoint || this.pendingPoint.key !== key) {
            this.pendingPoint = { key, time, price };
            if (this.cm.showToast) this.cm.showToast(`📍 Điểm 1 (${price.toFixed(2)}) — Click điểm 2 để nối Trendline`);
          } else {
            this.drawings[key].push({
              id, type: 'trendline',
              t1: this.pendingPoint.time, p1: this.pendingPoint.price,
              t2: time, p2: price,
              color: '#f59e0b', lineWidth: 2, dashed: false, label: ''
            });
            this.pendingPoint = null;
            this.saveToStorage();
            this.setTool('pointer');
            this.selectObject(key, id);
          }
        } else if (this.activeTool === 'zone') {
          if (!this.pendingPoint || this.pendingPoint.key !== key) {
            this.pendingPoint = { key, time, price };
            if (this.cm.showToast) this.cm.showToast(`📍 Góc 1 (${price.toFixed(2)}) — Click góc 2 để tạo Vùng Cản`);
          } else {
            const step = this.getTfStepSec(key);
            const t1 = Math.min(this.pendingPoint.time, time);
            let t2 = Math.max(this.pendingPoint.time, time);
            if (t2 === t1) t2 = t1 + step * 10;
            this.drawings[key].push({
              id, type: 'zone',
              t1, t2,
              p1: Math.max(this.pendingPoint.price, price),
              p2: Math.min(this.pendingPoint.price, price),
              color: '#a855f7', lineWidth: 1, dashed: false, label: 'Zone'
            });
            this.pendingPoint = null;
            this.saveToStorage();
            this.setTool('pointer');
            this.selectObject(key, id);
          }
        } else if (this.activeTool === 'rr_long' || this.activeTool === 'rr_short') {
          const isLong = this.activeTool === 'rr_long';
          const risk = Math.max(0.0005, price * 0.0035);
          const step = this.getTfStepSec(key);
          this.drawings[key].push({
            id,
            type: this.activeTool,
            t1: time,
            t2: time + step * 14,
            entry: price,
            sl: isLong ? price - risk : price + risk,
            tp: isLong ? price + risk * 2.0 : price - risk * 2.0,
            color: isLong ? '#10b981' : '#ef4444',
            lineWidth: 2,
            dashed: false,
            label: isLong ? 'LONG' : 'SHORT'
          });
          this.saveToStorage();
          this.setTool('pointer');
          this.selectObject(key, id);
        }
      });

      // Global drag handlers on window for smooth dragging
      const onMouseMove = (e) => {
        if (!this.dragState || this.dragState.key !== key) return;
        const rect = container.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const newPrice = series.coordinateToPrice(y);
        if (newPrice === null || isNaN(newPrice)) return;
        const newTime = this.xToTime(target, x);

        const obj = (this.drawings[key] || []).find(d => d.id === this.dragState.id);
        if (!obj) return;
        const { mode, startPrice, startTime, orig } = this.dragState;
        const dP = newPrice - startPrice;
        const dT = newTime - startTime;

        if (obj.type === 'hline') {
          obj.price = newPrice;
        } else if (obj.type === 'trendline') {
          if (mode === 'p1') { obj.t1 = newTime; obj.p1 = newPrice; }
          else if (mode === 'p2') { obj.t2 = newTime; obj.p2 = newPrice; }
          else { obj.t1 = orig.t1 + dT; obj.t2 = orig.t2 + dT; obj.p1 = orig.p1 + dP; obj.p2 = orig.p2 + dP; }
        } else if (obj.type === 'zone') {
          if (mode === 'tl') { obj.t1 = newTime; obj.p1 = newPrice; }
          else if (mode === 'br') { obj.t2 = newTime; obj.p2 = newPrice; }
          else if (mode === 'tr') { obj.t2 = newTime; obj.p1 = newPrice; }
          else if (mode === 'bl') { obj.t1 = newTime; obj.p2 = newPrice; }
          else { obj.t1 = orig.t1 + dT; obj.t2 = orig.t2 + dT; obj.p1 = orig.p1 + dP; obj.p2 = orig.p2 + dP; }
        } else if (obj.type === 'rr_long' || obj.type === 'rr_short') {
          if (mode === 'tp') { obj.tp = newPrice; }
          else if (mode === 'sl') { obj.sl = newPrice; }
          else if (mode === 'entry') { obj.entry = newPrice; }
          else if (mode === 'right') { obj.t2 = Math.max(obj.t1 + this.getTfStepSec(key) * 2, newTime); }
          else {
            obj.t1 = orig.t1 + dT;
            obj.t2 = orig.t2 + dT;
            obj.entry = orig.entry + dP;
            obj.sl = orig.sl + dP;
            obj.tp = orig.tp + dP;
          }
        }
        this.renderChart(key);
      };

      const onMouseUp = () => {
        if (!this.dragState || this.dragState.key !== key) return;
        this.dragState = null;
        try { chart.applyOptions({ handleScroll: true, handleScale: true }); } catch (e) {}
        document.body.style.cursor = '';
        this.saveToStorage();
        this.renderChart(key);
      };

      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
    });
  }

  startDrag(e, key, id, mode) {
    if (this.activeTool !== 'pointer') return;
    e.preventDefault();
    e.stopPropagation();
    const target = this.getTarget(key);
    if (!target) return;
    const obj = (this.drawings[key] || []).find(d => d.id === id);
    if (!obj) return;

    this.selectObject(key, id);
    const rect = target.container.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const startPrice = target.series.coordinateToPrice(y);
    const startTime = this.xToTime(target, x);

    this.dragState = {
      key, id, mode,
      startPrice: startPrice ?? 0,
      startTime,
      orig: JSON.parse(JSON.stringify(obj))
    };
    try { target.chart.applyOptions({ handleScroll: false, handleScale: false }); } catch (err) {}
    document.body.style.cursor = mode === 'move' ? 'grabbing' : 'nwse-resize';
  }

  startSyncLoop() {
    // Periodic lightweight sync for price-scale auto-scaling shifts (e.g. live ticks)
    setInterval(() => {
      const hasAny = (this.drawings.H4.length + this.drawings.TF2.length + this.drawings.M15.length) > 0;
      if (hasAny && !this.dragState) {
        this.renderAll();
      }
    }, 600);
  }

  renderAll() {
    ['H4', 'TF2', 'M15'].forEach(k => this.renderChart(k));
  }

  renderChart(key) {
    const target = this.getTarget(key);
    const svg = this.svgs[key];
    if (!target || !svg) return;

    const w = target.container.clientWidth || 0;
    const h = target.container.clientHeight || 0;
    if (w <= 0 || h <= 0) return;

    const plotW = Math.max(0, w - 62); // avoid covering right price scale
    svg.setAttribute('width', plotW);
    svg.setAttribute('height', h);
    svg.style.width = `${plotW}px`;
    svg.style.height = `${h}px`;

    while (svg.firstChild) svg.removeChild(svg.firstChild);

    const list = this.drawings[key] || [];
    if (list.length === 0) return;

    const ns = 'http://www.w3.org/2000/svg';
    const mk = (tag, attrs) => {
      const el = document.createElementNS(ns, tag);
      for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, String(v));
      return el;
    };

    const addHandle = (g, cx, cy, id, mode, cursor = 'pointer') => {
      const c = mk('circle', {
        cx, cy, r: 5,
        fill: '#ffffff', stroke: '#2962ff', 'stroke-width': 2,
        class: 'tv-draw-handle',
        style: `cursor:${cursor};pointer-events:all;`
      });
      c.addEventListener('mousedown', (e) => this.startDrag(e, key, id, mode));
      g.appendChild(c);
    };

    list.forEach(d => {
      const isSel = this.selected && this.selected.key === key && this.selected.id === d.id;
      const g = mk('g', { 'data-id': d.id });
      const color = d.color || '#38bdf8';
      const lw = d.lineWidth || 2;
      const dash = d.dashed ? '6,4' : '';

      if (d.type === 'hline') {
        const y = target.series.priceToCoordinate(d.price);
        if (y === null || isNaN(y) || y < -20 || y > h + 20) return;
        const hit = mk('line', { x1: 0, y1: y, x2: plotW, y2: y, stroke: 'transparent', 'stroke-width': 12, style: 'cursor:ns-resize;pointer-events:stroke;' });
        hit.addEventListener('mousedown', (e) => this.startDrag(e, key, d.id, 'move'));
        const vis = mk('line', { x1: 0, y1: y, x2: plotW, y2: y, stroke: color, 'stroke-width': isSel ? lw + 1 : lw, 'stroke-dasharray': dash, style: 'pointer-events:none;' });
        g.appendChild(hit);
        g.appendChild(vis);

        const lblTxt = `${d.label ? d.label + ' ' : ''}${Number(d.price).toFixed(2)}`;
        const tagBg = mk('rect', { x: 8, y: y - 16, width: Math.max(54, lblTxt.length * 6.5 + 10), height: 15, rx: 3, fill: color, opacity: 0.9, style: 'cursor:ns-resize;pointer-events:all;' });
        tagBg.addEventListener('mousedown', (e) => this.startDrag(e, key, d.id, 'move'));
        const tag = mk('text', { x: 13, y: y - 5, fill: '#0f172a', 'font-size': 10, 'font-weight': 700, 'font-family': 'JetBrains Mono, monospace', style: 'pointer-events:none;' });
        tag.textContent = lblTxt;
        g.appendChild(tagBg);
        g.appendChild(tag);

        if (isSel) addHandle(g, Math.round(plotW * 0.5), y, d.id, 'move', 'ns-resize');
      } else if (d.type === 'trendline') {
        const x1 = this.timeToX(target, d.t1);
        const x2 = this.timeToX(target, d.t2);
        const y1 = target.series.priceToCoordinate(d.p1);
        const y2 = target.series.priceToCoordinate(d.p2);
        if ([x1, x2, y1, y2].some(v => v === null || isNaN(v))) return;

        const hit = mk('line', { x1, y1, x2, y2, stroke: 'transparent', 'stroke-width': 14, style: 'cursor:move;pointer-events:stroke;' });
        hit.addEventListener('mousedown', (e) => this.startDrag(e, key, d.id, 'move'));
        const vis = mk('line', { x1, y1, x2, y2, stroke: color, 'stroke-width': isSel ? lw + 1 : lw, 'stroke-dasharray': dash, style: 'pointer-events:none;' });
        g.appendChild(hit);
        g.appendChild(vis);

        if (d.label) {
          const tx = (x1 + x2) / 2;
          const ty = (y1 + y2) / 2 - 8;
          const tEl = mk('text', { x: tx, y: ty, fill: color, 'font-size': 10, 'font-weight': 700, 'text-anchor': 'middle', 'font-family': 'JetBrains Mono, monospace', style: 'pointer-events:none;' });
          tEl.textContent = d.label;
          g.appendChild(tEl);
        }
        if (isSel) {
          addHandle(g, x1, y1, d.id, 'p1', 'grab');
          addHandle(g, x2, y2, d.id, 'p2', 'grab');
        }
      } else if (d.type === 'zone') {
        const x1 = this.timeToX(target, d.t1);
        const x2 = this.timeToX(target, d.t2);
        const y1 = target.series.priceToCoordinate(d.p1);
        const y2 = target.series.priceToCoordinate(d.p2);
        if ([x1, x2, y1, y2].some(v => v === null || isNaN(v))) return;

        const rx = Math.min(x1, x2);
        const ry = Math.min(y1, y2);
        const rw = Math.max(8, Math.abs(x2 - x1));
        const rh = Math.max(6, Math.abs(y2 - y1));

        const rect = mk('rect', {
          x: rx, y: ry, width: rw, height: rh,
          fill: color, 'fill-opacity': isSel ? 0.24 : 0.16,
          stroke: color, 'stroke-width': isSel ? lw + 1 : lw, 'stroke-dasharray': dash,
          style: 'cursor:move;pointer-events:all;'
        });
        rect.addEventListener('mousedown', (e) => this.startDrag(e, key, d.id, 'move'));
        g.appendChild(rect);

        if (d.label) {
          const tEl = mk('text', { x: rx + 6, y: ry + 13, fill: '#f8fafc', 'font-size': 10, 'font-weight': 700, 'font-family': 'JetBrains Mono, monospace', style: 'pointer-events:none;' });
          tEl.textContent = `${d.label} (${Math.max(d.p1, d.p2).toFixed(2)} - ${Math.min(d.p1, d.p2).toFixed(2)})`;
          g.appendChild(tEl);
        }
        if (isSel) {
          addHandle(g, x1, y1, d.id, 'tl', 'nwse-resize');
          addHandle(g, x2, y1, d.id, 'tr', 'nesw-resize');
          addHandle(g, x1, y2, d.id, 'bl', 'nesw-resize');
          addHandle(g, x2, y2, d.id, 'br', 'nwse-resize');
        }
      } else if (d.type === 'rr_long' || d.type === 'rr_short') {
        const x1 = this.timeToX(target, d.t1);
        const x2 = this.timeToX(target, d.t2);
        const yE = target.series.priceToCoordinate(d.entry);
        const ySL = target.series.priceToCoordinate(d.sl);
        const yTP = target.series.priceToCoordinate(d.tp);
        if ([x1, x2, yE, ySL, yTP].some(v => v === null || isNaN(v))) return;

        const rx = Math.min(x1, x2);
        const rw = Math.max(40, Math.abs(x2 - x1));
        const risk = Math.abs(d.entry - d.sl) || 0.0001;
        const reward = Math.abs(d.tp - d.entry);
        const rr = (reward / risk).toFixed(2);

        // TP shaded green box
        const tpRect = mk('rect', {
          x: rx, y: Math.min(yE, yTP), width: rw, height: Math.max(4, Math.abs(yTP - yE)),
          fill: '#10b981', 'fill-opacity': isSel ? 0.28 : 0.18,
          stroke: '#10b981', 'stroke-width': 1, style: 'cursor:move;pointer-events:all;'
        });
        tpRect.addEventListener('mousedown', (e) => this.startDrag(e, key, d.id, 'move'));
        g.appendChild(tpRect);

        // SL shaded red box
        const slRect = mk('rect', {
          x: rx, y: Math.min(yE, ySL), width: rw, height: Math.max(4, Math.abs(ySL - yE)),
          fill: '#ef4444', 'fill-opacity': isSel ? 0.28 : 0.18,
          stroke: '#ef4444', 'stroke-width': 1, style: 'cursor:move;pointer-events:all;'
        });
        slRect.addEventListener('mousedown', (e) => this.startDrag(e, key, d.id, 'move'));
        g.appendChild(slRect);

        // Entry divider line
        const eLine = mk('line', { x1: rx, y1: yE, x2: rx + rw, y2: yE, stroke: '#38bdf8', 'stroke-width': 2, style: 'pointer-events:none;' });
        g.appendChild(eLine);

        // RR Info Pill
        const lbl = `${d.label || (d.type === 'rr_long' ? 'LONG' : 'SHORT')} RR 1:${rr}`;
        const pill = mk('text', { x: rx + 6, y: yE - 5, fill: '#f8fafc', 'font-size': 10, 'font-weight': 700, 'font-family': 'JetBrains Mono, monospace', style: 'pointer-events:none;' });
        pill.textContent = lbl;
        g.appendChild(pill);

        if (isSel) {
          addHandle(g, rx + rw / 2, yTP, d.id, 'tp', 'ns-resize');
          addHandle(g, rx + rw / 2, yE, d.id, 'entry', 'ns-resize');
          addHandle(g, rx + rw / 2, ySL, d.id, 'sl', 'ns-resize');
          addHandle(g, rx + rw, yE, d.id, 'right', 'ew-resize');
        }
      }

      svg.appendChild(g);
    });
  }

  clearAllDrawings() {
    this.drawings = { H4: [], TF2: [], M15: [] };
    this.selected = null;
    this.saveToStorage();
    this.updateFloatingToolbar();
    this.renderAll();
    this.setTool('pointer');
    if (this.cm.showToast) this.cm.showToast('🗑️ Đã xóa toàn bộ nét vẽ trên 3 chart!');
  }
}

window.DrawingToolsManager = DrawingToolsManager;
