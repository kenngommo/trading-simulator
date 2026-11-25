/**
 * Replay Controller with Custom Start Date/Time Picker, Center Chart, and Speed Control
 */

class ReplayController {
  constructor(app) {
    this.app = app;
    this.isPlaying = false;
    this.intervalId = null;
    this.speedMs = 400;

    this.btnPlay = document.getElementById('btnPlay');
    this.btnStepForward = document.getElementById('btnStepForward');
    this.btnStepBack = document.getElementById('btnStepBack');
    this.speedSlider = document.getElementById('speedSlider');
    this.speedDisplay = document.getElementById('speedDisplay');
    this.progressBar = document.getElementById('progressFill');
    this.progressContainer = document.getElementById('progressBarBg');
    this.barCounter = document.getElementById('barCounter');
    this.dateIndicator = document.getElementById('dateIndicator');
    this.btnCenterChart = document.getElementById('btnCenterChart');
    this.btnPickStartDate = document.getElementById('btnPickStartDate');
    this.inputCustomDate = document.getElementById('inputCustomDate');

    this.bindEvents();
    this.setupKeyboardShortcuts();
  }

  bindEvents() {
    this.btnPlay.addEventListener('click', () => this.togglePlay());
    this.btnStepForward.addEventListener('click', () => this.step(1, 'forward'));
    this.btnStepBack.addEventListener('click', () => this.step(1, 'backward'));

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

      // Turbo Step Batching: At high speeds, step multiple bars per frame to bypass HTTP latency
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
        // 36x to 50x Turbo speed (150-200 bars/sec!)
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
      // Never hijack Ctrl/Alt/Meta combos (e.g. Ctrl+C, Ctrl+B, Alt+R)
      if (e.ctrlKey || e.altKey || e.metaKey) {
        return;
      }

      if (e.key === 'r' || e.key === 'R') {
        this.app.chartManager.centerCharts();
        return;
      }

      // Replay & quick-trade hotkeys only apply in BACKTEST mode
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
      // Convert local browser datetime (VN UTC+7) accurately to Unix UTC seconds!
      const parsedDate = new Date(dateTimeStr);
      const unixTs = !isNaN(parsedDate.getTime()) ? Math.floor(parsedDate.getTime() / 1000) : null;

      // If currently in LIVE mode, automatically switch to Backtest mode so live poll doesn't override
      if (this.app && this.app.liveRealtimeActive) {
        this.app.liveRealtimeActive = false;
        if (this.app.livePollTimer) { clearInterval(this.app.livePollTimer); this.app.livePollTimer = null; }
        if (this.app.liveTickTimer) { clearInterval(this.app.liveTickTimer); this.app.liveTickTimer = null; }
        const dotToggle = document.getElementById('liveModeDot');
        const textToggle = document.getElementById('liveModeText');
        if (dotToggle) dotToggle.innerText = '🔴';
        if (textToggle) textToggle.innerText = 'Chế độ: BACKTEST (Bấm sang LIVE)';
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
      
      // Format inputCustomDate in LOCAL time (VN UTC+7) so picker matches user's clock!
      if (this.inputCustomDate && !this.isPlaying) {
        const pad = (n) => String(n).padStart(2, '0');
        const localIso = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
        this.inputCustomDate.value = localIso;
      }
    }
  }
}

window.ReplayController = ReplayController;
