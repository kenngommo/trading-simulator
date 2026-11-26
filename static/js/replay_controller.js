/**
 * Replay Controller with TradingView-Style Bar Cut ("Jump to Bar"),
 * Custom Start Date/Time Picker, Center Chart, and Turbo Speed Control
 */

class ReplayController {
  constructor(app) {
    this.app = app;
    this.isPlaying = false;
    this.intervalId = null;
    this.speedMs = 400;
    this.barCutActive = false;
    this.cutOverlays = {};

    this.btnPlay = document.getElementById('btnPlay');
    this.btnStepForward = document.getElementById('btnStepForward');
    this.btnStepBack = document.getElementById('btnStepBack');
    this.btnRibbonBarCut = document.getElementById('btnRibbonBarCut');
    this.btnReplayBarCut = document.getElementById('btnReplayBarCut');
    this.speedSlider = document.getElementById('speedSlider');
    this.speedDisplay = document.getElementById('speedDisplay');
    this.progressBar = document.getElementById('progressFill');
    this.progressContainer = document.getElementById('progressBarBg');
    this.barCounter = document.getElementById('barCounter');
    this.dateIndicator = document.getElementById('dateIndicator');
    this.btnPickStartDate = document.getElementById('btnPickStartDate');
    this.inputCustomDate = document.getElementById('inputCustomDate');

    this.initBarCutUI();
    this.bindEvents();
    this.setupKeyboardShortcuts();
  }

  initBarCutUI() {
    // 1. Floating top instruction banner while Bar Cut mode is active
    let banner = document.getElementById('tvBarCutBanner');
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'tvBarCutBanner';
      banner.className = 'tv-bar-cut-banner';
      banner.innerHTML = `
        <span>✂️ <b style="color:#60a5fa;">CHẾ ĐỘ CẮT NẾN:</b> Di chuột & Click vào bất kỳ cây nến nào trên 3 biểu đồ để cắt về thời điểm đó</span>
        <button class="btn-header" id="btnBarCutShowFull" style="padding:3px 9px;font-size:11px;border-color:#10b981;color:#6ee7b7;background:rgba(16,185,129,0.18);" title="Mở toàn bộ lịch sử tới cây nến mới nhất để chọn lại điểm cắt">⏩ Hiện đủ nến tới hiện tại</button>
        <button class="btn-header" id="btnBarCutCancel" style="padding:3px 9px;font-size:11px;border-color:#ef4444;color:#fca5a5;">✕ Hủy (Esc)</button>
      `;
      document.body.appendChild(banner);
    }
    this.barCutBanner = banner;

    banner.querySelector('#btnBarCutCancel')?.addEventListener('click', () => this.toggleBarCutMode(false));
    banner.querySelector('#btnBarCutShowFull')?.addEventListener('click', async () => {
      if (this.app && this.app.totalBars > 0) {
        await this.app.jumpToIndex(this.app.totalBars - 1);
        if (this.app.showToast) this.app.showToast('⏩ Đã mở đủ toàn bộ lịch sử nến — Hãy click chọn cây nến muốn cắt!');
      }
    });

    // 2. Create visual curtain + vertical scissor line overlays on all 3 charts
    const cm = this.app && this.app.chartManager;
    if (!cm) return;

    const panes = [
      { key: 'H4', container: cm.containerH4, chart: cm.chartH4, getCandles: () => cm.rawCandlesH4 || [] },
      { key: 'TF2', container: cm.containerTF2, chart: cm.chartTF2, getCandles: () => cm.rawCandlesTF2 || [] },
      { key: 'M15', container: cm.containerM15, chart: cm.chartM15, getCandles: () => cm.rawCandlesM15 || [] }
    ];

    panes.forEach(({ key, container, chart, getCandles }) => {
      if (!container || !chart) return;
      let ov = container.querySelector('.tv-bar-cut-overlay');
      if (!ov) {
        ov = document.createElement('div');
        ov.className = 'tv-bar-cut-overlay';
        ov.innerHTML = `
          <div class="tv-bar-cut-curtain"></div>
          <div class="tv-bar-cut-badge">✂ --</div>
        `;
        container.appendChild(ov);
      }
      this.cutOverlays[key] = { ov, container, chart, getCandles };

      // Update curtain smoothly when moving crosshair in Bar Cut mode
      chart.subscribeCrosshairMove((param) => {
        if (!this.barCutActive) return;
        if (cm.activeHoverChart && cm.activeHoverChart !== key) return;
        if (!param || !param.time || !param.point) {
          this.hideAllCutOverlays();
          return;
        }
        this.renderCutCurtainsAtTime(param.time);
      });

      // Execute cut when clicking on any chart while Bar Cut mode is active
      chart.subscribeClick((param) => {
        if (!this.barCutActive) return;
        if (!param) return;
        let cutTime = param.time;
        if (!cutTime && param.point) {
          const arr = getCandles();
          const logical = chart.timeScale().coordinateToLogical(param.point.x);
          if (logical !== null && arr.length > 0) {
            const idx = Math.max(0, Math.min(arr.length - 1, Math.round(logical)));
            cutTime = arr[idx].time;
          }
        }
        if (cutTime) {
          this.executeBarCutAtTimestamp(cutTime);
        }
      });
    });
  }

  formatServerAndVnTime(unixSec) {
    const pad = (n) => String(n).padStart(2, '0');
    // Server time (MT5 UTC+3) & VN time (UTC+7)
    const srv = new Date((unixSec + 3 * 3600) * 1000);
    const vn = new Date((unixSec + 7 * 3600) * 1000);
    const dStr = `${pad(vn.getUTCDate())}/${pad(vn.getUTCMonth() + 1)}/${vn.getUTCFullYear()}`;
    const sTime = `${pad(srv.getUTCHours())}:${pad(srv.getUTCMinutes())}`;
    const vTime = `${pad(vn.getUTCHours())}:${pad(vn.getUTCMinutes())}`;
    return `${dStr} • ${sTime} Server (${vTime} VN)`;
  }

  renderCutCurtainsAtTime(targetTime) {
    const cm = this.app && this.app.chartManager;
    if (!cm) return;
    const labelStr = `✂ ${this.formatServerAndVnTime(targetTime)}`;

    Object.entries(this.cutOverlays).forEach(([key, item]) => {
      const { ov, container, chart, getCandles } = item;
      const arr = getCandles();
      if (!arr || arr.length === 0) {
        ov.classList.remove('visible');
        return;
      }
      const nearest = cm.findNearestCandle(arr, targetTime);
      if (!nearest) {
        ov.classList.remove('visible');
        return;
      }
      const x = chart.timeScale().timeToCoordinate(nearest.time);
      const plotW = Math.max(0, (container.clientWidth || 0) - 62);
      if (x === null || isNaN(x) || x < 0 || x > plotW) {
        ov.classList.remove('visible');
        return;
      }

      ov.classList.add('visible');
      const curtain = ov.querySelector('.tv-bar-cut-curtain');
      const badge = ov.querySelector('.tv-bar-cut-badge');
      if (curtain) {
        curtain.style.left = `${Math.round(x)}px`;
      }
      if (badge) {
        // Clamp badge horizontally so it never clips off left or right edges
        const clampedX = Math.max(115, Math.min(plotW - 115, Math.round(x)));
        badge.style.left = `${clampedX}px`;
        badge.textContent = labelStr;
      }
    });
  }

  hideAllCutOverlays() {
    Object.values(this.cutOverlays).forEach(({ ov }) => ov.classList.remove('visible'));
  }

  toggleBarCutMode(forceState) {
    const next = (forceState !== undefined) ? !!forceState : !this.barCutActive;
    this.barCutActive = next;

    if (next) {
      this.pause();
      if (this.app && this.app.drawingTools && this.app.drawingTools.activeTool !== 'pointer') {
        this.app.drawingTools.setTool('pointer');
      }
    } else {
      this.hideAllCutOverlays();
    }

    if (this.btnRibbonBarCut) this.btnRibbonBarCut.classList.toggle('bar-cut-active', next);
    if (this.btnReplayBarCut) this.btnReplayBarCut.classList.toggle('bar-cut-active', next);
    if (this.barCutBanner) this.barCutBanner.classList.toggle('open', next);

    const cm = this.app && this.app.chartManager;
    if (cm) {
      const cur = next ? 'col-resize' : '';
      [cm.containerH4, cm.containerTF2, cm.containerM15].forEach(c => {
        if (c) c.style.cursor = cur;
      });
    }
  }

  async executeBarCutAtTimestamp(unixTs) {
    this.toggleBarCutMode(false);
    try {
      // Switch cleanly from LIVE -> BACKTEST mode if currently in LIVE mode
      if (this.app && this.app.liveRealtimeActive) {
        this.app.liveRealtimeActive = false;
        if (this.app.livePollTimer) { clearInterval(this.app.livePollTimer); this.app.livePollTimer = null; }
        if (this.app.liveTickTimer) { clearInterval(this.app.liveTickTimer); this.app.liveTickTimer = null; }

        const btnToggle = document.getElementById('btnLiveModeToggle');
        const dotToggle = document.getElementById('liveModeDot');
        const textToggle = document.getElementById('liveModeText');
        if (btnToggle) {
          btnToggle.style.background = 'rgba(239,68,68,0.18)';
          btnToggle.style.borderColor = '#ef4444';
          btnToggle.style.color = '#fca5a5';
        }
        if (dotToggle) dotToggle.innerText = '🔴';
        if (textToggle) textToggle.innerText = 'Chế độ: BACKTEST (Bấm sang LIVE)';

        const replayBar = document.querySelector('.replay-bar');
        const pnlBadge = document.getElementById('floatingPnlBadge');
        if (replayBar) replayBar.style.display = 'flex';
        if (pnlBadge) pnlBadge.style.display = 'flex';
        if (this.app.chartManager) setTimeout(() => this.app.chartManager.resizeAll(), 60);
      }

      const resp = await fetch('/api/jump', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timestamp: Math.floor(unixTs) })
      });
      const res = await resp.json();
      if (res.success) {
        await this.app.refreshState();
        if (this.app.chartManager) this.app.chartManager.centerCharts();
        if (this.app.showToast) {
          this.app.showToast(`✂️ Đã cắt nến về ${this.formatServerAndVnTime(res.current_time || unixTs)} (Nến #${res.current_index})`);
        }
      }
    } catch (e) {
      console.error('Error executing Bar Cut:', e);
    }
  }

  bindEvents() {
    this.btnPlay.addEventListener('click', () => this.togglePlay());
    this.btnStepForward.addEventListener('click', () => this.step(1, 'forward'));
    this.btnStepBack.addEventListener('click', () => this.step(1, 'backward'));

    if (this.btnRibbonBarCut) {
      this.btnRibbonBarCut.addEventListener('click', () => this.toggleBarCutMode());
    }
    if (this.btnReplayBarCut) {
      this.btnReplayBarCut.addEventListener('click', () => this.toggleBarCutMode());
    }

    if (this.inputCustomDate) {
      this.inputCustomDate.addEventListener('change', (e) => {
        const val = e.target.value;
        if (val) {
          this.jumpToDateTime(val);
        }
      });
    }

    if (this.btnPickStartDate) {
      this.btnPickStartDate.addEventListener('click', () => {
        if (this.inputCustomDate) {
          this.inputCustomDate.showPicker ? this.inputCustomDate.showPicker() : this.inputCustomDate.focus();
        }
      });
    }

    this.speedSlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value);
      this.speedValue = val;
      this.speedDisplay.innerText = `${val}x`;

      if (val <= 5) {
        this.batchSteps = 1;
        this.speedMs = Math.round(500 / val);
      } else if (val <= 10) {
        this.batchSteps = 1;
        this.speedMs = Math.round(350 / val);
      } else if (val <= 20) {
        this.batchSteps = 2;
        this.speedMs = 40;
      } else if (val <= 35) {
        this.batchSteps = 3;
        this.speedMs = 30;
      } else {
        this.batchSteps = 5;
        this.speedMs = 25;
      }

      if (this.isPlaying) {
        this.pause();
        this.play();
      }
    });

    if (this.progressContainer) {
      this.progressContainer.addEventListener('click', (e) => {
        const rect = this.progressContainer.getBoundingClientRect();
        const clickRatio = (e.clientX - rect.left) / rect.width;
        const targetIndex = Math.round(clickRatio * this.app.totalBars);
        this.app.jumpToIndex(targetIndex);
      });
    }
  }

  setupKeyboardShortcuts() {
    window.addEventListener('keydown', (e) => {
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
        return;
      }

      if (e.key === 'Escape' && this.barCutActive) {
        e.preventDefault();
        this.toggleBarCutMode(false);
        return;
      }

      // Alt+X hotkey to toggle Bar Cut quickly from anywhere
      if (e.altKey && (e.key === 'x' || e.key === 'X')) {
        e.preventDefault();
        this.toggleBarCutMode();
        return;
      }

      if (e.ctrlKey || e.altKey || e.metaKey) {
        return;
      }

      if (e.key === 'r' || e.key === 'R') {
        this.app.chartManager.centerCharts();
        return;
      }

      if (this.app && this.app.liveRealtimeActive) {
        return;
      }

      if (e.code === 'Space') {
        e.preventDefault();
        this.togglePlay();
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        this.step(1, 'forward');
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        this.step(1, 'backward');
      } else if (e.key === 'b' || e.key === 'B') {
        this.app.tradePanel.executeAction('BUY');
      } else if (e.key === 's' || e.key === 'S') {
        this.app.tradePanel.executeAction('SELL');
      } else if (e.key === 'c' || e.key === 'C') {
        this.app.tradePanel.closeAll();
      }
    });
  }

  togglePlay() {
    if (this.isPlaying) {
      this.pause();
    } else {
      this.play();
    }
  }

  play() {
    if (this.isPlaying) return;
    if (this.barCutActive) this.toggleBarCutMode(false);
    this.isPlaying = true;
    this.btnPlay.innerHTML = '⏸';
    this.btnPlay.classList.add('active');

    const loop = async () => {
      if (!this.isPlaying) return;
      await this.step(this.batchSteps || 1, 'forward', true);
      if (this.isPlaying) {
        this.intervalId = setTimeout(loop, this.speedMs || 40);
      }
    };
    this.intervalId = setTimeout(loop, this.speedMs || 40);
  }

  pause() {
    this.isPlaying = false;
    this.btnPlay.innerHTML = '▶';
    this.btnPlay.classList.remove('active');
    if (this.intervalId) {
      clearTimeout(this.intervalId);
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  async step(steps = 1, direction = 'forward', isFromAutoLoop = false) {
    if (isFromAutoLoop && !this.isPlaying) return;
    if (this.isStepping) return;

    this.isStepping = true;
    try {
      const resp = await fetch('/api/step', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ steps, direction })
      });
      const newState = await resp.json();
      if (newState && newState.current_index !== undefined) {
        await this.app.applyState(newState);
      } else if (direction === 'forward') {
        this.pause();
      }
    } catch (e) {
      console.error('Error stepping replay:', e);
      this.pause();
    } finally {
      this.isStepping = false;
    }
  }

  async jumpToDateTime(dateTimeStr) {
    try {
      const parsedDate = new Date(dateTimeStr);
      const unixTs = !isNaN(parsedDate.getTime()) ? Math.floor(parsedDate.getTime() / 1000) : null;

      if (this.app && this.app.liveRealtimeActive) {
        this.app.liveRealtimeActive = false;
        if (this.app.livePollTimer) { clearInterval(this.app.livePollTimer); this.app.livePollTimer = null; }
        if (this.app.liveTickTimer) { clearInterval(this.app.liveTickTimer); this.app.liveTickTimer = null; }
        const dotToggle = document.getElementById('liveModeDot');
        const textToggle = document.getElementById('liveModeText');
        if (dotToggle) dotToggle.innerText = '🔴';
        if (textToggle) textToggle.innerText = 'Chế độ: BACKTEST (Bấm sang LIVE)';
        const replayBar = document.querySelector('.replay-bar');
        const pnlBadge = document.getElementById('floatingPnlBadge');
        if (replayBar) replayBar.style.display = 'flex';
        if (pnlBadge) pnlBadge.style.display = 'flex';
      }

      const payload = unixTs ? { timestamp: unixTs } : { datetime_str: dateTimeStr };
      const resp = await fetch('/api/jump', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const res = await resp.json();
      if (res.success) {
        await this.app.refreshState();
        this.app.chartManager.centerCharts();
        if (this.app.showToast) {
          this.app.showToast(`⏪ Đã tua về ${dateTimeStr.replace('T', ' ')} (VN) — Nến #${res.current_index}`);
        }
      }
    } catch (e) {
      console.error('Error jumping to date:', e);
    }
  }

  updateProgress(currentIndex, totalBars, timestamp) {
    if (totalBars > 0) {
      const pct = Math.min(100, Math.max(0, (currentIndex / totalBars) * 100));
      if (this.progressBar) this.progressBar.style.width = `${pct}%`;
      if (this.barCounter) this.barCounter.innerText = `Nến: ${currentIndex} / ${totalBars} (${pct.toFixed(0)}%)`;
    }
    if (this.dateIndicator && timestamp) {
      const d = new Date(timestamp * 1000);
      const dateStr = d.toLocaleDateString('vi-VN', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit'
      });
      this.dateIndicator.innerText = `📅 ${dateStr}`;

      if (this.inputCustomDate && !this.isPlaying) {
        const pad = (n) => String(n).padStart(2, '0');
        const localIso = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
        this.inputCustomDate.value = localIso;
      }
    }
  }
}

window.ReplayController = ReplayController;
