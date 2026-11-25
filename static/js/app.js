/**
 * Enhanced Trading Simulator Orchestrator:
 * - Web Audio API Synthesizer (Chimes for Entry, TP, SL, BE)
 * - Auto-Radar Backtester Engine (5s Pause + Auto RR 1:2 & 1:3 Execution + BE Trailing)
 * - Year 2000 Fast Navigation & Symbol Management
 */

class SoundSynthesizer {
  constructor() {
    this.audioCtx = null;
    this.soundEnabled = true;
    this._attachGlobalUnlock();
  }

  _attachGlobalUnlock() {
    const unlock = () => {
      this._initCtx();
      ['click', 'touchstart', 'keydown', 'mousedown'].forEach(ev => {
        window.removeEventListener(ev, unlock);
      });
    };
    ['click', 'touchstart', 'keydown', 'mousedown'].forEach(ev => {
      window.addEventListener(ev, unlock, { passive: true });
    });
  }

  _initCtx() {
    try {
      if (!this.audioCtx) {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (AudioContext) {
          this.audioCtx = new AudioContext();
        }
      }
      if (this.audioCtx && this.audioCtx.state === 'suspended') {
        this.audioCtx.resume();
      }
    } catch (e) {
      console.warn('AudioContext init error:', e);
    }
  }

  playEntryBell() {
    if (!this.soundEnabled) return;
    this._initCtx();
    if (!this.audioCtx) return;

    try {
      if (this.audioCtx.state === 'suspended') this.audioCtx.resume();
      const now = this.audioCtx.currentTime;

      // High resonant bell chime (880Hz A5 + 1760Hz A6 + 2640Hz E7)
      const osc1 = this.audioCtx.createOscillator();
      const osc2 = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();

      osc1.type = 'sine';
      osc1.frequency.setValueAtTime(880, now);

      osc2.type = 'triangle';
      osc2.frequency.setValueAtTime(1760, now);

      gain.gain.setValueAtTime(0.7, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 1.4);

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(this.audioCtx.destination);

      osc1.start(now);
      osc2.start(now);
      osc1.stop(now + 1.4);
      osc2.stop(now + 1.4);
    } catch (e) {
      console.warn('Audio play error:', e);
    }
  }

  playTpChime() {
    if (!this.soundEnabled) return;
    this._initCtx();
    if (!this.audioCtx) return;

    try {
      if (this.audioCtx.state === 'suspended') this.audioCtx.resume();
      const now = this.audioCtx.currentTime;

      // 2-Tone Ascending Victory Chime (D5 -> A5)
      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, now); // D5
      osc.frequency.setValueAtTime(880.0, now + 0.18); // A5

      gain.gain.setValueAtTime(0.7, now);
      gain.gain.setValueAtTime(0.75, now + 0.18);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 1.6);

      osc.connect(gain);
      gain.connect(this.audioCtx.destination);

      osc.start(now);
      osc.stop(now + 1.6);
    } catch (e) {
      console.warn('Audio play error:', e);
    }
  }

  playGrandTpChime() {
    if (!this.soundEnabled) return;
    this._initCtx();
    if (!this.audioCtx) return;

    try {
      if (this.audioCtx.state === 'suspended') this.audioCtx.resume();
      const now = this.audioCtx.currentTime;

      // 4-Tone Grand Fanfare Chime (D5 -> F#5 -> A5 -> D6)
      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();

      osc.type = 'triangle';
      osc.frequency.setValueAtTime(587.33, now);
      osc.frequency.setValueAtTime(739.99, now + 0.14);
      osc.frequency.setValueAtTime(880.0, now + 0.28);
      osc.frequency.setValueAtTime(1174.66, now + 0.42);

      gain.gain.setValueAtTime(0.7, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 2.0);

      osc.connect(gain);
      gain.connect(this.audioCtx.destination);

      osc.start(now);
      osc.stop(now + 2.0);
    } catch (e) {
      console.warn('Audio play error:', e);
    }
  }

  playSlAlert() {
    if (!this.soundEnabled) return;
    this._initCtx();
    if (!this.audioCtx) return;

    try {
      if (this.audioCtx.state === 'suspended') this.audioCtx.resume();
      const now = this.audioCtx.currentTime;

      // Low descending warning alert (440Hz -> 293Hz)
      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();

      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(440.0, now);
      osc.frequency.exponentialRampToValueAtTime(293.66, now + 0.4);

      gain.gain.setValueAtTime(0.55, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.9);

      osc.connect(gain);
      gain.connect(this.audioCtx.destination);

      osc.start(now);
      osc.stop(now + 0.9);
    } catch (e) {
      console.warn('Audio play error:', e);
    }
  }

  playBeChime() {
    if (!this.soundEnabled) return;
    this._initCtx();
    if (!this.audioCtx) return;

    try {
      if (this.audioCtx.state === 'suspended') this.audioCtx.resume();
      const now = this.audioCtx.currentTime;

      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(659.25, now); // E5

      gain.gain.setValueAtTime(0.6, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.6);

      osc.connect(gain);
      gain.connect(this.audioCtx.destination);

      osc.start(now);
      osc.stop(now + 0.6);
    } catch (e) {
      console.warn('Audio play error:', e);
    }
  }
}


class TradingSimulatorApp {
  constructor() {
    this.chartManager = null;
    this.replayController = null;
    this.indicatorsManager = null;
    this.tradePanel = null;
    this.sound = new SoundSynthesizer();

    this.defaultSymbol = localStorage.getItem('defaultSymbol') || 'NAS100';
    this.currentSymbol = this.defaultSymbol;
    try {
      this.hiddenSymbols = new Set(JSON.parse(localStorage.getItem('hiddenSymbols') || '[]'));
    } catch (e) {
      this.hiddenSymbols = new Set();
    }
    this.timeframePair = 'H4_H1_M15';
    this.activeChartSlot = 1; // 1 = TF1 (Left), 2 = TF2 (Mid), 3 = TF3 (Right)
    this.slotTimeframes = { 1: 'H4', 2: 'H1', 3: 'M15' };
    try {
      const savedFavs = JSON.parse(localStorage.getItem('tvFavoriteTimeframes') || 'null');
      this.favoriteTimeframes = Array.isArray(savedFavs) && savedFavs.length > 0
        ? savedFavs
        : ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'];
    } catch (e) {
      this.favoriteTimeframes = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'];
    }
    this.forecastMode = 'COMBINED_HTF_LTF';
    this.liveRealtimeActive = false;
    this.livePollTimer = null;
    this.totalBars = 0;
    this.currentIndex = 0;
    this.state = null;

    // Configurable Risk Engine: 'PERCENT' (% Balance), 'FIXED_USD' ($ USD), 'FIXED_LOT' (Lots)
    this.riskConfig = {
      mode: 'PERCENT',
      value: 1.0
    };

    // Position 2 Exit Strategy: 'ATR_TRAILING' (Open TP + 3 ATR Trailing) or 'FIXED_RR' (RR 1:3)
    this.pos2ExitConfig = {
      mode: 'ATR_TRAILING',
      atrMultiplier: 3.0,
      fixedRR: 3.0
    };

    // Auto-Radar State (OFF by default so LIVE mode stays 100% clean)
    this.autoRadarActive = false;
    this.isAutoPaused = false;
    this.autoPauseTimeout = null;
    this.pauseInterval = null;
    this.lastProcessedIndex = -1;
    this.lastClosedCount = 0;
    this.activeCluster = null;

    this.symbolSelect = document.getElementById('symbolSelect');
    this.btnAutoRadar = document.getElementById('btnAutoRadar');
    this.btnSoundToggle = document.getElementById('btnSoundToggle');
    this.btnTestSound = document.getElementById('btnTestSound');
    this.soundStatusText = document.getElementById('soundStatusText');
    this.btnJump2000 = document.getElementById('btnJump2000');
    this.btnReset = document.getElementById('btnReset');
    this.btnOpenResetModal = document.getElementById('btnOpenResetModal');
    this.resetBacktestModal = document.getElementById('resetBacktestModal');
    this.btnCloseResetModal = document.getElementById('btnCloseResetModal');
    this.btnCancelReset = document.getElementById('btnCancelReset');
    this.btnConfirmReset = document.getElementById('btnConfirmReset');
    this.inputResetBalance = document.getElementById('inputResetBalance');
    this.inputRiskValue = document.getElementById('inputRiskValue');
    this.riskModeLabel = document.getElementById('riskModeLabel');
    this.riskUnitLabel = document.getElementById('riskUnitLabel');
    this.riskDescText = document.getElementById('riskDescText');
    this.inputAtrMultiplier = document.getElementById('inputAtrMultiplier');


    this.btnStatsModal = document.getElementById('btnStatsModal');
    this.statsModal = document.getElementById('statsModal');
    this.btnCloseStats = document.getElementById('btnCloseStats');
    this.fileCsvInput = document.getElementById('fileCsvInput');

    this.pauseOverlay = document.getElementById('radarPauseOverlay');
    this.pauseOverlayTitle = document.getElementById('pauseOverlayTitle');
    this.pauseOverlayDesc = document.getElementById('pauseOverlayDesc');
    this.pauseOverlayTimer = document.getElementById('pauseOverlayTimer');
  }


  async init() {
    this.chartManager = new MultiChartManager();
    if (window.DrawingToolsManager) {
      this.drawingTools = new DrawingToolsManager(this.chartManager);
    }
    this.replayController = new ReplayController(this);
    this.indicatorsManager = new IndicatorsManager(this);
    if (window.ScriptEditorManager) {
      this.scriptEditor = new ScriptEditorManager(this);
    }
    this.tradePanel = new TradePanel(this);

    this.bindEvents();
    this.setupResetBacktestModal();
    this.setupSymbolSearchModal();
    this.setupEA();
    await this.loadSymbols();
    // Default to LIVE mode on startup
    this.liveRealtimeActive = false;
    await this.toggleLiveRealtime();
  }

  setupResetBacktestModal() {
    // 1. Open / Close Modal
    if (this.btnOpenResetModal) {
      this.btnOpenResetModal.addEventListener('click', () => {
        if (this.resetBacktestModal) {
          const currentBal = (this.state && this.state.account) ? this.state.account.initial_balance || 10000 : 10000;
          if (this.inputResetBalance) this.inputResetBalance.value = currentBal;
          this.resetBacktestModal.classList.add('open');
        }
      });
    }

    if (this.btnCloseResetModal) {
      this.btnCloseResetModal.addEventListener('click', () => {
        if (this.resetBacktestModal) this.resetBacktestModal.classList.remove('open');
      });
    }

    if (this.btnCancelReset) {
      this.btnCancelReset.addEventListener('click', () => {
        if (this.resetBacktestModal) this.resetBacktestModal.classList.remove('open');
      });
    }

    // 2. Risk Mode Radio Change Handler
    const radioModes = document.querySelectorAll('input[name="radioRiskMode"]');
    radioModes.forEach(radio => {
      radio.addEventListener('change', (e) => {
        const mode = e.target.value;
        if (mode === 'PERCENT') {
          if (this.riskModeLabel) this.riskModeLabel.innerText = 'Mức rủi ro (% Balance):';
          if (this.riskUnitLabel) this.riskUnitLabel.innerText = '%';
          if (this.inputRiskValue) { this.inputRiskValue.value = '1.0'; this.inputRiskValue.step = '0.1'; this.inputRiskValue.min = '0.1'; }
          if (this.riskDescText) this.riskDescText.innerText = 'Tự động tính Lot để khi dính SL chỉ mất đúng 1.0% tài khoản (~$100 cho tài khoản $10,000).';
        } else if (mode === 'FIXED_USD') {
          if (this.riskModeLabel) this.riskModeLabel.innerText = 'Số tiền rủi ro cố định (USD):';
          if (this.riskUnitLabel) this.riskUnitLabel.innerText = '$';
          if (this.inputRiskValue) { this.inputRiskValue.value = '100'; this.inputRiskValue.step = '10'; this.inputRiskValue.min = '1'; }
          if (this.riskDescText) this.riskDescText.innerText = 'Tự động tính Lot để khi dính SL chỉ mất đúng số tiền $ USD cố định trên mỗi vị thế.';
        } else if (mode === 'FIXED_LOT') {
          if (this.riskModeLabel) this.riskModeLabel.innerText = 'Khối lượng vào lệnh cố định (Lots):';
          if (this.riskUnitLabel) this.riskUnitLabel.innerText = 'lots';
          if (this.inputRiskValue) { this.inputRiskValue.value = '0.10'; this.inputRiskValue.step = '0.01'; this.inputRiskValue.min = '0.01'; }
          if (this.riskDescText) this.riskDescText.innerText = 'Vào lệnh khối lượng cố định không phụ thuộc vào khoảng cách Stop Loss.';
        }
      });
    });

    // 3. Confirm Reset & Start Backtest
    if (this.btnConfirmReset) {
      this.btnConfirmReset.addEventListener('click', async () => {
        const initialBal = parseFloat(this.inputResetBalance ? this.inputResetBalance.value : 10000) || 10000;
        
        let selectedMode = 'PERCENT';
        const checkedRadio = document.querySelector('input[name="radioRiskMode"]:checked');
        if (checkedRadio) selectedMode = checkedRadio.value;

        const riskVal = parseFloat(this.inputRiskValue ? this.inputRiskValue.value : 1.0) || 1.0;

        let startPoint = 'YEAR_2000';
        const checkedStart = document.querySelector('input[name="radioStartPoint"]:checked');
        if (checkedStart) startPoint = checkedStart.value;

        try {
          const resp = await fetch('/api/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              initial_balance: initialBal,
              risk_mode: selectedMode,
              risk_value: riskVal,
              start_point: startPoint
            })
          });
          const res = await resp.json();
          if (res.success) {
            let pos2Mode = 'ATR_TRAILING';
            const checkedPos2 = document.querySelector('input[name="radioPos2Mode"]:checked');
            if (checkedPos2) pos2Mode = checkedPos2.value;
            const atrMult = parseFloat(this.inputAtrMultiplier ? this.inputAtrMultiplier.value : 3.0) || 3.0;

            this.riskConfig = {
              mode: selectedMode,
              value: riskVal
            };

            this.pos2ExitConfig = {
              mode: pos2Mode,
              atrMultiplier: atrMult,
              fixedRR: 3.0
            };

            this.activeCluster = null;
            this.lastProcessedIndex = -1;

            if (this.resetBacktestModal) this.resetBacktestModal.classList.remove('open');
            await this.refreshState();
            if (this.chartManager) this.chartManager.resetPriceScaleAndCenter();
            
            const modeDesc = selectedMode === 'PERCENT' ? `${riskVal}% Balance` : (selectedMode === 'FIXED_USD' ? `$${riskVal}` : `${riskVal} Lots`);
            const pos2Desc = pos2Mode === 'ATR_TRAILING' ? `Lệnh 2: Thả TP + ${atrMult} ATR Trailing` : 'Lệnh 2: RR 1:3';
            if (this.chartManager) {
              this.chartManager.showToast(`🚀 Backtest Mới! Vốn: $${initialBal.toLocaleString()} | Risk: ${modeDesc} | ${pos2Desc}`);
            }
          }
        } catch (e) {
          console.error('Error resetting backtest:', e);
        }
      });

    }
  }

  calculateLotsForTrade(slDist, pipSize = 0.0001) {
    const balance = (this.state && this.state.account) ? this.state.account.balance : 10000;
    const slPips = Math.max(1, slDist / pipSize);
    let lotTotal = 0.10;

    if (this.riskConfig.mode === 'PERCENT') {
      const riskUsd = balance * (this.riskConfig.value / 100.0);
      lotTotal = parseFloat((riskUsd / (slPips * 10.0)).toFixed(2));
    } else if (this.riskConfig.mode === 'FIXED_USD') {
      const riskUsd = this.riskConfig.value;
      lotTotal = parseFloat((riskUsd / (slPips * 10.0)).toFixed(2));
    } else if (this.riskConfig.mode === 'FIXED_LOT') {
      lotTotal = parseFloat(this.riskConfig.value.toFixed(2));
    }

    lotTotal = Math.max(0.02, lotTotal);
    const lotSplit = parseFloat((lotTotal / 2.0).toFixed(2));
    return {
      lotTotal,
      lotSplit: Math.max(0.01, lotSplit)
    };
  }

  bindEvents() {
    if (this.symbolSelect) {
      this.symbolSelect.addEventListener('change', (e) => {
        const val = e.target.value;
        if (val === '_OPEN_SEARCH_') {
          this.openSymbolSearchModal();
          this.symbolSelect.value = this.currentSymbol;
        } else if (val === '_MANAGE_SYMBOLS_') {
          this.openSymbolManageModal();
          this.symbolSelect.value = this.currentSymbol;
        } else {
          this.loadSymbol(val);
        }
      });
    }


    if (this.btnAutoRadar) {
      this.btnAutoRadar.addEventListener('click', () => {
        this.autoRadarActive = !this.autoRadarActive;
        this.btnAutoRadar.classList.toggle('active', this.autoRadarActive);
        if (this.autoRadarActive) {
          this.btnAutoRadar.style.background = 'linear-gradient(135deg, rgba(168, 85, 247, 0.35) 0%, rgba(59, 130, 246, 0.35) 100%)';
          this.btnAutoRadar.style.borderColor = 'var(--color-purple)';
        } else {
          this.btnAutoRadar.style.background = 'transparent';
          this.btnAutoRadar.style.borderColor = 'var(--border-color)';
        }
      });
    }

    if (this.btnSoundToggle) {
      this.btnSoundToggle.addEventListener('click', () => {
        this.sound.soundEnabled = !this.sound.soundEnabled;
        this.btnSoundToggle.classList.toggle('active', this.sound.soundEnabled);
        if (this.soundStatusText) {
          this.soundStatusText.innerText = this.sound.soundEnabled ? 'Chuông: BẬT' : 'Chuông: TẮT';
        }
        if (this.sound.soundEnabled) {
          this.sound._initCtx();
          this.sound.playEntryBell();
          if (this.chartManager) this.chartManager.showToast('🔔 Chuông báo: ĐÃ BẬT');
        } else {
          if (this.chartManager) this.chartManager.showToast('🔕 Chuông báo: ĐÃ TẮT');
        }
      });
    }

    if (this.btnTestSound) {
      this.btnTestSound.addEventListener('click', () => {
        this.sound._initCtx();
        this.sound.playEntryBell();
        if (this.chartManager) this.chartManager.showToast('🔊 Đang phát chuông thử nghiệm!');
      });
    }


    if (this.btnJump2000) {
      this.btnJump2000.addEventListener('click', () => this.jumpToYear2000());
    }

    if (this.btnReset) {
      this.btnReset.addEventListener('click', async () => {
        if (confirm('Bạn có chắc muốn Reset lại toàn bộ tài khoản và vị thế về ban đầu?')) {
          await fetch('/api/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ initial_balance: 10000 })
          });
          this.activeCluster = null;
          await this.refreshState();
        }
      });
    }

    if (this.btnStatsModal) {
      this.btnStatsModal.addEventListener('click', () => this.openStatsModal());
    }
    if (this.btnCloseStats) {
      this.btnCloseStats.addEventListener('click', () => this.statsModal.classList.remove('open'));
    }
    if (this.fileCsvInput) {
      this.fileCsvInput.addEventListener('change', (e) => this.handleCsvUpload(e));
    }

    const btnToggleSidebar = document.getElementById('btnToggleSidebar');
    if (btnToggleSidebar) {
      btnToggleSidebar.addEventListener('click', () => this.toggleSidebar());
    }

    const btnToggleHeaderTools = document.getElementById('btnToggleHeaderTools');
    if (btnToggleHeaderTools) {
      btnToggleHeaderTools.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleHeaderTools();
      });
    }

    // Close Tools popover or TF dropdown when clicking outside
    document.addEventListener('click', (e) => {
      const pop = document.getElementById('headerToolsPopover');
      const btn = document.getElementById('btnToggleHeaderTools');
      if (pop && pop.classList.contains('open') && !pop.contains(e.target) && (!btn || !btn.contains(e.target))) {
        this.toggleHeaderTools(false);
      }
      const tfMenu = document.getElementById('tvTfDropdownMenu');
      const tfBtn = document.getElementById('btnTvTfDropdown');
      if (tfMenu && tfMenu.classList.contains('open') && !tfMenu.contains(e.target) && (!tfBtn || !tfBtn.contains(e.target))) {
        tfMenu.classList.remove('open');
      }
    });

    this.initTradingViewTimeframeBar();

    const btnManageSymbols = document.getElementById('btnManageSymbols');
    if (btnManageSymbols) {
      btnManageSymbols.addEventListener('click', () => this.openSymbolManageModal());
    }
    const btnCloseSymMgr = document.getElementById('btnCloseSymbolManage');
    const btnCancelSymMgr = document.getElementById('btnCancelSymbolManage');
    const btnSaveSymMgr = document.getElementById('btnSaveSymbolManage');
    const btnShowAllSym = document.getElementById('btnSymbolManageShowAll');
    const symMgrSearch = document.getElementById('symbolManageSearch');
    if (btnCloseSymMgr) btnCloseSymMgr.addEventListener('click', () => this.closeSymbolManageModal());
    if (btnCancelSymMgr) btnCancelSymMgr.addEventListener('click', () => this.closeSymbolManageModal());
    if (btnSaveSymMgr) btnSaveSymMgr.addEventListener('click', () => this.saveSymbolManageModal());
    if (btnShowAllSym) btnShowAllSym.addEventListener('click', () => {
      this.hiddenSymbols.clear();
      this.renderSymbolManageList();
    });
    if (symMgrSearch) symMgrSearch.addEventListener('input', () => this.renderSymbolManageList());

    const btnEdgeToggleSidebar = document.getElementById('btnEdgeToggleSidebar');
    if (btnEdgeToggleSidebar) {
      btnEdgeToggleSidebar.addEventListener('click', () => this.toggleSidebar());
    }

    const btnToggleDynamicSlTp = document.getElementById('btnToggleDynamicSlTp');
    if (btnToggleDynamicSlTp) {
      btnToggleDynamicSlTp.addEventListener('click', () => {
        if (this.chartManager) this.chartManager.toggleDynamicSlTp();
      });
    }

    const btnLiveModeToggle = document.getElementById('btnLiveModeToggle');
    if (btnLiveModeToggle) {
      btnLiveModeToggle.addEventListener('click', async () => {
        await this.toggleLiveRealtime();
      });
    }

    const btnQuickLoadTF1 = document.getElementById('btnQuickLoadTF1');
    if (btnQuickLoadTF1) {
      btnQuickLoadTF1.addEventListener('click', () => {
        if (this.indicatorsManager) this.indicatorsManager.loadPresetTF1();
      });
    }

    // Global Hotkey Ctrl+B to toggle sidebar
    window.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'b' || e.key === 'B')) {
        e.preventDefault();
        this.toggleSidebar();
      }
    });
  }

  toggleSidebar(forceState) {
    const sidebar = document.querySelector('.trade-sidebar');
    const btn = document.getElementById('btnToggleSidebar');
    const edgeBtn = document.getElementById('btnEdgeToggleSidebar');
    if (!sidebar) return;

    const currentlyCollapsed = sidebar.classList.contains('collapsed');
    const shouldCollapse = (forceState !== undefined) ? !forceState : !currentlyCollapsed;

    if (shouldCollapse) {
      sidebar.classList.add('collapsed');
      if (btn) {
        btn.classList.add('active');
        btn.innerHTML = '<span>◨ Hiện Sidebar</span>';
        btn.title = "Mở rộng bảng lệnh bên phải (Hiện sidebar - Phím Ctrl+B)";
      }
      if (edgeBtn) {
        edgeBtn.innerHTML = '❮';
        edgeBtn.classList.add('collapsed-handle');
        edgeBtn.title = "Mở rộng bảng lệnh bên phải (Hiện sidebar)";
      }
    } else {
      sidebar.classList.remove('collapsed');
      if (btn) {
        btn.classList.remove('active');
        btn.innerHTML = '<span>◧ Ẩn Sidebar</span>';
        btn.title = "Thu gọn bảng lệnh bên phải (Ẩn sidebar - Phím Ctrl+B)";
      }
      if (edgeBtn) {
        edgeBtn.innerHTML = '❯';
        edgeBtn.classList.remove('collapsed-handle');
        edgeBtn.title = "Thu gọn bảng lệnh bên phải";
      }
    }

    if (this.chartManager) {
      setTimeout(() => this.chartManager.resizeAll(), 40);
      setTimeout(() => this.chartManager.resizeAll(), 150);
      setTimeout(() => this.chartManager.resizeAll(), 300);
    }
  }

  jumpToYear2000() {
    if (this.replayController) {
      this.replayController.jumpToDateTime('2000-01-03 00:00:00');
    }
  }

  toggleHeaderTools(forceExpanded) {
    const pop = document.getElementById('headerToolsPopover');
    const arrow = document.getElementById('headerToolsArrow');
    const btn = document.getElementById('btnToggleHeaderTools');
    if (!pop) return;
    const currentlyOpen = pop.classList.contains('open');
    const shouldOpen = (forceExpanded !== undefined) ? !!forceExpanded : !currentlyOpen;
    pop.classList.toggle('open', shouldOpen);
    if (arrow) arrow.innerText = shouldOpen ? '▾' : '▸';
    if (btn) btn.classList.toggle('active', shouldOpen);
  }

  initTradingViewTimeframeBar() {
    this._allTfMeta = [
      { code: 'M1', short: '1m', label: '1 phút', group: 'PHÚT' },
      { code: 'M5', short: '5m', label: '5 phút', group: 'PHÚT' },
      { code: 'M15', short: '15m', label: '15 phút', group: 'PHÚT' },
      { code: 'M30', short: '30m', label: '30 phút', group: 'PHÚT' },
      { code: 'H1', short: '1h', label: '1 giờ', group: 'GIỜ' },
      { code: 'H4', short: '4h', label: '4 giờ', group: 'GIỜ' },
      { code: 'D1', short: '1D', label: '1 ngày', group: 'NGÀY / TUẦN' },
      { code: 'W1', short: '1W', label: '1 tuần', group: 'NGÀY / TUẦN' },
    ];

    // Pane click listeners -> focus that chart & update TF bar
    const paneMap = [
      { slot: 1, el: document.getElementById('paneH4') },
      { slot: 2, el: document.getElementById('paneTF2') },
      { slot: 3, el: document.getElementById('paneM15') },
    ];
    paneMap.forEach(({ slot, el }) => {
      if (!el) return;
      el.addEventListener('mousedown', () => this.setActiveChartSlot(slot));
    });

    // K1 / K2 / K3 quick tab buttons in header
    [1, 2, 3].forEach(slot => {
      const tab = document.getElementById(`tvPaneTab${slot}`);
      if (tab) {
        tab.addEventListener('click', () => this.setActiveChartSlot(slot));
      }
    });

    // Dropdown toggle button
    const dropBtn = document.getElementById('btnTvTfDropdown');
    const dropMenu = document.getElementById('tvTfDropdownMenu');
    if (dropBtn && dropMenu) {
      dropBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.renderTvTfDropdown();
        dropMenu.classList.toggle('open');
      });
    }

    this.syncSlotTimeframesFromPair(this.timeframePair);
    this.setActiveChartSlot(1);
  }

  syncSlotTimeframesFromPair(tfPair) {
    const tfp = String(tfPair || 'H4_H1_M15').toUpperCase().trim();
    if (tfp === 'H4_H1_M15' || tfp === 'H4_M15') {
      this.slotTimeframes = { 1: 'H4', 2: 'H1', 3: 'M15' };
    } else if (tfp === 'D1_H4_H1' || tfp === 'H4_H1') {
      this.slotTimeframes = { 1: 'D1', 2: 'H4', 3: 'H1' };
    } else if (tfp === 'H1_M15_M5' || tfp === 'H1_M5') {
      this.slotTimeframes = { 1: 'H1', 2: 'M15', 3: 'M5' };
    } else if (tfp === 'M15_M5_M1' || tfp === 'M5_M1') {
      this.slotTimeframes = { 1: 'M15', 2: 'M5', 3: 'M1' };
    } else {
      const parts = tfp.split('_');
      if (parts.length === 3) {
        this.slotTimeframes = { 1: parts[0], 2: parts[1], 3: parts[2] };
      }
    }
    this.renderTvTfBar();
  }

  setActiveChartSlot(slot) {
    this.activeChartSlot = slot;
    const panes = {
      1: document.getElementById('paneH4'),
      2: document.getElementById('paneTF2'),
      3: document.getElementById('paneM15')
    };
    [1, 2, 3].forEach(s => {
      if (panes[s]) panes[s].classList.toggle('active-pane', s === slot);
      const tab = document.getElementById(`tvPaneTab${s}`);
      if (tab) tab.classList.toggle('active', s === slot);
    });
    this.renderTvTfBar();
  }

  renderTvTfBar() {
    [1, 2, 3].forEach(s => {
      const el = document.getElementById(`tvPaneTf${s}`);
      if (el) el.innerText = this.slotTimeframes[s] || '--';
    });

    const activeTf = this.slotTimeframes[this.activeChartSlot] || 'H4';
    const favList = document.getElementById('tvFavTfList');
    if (!favList || !this._allTfMeta) return;
    favList.innerHTML = '';

    // Always include activeTf in bar even if not starred so user clearly sees it
    const toShow = [...this.favoriteTimeframes];
    if (!toShow.includes(activeTf)) toShow.push(activeTf);

    this._allTfMeta
      .filter(m => toShow.includes(m.code))
      .forEach(m => {
        const btn = document.createElement('button');
        btn.className = 'tv-fav-tf-btn' + (m.code === activeTf ? ' active' : '');
        btn.innerText = m.short;
        btn.title = `Đổi Khung ${this.activeChartSlot} sang ${m.code} (${m.label})`;
        btn.addEventListener('click', () => this.changeActiveSlotTimeframe(m.code));
        favList.appendChild(btn);
      });
  }

  renderTvTfDropdown() {
    const menu = document.getElementById('tvTfDropdownMenu');
    if (!menu || !this._allTfMeta) return;
    const activeTf = this.slotTimeframes[this.activeChartSlot] || 'H4';
    menu.innerHTML = '';

    const groups = ['PHÚT', 'GIỜ', 'NGÀY / TUẦN'];
    groups.forEach(g => {
      const hdr = document.createElement('div');
      hdr.className = 'tv-tf-group-lbl';
      hdr.innerText = g;
      menu.appendChild(hdr);

      this._allTfMeta.filter(m => m.group === g).forEach(m => {
        const isFav = this.favoriteTimeframes.includes(m.code);
        const item = document.createElement('div');
        item.className = 'tv-tf-drop-item' + (m.code === activeTf ? ' active' : '');
        item.innerHTML = `
          <span><b>${m.short}</b> &nbsp;<span style="color:#94a3b8;font-size:11px;">${m.label} (${m.code})</span></span>
          <span class="tv-tf-star ${isFav ? 'fav' : ''}" title="Ghim / Bỏ ghim yêu thích">${isFav ? '★' : '☆'}</span>
        `;
        item.addEventListener('click', (e) => {
          if (e.target.classList.contains('tv-tf-star')) {
            e.stopPropagation();
            if (isFav) {
              this.favoriteTimeframes = this.favoriteTimeframes.filter(c => c !== m.code);
            } else {
              this.favoriteTimeframes.push(m.code);
            }
            localStorage.setItem('tvFavoriteTimeframes', JSON.stringify(this.favoriteTimeframes));
            this.renderTvTfBar();
            this.renderTvTfDropdown();
            return;
          }
          menu.classList.remove('open');
          this.changeActiveSlotTimeframe(m.code);
        });
        menu.appendChild(item);
      });
    });
  }

  async changeActiveSlotTimeframe(newTf) {
    const slot = this.activeChartSlot || 1;
    if (this.slotTimeframes[slot] === newTf) return;
    this.slotTimeframes[slot] = newTf;
    const newTriplet = `${this.slotTimeframes[1]}_${this.slotTimeframes[2]}_${this.slotTimeframes[3]}`;
    this.timeframePair = newTriplet;
    this.renderTvTfBar();

    // Sync tfPairSelect if matching preset exists
    const tfSel = document.getElementById('tfPairSelect');
    if (tfSel) {
      const hasOpt = Array.from(tfSel.options).some(o => o.value === newTriplet);
      if (hasOpt) tfSel.value = newTriplet;
    }

    this.showToast(`⏱️ Khung ${slot} ➔ ${newTf} (Bộ khung: ${this.slotTimeframes[1]} + ${this.slotTimeframes[2]} + ${this.slotTimeframes[3]})`);
    if (this.liveRealtimeActive) {
      await this.syncLiveRealtime();
    } else {
      await this.loadSymbol(this.currentSymbol, newTriplet);
    }
  }

  renderSymbolDropdown() {
    if (!this.symbolSelect || !this.allAvailableSymbols) return;
    this.symbolSelect.innerHTML = '';

    // Filter out hidden symbols, but always keep currentSymbol & defaultSymbol visible
    const visibleList = this.allAvailableSymbols.filter(s =>
      !this.hiddenSymbols.has(s.symbol) || s.symbol === this.currentSymbol || s.symbol === this.defaultSymbol
    ).slice(0, 30);

    // Ensure NAS100 / defaultSymbol is at the very top
    const ensureTop = (sym) => {
      const idx = visibleList.findIndex(s => s.symbol === sym);
      if (idx > 0) {
        const [item] = visibleList.splice(idx, 1);
        visibleList.unshift(item);
      } else if (idx === -1) {
        const found = this.allAvailableSymbols.find(s => s.symbol === sym);
        visibleList.unshift(found || { symbol: sym, name: sym });
      }
    };
    ensureTop(this.defaultSymbol || 'NAS100');
    if (this.currentSymbol !== this.defaultSymbol) ensureTop(this.currentSymbol);

    visibleList.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.symbol;
      const star = s.symbol === this.defaultSymbol ? '⭐ ' : '';
      opt.innerText = `${star}${s.symbol} - ${s.name || s.symbol}`;
      if (s.symbol === this.currentSymbol) opt.selected = true;
      this.symbolSelect.appendChild(opt);
    });

    const optManage = document.createElement('option');
    optManage.value = '_MANAGE_SYMBOLS_';
    optManage.innerText = '✏️ Sửa / Ẩn-Hiện danh sách cặp...';
    optManage.style.color = '#fbbf24';
    optManage.style.fontWeight = 'bold';
    this.symbolSelect.appendChild(optManage);

    const optSearch = document.createElement('option');
    optSearch.value = '_OPEN_SEARCH_';
    optSearch.innerText = '🔍 Tìm cặp khác (TradingView Search)...';
    optSearch.style.color = '#38bdf8';
    optSearch.style.fontWeight = 'bold';
    this.symbolSelect.appendChild(optSearch);
  }

  openSymbolManageModal() {
    const modal = document.getElementById('symbolManageModal');
    if (!modal) return;
    this.renderSymbolManageList();
    modal.classList.add('open');
  }

  closeSymbolManageModal() {
    const modal = document.getElementById('symbolManageModal');
    if (modal) modal.classList.remove('open');
  }

  renderSymbolManageList() {
    const listEl = document.getElementById('symbolManageList');
    const q = (document.getElementById('symbolManageSearch')?.value || '').toLowerCase().trim();
    if (!listEl) return;
    listEl.innerHTML = '';

    const items = (this.allAvailableSymbols || []).filter(s =>
      !q || s.symbol.toLowerCase().includes(q) || String(s.name || '').toLowerCase().includes(q)
    ).slice(0, 60);

    items.forEach(s => {
      const isVisible = !this.hiddenSymbols.has(s.symbol);
      const isDef = s.symbol === this.defaultSymbol;
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:6px 10px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:5px;';
      row.innerHTML = `
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;flex:1;">
          <input type="checkbox" class="sym-vis-chk" data-sym="${s.symbol}" ${isVisible ? 'checked' : ''} style="width:16px;height:16px;cursor:pointer;">
          <span style="font-weight:700;color:#f8fafc;font-size:12px;">${s.symbol}</span>
          <span style="color:#94a3b8;font-size:11px;">${s.name || ''}</span>
        </label>
        <button class="btn-header btn-set-def-sym" data-sym="${s.symbol}" style="padding:2px 8px;font-size:10.5px;${isDef ? 'border-color:#fbbf24;color:#fbbf24;background:rgba(245,158,11,0.18);font-weight:700;' : ''}">
          ${isDef ? '⭐ Mặc định' : '☆ Đặt mặc định'}
        </button>
      `;
      listEl.appendChild(row);
    });

    listEl.querySelectorAll('.sym-vis-chk').forEach(chk => {
      chk.addEventListener('change', (e) => {
        const sym = e.target.getAttribute('data-sym');
        if (e.target.checked) this.hiddenSymbols.delete(sym);
        else this.hiddenSymbols.add(sym);
      });
    });

    listEl.querySelectorAll('.btn-set-def-sym').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const sym = e.currentTarget.getAttribute('data-sym');
        this.defaultSymbol = sym;
        this.hiddenSymbols.delete(sym);
        localStorage.setItem('defaultSymbol', sym);
        this.renderSymbolManageList();
      });
    });
  }

  saveSymbolManageModal() {
    localStorage.setItem('hiddenSymbols', JSON.stringify(Array.from(this.hiddenSymbols)));
    localStorage.setItem('defaultSymbol', this.defaultSymbol || 'NAS100');
    this.renderSymbolDropdown();
    this.closeSymbolManageModal();
    this.showToast(`✅ Đã lưu danh sách cặp (Mặc định: ${this.defaultSymbol})!`);
  }

  async loadSymbols() {
    try {
      const resp = await fetch('/api/symbols');
      const res = await resp.json();
      this.allAvailableSymbols = res.symbols || [];
      if (this.allAvailableSymbols.length > 0 && this.symbolSelect) {
        this.renderSymbolDropdown();
      }
    } catch (e) {
      console.error('Error loading symbols:', e);
    }
  }

  setupSymbolSearchModal() {
    this.symbolSearchModal = document.getElementById('symbolSearchModal');
    this.btnOpenSymbolSearch = document.getElementById('btnOpenSymbolSearch');
    this.btnCloseSymbolSearch = document.getElementById('btnCloseSymbolSearch');
    this.btnCloseSymbolSearchFooter = document.getElementById('btnCloseSymbolSearchFooter');
    this.symbolModalSearchInput = document.getElementById('symbolModalSearchInput');
    this.symbolModalResultsList = document.getElementById('symbolModalResultsList');
    this.btnManualAddSymbol = document.getElementById('btnManualAddSymbol');
    this.symbolModalCountText = document.getElementById('symbolModalCountText');

    this.currentSymFilterCategory = 'ALL';

    if (this.btnOpenSymbolSearch) {
      this.btnOpenSymbolSearch.addEventListener('click', () => this.openSymbolSearchModal());
    }
    if (this.btnCloseSymbolSearch) {
      this.btnCloseSymbolSearch.addEventListener('click', () => this.closeSymbolSearchModal());
    }
    if (this.btnCloseSymbolSearchFooter) {
      this.btnCloseSymbolSearchFooter.addEventListener('click', () => this.closeSymbolSearchModal());
    }

    if (this.symbolModalSearchInput) {
      let debounceTimer = null;
      this.symbolModalSearchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          this.renderSymbolSearchResults(e.target.value, this.currentSymFilterCategory);
        }, 120);
      });

      this.symbolModalSearchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          const val = this.symbolModalSearchInput.value.trim().toUpperCase();
          if (val) this.selectSymbolAndLoad(val);
        }
      });
    }

    if (this.btnManualAddSymbol) {
      this.btnManualAddSymbol.addEventListener('click', () => {
        const val = this.symbolModalSearchInput ? this.symbolModalSearchInput.value.trim().toUpperCase() : '';
        if (val) {
          this.selectSymbolAndLoad(val);
        } else {
          alert('Vui lòng nhập mã cặp tiền hoặc tài sản cần nạp từ MT5!');
        }
      });
    }

    // Category filter tabs
    const tabAll = document.getElementById('tabSymAll');
    const tabForex = document.getElementById('tabSymForex');
    const tabMetals = document.getElementById('tabSymMetals');
    const tabIndices = document.getElementById('tabSymIndices');
    const tabCrypto = document.getElementById('tabSymCrypto');

    const setSymTab = (cat, activeTab) => {
      this.currentSymFilterCategory = cat;
      [tabAll, tabForex, tabMetals, tabIndices, tabCrypto].forEach(t => {
        if (t) t.classList.remove('active');
      });
      if (activeTab) activeTab.classList.add('active');
      const query = this.symbolModalSearchInput ? this.symbolModalSearchInput.value : '';
      this.renderSymbolSearchResults(query, cat);
    };

    if (tabAll) tabAll.addEventListener('click', () => setSymTab('ALL', tabAll));
    if (tabForex) tabForex.addEventListener('click', () => setSymTab('FOREX', tabForex));
    if (tabMetals) tabMetals.addEventListener('click', () => setSymTab('METALS', tabMetals));
    if (tabIndices) tabIndices.addEventListener('click', () => setSymTab('INDICES', tabIndices));
    if (tabCrypto) tabCrypto.addEventListener('click', () => setSymTab('CRYPTO', tabCrypto));
  }

  openSymbolSearchModal() {
    if (this.symbolSearchModal) {
      this.symbolSearchModal.classList.add('open');
      if (this.symbolModalSearchInput) {
        this.symbolModalSearchInput.value = '';
        setTimeout(() => this.symbolModalSearchInput.focus(), 100);
      }
      this.renderSymbolSearchResults('', 'ALL');
    }
  }

  closeSymbolSearchModal() {
    if (this.symbolSearchModal) {
      this.symbolSearchModal.classList.remove('open');
    }
  }

  renderSymbolSearchResults(query = '', category = 'ALL') {
    if (!this.symbolModalResultsList) return;
    const q = (query || '').trim().toUpperCase();
    const cat = (category || 'ALL').toUpperCase();

    let symbols = this.allAvailableSymbols || [];

    const anyMatch = (str, list) => list.some(item => str.includes(item));

    // Filter by category
    if (cat === 'FOREX') {
      symbols = symbols.filter(s => {
        const path = (s.path || '').toUpperCase();
        const sym = s.symbol.toUpperCase();
        return path.includes('FOREX') || (sym.length === 6 && (sym.endsWith('USD') || sym.startsWith('USD') || sym.endsWith('JPY') || sym.startsWith('EUR') || sym.startsWith('GBP')));
      });
    } else if (cat === 'METALS') {
      symbols = symbols.filter(s => {
        const p = (s.path || '').toUpperCase();
        const sym = s.symbol.toUpperCase();
        return p.includes('METAL') || p.includes('COMMODIT') || sym.includes('XAU') || sym.includes('GOLD') || sym.includes('XAG') || sym.includes('SILVER') || sym.includes('OIL');
      });
    } else if (cat === 'INDICES') {
      symbols = symbols.filter(s => {
        const p = (s.path || '').toUpperCase();
        const sym = s.symbol.toUpperCase();
        return p.includes('IND') || anyMatch(sym, ['US30', 'NAS100', 'JPN225', 'UK100', 'GER40', 'SPX', 'USTEC', 'WS30', 'DJ30', 'DAX', 'FTSE', 'ASX']);
      });
    } else if (cat === 'CRYPTO') {
      symbols = symbols.filter(s => {
        const p = (s.path || '').toUpperCase();
        const sym = s.symbol.toUpperCase();
        return p.includes('CRYPTO') || anyMatch(sym, ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'BNB']);
      });
    }

    // Filter by search text
    if (q) {
      symbols = symbols.filter(s => {
        const sym = s.symbol.toUpperCase();
        const name = (s.name || '').toUpperCase();
        return sym.includes(q) || name.includes(q);
      });
    }

    if (this.symbolModalCountText) {
      this.symbolModalCountText.innerText = `Tìm thấy ${symbols.length} cặp tiền / tài sản khả dụng trên MT5 Broker Server`;
    }

    this.symbolModalResultsList.innerHTML = '';

    if (symbols.length === 0) {
      this.symbolModalResultsList.innerHTML = `
        <div style="text-align:center;padding:28px 16px;color:#94a3b8;font-size:12px;">
          <div>Không tìm thấy cặp khớp với từ khóa "<b>${query}</b>" trong danh sách đã tải.</div>
          <div style="margin-top:10px;">
            <button class="btn-header" style="background:#10b981;color:#fff;font-weight:700;padding:6px 14px;border:none;" onclick="window.app.selectSymbolAndLoad('${q}')">
              ⚡ Tự động tìm kiếm & Nạp "${q}" từ MT5 Server
            </button>
          </div>
        </div>
      `;
      return;
    }

    symbols.forEach(s => {
      const row = document.createElement('div');
      row.className = 'sym-result-row';
      row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:9px 14px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:6px;cursor:pointer;transition:all 0.15s ease;';
      
      row.onmouseenter = () => row.style.background = 'rgba(56,189,248,0.1)';
      row.onmouseleave = () => row.style.background = 'rgba(255,255,255,0.03)';

      const isCurrent = (s.symbol === this.currentSymbol);
      const isVisibleInMw = s.visible !== false;

      row.innerHTML = `
        <div style="display:flex;align-items:center;gap:12px;">
          <span style="font-size:14px;font-weight:800;color:${isCurrent ? '#10b981' : '#f8fafc'};font-family:var(--font-mono);">${s.symbol}</span>
          <span style="font-size:12px;color:#94a3b8;">${s.name || s.symbol}</span>
          ${s.path ? `<span style="font-size:10px;padding:2px 6px;border-radius:3px;background:rgba(255,255,255,0.05);color:#cbd5e1;">${s.path}</span>` : ''}
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
          ${isVisibleInMw ? 
            `<span style="font-size:11px;padding:3px 8px;border-radius:4px;background:rgba(16,185,129,0.15);color:#10b981;font-weight:600;">🟢 Trong Market Watch</span>` :
            `<span style="font-size:11px;padding:3px 8px;border-radius:4px;background:rgba(245,158,11,0.15);color:#fbbf24;font-weight:600;" title="Sẽ tự động gọi mt5.symbol_select để thêm vào Market Watch">⚡ Tự động thêm vào MT5</span>`
          }
          <button class="btn-header" style="padding:4px 10px;font-size:11px;background:${isCurrent ? '#10b981' : '#1e293b'};color:${isCurrent ? '#fff' : '#38bdf8'};border-color:#38bdf8;font-weight:700;">
            ${isCurrent ? 'Đang Chọn' : 'Chọn Cặp'}
          </button>
        </div>
      `;

      row.addEventListener('click', () => {
        this.selectSymbolAndLoad(s.symbol);
      });

      this.symbolModalResultsList.appendChild(row);
    });
  }

  async selectSymbolAndLoad(symbol) {
    if (!symbol) return;
    const sym = symbol.trim().toUpperCase();
    this.closeSymbolSearchModal();

    // Ensure it exists in dropdown
    if (this.symbolSelect) {
      let optExists = false;
      for (let i = 0; i < this.symbolSelect.options.length; i++) {
        if (this.symbolSelect.options[i].value === sym) {
          this.symbolSelect.selectedIndex = i;
          optExists = true;
          break;
        }
      }
      if (!optExists) {
        const newOpt = document.createElement('option');
        newOpt.value = sym;
        newOpt.innerText = `${sym} - (MT5 Broker)`;
        newOpt.selected = true;
        this.symbolSelect.insertBefore(newOpt, this.symbolSelect.firstChild);
        this.symbolSelect.value = sym;
      }
    }

    this.showToast(`⚡ Đang kết nối & tự động thêm ${sym} vào MT5 Market Watch...`);
    await this.loadSymbol(sym);
  }

  async loadSymbol(symbol, timeframePair = null) {
    this.currentSymbol = symbol;
    if (timeframePair) this.timeframePair = timeframePair;
    if (this.liveRealtimeActive) {
      await this.syncLiveRealtime(false);
      return;
    }
    const tfPair = this.timeframePair || 'H4_H1_M15';
    try {
      const resp = await fetch(`/api/load_symbol?symbol=${encodeURIComponent(symbol)}&timeframe_pair=${encodeURIComponent(tfPair)}`);
      const res = await resp.json();
      if (res.success) {
        if (res.source === 'MT5_TERMINAL') {
          this.showToast(`🟢 Đã lấy dữ liệu trực tiếp từ MT5 Server! (${res.tf1} - ${res.tf2} - ${res.tf3})`);
        }
        await this.refreshState();
        this.chartManager.centerCharts();
      }
    } catch (e) {
      console.error('Error loading symbol:', e);
    }
  }

  async applyState(newState) {
    if (!newState) return;
    this.state = newState;
    this.totalBars = this.state.total_bars;
    this.currentIndex = this.state.current_index;

    // Update Chart Series & Indicators
    this.chartManager.updateData(this.state);

    // Render Simple DCA EA Basket Lines (BE, TP)
    if (this.chartManager.renderEABasketLines) {
      this.chartManager.renderEABasketLines(this.state.ea_status);
    }

    // Update Timeframe Badges (Macro & Execution)
    if (this.chartManager.updateTimeframeBadges) {
      this.chartManager.updateTimeframeBadges(this.state.macro_tf || 'H1', this.state.exec_tf || 'M5');
    }

    // Update Basket Radar HUD
    this.updateBasketRadarHUD(this.state.ea_status, this.state.ea_enabled);

    // Update Non-Lookahead Probabilistic Context Forecast Bar
    this.updateProbabilisticForecastHUD(this.state.probabilistic_forecast);

    // Update Replay Controller Progress
    if (this.replayController) {
      this.replayController.updateProgress(
        this.currentIndex,
        this.totalBars,
        this.state.current_time
      );
    }

    // Update Trade Panel, Floating PnL & History
    if (this.tradePanel) {
      this.tradePanel.updateUI(this.state);
    }

    // Evaluate Auto-Radar Rules ONLY in BACKTEST mode (never during LIVE MT5 mode!)
    if (!this.liveRealtimeActive && this.autoRadarActive && !this.isAutoPaused) {
      await this.evaluateAutoRadarLogic();
    }
  }

  async jumpToIndex(index) {
    try {
      const resp = await fetch('/api/jump', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ index: Math.max(0, Math.round(index)) })
      });
      const res = await resp.json();
      if (res.success) {
        await this.refreshState();
        if (this.chartManager) this.chartManager.centerCharts();
      }
    } catch (e) {
      console.error('Error jumping to index:', e);
    }
  }

  async refreshState() {
    try {
      const resp = await fetch('/api/state');
      const newState = await resp.json();
      await this.applyState(newState);
    } catch (e) {
      console.error('Error refreshing state:', e);
    }
  }


  // =========================================================================
  // AUTO-RADAR BACKTESTING ENGINE WITH 5S PAUSE, RR 1:2, 1:3 & BE TRAILING
  // =========================================================================
  async evaluateAutoRadarLogic() {
    if (!this.state || !this.state.candles_m15 || this.state.candles_m15.length < 50) return;

    const currentBarIdx = this.currentIndex;
    const closedPositions = this.state.account.closed_positions || [];
    const openPositions = this.state.account.open_positions || [];

    // 1. CHECK CLOSED POSITIONS EVENTS (SL or TP Hit)
    if (closedPositions.length > this.lastClosedCount) {
      const newlyClosed = closedPositions.slice(this.lastClosedCount);
      this.lastClosedCount = closedPositions.length;

      for (const closed of newlyClosed) {
        const reason = closed.exit_reason || '';
        const isTp = reason.includes('TP');
        const isSl = reason.includes('SL');

        if (isTp) {
          // Check if this was Pos 1 (TP 1:2) of our active cluster -> Trail Pos 2 to BE!
          if (this.activeCluster && closed.id === this.activeCluster.pos1Id) {
            this.activeCluster.pos1Closed = true;
            // Move Pos 2 to BE
            await this.trailRemainingPositionToBE(this.activeCluster.pos2Id, this.activeCluster.entry);
            
            this.sound.playTpChime();
            this.trigger2sPause(
              '🎯 TAKE PROFIT 1 (RR 1:2) HIT!',
              `Lệnh 1 chốt lãi +$${closed.pnl.toFixed(2)} (+${closed.pnl_pips}p). Đã tự động dời SL lệnh 2 về Hòa Vốn (BE @ ${this.activeCluster.entry})!`,
              '#10b981'
            );
            return;
          } else {
            // Pos 2 TP 1:3 Hit
            this.sound.playGrandTpChime();
            this.trigger2sPause(
              '🔥 TAKE PROFIT 2 (RR 1:3) HIT!',
              `Lệnh 2 hoàn thành mục tiêu lợi nhuận +$${closed.pnl.toFixed(2)} (+${closed.pnl_pips}p)!`,
              '#3b82f6'
            );
            if (this.activeCluster && closed.id === this.activeCluster.pos2Id) {
              this.activeCluster = null;
            }
            return;
          }
        } else if (isSl) {
          this.sound.playSlAlert();
          this.trigger2sPause(
            '🛑 STOP LOSS HIT',
            `Lệnh đã chạm mức cắt lỗ ($${closed.pnl.toFixed(2)}, ${closed.pnl_pips} pips).`,
            '#ef4444'
          );
          this.activeCluster = null;
          return;
        }

      }
    }

    // 2. CHECK ACTIVE POSITION 2 ATR TRAILING STOP (Open TP Mode)
    if (this.activeCluster && !this.activeCluster.pos2Closed && this.pos2ExitConfig.mode === 'ATR_TRAILING') {
      const pos2Id = this.activeCluster.pos2Id;
      const pos2 = openPositions.find(p => p.id === pos2Id);
      if (pos2) {
        const atr = this.calculateATR(this.state.candles_m15, 14);
        const trailDist = atr * (this.pos2ExitConfig.atrMultiplier || 3.0);
        const currentPrice = this.state.current_price;
        const isBuy = pos2.type === 'BUY';

        if (isBuy) {
          const trailSL = parseFloat((currentPrice - trailDist).toFixed(5));
          if (trailSL > (pos2.sl || 0)) {
            await this.updatePositionSL(pos2Id, trailSL);
            pos2.sl = trailSL;
          }
        } else {
          const trailSL = parseFloat((currentPrice + trailDist).toFixed(5));
          if (trailSL < (pos2.sl || 999999) || !pos2.sl) {
            await this.updatePositionSL(pos2Id, trailSL);
            pos2.sl = trailSL;
          }
        }
      }
    }

    // 3. CHECK NEW RADAR ENTRY SIGNALS
    if (currentBarIdx !== this.lastProcessedIndex && openPositions.length === 0) {
      this.lastProcessedIndex = currentBarIdx;

      const candles = this.state.candles_m15; // H1 execution candles
      const lastCandle = candles[candles.length - 1];
      const prevCandle = candles[candles.length - 2];
      const prev2Candle = candles[candles.length - 3];

      const indicators = this.state.indicators || {};
      const ema21 = indicators.ema21_m15?.data?.slice(-1)[0]?.value || lastCandle.close;
      const ema50 = indicators.ema50_m15?.data?.slice(-1)[0]?.value || lastCandle.close;
      const ema200 = indicators.ema200_m15?.data?.slice(-1)[0]?.value || lastCandle.close;
      const rsi = indicators.rsi_m15?.data?.slice(-1)[0]?.value || 50.0;
      const stochK = indicators.stoch_m15?.data?.slice(-1)[0]?.k || 50.0;

      const latestDivM15 = this.state.copilot_signals?.M15;
      const latestDivH4 = this.state.copilot_signals?.H4;

      let detectedSignal = null;

      // Check Strategy 1: Divergence Signal
      if (latestDivM15 && (latestDivM15.type === 'BULLISH' || latestDivM15.type === 'BEARISH')) {
        detectedSignal = {
          type: latestDivM15.type === 'BULLISH' ? 'BUY' : 'SELL',
          strategy: '⚡ Phân Kỳ RSI/Stoch (Divergence)'
        };
      }
      // Check Strategy 2: EMA 21 Breakout
      else if (lastCandle.close > ema21 && prevCandle.close <= ema21 && lastCandle.close > ema200) {
        detectedSignal = {
          type: 'BUY',
          strategy: '🚀 EMA 21 Breakout (Trend Alignment)'
        };
      } else if (lastCandle.close < ema21 && prevCandle.close >= ema21 && lastCandle.close < ema200) {
        detectedSignal = {
          type: 'SELL',
          strategy: '🚀 EMA 21 Breakout (Trend Alignment)'
        };
      }
      // Check Strategy 3: Trend Following Pullback (EMA 50 & 200)
      else if (ema50 > ema200 && lastCandle.low <= ema50 && lastCandle.close > ema50) {
        detectedSignal = {
          type: 'BUY',
          strategy: '🌊 Trend Following (EMA 50 Pullback)'
        };
      } else if (ema50 < ema200 && lastCandle.high >= ema50 && lastCandle.close < ema50) {
        detectedSignal = {
          type: 'SELL',
          strategy: '🌊 Trend Following (EMA 50 Pullback)'
        };
      }

      if (detectedSignal) {
        await this.executeRadarSplitOrder(detectedSignal, lastCandle);
      }
    }
  }

  async executeRadarSplitOrder(signal, lastCandle) {
    const entry = lastCandle.close;
    const isBuy = signal.type === 'BUY';
    const symInfo = (this.state && this.state.symbol_info) || {};
    const pipSize = symInfo.pip_size || 0.01;
    const digits = symInfo.digits !== undefined ? symInfo.digits : 2;

    // Calculate Dynamic Stop Loss based on Swing & ATR
    const candles = this.state.candles_m15.slice(-20);
    let slDist = 0;
    let sl = 0;

    if (isBuy) {
      const swingLow = Math.min(...candles.map(c => c.low));
      slDist = Math.max((entry - swingLow) + (pipSize * 5), pipSize * 25);
      sl = parseFloat((entry - slDist).toFixed(digits));
    } else {
      const swingHigh = Math.max(...candles.map(c => c.high));
      slDist = Math.max((swingHigh - entry) + (pipSize * 5), pipSize * 25);
      sl = parseFloat((entry + slDist).toFixed(digits));
    }

    // Calculate TP 1:2 and Pos 2 (Fixed RR 1:3 or Open TP with 3 ATR Trailing)
    const tp1 = parseFloat((isBuy ? entry + (slDist * 2.0) : entry - (slDist * 2.0)).toFixed(digits));
    const isAtrTrailing = this.pos2ExitConfig.mode === 'ATR_TRAILING';
    const tp2 = isAtrTrailing ? null : parseFloat((isBuy ? entry + (slDist * (this.pos2ExitConfig.fixedRR || 3.0)) : entry - (slDist * (this.pos2ExitConfig.fixedRR || 3.0))).toFixed(digits));

    // Calculate Lot Size according to active Risk Configuration (% Balance, Fixed USD, or Fixed Lots)
    const { lotTotal, lotSplit } = this.calculateLotsForTrade(slDist, pipSize);


    try {
      // 1. Open Pos 1 with TP @ RR 1:2
      const resp1 = await fetch('/api/order/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: signal.type,
          lots: lotSplit,
          sl: sl,
          tp: tp1
        })
      });
      const res1 = await resp1.json();

      // 2. Open Pos 2 (Fixed RR 1:3 or Open TP for 3 ATR Trailing)
      const order2Body = {
        type: signal.type,
        lots: lotSplit,
        sl: sl
      };
      if (tp2 !== null) order2Body.tp = tp2;

      const resp2 = await fetch('/api/order/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(order2Body)
      });
      const res2 = await resp2.json();

      if (res1.success && res2.success) {
        this.activeCluster = {
          pos1Id: res1.position.id,
          pos2Id: res2.position.id,
          entry: entry,
          sl: sl,
          tp1: tp1,
          tp2: tp2,
          pos1Closed: false,
          pos2Closed: false
        };

        // Play Entry Bell Chime
        this.sound.playEntryBell();

        const pos2Desc = isAtrTrailing ? `TP2: Thả TP (${this.pos2ExitConfig.atrMultiplier || 3.0} ATR Trailing)` : `TP2: ${tp2} (1:3)`;

        // Trigger 2-Second Pause with live visual countdown
        this.trigger2sPause(
          `🚨 TÍN HIỆU RADAR: ${signal.type} ${this.currentSymbol}`,
          `${signal.strategy} | Entry: ${entry} | SL: ${sl} | TP1: ${tp1} (1:2) | ${pos2Desc}`,
          signal.type === 'BUY' ? 'var(--color-bull)' : 'var(--color-bear)'
        );
      }
    } catch (e) {
      console.error('Error executing Radar split orders:', e);
    }
  }

  calculateATR(candles, period = 14) {
    if (!candles || candles.length < period + 1) return 0.0015;
    let trSum = 0;
    for (let i = candles.length - period; i < candles.length; i++) {
      const c = candles[i];
      const prev = candles[i - 1];
      const tr = Math.max(c.high - c.low, Math.abs(c.high - prev.close), Math.abs(c.low - prev.close));
      trSum += tr;
    }
    return trSum / period;
  }

  async updatePositionSL(posId, newSL) {
    try {
      await fetch('/api/order/update_sl', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: posId, new_sl: newSL })
      });
    } catch (e) {
      console.error('Error updating position SL:', e);
    }
  }

  async trailRemainingPositionToBE(posId, entryPrice) {
    await this.updatePositionSL(posId, entryPrice);
  }


  trigger2sPause(title, desc, color) {
    if (this.isAutoPaused) return;
    this.isAutoPaused = true;

    // Pause replay
    if (this.replayController) {
      this.replayController.pause();
    }

    // Show Overlay Banner
    if (this.pauseOverlay) {
      this.pauseOverlayTitle.innerHTML = `<span>${title}</span>`;
      this.pauseOverlayTitle.style.color = color;
      this.pauseOverlayDesc.innerText = desc;
      this.pauseOverlay.style.display = 'block';
      this.pauseOverlay.style.borderColor = color;
    }

    let secondsLeft = 2.0;
    if (this.pauseInterval) clearInterval(this.pauseInterval);
    if (this.autoPauseTimeout) clearTimeout(this.autoPauseTimeout);

    if (this.pauseOverlayTimer) {
      this.pauseOverlayTimer.innerText = `⏱️ Tạm dừng: 2.0s`;
    }

    this.pauseInterval = setInterval(() => {
      secondsLeft -= 0.5;
      if (this.pauseOverlayTimer) {
        this.pauseOverlayTimer.innerText = `⏱️ Tạm dừng: ${Math.max(0, secondsLeft).toFixed(1)}s`;
      }
      if (secondsLeft <= 0) {
        clearInterval(this.pauseInterval);
      }
    }, 500);

    this.autoPauseTimeout = setTimeout(async () => {
      this.isAutoPaused = false;
      if (this.pauseOverlay) {
        this.pauseOverlay.style.display = 'none';
      }
      // Auto-resume replay if auto-radar is active
      if (this.autoRadarActive && this.replayController) {
        this.replayController.play();
      }
    }, 2000);
  }


  openStatsModal() {
    if (!this.statsModal || !this.state) return;
    const stats = this.state.stats;
    const content = document.getElementById('statsContent');
    if (content) {
      content.innerHTML = `
        <div style="display:grid;grid-template-columns:repeat(2, 1fr);gap:12px;margin-bottom:16px;">
          <div class="metric-card"><div class="metric-label">Balance</div><div class="metric-value">$${stats.balance.toLocaleString()}</div></div>
          <div class="metric-card"><div class="metric-label">Net Profit</div><div class="metric-value ${stats.net_profit >= 0 ? 'bull' : 'bear'}">${stats.net_profit >= 0 ? '+' : ''}$${stats.net_profit.toLocaleString()} (${stats.net_profit_pct}%)</div></div>
          <div class="metric-card"><div class="metric-label">Win Rate</div><div class="metric-value">${stats.win_rate}% (${stats.won_trades}/${stats.total_trades})</div></div>
          <div class="metric-card"><div class="metric-label">Profit Factor</div><div class="metric-value">${stats.profit_factor}</div></div>
          <div class="metric-card"><div class="metric-label">Max Drawdown</div><div class="metric-value bear">${stats.max_drawdown_pct}%</div></div>
          <div class="metric-card"><div class="metric-label">Total Pips</div><div class="metric-value bull">+${stats.total_pips} pips</div></div>
        </div>
      `;
    }
    this.statsModal.classList.add('open');
  }

  async handleCsvUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('symbol', this.currentSymbol);

    try {
      const resp = await fetch('/api/upload_csv', { method: 'POST', body: formData });
      const res = await resp.json();
      if (res.success) {
        alert(`Đã import thành công ${res.candle_count} nến!`);
        await this.refreshState();
        this.chartManager.centerCharts();
      } else {
        alert(`Lỗi import: ${res.detail || 'Không xác định'}`);
      }
    } catch (err) {
      console.error('CSV upload error:', err);
      alert('Lỗi upload file CSV.');
    }
  }

  showToast(msg) {
    if (this.chartManager && this.chartManager.showToast) {
      this.chartManager.showToast(msg);
    } else {
      const toast = document.getElementById('appToast');
      if (toast) {
        toast.innerText = msg;
        toast.classList.add('show');
        setTimeout(() => { toast.classList.remove('show'); }, 3000);
      }
    }
  }

  setupEA() {
    this.tfPairSelect = document.getElementById('tfPairSelect');
    this.eaPresetSelect = document.getElementById('eaPresetSelect');
    this.btnEAConfig = document.getElementById('btnEAConfig');
    this.btnToggleEA = document.getElementById('btnToggleEA');
    this.eaToggleText = document.getElementById('eaToggleText');
    this.btnFastBacktest = document.getElementById('btnFastBacktest');
    this.basketRadarHud = document.getElementById('basketRadarHud');
    this.eaConfigModal = document.getElementById('eaConfigModal');
    this.btnCloseEAConfig = document.getElementById('btnCloseEAConfig');
    this.btnCancelEAConfig = document.getElementById('btnCancelEAConfig');
    this.btnSaveEAConfig = document.getElementById('btnSaveEAConfig');
    this.eaModalPresetSelect = document.getElementById('eaModalPresetSelect');
    this.fastBacktestModal = document.getElementById('fastBacktestModal');
    this.btnCloseFastBacktest = document.getElementById('btnCloseFastBacktest');
    this.btnOkFastBacktest = document.getElementById('btnOkFastBacktest');

    // 1. Timeframe pair change
    if (this.tfPairSelect) {
      this.tfPairSelect.addEventListener('change', async (e) => {
        this.timeframePair = e.target.value;
        this.syncSlotTimeframesFromPair(this.timeframePair);
        if (this.liveRealtimeActive) {
          await this.syncLiveRealtime();
        } else {
          await this.loadSymbol(this.currentSymbol, this.timeframePair);
        }
        this.showToast(`Đã chuyển sang ${e.target.options[e.target.selectedIndex].text}`);
      });
    }

    // 1b. Forecast Mode Selector (Combined 70% HTF + 30% LTF vs 100% HTF Anchor vs LTF Only)
    this.forecastModeSelect = document.getElementById('forecastModeSelect');
    if (this.forecastModeSelect) {
      this.forecastModeSelect.addEventListener('change', async (e) => {
        this.forecastMode = e.target.value;
        try {
          const resp = await fetch('/api/forecast/mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ forecast_mode: this.forecastMode })
          });
          const res = await resp.json();
          if (res.success && res.forecast) {
            this.updateProbabilisticForecastHUD(res.forecast);
            if (this.chartManager && this.chartManager.renderProbabilisticFutureProjection) {
              this.chartManager.renderProbabilisticFutureProjection(res.forecast);
            }
            const labelText = e.target.options[e.target.selectedIndex].text;
            this.showToast(`⚓ Đã chuyển chế độ Forecast: ${labelText}`);
          }
        } catch (err) {
          console.error('Error setting forecast mode:', err);
        }
      });
    }

    // 1c. Live Realtime Forecast Toggle Button
    this.btnLiveForecast = document.getElementById('btnLiveForecast');
    this.liveToggleText = document.getElementById('liveToggleText');
    if (this.btnLiveForecast) {
      this.btnLiveForecast.addEventListener('click', async () => {
        await this.toggleLiveRealtime();
      });
    }

    // 1d. Multi-Pair Live Strategic Radar Modal & Accuracy/Self-Improvement Modal
    this.btnOpenLiveRadar = document.getElementById('btnOpenLiveRadar');
    this.liveRadarModal = document.getElementById('liveRadarModal');
    this.btnCloseLiveRadar = document.getElementById('btnCloseLiveRadar');
    this.btnOkLiveRadar = document.getElementById('btnOkLiveRadar');
    this.btnRefreshLiveRadar = document.getElementById('btnRefreshLiveRadar');
    this.btnCalibrateAllRadar = document.getElementById('btnCalibrateAllRadar');
    this.liveRadarTfSelect = document.getElementById('liveRadarTfSelect');

    this.btnOpenAccuracyModal = document.getElementById('btnOpenAccuracyModal');
    this.probTrustBadge = document.getElementById('probTrustBadge');
    this.forecastAccuracyModal = document.getElementById('forecastAccuracyModal');
    this.btnCloseAccuracyModal = document.getElementById('btnCloseAccuracyModal');
    this.btnOkAccuracyModal = document.getElementById('btnOkAccuracyModal');
    this.btnRefreshAccuracy = document.getElementById('btnRefreshAccuracy');
    this.btnRunSingleCalibration = document.getElementById('btnRunSingleCalibration');

    if (this.btnOpenLiveRadar) {
      this.btnOpenLiveRadar.addEventListener('click', async () => {
        if (this.liveRadarModal) this.liveRadarModal.classList.add('open');
        await this.scanLiveRadar();
      });
    }
    if (this.btnCloseLiveRadar) {
      this.btnCloseLiveRadar.addEventListener('click', () => {
        if (this.liveRadarModal) this.liveRadarModal.classList.remove('open');
      });
    }
    if (this.btnOkLiveRadar) {
      this.btnOkLiveRadar.addEventListener('click', () => {
        if (this.liveRadarModal) this.liveRadarModal.classList.remove('open');
      });
    }
    if (this.btnRefreshLiveRadar) {
      this.btnRefreshLiveRadar.addEventListener('click', async () => {
        await this.scanLiveRadar();
      });
    }
    if (this.btnCalibrateAllRadar) {
      this.btnCalibrateAllRadar.addEventListener('click', async () => {
        await this.runAllRadarCalibration();
      });
    }
    if (this.liveRadarTfSelect) {
      this.liveRadarTfSelect.addEventListener('change', async () => {
        await this.scanLiveRadar();
      });
    }

    const openAccHandler = async (e) => {
      if (e) e.stopPropagation();
      if (this.forecastAccuracyModal) this.forecastAccuracyModal.classList.add('open');
      await this.loadForecastAccuracyModal();
    };
    if (this.btnOpenAccuracyModal) {
      this.btnOpenAccuracyModal.addEventListener('click', openAccHandler);
    }
    if (this.probTrustBadge) {
      this.probTrustBadge.addEventListener('click', openAccHandler);
    }
    if (this.btnCloseAccuracyModal) {
      this.btnCloseAccuracyModal.addEventListener('click', () => {
        if (this.forecastAccuracyModal) this.forecastAccuracyModal.classList.remove('open');
      });
    }
    if (this.btnOkAccuracyModal) {
      this.btnOkAccuracyModal.addEventListener('click', () => {
        if (this.forecastAccuracyModal) this.forecastAccuracyModal.classList.remove('open');
      });
    }
    if (this.btnRefreshAccuracy) {
      this.btnRefreshAccuracy.addEventListener('click', async () => {
        await this.loadForecastAccuracyModal();
      });
    }
    if (this.btnRunSingleCalibration) {
      this.btnRunSingleCalibration.addEventListener('click', async () => {
        await this.runSingleSymbolCalibration();
      });
    }

    // 2. Preset Select change & click -> Call API /api/forecast/future_candles & render future candles
    if (this.eaPresetSelect) {
      const handlePresetSelection = async (presetName, isClick = false) => {
        try {
          const isProbPreset = presetName.includes('Probabilistic') || presetName.startsWith('v3.0');
          if (this.chartManager && localStorage.getItem('enableDynamicSlTp') === 'true') {
            this.chartManager.showFutureProjection = isProbPreset;
            if (this.chartManager.updateDynamicSlTpUI) this.chartManager.updateDynamicSlTpUI();
          }

          const resp = await fetch('/api/ea/select_preset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preset_name: presetName })
          });
          const res = await resp.json();
          if (res.success) {
            if (isProbPreset) {
              const fcResp = await fetch(`/api/forecast/future_candles?preset_name=${encodeURIComponent(presetName)}`);
              const fcRes = await fcResp.json();
              if (fcRes.success && fcRes.forecast) {
                this.updateProbabilisticForecastHUD(fcRes.forecast);
                if (this.chartManager && this.chartManager.renderProbabilisticFutureProjection) {
                  this.chartManager.renderProbabilisticFutureProjection(fcRes.forecast);
                  this.chartManager.centerCharts();
                }
                const fCount = (fcRes.future_candles || []).length;
                this.showToast(
                  `🔮 Đã vẽ ${fCount} nến tương lai (${presetName}): 🟢UP ${fcRes.prob_up_pct}% | 🔴DN ${fcRes.prob_down_pct}% | ⚪SW ${fcRes.prob_sideway_pct}%`
                );
              }
            } else {
              if (this.chartManager && this.chartManager.renderProbabilisticFutureProjection) {
                this.chartManager.renderProbabilisticFutureProjection(null);
              }
              if (!isClick) {
                this.showToast(`Đã áp dụng Preset: ${presetName}`);
              }
            }
            if (!isClick) {
              await this.refreshState();
            }
          }
        } catch (err) {
          console.error('Error selecting preset:', err);
        }
      };

      this.eaPresetSelect.addEventListener('change', async (e) => {
        await handlePresetSelection(e.target.value, false);
      });
    }

    // Click on AI Context bar to refresh / re-center Future Probabilistic Candles on demand
    const probBar = document.getElementById('probContextBar');
    if (probBar) {
      probBar.style.cursor = 'pointer';
      probBar.title = 'Nhấp để cập nhật & vẽ phóng chiếu 8 nến tương lai kèm xác suất (% UP / % DOWN / % SIDEWAY)';
      probBar.addEventListener('click', async () => {
        try {
          if (this.chartManager && localStorage.getItem('enableDynamicSlTp') !== 'false') {
            this.chartManager.showFutureProjection = true;
            if (this.chartManager.updateDynamicSlTpUI) this.chartManager.updateDynamicSlTpUI();
          }
          const presetName = this.eaPresetSelect ? this.eaPresetSelect.value : 'v3.0_EMA21_Probabilistic_MacroKNN';
          const fcResp = await fetch(`/api/forecast/future_candles?preset_name=${encodeURIComponent(presetName)}`);
          const fcRes = await fcResp.json();
          if (fcRes.success && fcRes.forecast) {
            this.updateProbabilisticForecastHUD(fcRes.forecast);
            if (this.chartManager && this.chartManager.renderProbabilisticFutureProjection) {
              this.chartManager.renderProbabilisticFutureProjection(fcRes.forecast);
              this.chartManager.centerCharts();
            }
            this.showToast(
              `🔮 Dự báo +${(fcRes.future_candles || []).length} nến: 🟢UP ${fcRes.prob_up_pct}% | 🔴DN ${fcRes.prob_down_pct}% | ⚪SW ${fcRes.prob_sideway_pct}%`
            );
          }
        } catch (err) {
          console.error('Error fetching future candles:', err);
        }
      });
    }

    // 3. EA Toggle button
    if (this.btnToggleEA) {
      this.btnToggleEA.addEventListener('click', async () => {
        const currentlyEnabled = this.state && this.state.ea_enabled;
        const newEnabled = !currentlyEnabled;
        try {
          const resp = await fetch('/api/ea/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: newEnabled })
          });
          const res = await resp.json();
          if (res.success) {
            await this.refreshState();
            this.showToast(newEnabled ? '⚡ Đã BẬT EA Replay (Tự động theo từng nến M5)' : '⏸️ Đã TẮT EA Replay');
          }
        } catch (err) {
          console.error('Error toggling EA:', err);
        }
      });
    }

    // 4. EA Config Modal
    if (this.btnEAConfig) {
      this.btnEAConfig.addEventListener('click', async () => {
        await this.openEAConfigModal();
      });
    }
    if (this.btnCloseEAConfig) {
      this.btnCloseEAConfig.addEventListener('click', () => {
        if (this.eaConfigModal) this.eaConfigModal.classList.remove('open');
      });
    }
    if (this.btnCancelEAConfig) {
      this.btnCancelEAConfig.addEventListener('click', () => {
        if (this.eaConfigModal) this.eaConfigModal.classList.remove('open');
      });
    }
    if (this.eaModalPresetSelect) {
      this.eaModalPresetSelect.addEventListener('change', async (e) => {
        const preset = e.target.value;
        await this.loadPresetIntoConfigModal(preset);
      });
    }
    if (this.btnSaveEAConfig) {
      this.btnSaveEAConfig.addEventListener('click', async () => {
        await this.saveEAConfigModal();
      });
    }

    // 5. Fast Backtest Modal
    if (this.btnFastBacktest) {
      this.btnFastBacktest.addEventListener('click', async () => {
        await this.triggerFastBacktest();
      });
    }
    if (this.btnCloseFastBacktest) {
      this.btnCloseFastBacktest.addEventListener('click', () => {
        if (this.fastBacktestModal) this.fastBacktestModal.classList.remove('open');
      });
    }
    if (this.btnOkFastBacktest) {
      this.btnOkFastBacktest.addEventListener('click', () => {
        if (this.fastBacktestModal) this.fastBacktestModal.classList.remove('open');
      });
    }
  }

  async openEAConfigModal() {
    try {
      const resp = await fetch('/api/ea/config');
      const res = await resp.json();
      if (res.success && res.config) {
        const cfg = res.config;
        if (document.getElementById('eaConfigDirection')) document.getElementById('eaConfigDirection').value = cfg.direction || 'HEDGING_DUAL';
        if (document.getElementById('eaConfigFirstTrigger')) document.getElementById('eaConfigFirstTrigger').value = cfg.first_order_trigger || 'IMMEDIATE';
        if (document.getElementById('eaConfigStepPips')) document.getElementById('eaConfigStepPips').value = cfg.step_pips || 80;
        if (document.getElementById('eaConfigMaxActive')) document.getElementById('eaConfigMaxActive').value = cfg.max_active_orders || 4;
        if (document.getElementById('eaConfigLotSeq')) document.getElementById('eaConfigLotSeq').value = (cfg.lot_sequence || []).join(',');
        if (document.getElementById('eaConfigTpSeq')) document.getElementById('eaConfigTpSeq').value = (cfg.tp_sequence || []).join(',');
        if (document.getElementById('eaConfigEnableSW')) document.getElementById('eaConfigEnableSW').checked = !!cfg.enable_sliding_window;
        if (document.getElementById('eaConfigEnableBBFilter')) document.getElementById('eaConfigEnableBBFilter').checked = !!cfg.enable_bb_filter;
      }
      if (this.eaConfigModal) this.eaConfigModal.classList.add('open');
    } catch (err) {
      console.error('Error opening EA config modal:', err);
    }
  }

  async loadPresetIntoConfigModal(presetName) {
    try {
      const resp = await fetch('/api/ea/presets');
      const res = await resp.json();
      if (res.success && res.presets && res.presets[presetName]) {
        const cfg = res.presets[presetName];
        if (document.getElementById('eaConfigDirection')) document.getElementById('eaConfigDirection').value = cfg.direction || 'HEDGING_DUAL';
        if (document.getElementById('eaConfigFirstTrigger')) document.getElementById('eaConfigFirstTrigger').value = cfg.first_order_trigger || 'IMMEDIATE';
        if (document.getElementById('eaConfigStepPips')) document.getElementById('eaConfigStepPips').value = cfg.step_pips || 80;
        if (document.getElementById('eaConfigMaxActive')) document.getElementById('eaConfigMaxActive').value = cfg.max_active_orders || 4;
        if (document.getElementById('eaConfigLotSeq')) document.getElementById('eaConfigLotSeq').value = (cfg.lot_sequence || []).join(',');
        if (document.getElementById('eaConfigTpSeq')) document.getElementById('eaConfigTpSeq').value = (cfg.tp_sequence || []).join(',');
        if (document.getElementById('eaConfigEnableSW')) document.getElementById('eaConfigEnableSW').checked = !!cfg.enable_sliding_window;
        if (document.getElementById('eaConfigEnableBBFilter')) document.getElementById('eaConfigEnableBBFilter').checked = !!cfg.enable_bb_filter;
      }
    } catch (err) {
      console.error('Error loading preset into config:', err);
    }
  }

  async saveEAConfigModal() {
    try {
      const stepPips = parseFloat(document.getElementById('eaConfigStepPips').value) || 80;
      const maxActive = parseInt(document.getElementById('eaConfigMaxActive').value) || 4;
      const lotSeqStr = document.getElementById('eaConfigLotSeq').value;
      const tpSeqStr = document.getElementById('eaConfigTpSeq').value;
      const direction = document.getElementById('eaConfigDirection').value;
      const firstTrigger = document.getElementById('eaConfigFirstTrigger').value;
      const enableSW = document.getElementById('eaConfigEnableSW').checked;
      const enableBB = document.getElementById('eaConfigEnableBBFilter').checked;

      const lotSeq = lotSeqStr.split(',').map(x => parseFloat(x.trim())).filter(x => !isNaN(x) && x > 0);
      const tpSeq = tpSeqStr.split(',').map(x => parseFloat(x.trim())).filter(x => !isNaN(x) && x > 0);

      const payload = {
        config: {
          step_pips: stepPips,
          max_active_orders: maxActive,
          lot_sequence: lotSeq,
          tp_sequence: tpSeq,
          direction: direction,
          first_order_trigger: firstTrigger,
          enable_sliding_window: enableSW,
          enable_bb_filter: enableBB
        }
      };

      const resp = await fetch('/api/ea/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const res = await resp.json();
      if (res.success) {
        this.showToast('✅ Đã lưu cấu hình Simple DCA EA!');
        if (this.eaConfigModal) this.eaConfigModal.classList.remove('open');
        await this.refreshState();
      }
    } catch (err) {
      console.error('Error saving EA config:', err);
    }
  }

  async triggerFastBacktest() {
    this.showToast('⏳ Đang chạy Fast Backtest trên toàn bộ tập dữ liệu...');
    try {
      const presetName = this.eaPresetSelect ? this.eaPresetSelect.value : null;
      const resp = await fetch('/api/ea/fast_backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: this.currentSymbol,
          timeframe_pair: this.timeframePair || 'H1_M5',
          preset_name: presetName
        })
      });
      const report = await resp.json();
      if (report.success) {
        this.renderFastBacktestReport(report);
        if (this.fastBacktestModal) this.fastBacktestModal.classList.add('open');
      } else {
        alert('Lỗi Fast Backtest: ' + (report.error || 'Unknown error'));
      }
    } catch (err) {
      console.error('Error running fast backtest:', err);
      alert('Lỗi kết nối khi chạy Fast Backtest: ' + err.message);
    }
  }

  renderFastBacktestReport(data) {
    const elProfit = document.getElementById('btNetProfit');
    const elProfitPct = document.getElementById('btNetProfitPct');
    const elPF = document.getElementById('btProfitFactor');
    const elDD = document.getElementById('btMaxDrawdown');
    const elDDUsd = document.getElementById('btMaxDrawdownUsd');
    const elCycles = document.getElementById('btCycles');
    const elCuts = document.getElementById('btCuts');
    const elCutLoss = document.getElementById('btCutLoss');
    const elBars = document.getElementById('btBarsTested');

    const isProfit = data.net_profit >= 0;
    if (elProfit) {
      elProfit.innerText = (isProfit ? '+$' : '-$') + Math.abs(data.net_profit).toLocaleString('en-US', { minimumFractionDigits: 2 });
      elProfit.style.color = isProfit ? 'var(--color-bull)' : 'var(--color-bear)';
    }
    if (elProfitPct) {
      elProfitPct.innerText = `(${data.net_profit_pct > 0 ? '+' : ''}${data.net_profit_pct.toFixed(2)}%)`;
    }
    if (elPF) elPF.innerText = data.profit_factor >= 999 ? '∞' : data.profit_factor.toFixed(2);
    if (elDD) elDD.innerText = `${data.max_drawdown_pct.toFixed(2)}%`;
    if (elDDUsd) elDDUsd.innerText = `(-$${data.max_drawdown_usd.toFixed(2)})`;
    if (elCycles) elCycles.innerText = data.completed_cycles.toLocaleString('en-US');
    if (elCuts) elCuts.innerText = data.total_cuts.toLocaleString('en-US');
    if (elCutLoss) elCutLoss.innerText = `-$${Math.abs(data.total_cut_loss).toFixed(2)}`;
    if (elBars) elBars.innerText = `${data.total_bars_tested.toLocaleString('en-US')} nến ${data.symbol}`;

    // Render SVG Equity Curve
    this.renderEquitySvg(data.equity_curve || []);

    // Render Recent Trades Table (Server Time & VN Time)
    const tbody = document.getElementById('btTradesTableBody');
    if (tbody) {
      tbody.innerHTML = '';
      const trades = data.closed_trades || [];
      if (trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-dim);padding:10px;">Chưa có giao dịch chốt chu kỳ</td></tr>';
      } else {
        trades.slice(-50).reverse().forEach(tr => {
          const row = document.createElement('tr');
          row.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
          const dt = new Date(tr.time * 1000);
          const srvTimeStr = dt.toISOString().slice(11, 16);
          // VN time (UTC+7)
          const vnDt = new Date((tr.time + 7 * 3600) * 1000);
          const vnTimeStr = vnDt.toISOString().slice(11, 16);
          const isBuy = tr.type && tr.type.includes('BUY');
          
          row.innerHTML = `
            <td style="padding:4px 8px;color:var(--text-muted);">${srvTimeStr} (${vnTimeStr} VN)</td>
            <td style="padding:4px 8px;font-weight:700;color:${isBuy ? 'var(--color-bull)' : 'var(--color-bear)'};">${isBuy ? 'BUY BASKET' : 'SELL BASKET'}</td>
            <td style="padding:4px 8px;color:#10b981;">${tr.tp_price ? tr.tp_price.toFixed(2) : '--'}</td>
            <td style="padding:4px 8px;color:#38bdf8;">${tr.be_price ? tr.be_price.toFixed(2) : '--'}</td>
            <td style="padding:4px 8px;text-align:center;">${tr.orders_count || 1}</td>
            <td style="padding:4px 8px;font-weight:700;color:var(--color-bull);">+$${(tr.profit || 0).toFixed(2)}</td>
          `;
          tbody.appendChild(row);
        });
      }
    }
  }

  renderEquitySvg(curve) {
    const container = document.getElementById('btEquitySvgContainer');
    if (!container) return;
    if (!curve || curve.length < 2) {
      container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-dim);font-size:12px;">Chưa đủ dữ liệu vẽ đồ thị</div>';
      return;
    }

    const width = container.clientWidth || 800;
    const height = container.clientHeight || 180;
    const padding = 20;

    const equities = curve.map(c => c.equity);
    const minEq = Math.min(...equities);
    const maxEq = Math.max(...equities);
    const range = (maxEq - minEq) || 1;

    const points = curve.map((c, i) => {
      const x = padding + (i / (curve.length - 1)) * (width - 2 * padding);
      const y = height - padding - ((c.equity - minEq) / range) * (height - 2 * padding);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    const lastEq = curve[curve.length - 1].equity;
    const isUp = lastEq >= curve[0].equity;
    const strokeColor = isUp ? '#10b981' : '#f23645';

    container.innerHTML = `
      <svg width="100%" height="100%" viewBox="0 0 ${width} ${height}" style="display:block;">
        <defs>
          <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${strokeColor}" stop-opacity="0.3"/>
            <stop offset="100%" stop-color="${strokeColor}" stop-opacity="0.0"/>
          </linearGradient>
        </defs>
        <!-- Horizontal grid line at min and max -->
        <line x1="${padding}" y1="${padding}" x2="${width - padding}" y2="${padding}" stroke="rgba(255,255,255,0.08)" stroke-dasharray="3,3"/>
        <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="rgba(255,255,255,0.08)" stroke-dasharray="3,3"/>
        <!-- Min & Max Labels -->
        <text x="${padding + 4}" y="${padding + 12}" fill="#94a3b8" font-size="10" font-family="monospace">$${maxEq.toFixed(0)}</text>
        <text x="${padding + 4}" y="${height - padding - 4}" fill="#94a3b8" font-size="10" font-family="monospace">$${minEq.toFixed(0)}</text>
        <!-- Polyline -->
        <polyline fill="none" stroke="${strokeColor}" stroke-width="2" points="${points}" />
      </svg>
    `;
  }

  updateBasketRadarHUD(eaStatus, eaEnabled) {
    if (!this.basketRadarHud) return;

    if (!eaEnabled && (!eaStatus || (!eaStatus.buy_basket.active_orders && !eaStatus.sell_basket.active_orders))) {
      this.basketRadarHud.style.display = 'none';
      if (this.btnToggleEA) {
        this.btnToggleEA.classList.remove('active');
        if (this.eaToggleText) this.eaToggleText.innerText = 'EA Replay: TẮT';
      }
      return;
    }

    this.basketRadarHud.style.display = 'block';
    if (this.btnToggleEA) {
      if (eaEnabled) {
        this.btnToggleEA.classList.add('active');
        if (this.eaToggleText) this.eaToggleText.innerText = 'EA Replay: BẬT';
      } else {
        this.btnToggleEA.classList.remove('active');
        if (this.eaToggleText) this.eaToggleText.innerText = 'EA Replay: TẮT';
      }
    }

    if (!eaStatus) return;

    const elPreset = document.getElementById('radarPresetName');
    if (elPreset && eaStatus.preset_name) elPreset.innerText = eaStatus.preset_name;

    // BUY BASKET
    const bb = eaStatus.buy_basket;
    const elBuyTiers = document.getElementById('radarBuyTiers');
    const elBuyBe = document.getElementById('radarBuyBe');
    const elBuyTp = document.getElementById('radarBuyTp');
    if (elBuyTiers) {
      elBuyTiers.innerText = `Tiers: ${bb.current_tier}/${bb.max_tiers} (${bb.active_orders} orders)`;
      elBuyTiers.style.color = bb.active_orders > 0 ? 'var(--color-bull)' : 'var(--text-muted)';
    }
    if (elBuyBe) elBuyBe.innerText = bb.be_price > 0 ? `BE: ${bb.be_price}` : 'BE: --';
    if (elBuyTp) elBuyTp.innerText = bb.tp_price > 0 ? `TP: ${bb.tp_price} (+${bb.dist_to_tp_pips}p)` : 'TP: --';

    // SELL BASKET
    const sb = eaStatus.sell_basket;
    const elSellTiers = document.getElementById('radarSellTiers');
    const elSellBe = document.getElementById('radarSellBe');
    const elSellTp = document.getElementById('radarSellTp');
    if (elSellTiers) {
      elSellTiers.innerText = `Tiers: ${sb.current_tier}/${sb.max_tiers} (${sb.active_orders} orders)`;
      elSellTiers.style.color = sb.active_orders > 0 ? 'var(--color-bear)' : 'var(--text-muted)';
    }
    if (elSellBe) elSellBe.innerText = sb.be_price > 0 ? `BE: ${sb.be_price}` : 'BE: --';
    if (elSellTp) elSellTp.innerText = sb.tp_price > 0 ? `TP: ${sb.tp_price} (+${sb.dist_to_tp_pips}p)` : 'TP: --';

    // Floating & Stats
    const totFloating = (bb.floating_pnl || 0) + (sb.floating_pnl || 0);
    const elFloating = document.getElementById('radarFloatingPnl');
    if (elFloating) {
      elFloating.innerText = (totFloating >= 0 ? '+$' : '-$') + Math.abs(totFloating).toFixed(2);
      elFloating.style.color = totFloating >= 0 ? 'var(--color-bull)' : 'var(--color-bear)';
    }

    const elCycles = document.getElementById('radarCycles');
    if (elCycles) elCycles.innerText = eaStatus.completed_cycles || 0;

    const elCuts = document.getElementById('radarCuts');
    if (elCuts) elCuts.innerText = eaStatus.total_cuts || 0;

    const elCutLoss = document.getElementById('radarCutLoss');
    if (elCutLoss) elCutLoss.innerText = `-$${Math.abs(eaStatus.total_cut_loss || 0).toFixed(2)}`;
  }

  updateProbabilisticForecastHUD(fc) {
    if (!fc) return;
    const elUp = document.getElementById('probUpText');
    const elSw = document.getElementById('probSidewayText');
    const elDn = document.getElementById('probDownText');
    const barUp = document.getElementById('probBarUp');
    const barSw = document.getElementById('probBarSideway');
    const barDn = document.getElementById('probBarDown');
    const elMacro = document.getElementById('probMacroRegime');
    const elWave = document.getElementById('probExpWave');
    const elSamples = document.getElementById('probSampleCount');
    const elAction = document.getElementById('probActionBadge');
    const elTactical = document.getElementById('probTacticalBadge');
    const elSession = document.getElementById('probSessionBadge');
    const elDnaTime = document.getElementById('probDnaTimeBadge');

    // Tier-1 Macro HTF Bar elements
    const elMacUp = document.getElementById('macroProbUpText');
    const elMacSw = document.getElementById('macroProbSwText');
    const elMacDn = document.getElementById('macroProbDnText');
    const barMacUp = document.getElementById('macroBarUp');
    const barMacSw = document.getElementById('macroBarSw');
    const barMacDn = document.getElementById('macroBarDn');

    const pUp = fc.prob_up_pct ?? 33.3;
    const pSw = fc.prob_sideway_pct ?? 33.4;
    const pDn = fc.prob_down_pct ?? 33.3;

    const mUp = fc.macro_prob_up_pct ?? pUp;
    const mSw = fc.macro_prob_sideway_pct ?? pSw;
    const mDn = fc.macro_prob_down_pct ?? pDn;

    if (elUp) elUp.innerText = `🟢 UP ${pUp.toFixed(1)}%`;
    if (elSw) elSw.innerText = `⚪ SW ${pSw.toFixed(1)}%`;
    if (elDn) elDn.innerText = `🔴 DN ${pDn.toFixed(1)}%`;

    if (barUp) barUp.style.width = `${pUp}%`;
    if (barSw) barSw.style.width = `${pSw}%`;
    if (barDn) barDn.style.width = `${pDn}%`;

    if (elMacUp) elMacUp.innerText = `🟢 UP ${mUp.toFixed(1)}%`;
    if (elMacSw) elMacSw.innerText = `⚪ SW ${mSw.toFixed(1)}%`;
    if (elMacDn) elMacDn.innerText = `🔴 DN ${mDn.toFixed(1)}%`;

    if (barMacUp) barMacUp.style.width = `${mUp}%`;
    if (barMacSw) barMacSw.style.width = `${mSw}%`;
    if (barMacDn) barMacDn.style.width = `${mDn}%`;

    if (elMacro) {
      elMacro.innerText = fc.macro_regime || 'NEUTRAL';
      elMacro.style.color = fc.macro_regime === 'BULL' ? '#10b981' : (fc.macro_regime === 'BEAR' ? '#ef4444' : '#38bdf8');
    }
    if (elWave) elWave.innerText = `${(fc.expected_wave_atr || 0).toFixed(2)} ATR`;
    if (elSamples) elSamples.innerText = `${fc.sample_count || 0}/${fc.total_memory_samples || 0}`;

    if (elTactical && fc.tactical_badge) {
      elTactical.innerText = fc.tactical_badge;
      const st = fc.tactical_status || '';
      if (st.includes('ALIGNED_BUY')) {
        elTactical.style.background = 'rgba(16,185,129,0.25)';
        elTactical.style.color = '#10b981';
        elTactical.style.border = '1px solid rgba(16,185,129,0.5)';
      } else if (st.includes('ALIGNED_SELL')) {
        elTactical.style.background = 'rgba(239,68,68,0.25)';
        elTactical.style.color = '#ef4444';
        elTactical.style.border = '1px solid rgba(239,68,68,0.5)';
      } else if (st.includes('PULLBACK')) {
        elTactical.style.background = 'rgba(245,158,11,0.22)';
        elTactical.style.color = '#fbbf24';
        elTactical.style.border = '1px solid rgba(245,158,11,0.5)';
      } else {
        elTactical.style.background = 'rgba(148,163,184,0.18)';
        elTactical.style.color = '#94a3b8';
        elTactical.style.border = '1px solid rgba(148,163,184,0.3)';
      }
    }

    if (fc.dna_session) {
      if (elDnaTime && fc.dna_session.formatted_short) {
        elDnaTime.innerText = `🕒 ${fc.dna_session.formatted_short}`;
      }
      if (elSession && fc.dna_session.session_badge) {
        elSession.innerText = fc.dna_session.session_badge;
        const ss = fc.dna_session.session_status || '';
        if (ss === 'GOLDEN_WINDOW') {
          elSession.style.background = 'rgba(16,185,129,0.2)';
          elSession.style.color = '#34d399';
        } else if (ss === 'FORBIDDEN_ZONE') {
          elSession.style.background = 'rgba(239,68,68,0.25)';
          elSession.style.color = '#fca5a5';
        } else {
          elSession.style.background = 'rgba(148,163,184,0.18)';
          elSession.style.color = '#cbd5e1';
        }
      }
    }

    if (elAction) {
      const act = fc.action || 'NEUTRAL';
      elAction.innerText = act;
      if (act.includes('BUY')) {
        elAction.style.background = 'rgba(16,185,129,0.22)';
        elAction.style.color = '#10b981';
      } else if (act.includes('SELL')) {
        elAction.style.background = 'rgba(239,68,68,0.22)';
        elAction.style.color = '#ef4444';
      } else if (act.includes('SIDEWAY')) {
        elAction.style.background = 'rgba(245,158,11,0.22)';
        elAction.style.color = '#f59e0b';
      } else {
        elAction.style.background = 'rgba(148,163,184,0.2)';
        elAction.style.color = '#cbd5e1';
      }
    }

    const elTrust = document.getElementById('probTrustBadge');
    if (elTrust) {
      const tScore = fc.trust_score ?? 75.0;
      const mVer = fc.model_version || 'v3.0-Base';
      const snap = fc.metrics_snapshot || {};
      const wrStr = snap.setup_winrate_pct ? ` | WR ${snap.setup_winrate_pct}%` : '';
      elTrust.innerText = `🎯 Trust: ${tScore.toFixed(1)}/100${wrStr} (${mVer})`;
      if (tScore >= 72.0) {
        elTrust.style.background = 'rgba(16,185,129,0.22)';
        elTrust.style.color = '#34d399';
        elTrust.style.borderColor = 'rgba(16,185,129,0.5)';
      } else if (tScore < 56.0 || fc.guardrail_status === 'TIGHTENED') {
        elTrust.style.background = 'rgba(239,68,68,0.25)';
        elTrust.style.color = '#fca5a5';
        elTrust.style.borderColor = 'rgba(239,68,68,0.5)';
      } else {
        elTrust.style.background = 'rgba(245,158,11,0.2)';
        elTrust.style.color = '#fbbf24';
        elTrust.style.borderColor = 'rgba(245,158,11,0.45)';
      }
    }
  }

  async toggleLiveRealtime() {
    this.liveRealtimeActive = !this.liveRealtimeActive;
    const btnToggle = document.getElementById('btnLiveModeToggle');
    const dotToggle = document.getElementById('liveModeDot');
    const textToggle = document.getElementById('liveModeText');

    if (this.liveRealtimeActive) {
      if (this.replayController) this.replayController.pause();
      if (btnToggle) {
        btnToggle.style.background = 'linear-gradient(135deg, rgba(239,68,68,0.45) 0%, rgba(245,158,11,0.35) 100%)';
        btnToggle.style.borderColor = '#ef4444';
        btnToggle.style.color = '#fff';
      }
      if (dotToggle) dotToggle.innerText = '🟢';
      if (textToggle) textToggle.innerText = 'Chế độ: LIVE MT5 (Bấm về Backtest)';

      if (this.btnLiveForecast) {
        this.btnLiveForecast.style.background = 'linear-gradient(135deg, rgba(239,68,68,0.45) 0%, rgba(245,158,11,0.35) 100%)';
        this.btnLiveForecast.style.borderColor = '#ef4444';
        this.btnLiveForecast.style.color = '#fff';
      }
      if (this.liveToggleText) this.liveToggleText.innerText = 'Live Realtime: ĐANG CHẠY';

      // Clean LIVE Mode: collapse header tools, hide sidebar, bottom replay footer, and floating PnL badge -> 100% 3 synchronized charts!
      this.toggleHeaderTools(false);
      this.toggleSidebar(false);
      const replayBar = document.querySelector('.replay-bar');
      const pnlBadge = document.getElementById('floatingPnlBadge');
      if (replayBar) replayBar.style.display = 'none';
      if (pnlBadge) pnlBadge.style.display = 'none';
      if (this.chartManager) setTimeout(() => this.chartManager.resizeAll(), 80);

      this.showToast('🟢 ĐÃ BẬT CHẾ ĐỘ LIVE! Hiển thị toàn màn hình 3 khung đồng bộ từ MT5...');
      await this.syncLiveRealtime();

      if (this.livePollTimer) clearInterval(this.livePollTimer);
      if (this.liveTickTimer) clearInterval(this.liveTickTimer);
      // Fast 1.2s real-time MT5 tick update (zero stutter)
      this.liveTickTimer = setInterval(async () => {
        if (this.liveRealtimeActive) {
          await this.pollLiveTick();
        }
      }, 1200);
      // Full indicator & dashboard sync every 12s
      this.livePollTimer = setInterval(async () => {
        if (this.liveRealtimeActive) {
          await this.syncLiveRealtime(true);
        }
      }, 12000);
    } else {
      if (this.livePollTimer) {
        clearInterval(this.livePollTimer);
        this.livePollTimer = null;
      }
      if (this.liveTickTimer) {
        clearInterval(this.liveTickTimer);
        this.liveTickTimer = null;
      }
      if (btnToggle) {
        btnToggle.style.background = 'rgba(239,68,68,0.18)';
        btnToggle.style.borderColor = '#ef4444';
        btnToggle.style.color = '#fca5a5';
      }
      if (dotToggle) dotToggle.innerText = '🔴';
      if (textToggle) textToggle.innerText = 'Chế độ: BACKTEST (Bấm sang LIVE)';

      if (this.btnLiveForecast) {
        this.btnLiveForecast.style.background = 'rgba(239,68,68,0.18)';
        this.btnLiveForecast.style.color = '#fca5a5';
      }
      if (this.liveToggleText) this.liveToggleText.innerText = 'Live Realtime: TẮT';

      // Show Replay footer & Floating PnL badge in BACKTEST mode (keep floating Tools popover closed until clicked)
      this.toggleHeaderTools(false);
      const replayBar = document.querySelector('.replay-bar');
      const pnlBadge = document.getElementById('floatingPnlBadge');
      if (replayBar) replayBar.style.display = 'flex';
      if (pnlBadge) pnlBadge.style.display = 'flex';
      if (this.chartManager) setTimeout(() => this.chartManager.resizeAll(), 80);

      this.showToast('⏪ Đã quay về Chế độ BACKTEST (Replay)');
      await this.loadSymbol(this.currentSymbol, this.timeframePair);
    }
  }

  async pollLiveTick() {
    try {
      const resp = await fetch(`/api/live/tick?symbol=${encodeURIComponent(this.currentSymbol)}`);
      const tick = await resp.json();
      if (tick && tick.success && tick.bid > 0 && this.chartManager && this.chartManager.applyLiveTick) {
        this.chartManager.applyLiveTick(tick.bid);
        const d = (this.tradePanel && this.tradePanel.getDigits) ? this.tradePanel.getDigits() : 2;
        const btnBuy = document.getElementById('buyPriceLabel') || document.getElementById('buyPriceVal');
        const btnSell = document.getElementById('sellPriceLabel') || document.getElementById('sellPriceVal');
        if (btnBuy && tick.ask) btnBuy.innerText = Number(tick.ask).toFixed(d);
        if (btnSell && tick.bid) btnSell.innerText = Number(tick.bid).toFixed(d);
      }
    } catch (e) {}
  }

  async syncLiveRealtime(silent = false) {
    try {
      const url = `/api/live/sync?symbol=${encodeURIComponent(this.currentSymbol)}&timeframe_pair=${encodeURIComponent(this.timeframePair)}`;
      const resp = await fetch(url);
      const liveState = await resp.json();
      if (liveState && (liveState.candles_tf3 || liveState.candles_m15)) {
        await this.applyState(liveState);
        if (!silent) {
          const src = liveState.live_source || 'MT5';
          const fc = liveState.probabilistic_forecast || {};
          const dna = liveState.dna_session || {};
          this.showToast(
            `🔴 LIVE [${src}] ${this.currentSymbol} | ${dna.formatted_short || ''} | ${fc.tactical_badge || ''}`
          );
          if (this.chartManager) this.chartManager.centerCharts();
        }
      }
    } catch (err) {
      console.error('Error syncing live realtime:', err);
    }
  }

  async scanLiveRadar() {
    const tbody = document.getElementById('liveRadarTableBody');
    const scanTimeEl = document.getElementById('liveRadarScanTime');
    const tfPair = this.liveRadarTfSelect ? this.liveRadarTfSelect.value : (this.timeframePair || 'H4_M15');
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="9" style="padding:18px;text-align:center;color:#38bdf8;">⏳ Đang quét dữ liệu Realtime, đối soát SQLite & chạy thuật toán Combine HTF+LTF k-NN...</td></tr>';
    }
    try {
      const resp = await fetch(`/api/live/radar_scan?timeframe_pair=${encodeURIComponent(tfPair)}`);
      const data = await resp.json();
      if (!data.success) return;
      if (scanTimeEl && data.scan_time_formatted) {
        scanTimeEl.innerText = data.scan_time_formatted;
      }
      if (!tbody) return;
      tbody.innerHTML = '';
      (data.results || []).forEach(r => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid rgba(255,255,255,0.06)';
        const isAlignedBuy = (r.tactical_status || '').includes('ALIGNED_BUY');
        const isAlignedSell = (r.tactical_status || '').includes('ALIGNED_SELL');
        const isPullback = (r.tactical_status || '').includes('PULLBACK');
        const tacColor = isAlignedBuy ? '#10b981' : (isAlignedSell ? '#ef4444' : (isPullback ? '#fbbf24' : '#94a3b8'));
        const sessColor = r.session_status === 'GOLDEN_WINDOW' ? '#34d399' : (r.session_status === 'FORBIDDEN_ZONE' ? '#f87171' : '#cbd5e1');
        const st = r.setup || {};
        const dirColor = st.direction === 'BUY' ? '#10b981' : '#ef4444';
        const tScore = r.trust_score ?? 75.0;
        const tColor = tScore >= 72.0 ? '#10b981' : (tScore < 56.0 ? '#ef4444' : '#fbbf24');

        tr.innerHTML = `
          <td style="padding:8px 10px;">
            <b style="color:#f8fafc;font-size:12.5px;">${r.symbol}</b>
            <div style="font-size:10px;color:#38bdf8;">${r.price} (${r.source})</div>
          </td>
          <td style="padding:8px 10px;color:#cbd5e1;">${r.time_formatted}</td>
          <td style="padding:8px 10px;">
            <span style="color:#10b981;font-weight:700;">🟢${r.macro_prob_up_pct}%</span> |
            <span style="color:#ef4444;font-weight:700;">🔴${r.macro_prob_down_pct}%</span>
            <div style="font-size:10px;color:#94a3b8;">${r.macro_tf} Regime: <b>${r.macro_regime}</b></div>
          </td>
          <td style="padding:8px 10px;">
            <span style="color:#10b981;font-weight:700;">UP ${r.prob_up_pct}%</span> /
            <span style="color:#ef4444;font-weight:700;">DN ${r.prob_down_pct}%</span>
            <div style="font-size:10px;color:#f59e0b;">Wave: ${r.expected_wave_atr} ATR</div>
          </td>
          <td style="padding:8px 10px;">
            <b style="color:${tColor};">🎯 ${tScore}/100 (WR: ${r.setup_winrate_pct || 0}%)</b>
            <div style="font-size:10px;color:#c084fc;">${r.model_version || 'v3.0'} | Exp: ${r.expectancy_r >= 0 ? '+' : ''}${r.expectancy_r || 0}R</div>
          </td>
          <td style="padding:8px 10px;font-weight:700;color:${tacColor};">${r.tactical_badge}</td>
          <td style="padding:8px 10px;">
            <b style="color:${dirColor};">${st.direction || '--'} (${st.order_type || 'MARKET'}) @ ${st.entry || '--'}</b>
            <div style="font-size:10px;color:#38bdf8;font-weight:600;">${st.strategy_name || ''}</div>
            <div style="font-size:10px;color:#cbd5e1;">SL: <span style="color:#ef4444;">${st.sl || '--'} (${st.sl_pips || '--'}p)</span> | TP1: <span style="color:#10b981;">${st.tp1 || '--'}</span> | TP2: <span style="color:#38bdf8;">${st.tp2 || '--'}</span></div>
            <div style="font-size:10px;color:#fbbf24;">📦 Lot ($100 SL): <b>${st.lot_size_100usd || '--'} Lot</b> | Playbooks: ${(st.verified_playbooks || []).join(', ')}</div>
          </td>
          <td style="padding:8px 10px;color:${sessColor};font-size:10.5px;">${r.session_badge}</td>
          <td style="padding:8px 10px;display:flex;gap:5px;">
            <button class="btn-header" style="background:#38bdf8;color:#0f172a;font-weight:700;padding:4px 8px;border:none;"
              onclick="window.app.openLiveSymbolFromRadar('${r.symbol}', '${r.timeframe_pair}')">
              🔍 Xem Live
            </button>
            <button class="btn-header" style="background:rgba(16,185,129,0.22);color:#34d399;font-weight:700;padding:4px 7px;border:1px solid #10b981;"
              onclick="window.app.openAccuracyForSymbol('${r.symbol}', '${r.timeframe_pair}')" title="Xem bảng điểm 3-in-1 & Tự học">
              🎯
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      console.error('Error scanning live radar:', err);
      if (tbody) {
        tbody.innerHTML = '<tr><td colspan="9" style="padding:14px;text-align:center;color:#ef4444;">Lỗi khi quét Radar Realtime.</td></tr>';
      }
    }
  }

  async openAccuracyForSymbol(symbol, tfPair) {
    if (this.liveRadarModal) this.liveRadarModal.classList.remove('open');
    this.currentSymbol = symbol || this.currentSymbol;
    this.timeframePair = tfPair || this.timeframePair || 'H4_M15';
    if (this.forecastAccuracyModal) this.forecastAccuracyModal.classList.add('open');
    await this.loadForecastAccuracyModal();
  }

  async loadForecastAccuracyModal() {
    const sym = this.currentSymbol || 'XAUUSD';
    const tfPair = this.timeframePair || 'H4_M15';
    const symLbl = document.getElementById('accSymbolLabel');
    if (symLbl) symLbl.innerText = `${sym} (${tfPair})`;

    try {
      const resp = await fetch(`/api/forecast/accuracy?symbol=${encodeURIComponent(sym)}&timeframe_pair=${encodeURIComponent(tfPair)}`);
      const data = await resp.json();
      if (data.success && data.scorecard) {
        this.renderAccuracyScorecard(data.scorecard);
      }
    } catch (err) {
      console.error('Error loading forecast accuracy modal:', err);
    }
  }

  renderAccuracyScorecard(sc) {
    if (!sc) return;
    const t1 = sc.tier1_probabilistic || {};
    const t2 = sc.tier2_tactical_setup || {};
    const t3 = sc.tier3_wave_trajectory || {};
    const prof = sc.profile || {};

    const elVer = document.getElementById('accModelVersionBadge');
    const elGuard = document.getElementById('accGuardrailBadge');
    const elTrust = document.getElementById('accTrustScoreVal');
    const elVerCnt = document.getElementById('accVerifiedCountText');
    const elNonAdv = document.getElementById('accNonAdverseVal');
    const elBrier = document.getElementById('accBrierDirText');
    const elWr = document.getElementById('accSetupWinrateVal');
    const elExpR = document.getElementById('accSetupExpRText');
    const elCap = document.getElementById('accWaveCaptureVal');
    const elMae = document.getElementById('accWaveMaeText');

    if (elVer) elVer.innerText = sc.model_version || 'v3.0-Base';
    if (elGuard) {
      elGuard.innerText = sc.guardrail_badge || '🟢 MÔ HÌNH ĐỒNG BỘ TỐT';
      if (sc.guardrail_status === 'TIGHTENED') {
        elGuard.style.background = 'rgba(239,68,68,0.25)';
        elGuard.style.color = '#fca5a5';
      } else {
        elGuard.style.background = 'rgba(16,185,129,0.22)';
        elGuard.style.color = '#34d399';
      }
    }
    if (elTrust) {
      elTrust.innerText = `${sc.trust_score || 75.0} / 100`;
      elTrust.style.color = sc.trust_score >= 72 ? '#10b981' : (sc.trust_score < 56 ? '#ef4444' : '#fbbf24');
    }
    if (elVerCnt) {
      elVerCnt.innerText = `Đã đối soát: ${sc.verified_count || 0} dự báo (Đang chờ: ${sc.pending_count || 0})`;
    }
    if (elNonAdv) elNonAdv.innerText = `${t1.non_adverse_survival_pct || 0}% Non-Adverse`;
    if (elBrier) elBrier.innerText = `Đúng hướng: ${t1.directional_accuracy_pct || 0}% | Brier: ${t1.brier_score || 0.20}`;
    if (elWr) elWr.innerText = `WR: ${t2.setup_winrate_pct || 0}% (${t2.evaluated_setups_count || 0} kèo)`;
    if (elExpR) elExpR.innerText = `Kỳ vọng: ${(t2.expectancy_r >= 0 ? '+' : '')}${t2.expectancy_r || 0}R | TP1 Hit: ${t2.tp1_hit_pct || 0}%`;
    if (elCap) elCap.innerText = `Capture: ${t3.amplitude_capture_pct || 0}%`;
    if (elMae) elMae.innerText = `Sai số đường phóng chiếu: ${t3.avg_wave_mae_atr || 0} ATR (MFE TB: ${t3.avg_realized_mfe_atr || 0} ATR)`;

    // Reliability Buckets Table
    const relBody = document.getElementById('accReliabilityTableBody');
    if (relBody) {
      relBody.innerHTML = '';
      (t1.reliability_buckets || []).forEach(b => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
        tr.innerHTML = `
          <td style="padding:5px 6px;font-weight:700;color:#38bdf8;">${b.bucket}</td>
          <td style="padding:5px 6px;color:#cbd5e1;">${b.count}</td>
          <td style="padding:5px 6px;color:#94a3b8;">${b.predicted_prob_pct}%</td>
          <td style="padding:5px 6px;font-weight:700;color:#10b981;">${b.actual_win_pct}%</td>
          <td style="padding:5px 6px;font-weight:700;color:#fbbf24;">${b.non_adverse_pct}%</td>
        `;
        relBody.appendChild(tr);
      });
    }

    // Active Champion Profile Box
    const profBox = document.getElementById('accActiveProfileBox');
    if (profBox) {
      const fw = (prof.f_weights_ltf || [1.25, 1.15, 1.35, 1.20, 1.05]).map(x => Number(x).toFixed(2)).join(', ');
      const htfPct = Math.round((prof.htf_weight ?? 0.70) * 100);
      const ltfPct = 100 - htfPct;
      const upHist = prof.upgrade_history || [];
      const lastUp = upHist.length > 0 ? upHist[upHist.length - 1] : null;
      const lastUpHtml = lastUp
        ? `<div style="margin-top:4px;color:#34d399;">🏆 Nâng cấp gần nhất (${lastUp.time}): <b>${lastUp.from_version} ➔ ${lastUp.to_version}</b> (Trust: ${lastUp.trust_before} ➔ ${lastUp.trust_after}, WR: ${lastUp.wr_before}% ➔ ${lastUp.wr_after}%)</div>`
        : `<div style="margin-top:4px;color:#94a3b8;">ℹ️ Đang ở cấu hình gốc hoặc chờ chạy vòng lặp đấu loại Champion vs Challenger.</div>`;

      const lb = sc.learning_benchmark;
      let lbHtml = '';
      if (lb && lb.pillar1_oos_gain && lb.pillar3_generalization) {
        const p1 = lb.pillar1_oos_gain;
        const p3 = lb.pillar3_generalization;
        const p4 = lb.pillar4_learned_dna || {};
        const dTrustStr = (p1.delta_trust >= 0 ? '+' : '') + p1.delta_trust;
        const dWrStr = (p1.delta_wr_pct >= 0 ? '+' : '') + p1.delta_wr_pct + '%';
        const dRStr = (p1.delta_exp_r >= 0 ? '+' : '') + p1.delta_exp_r + 'R';
        lbHtml = `
          <div style="margin-top:6px;padding-top:6px;border-top:1px dashed rgba(148,163,184,0.25);">
            <div>🧪 <b>Hạng Tự Học (4-Pillar Benchmark):</b> <span style="color:#10b981;font-weight:700;">${lb.learning_grade}</span> | Chặng thắng OOS: <b>${lb.folds_won_ratio}</b></div>
            <div>📈 <b>Độ Lợi Học Tập OOS (Gốc ➔ Học):</b> Trust <b>${p1.baseline_trust} ➔ ${p1.adaptive_trust} (${dTrustStr})</b> | WR <b>${p1.baseline_wr_pct}% ➔ ${p1.adaptive_wr_pct}% (${dWrStr})</b> | Exp <b>${p1.baseline_exp_r}R ➔ ${p1.adaptive_exp_r}R (${dRStr})</b></div>
            <div>🛡️ <b>Chống Học Vẹt (OOS Retention):</b> <b style="color:#38bdf8;">${p3.oos_retention_pct}%</b> (${p3.overfit_status}) | Đặc trưng trội: <b>${p4.top_discriminative_feature || '--'}</b></div>
          </div>
        `;
      }

      const ea = sc.strategy_edge_audit;
      let eaHtml = '';
      if (ea && ea.total_filtered && ea.playbooks) {
        const tf = ea.total_filtered;
        const p1f = (ea.playbooks.EMA21_TREND_IMPULSE || {}).filtered || {};
        const p2f = (ea.playbooks.STOCH_RSI_DIV_REVERSAL || {}).filtered || {};
        const p3f = (ea.playbooks.BB_FAKEOUT_STOP || {}).filtered || {};
        const p3un = (ea.playbooks.BB_FAKEOUT_STOP || {}).unfilled_stop_cancelled || 0;
        eaHtml = `
          <div style="margin-top:6px;padding-top:6px;border-top:1px dashed rgba(56,189,248,0.35);">
            <div>📊 <b>Kiểm Định Định Lượng 3 Chiến Lược (${ea.bars_scanned} nến):</b> Mẫu Lọc <b>N=${tf.n}</b> (Đã chặn ${ea.whipsaws_vetoed} nhiễu) | WR: <b style="color:#10b981;">${tf.wr_pct}%</b> | PF: <b style="color:#fbbf24;">${tf.pf}</b> | Exp: <b>+${tf.exp_r}R</b> (Tổng: <b>+${tf.net_r}R</b>)</div>
            <div style="font-size:10.5px;color:#cbd5e1;">• [1] EMA21 Impulse: N=${p1f.n || 0}, WR=${p1f.wr_pct || 0}%, PF=${p1f.pf || 0} | [2] Stoch+RSI Div: N=${p2f.n || 0}, WR=${p2f.wr_pct || 0}%, PF=${p2f.pf || 0}</div>
            <div style="font-size:10.5px;color:#38bdf8;">• [3] BB(20,2) Fakeout Stop: N=${p3f.n || 0} khớp (Đã lọc ${p3un} bẫy Stop không khớp), WR=${p3f.wr_pct || 0}%, PF=${p3f.pf || 0}, Exp=${p3f.exp_r || 0}R</div>
          </div>
        `;
      }

      profBox.innerHTML = `
        <div>• <b>Tỷ lệ Pha Trộn Đa Khung:</b> <span style="color:#fbbf24;">${htfPct}% HTF Anchor + ${ltfPct}% LTF Trigger</span> | <b>k-Neighbors:</b> ${prof.k_neighbors || 35}</div>
        <div>• <b>Trọng số 5 Đặc trưng [ER20, Sqz4, CLV, Slope, Stack]:</b> <span style="color:#38bdf8;">[${fw}]</span></div>
        <div>• <b>Ưu tiên Mẫu Gần & Cùng Phiên DNA:</b> TimeDecay=${prof.time_decay_strength ?? 0.20} | SessionBonus=${prof.session_affinity_bonus ?? 0.15} | Temp=${prof.prob_temperature ?? 1.0}</div>
        ${lastUpHtml}
        ${lbHtml}
        ${eaHtml}
      `;
    }

    // Recent Verified Forecasts Table
    const recBody = document.getElementById('accRecentVerifiedBody');
    if (recBody) {
      recBody.innerHTML = '';
      const recs = sc.recent_forecasts || [];
      if (recs.length === 0) {
        recBody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;color:#94a3b8;">Chưa có dữ liệu đối soát.</td></tr>';
      } else {
        recs.forEach(r => {
          const tr = document.createElement('tr');
          tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
          const rVal = Number(r.realized_r || 0);
          const rColor = rVal > 0 ? '#10b981' : (rVal < 0 ? '#ef4444' : '#94a3b8');
          const outBadge = r. directional_correct ? '✅ Đúng hướng' : (r.non_adverse_survival ? '🟡 Không ngược' : '❌ Ngược sóng');
          tr.innerHTML = `
            <td style="padding:5px 8px;color:#cbd5e1;">${r.server_vn_time}</td>
            <td style="padding:5px 8px;">
              <span style="color:#10b981;">U:${r.prob_up}%</span> / <span style="color:#ef4444;">D:${r.prob_down}%</span> / <span style="color:#94a3b8;">S:${r.prob_sideway}%</span>
            </td>
            <td style="padding:5px 8px;color:#38bdf8;font-weight:700;">${r.setup_dir} @ ${r.entry_price} (${r.tactical_status})</td>
            <td style="padding:5px 8px;"><b>${r.actual_label}</b> (${outBadge})</td>
            <td style="padding:5px 8px;font-weight:700;color:${rColor};">${r.setup_outcome}</td>
            <td style="padding:5px 8px;font-weight:700;color:${rColor};">${rVal >= 0 ? '+' : ''}${rVal.toFixed(2)} R</td>
            <td style="padding:5px 8px;color:#c084fc;">${r.wave_mae_atr} ATR (MFE: ${r.mfe_atr} ATR)</td>
          `;
          recBody.appendChild(tr);
        });
      }
    }
  }

  async runSingleSymbolCalibration() {
    const sym = this.currentSymbol || 'XAUUSD';
    const tfPair = this.timeframePair || 'H4_M15';
    const banner = document.getElementById('accCalibrationResultBanner');
    if (banner) {
      banner.style.display = 'block';
      banner.innerText = `⏳ Đang chạy đấu loại Champion vs Challenger (3-Layer Adaptive Calibration) trên dữ liệu lịch sử ${sym} (${tfPair})...`;
    }
    try {
      const resp = await fetch('/api/forecast/calibrate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: sym, timeframe_pair: tfPair, calibrate_all_radar_pairs: false })
      });
      const res = await resp.json();
      if (res.success && res.primary_report) {
        const rep = res.primary_report;
        const bm = rep.before_metrics || {};
        const am = rep.after_metrics || {};
        if (banner) {
          banner.innerHTML = rep.promoted
            ? `🏆 <b>ĐÃ NÂNG CẤP MÔ HÌNH (${rep.version_before} ➔ ${rep.version_after}):</b> Chiến thắng bởi <b>${rep.winning_challenger}</b> | Trust Score: <b>${bm.composite_score} ➔ ${am.composite_score}/100</b> | Setup WR: <b>${bm.setup_winrate_pct}% ➔ ${am.setup_winrate_pct}%</b> | Kỳ vọng: <b>${bm.expectancy_r}R ➔ ${am.expectancy_r}R</b> (${rep.elapsed_sec}s)`
            : `🛡️ <b>GIỮ NGUYÊN CHAMPION (${rep.version_after}):</b> Cấu hình hiện tại đã đạt tối ưu trên tập Out-of-Sample (Trust: <b>${am.composite_score}/100</b> | WR: <b>${am.setup_winrate_pct}%</b> | Kỳ vọng: <b>${am.expectancy_r}R</b>).`;
        }
        if (rep.scorecard) {
          this.renderAccuracyScorecard(rep.scorecard);
        }
        await this.refreshState();
        this.showToast(`🧠 Hoàn tất Tự học ${sym}: Trust ${am.composite_score}/100 (${rep.version_after})`);
      }
    } catch (err) {
      console.error('Error calibrating symbol:', err);
      if (banner) banner.innerText = '❌ Lỗi khi chạy hiệu chỉnh mô hình.';
    }
  }

  async runAllRadarCalibration() {
    const tfPair = this.liveRadarTfSelect ? this.liveRadarTfSelect.value : (this.timeframePair || 'H4_M15');
    this.showToast(`⏳ Đang chạy Tự học & Đấu loại Champion vs Challenger cho toàn bộ 6 cặp tiền (${tfPair})...`);
    try {
      const resp = await fetch('/api/forecast/calibrate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timeframe_pair: tfPair, calibrate_all_radar_pairs: true })
      });
      const res = await resp.json();
      if (res.success) {
        await this.scanLiveRadar();
        this.showToast(`🏆 Đã hoàn tất tự học & nâng cấp ${res.calibrated_count} cặp tiền trên Radar!`);
      }
    } catch (err) {
      console.error('Error calibrating all radar pairs:', err);
    }
  }

  async openLiveSymbolFromRadar(symbol, tfPair) {
    if (this.liveRadarModal) this.liveRadarModal.classList.remove('open');
    this.currentSymbol = symbol;
    this.timeframePair = tfPair || 'H4_M15';
    if (this.symbolSelect) this.symbolSelect.value = symbol;
    if (this.tfPairSelect) this.tfPairSelect.value = this.timeframePair;
    if (!this.liveRealtimeActive) {
      await this.toggleLiveRealtime();
    } else {
      await this.syncLiveRealtime();
    }
  }
}

// Bootstrap on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  window.app = new TradingSimulatorApp();
  window.app.init();
});
