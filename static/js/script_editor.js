/**
 * Custom Script Editor Manager (TradingView Pine Editor Style)
 */

const SCRIPT_STARTERS = {
  ema_cross: `# EMA 9 / 21 Crossover + Buy/Sell Signals
fast = ta.ema(close, 9)
slow = ta.ema(close, 21)

plot("EMA 9", fast, color="#00e676", width=2)
plot("EMA 21", slow, color="#ff5252", width=2)

bull_cross = ta.crossover(fast, slow)
bear_cross = ta.crossunder(fast, slow)

for i in range(len(close)):
    if bull_cross[i]:
        marker(i, "BUY 9/21", color="#00e676", position="belowBar", shape="arrowUp")
    elif bear_cross[i]:
        marker(i, "SELL 9/21", color="#ff5252", position="aboveBar", shape="arrowDown")
`,
  donchian: `# Donchian Channel Breakout (20)
upper = ta.highest(high, 20)
lower = ta.lowest(low, 20)
mid = [(u + l) / 2.0 if (u is not None and l is not None) else None for u, l in zip(upper, lower)]

plot("DC Upper", upper, color="#38bdf8", width=2)
plot("DC Mid", mid, color="#94a3b8", width=1, style="dashed")
plot("DC Lower", lower, color="#38bdf8", width=2)
`,
  rsi_signal: `# RSI 14 Extreme Reversal Markers on Price Chart
r = ta.rsi(close, 14)

for i in range(1, len(close)):
    if r[i - 1] < 25 and r[i] >= 25:
        marker(i, "RSI OS", color="#10b981", position="belowBar", shape="arrowUp")
    elif r[i - 1] > 75 and r[i] <= 75:
        marker(i, "RSI OB", color="#ef4444", position="aboveBar", shape="arrowDown")
`
};

class ScriptEditorManager {
  constructor(app) {
    this.app = app;
    this.modal = document.getElementById('scriptEditorModal');
    this.btnOpen = document.getElementById('btnOpenScriptEditor');
    this.btnClose = document.getElementById('btnCloseScriptEditor');
    this.btnCancel = document.getElementById('btnCancelScriptEditor');
    this.btnSave = document.getElementById('btnSaveScriptOnly');
    this.btnRun = document.getElementById('btnRunAddScript');
    this.btnDelete = document.getElementById('btnDeleteScript');

    this.savedSelect = document.getElementById('scriptSavedSelect');
    this.starterSelect = document.getElementById('scriptStarterSelect');
    this.nameInput = document.getElementById('scriptNameInput');
    this.tfSelect = document.getElementById('scriptTargetTf');
    this.codeArea = document.getElementById('scriptCodeArea');
    this.consoleEl = document.getElementById('scriptConsoleOutput');

    if (this.codeArea && !this.codeArea.value.trim()) {
      this.codeArea.value = SCRIPT_STARTERS.ema_cross;
    }

    this.bindEvents();
  }

  bindEvents() {
    if (this.btnOpen) this.btnOpen.addEventListener('click', () => this.open());
    if (this.btnClose) this.btnClose.addEventListener('click', () => this.close());
    if (this.btnCancel) this.btnCancel.addEventListener('click', () => this.close());
    if (this.btnSave) this.btnSave.addEventListener('click', () => this.saveScript());
    if (this.btnRun) this.btnRun.addEventListener('click', () => this.runAndAddToChart());
    if (this.btnDelete) this.btnDelete.addEventListener('click', () => this.deleteCurrentScript());

    if (this.savedSelect) {
      this.savedSelect.addEventListener('change', (e) => {
        if (e.target.value) this.loadScript(e.target.value);
      });
    }

    if (this.starterSelect) {
      this.starterSelect.addEventListener('change', (e) => {
        const k = e.target.value;
        if (k && SCRIPT_STARTERS[k]) {
          if (this.codeArea) this.codeArea.value = SCRIPT_STARTERS[k];
          if (this.nameInput) this.nameInput.value = `my_${k}`;
          this.setConsole(`✨ Đã nạp code mẫu "${k}". Bấm "▶ Add to Chart" để vẽ ngay!`, '');
        }
        e.target.value = '';
      });
    }

    // Support Tab key for 4-space indentation inside textarea
    if (this.codeArea) {
      this.codeArea.addEventListener('keydown', (e) => {
        if (e.key === 'Tab') {
          e.preventDefault();
          const start = this.codeArea.selectionStart;
          const end = this.codeArea.selectionEnd;
          this.codeArea.value = this.codeArea.value.substring(0, start) + '    ' + this.codeArea.value.substring(end);
          this.codeArea.selectionStart = this.codeArea.selectionEnd = start + 4;
        }
      });
    }
  }

  open() {
    if (this.modal) this.modal.classList.add('open');
    this.refreshScriptsList();
  }

  close() {
    if (this.modal) this.modal.classList.remove('open');
  }

  setConsole(msg, status = '') {
    if (!this.consoleEl) return;
    this.consoleEl.className = `tv-script-console ${status}`;
    this.consoleEl.innerText = msg;
  }

  async refreshScriptsList() {
    try {
      const resp = await fetch('/api/scripts');
      const res = await resp.json();
      if (this.savedSelect && res.scripts) {
        this.savedSelect.innerHTML = '<option value="">📂 Script đã lưu...</option>';
        for (const name of res.scripts) {
          const opt = document.createElement('option');
          opt.value = name;
          opt.innerText = name;
          this.savedSelect.appendChild(opt);
        }
      }
    } catch (e) {
      console.warn('Error listing scripts:', e);
    }
  }

  async loadScript(name) {
    try {
      const resp = await fetch(`/api/scripts/load?name=${encodeURIComponent(name)}`);
      const res = await resp.json();
      if (res.success) {
        if (this.nameInput) this.nameInput.value = res.name;
        if (this.codeArea) this.codeArea.value = res.code;
        this.setConsole(`📂 Đã tải script "${res.name}".`, 'ok');
      }
    } catch (e) {
      this.setConsole(`Lỗi tải script: ${e}`, 'err');
    }
  }

  async saveScript() {
    const name = (this.nameInput ? this.nameInput.value.trim() : '') || 'my_script';
    const code = this.codeArea ? this.codeArea.value : '';
    try {
      const resp = await fetch('/api/scripts/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, code })
      });
      const res = await resp.json();
      if (res.success) {
        this.setConsole(`💾 Đã lưu script "${res.name}.py" thành công!`, 'ok');
        await this.refreshScriptsList();
      }
    } catch (e) {
      this.setConsole(`Lỗi lưu script: ${e}`, 'err');
    }
  }

  async deleteCurrentScript() {
    const name = (this.nameInput ? this.nameInput.value.trim() : '');
    if (!name) return;
    try {
      const resp = await fetch(`/api/scripts/delete?name=${encodeURIComponent(name)}`, { method: 'DELETE' });
      const res = await resp.json();
      this.setConsole(`🗑️ Đã xóa script "${name}" khỏi hệ thống.`, 'ok');
      await this.refreshScriptsList();
      if (this.app && this.app.indicatorsManager) {
        await this.app.indicatorsManager.fetchConfigSilent();
      }
      if (this.app) await this.app.refreshState();
    } catch (e) {
      this.setConsole(`Lỗi xóa script: ${e}`, 'err');
    }
  }

  async runAndAddToChart() {
    const name = (this.nameInput ? this.nameInput.value.trim() : '') || 'my_script';
    const code = this.codeArea ? this.codeArea.value : '';
    const timeframe = this.tfSelect ? this.tfSelect.value : 'TF3';

    this.setConsole('⏳ Đang biên dịch & chạy script trên dữ liệu biểu đồ...', '');
    try {
      const resp = await fetch('/api/scripts/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, code, timeframe, add_to_chart: true })
      });
      const res = await resp.json();
      if (!res.success) {
        this.setConsole(`❌ Lỗi Script:\n${res.error}`, 'err');
        return;
      }
      const logsStr = (res.logs && res.logs.length) ? `\nLogs:\n${res.logs.join('\n')}` : '';
      this.setConsole(
        `✅ Thành công (${res.elapsed_ms}ms) — Đã vẽ ${res.plot_count} đường (plots) & ${res.marker_count} mũi tên (markers) lên ${timeframe}!${logsStr}`,
        'ok'
      );
      await this.refreshScriptsList();
      if (this.app && this.app.indicatorsManager) {
        await this.app.indicatorsManager.fetchConfigSilent();
      }
      if (this.app) {
        await this.app.refreshState();
        if (this.app.chartManager) {
          this.app.chartManager.showToast(`📝 Đã nạp Custom Script "${res.name}" lên ${timeframe}!`);
        }
      }
    } catch (e) {
      this.setConsole(`❌ Lỗi kết nối: ${e}`, 'err');
    }
  }
}

window.ScriptEditorManager = ScriptEditorManager;
