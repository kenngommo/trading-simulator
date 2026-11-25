/**
 * Indicators & Templates Manager (TradingView Style)
 */

class IndicatorsManager {
  constructor(app) {
    this.app = app;
    this.modal = document.getElementById('indicatorModal');
    this.btnOpenModal = document.getElementById('btnOpenIndicators');
    this.btnCloseModal = document.getElementById('btnCloseIndicators');
    this.btnSaveConfig = document.getElementById('btnSaveIndicators');
    this.templateSelect = document.getElementById('templateSelect');
    this.btnSaveTemplate = document.getElementById('btnSaveTemplate');

    this.searchInput = document.getElementById('indicatorSearchInput');
    this.tabBtnActive = document.getElementById('tabBtnActiveIndicators');
    this.tabBtnCatalog = document.getElementById('tabBtnCatalogIndicators');
    this.quickAddBar = document.getElementById('quickAddIndicatorBar');
    this.btnAddIndicator = document.getElementById('btnConfirmAddIndicator');
    this.btnPresetTF1Only = document.getElementById('btnPresetTF1Only');
    this.btnPresetAll3Charts = document.getElementById('btnPresetAll3Charts');

    this.currentView = 'active'; // 'active' or 'catalog'
    this.currentConfig = {};
    this.availableCatalog = [];
    this.activeTemplateName = localStorage.getItem('activeTemplateName') || '';

    // TradingView-Style Single Indicator Settings Modal
    this.settingsModal = document.getElementById('indSettingsModal');
    this.btnCloseSettings = document.getElementById('btnCloseIndSettings');
    this.btnCancelSettings = document.getElementById('btnIndSettingsCancel');
    this.btnOkSettings = document.getElementById('btnIndSettingsOk');
    this.btnResetSettings = document.getElementById('btnIndSettingsReset');
    this.tvTabInputs = document.getElementById('tvTabInputs');
    this.tvTabStyle = document.getElementById('tvTabStyle');
    this.tvPanelInputs = document.getElementById('tvPanelInputs');
    this.tvPanelStyle = document.getElementById('tvPanelStyle');
    this.editingKey = null;
    this.editingDraft = null;

    this.bindEvents();
    this.loadTemplatesList();
    this.fetchCatalog();
    this.fetchConfigSilent();
  }

  async fetchConfigSilent() {
    try {
      const resp = await fetch('/api/indicators/config');
      const res = await resp.json();
      this.currentConfig = res.active_indicators || {};
    } catch (e) {}
  }

  bindEvents() {
    if (this.btnOpenModal) {
      this.btnOpenModal.addEventListener('click', () => this.openModal());
    }
    if (this.btnCloseModal) {
      this.btnCloseModal.addEventListener('click', () => this.closeModal());
    }
    if (this.btnSaveConfig) {
      this.btnSaveConfig.addEventListener('click', () => this.saveCurrentConfig());
    }
    if (this.templateSelect) {
      this.templateSelect.addEventListener('change', (e) => this.loadTemplate(e.target.value));
    }
    if (this.btnSaveTemplate) {
      this.btnSaveTemplate.addEventListener('click', () => this.promptSaveNewTemplate());
    }

    if (this.tabBtnActive) {
      this.tabBtnActive.addEventListener('click', () => {
        this.currentView = 'active';
        this.tabBtnActive.classList.add('active');
        if (this.tabBtnCatalog) this.tabBtnCatalog.classList.remove('active');
        if (this.quickAddBar) this.quickAddBar.style.display = 'none';
        this.renderConfigUI();
      });
    }

    if (this.tabBtnCatalog) {
      this.tabBtnCatalog.addEventListener('click', () => {
        this.currentView = 'catalog';
        this.tabBtnCatalog.classList.add('active');
        if (this.tabBtnActive) this.tabBtnActive.classList.remove('active');
        if (this.quickAddBar) this.quickAddBar.style.display = 'block';
        this.renderCatalogUI();
      });
    }

    if (this.searchInput) {
      this.searchInput.addEventListener('input', () => {
        if (this.currentView === 'active') {
          this.renderConfigUI();
        } else {
          this.renderCatalogUI();
        }
      });
    }

    if (this.btnAddIndicator) {
      this.btnAddIndicator.addEventListener('click', () => this.handleAddQuickIndicator());
    }

    if (this.btnPresetTF1Only) {
      this.btnPresetTF1Only.addEventListener('click', () => this.loadPresetTF1());
    }

    if (this.btnPresetAll3Charts) {
      this.btnPresetAll3Charts.addEventListener('click', () => this.loadPresetAll3Charts());
    }

    // TradingView-Style Single Indicator Settings Modal events
    if (this.btnCloseSettings) {
      this.btnCloseSettings.addEventListener('click', () => this.closeIndicatorSettings());
    }
    if (this.btnCancelSettings) {
      this.btnCancelSettings.addEventListener('click', () => this.closeIndicatorSettings());
    }
    if (this.btnOkSettings) {
      this.btnOkSettings.addEventListener('click', () => this.applyIndicatorSettings());
    }
    if (this.btnResetSettings) {
      this.btnResetSettings.addEventListener('click', () => this.resetIndicatorDefaults());
    }
    if (this.tvTabInputs) {
      this.tvTabInputs.addEventListener('click', () => this.switchSettingsTab('inputs'));
    }
    if (this.tvTabStyle) {
      this.tvTabStyle.addEventListener('click', () => this.switchSettingsTab('style'));
    }
  }

  async fetchCatalog() {
    try {
      const resp = await fetch('/api/indicators/available');
      const res = await resp.json();
      this.availableCatalog = res.indicators || [];
    } catch (e) {
      console.warn('Error fetching indicator catalog:', e);
    }
  }

  openModal() {
    this.fetchConfigAndPopulateUI();
    this.modal.classList.add('open');
  }

  closeModal() {
    this.modal.classList.remove('open');
  }

  async fetchConfigAndPopulateUI() {
    try {
      const resp = await fetch('/api/indicators/config');
      const res = await resp.json();
      this.currentConfig = res.active_indicators || {};
      if (this.currentView === 'active') {
        this.renderConfigUI();
      } else {
        this.renderCatalogUI();
      }
    } catch (e) {
      console.error('Error fetching indicator config:', e);
    }
  }

  renderConfigUI() {
    const listEl = document.getElementById('indicatorList');
    if (!listEl) return;
    listEl.innerHTML = '';

    const filterText = (this.searchInput ? this.searchInput.value : '').toLowerCase().trim();

    const keys = Object.keys(this.currentConfig);
    if (keys.length === 0) {
      listEl.innerHTML = `<div style="text-align:center;padding:24px;color:var(--text-dim);">Chưa có chỉ báo nào đang bật. Bấm tab <b>"+ Thư Viện"</b> để thêm chỉ báo mới.</div>`;
      return;
    }

    for (const [key, item] of Object.entries(this.currentConfig)) {
      if (filterText && !key.toLowerCase().includes(filterText) && !String(item.type).toLowerCase().includes(filterText)) {
        continue;
      }

      const row = document.createElement('div');
      row.className = 'ind-row';
      row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:rgba(255,255,255,0.03);border-radius:6px;margin-bottom:6px;border:1px solid rgba(255,255,255,0.05);';

      const isChecked = item.enabled ? 'checked' : '';
      const periodVal = item.period || (item.type === 'BB' ? 20 : 14);
      const colorVal = item.color || '#3b82f6';
      const tfVal = (item.timeframe || 'TF3').toUpperCase();

      row.innerHTML = `
        <div class="ind-info" style="display:flex;align-items:center;gap:8px;">
          <input type="checkbox" class="ind-checkbox" id="chk_${key}" ${isChecked} style="cursor:pointer;width:16px;height:16px;">
          <div>
            <label class="ind-name" for="chk_${key}" style="font-weight:700;color:#f8fafc;cursor:pointer;">${key.toUpperCase()}</label>
            <div style="font-size:10px;color:#94a3b8;">Loại: <span style="color:#38bdf8;">${item.type}</span></div>
          </div>
        </div>
        <div class="ind-controls" style="display:flex;align-items:center;gap:8px;">
          <span style="font-size:11px;color:var(--text-muted);">Target:</span>
          <select class="ind-input" id="tf_${key}" style="width:105px;padding:3px 6px;background:#0f172a;border:1px solid #334155;color:#38bdf8;border-radius:4px;font-size:11px;font-weight:600;">
            <option value="TF1" ${tfVal === 'TF1' || tfVal === 'H4' ? 'selected' : ''}>Khung 1 (HTF)</option>
            <option value="TF2" ${tfVal === 'TF2' || tfVal === 'H1' ? 'selected' : ''}>Khung 2 (MTF)</option>
            <option value="TF3" ${tfVal === 'TF3' || tfVal === 'M15' || tfVal === 'M5' ? 'selected' : ''}>Khung 3 (LTF)</option>
          </select>
          ${item.period !== undefined ? `
            <span style="font-size:11px;color:var(--text-muted);">Period:</span>
            <input type="number" class="ind-input" id="period_${key}" value="${periodVal}" style="width:50px;padding:3px 6px;background:#0f172a;border:1px solid #334155;color:#fff;border-radius:4px;font-size:11px;">
          ` : ''}
          ${item.color ? `
            <input type="color" class="color-picker" id="color_${key}" value="${colorVal}" style="width:28px;height:24px;border:none;background:transparent;cursor:pointer;">
          ` : ''}
          <button class="btn-cfg-ind" data-key="${key}" title="Cấu hình chi tiết Inputs & Style (TradingView)" style="background:rgba(56,189,248,0.15);border:1px solid #38bdf8;color:#38bdf8;border-radius:4px;padding:3px 8px;cursor:pointer;font-size:11px;">
            ⚙️
          </button>
          <button class="btn-del-ind" data-key="${key}" title="Xóa chỉ báo này" style="background:rgba(239,68,68,0.15);border:1px solid #ef4444;color:#fca5a5;border-radius:4px;padding:3px 8px;cursor:pointer;font-size:11px;">
            🗑️
          </button>
        </div>
      `;
      listEl.appendChild(row);
    }

    // Bind config (gear) buttons
    listEl.querySelectorAll('.btn-cfg-ind').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const k = e.currentTarget.getAttribute('data-key');
        if (k && this.currentConfig[k]) {
          this.openIndicatorSettings(k);
        }
      });
    });

    // Bind delete buttons
    listEl.querySelectorAll('.btn-del-ind').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const k = e.currentTarget.getAttribute('data-key');
        if (k && this.currentConfig[k]) {
          delete this.currentConfig[k];
          this.renderConfigUI();
        }
      });
    });
  }

  renderCatalogUI() {
    const listEl = document.getElementById('indicatorList');
    if (!listEl) return;
    listEl.innerHTML = '';

    const filterText = (this.searchInput ? this.searchInput.value : '').toLowerCase().trim();

    const catalogGrid = document.createElement('div');
    catalogGrid.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:10px;';

    for (const ind of this.availableCatalog) {
      if (filterText && !ind.name.toLowerCase().includes(filterText) && !ind.type.toLowerCase().includes(filterText)) {
        continue;
      }

      const card = document.createElement('div');
      card.style.cssText = 'background:rgba(30,41,59,0.7);border:1px solid rgba(255,255,255,0.07);border-radius:8px;padding:10px 14px;display:flex;flex-direction:column;justify-content:space-between;cursor:pointer;transition:border-color 0.2s;';
      card.onmouseenter = () => card.style.borderColor = '#38bdf8';
      card.onmouseleave = () => card.style.borderColor = 'rgba(255,255,255,0.07)';

      card.innerHTML = `
        <div>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-weight:700;color:#f8fafc;font-size:12px;">${ind.name}</span>
            <span style="font-size:9px;padding:2px 5px;background:rgba(56,189,248,0.15);color:#38bdf8;border-radius:4px;">${ind.category}</span>
          </div>
          <div style="font-size:11px;color:#94a3b8;margin-top:4px;">
            Hiển thị: <b>${ind.overlay ? 'Đè lên giá (Overlay)' : 'Khung phụ (Sub-pane)'}</b>
          </div>
        </div>
        <div style="margin-top:10px;display:flex;justify-content:space-between;align-items:center;">
          <span style="font-size:10px;color:var(--text-dim);">Code: ${ind.type}</span>
          <button style="padding:4px 10px;background:#10b981;color:#fff;border:none;border-radius:4px;font-size:11px;font-weight:700;cursor:pointer;">+ Thêm</button>
        </div>
      `;

      card.querySelector('button').addEventListener('click', (e) => {
        e.stopPropagation();
        this.addFromCatalog(ind);
      });
      card.addEventListener('click', () => {
        this.addFromCatalog(ind);
      });

      catalogGrid.appendChild(card);
    }

    listEl.appendChild(catalogGrid);
  }

  addFromCatalog(ind) {
    const type = ind.type;
    const targetChart = 'TF3';
    const key = `${type.toLowerCase()}_${Date.now().toString().slice(-4)}_${targetChart.toLowerCase()}`;

    const newInd = {
      enabled: true,
      type: type,
      timeframe: targetChart,
      color: ind.default_color || '#3b82f6'
    };
    if (ind.default_period) newInd.period = ind.default_period;
    if (ind.default_multiplier) newInd.multiplier = ind.default_multiplier;
    if (ind.default_k) newInd.k = ind.default_k;
    if (ind.default_d) newInd.d = ind.default_d;

    this.currentConfig[key] = newInd;
    this.currentView = 'active';
    if (this.tabBtnActive) this.tabBtnActive.classList.add('active');
    if (this.tabBtnCatalog) this.tabBtnCatalog.classList.remove('active');
    if (this.quickAddBar) this.quickAddBar.style.display = 'none';
    this.renderConfigUI();
  }

  handleAddQuickIndicator() {
    const typeEl = document.getElementById('quickAddType');
    const chartEl = document.getElementById('quickAddTargetChart');
    const periodEl = document.getElementById('quickAddPeriod');
    const colorEl = document.getElementById('quickAddColor');

    if (!typeEl || !chartEl) return;
    const type = typeEl.value;
    const chart = chartEl.value;
    const period = periodEl ? parseInt(periodEl.value) || 21 : 21;
    const color = colorEl ? colorEl.value : '#00e676';

    const charts = chart === 'ALL' ? ['TF1', 'TF2', 'TF3'] : [chart];

    for (const c of charts) {
      const key = `${type.toLowerCase()}_${period}_${c.toLowerCase()}`;
      this.currentConfig[key] = {
        enabled: true,
        type: type,
        timeframe: c,
        period: period,
        color: color
      };
    }

    this.currentView = 'active';
    if (this.tabBtnActive) this.tabBtnActive.classList.add('active');
    if (this.tabBtnCatalog) this.tabBtnCatalog.classList.remove('active');
    if (this.quickAddBar) this.quickAddBar.style.display = 'none';
    this.renderConfigUI();
  }

  async saveCurrentConfig() {
    for (const key of Object.keys(this.currentConfig)) {
      const chk = document.getElementById(`chk_${key}`);
      const period = document.getElementById(`period_${key}`);
      const color = document.getElementById(`color_${key}`);
      const tf = document.getElementById(`tf_${key}`);

      if (chk) this.currentConfig[key].enabled = chk.checked;
      if (period) this.currentConfig[key].period = parseInt(period.value) || 14;
      if (color) this.currentConfig[key].color = color.value;
      if (tf) this.currentConfig[key].timeframe = tf.value;
    }

    try {
      await fetch('/api/indicators/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.currentConfig)
      });
      this.closeModal();
      await this.app.refreshState();
    } catch (e) {
      console.error('Error saving indicator config:', e);
    }
  }

  async loadTemplatesList(selectName = null) {
    try {
      const resp = await fetch('/api/templates');
      const res = await resp.json();
      if (this.templateSelect && res.templates) {
        const targetSel = selectName || this.activeTemplateName || '';
        this.templateSelect.innerHTML = `<option value="">📁 Select Template...</option>`;
        res.templates.forEach(t => {
          const opt = document.createElement('option');
          opt.value = t;
          opt.innerText = t.replace(/_/g, ' ');
          if (t === targetSel) opt.selected = true;
          this.templateSelect.appendChild(opt);
        });
      }
    } catch (e) {
      console.error('Error loading template list:', e);
    }
  }

  async loadTemplate(name) {
    if (!name) return;
    try {
      const resp = await fetch(`/api/templates/load?name=${encodeURIComponent(name)}`);
      const res = await resp.json();
      if (res.success) {
        this.currentConfig = res.config;
        this.activeTemplateName = name;
        localStorage.setItem('activeTemplateName', name);
        // Restore optional layout meta saved with this template (sub-window order & heights)
        try {
          const meta = JSON.parse(localStorage.getItem(`templateMeta_${name}`) || 'null');
          if (meta && this.app && this.app.chartManager) {
            if (meta.subWindowHeights) {
              this.app.chartManager.subWindowHeights = meta.subWindowHeights;
              localStorage.setItem('subWindowHeights', JSON.stringify(meta.subWindowHeights));
            }
            if (Array.isArray(meta.subWindowOrder) && meta.subWindowOrder.length === 3) {
              this.app.chartManager.subWindowOrder = meta.subWindowOrder;
              localStorage.setItem('subWindowOrder', JSON.stringify(meta.subWindowOrder));
              this.app.chartManager.applySubWindowOrder();
            }
          }
        } catch (err) {}
        await this.app.refreshState();
        if (this.app && this.app.chartManager) {
          this.app.chartManager.showToast(`📁 Đã nạp Template: ${name}`);
        }
      }
    } catch (e) {
      console.error('Error loading template:', e);
    }
  }

  async loadPresetTF1() {
    await this.loadTemplate('TF1');
    if (this.app && this.app.chartManager) {
      this.app.chartManager.showToast('✅ Đã nạp trọn bộ TradingView KHƯƠNG (Template TF1) cho toàn bộ hệ thống!');
    }
  }

  async loadPresetAll3Charts() {
    await this.loadTemplate('TF1');
    if (this.app && this.app.chartManager) {
      this.app.chartManager.showToast('🚀 Đã nạp trọn bộ TradingView KHƯƠNG (9EMA Ribbon + BB + RSI_MA9_WMA45 + Stoch 14-3-3 + MACD + MTF Signals) trên cả 3 khung!');
    }
  }

  ensureSaveTemplateModal() {
    let modal = document.getElementById('saveTemplateModal');
    if (modal) return modal;

    modal = document.createElement('div');
    modal.id = 'saveTemplateModal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
      <div class="modal-card" style="width:430px;max-width:92vw;padding:18px 20px;background:#131722;border:1px solid #38bdf8;border-radius:10px;">
        <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #2b3347;padding-bottom:10px;margin-bottom:14px;">
          <h3 style="margin:0;font-size:14px;color:#38bdf8;">💾 Lưu Template (Save / Save As)</h3>
          <button id="btnCloseSaveTpl" style="background:none;border:none;color:#94a3b8;font-size:16px;cursor:pointer;">✕</button>
        </div>

        <div id="tplOverwriteBox" style="background:rgba(56,189,248,0.08);border:1px solid rgba(56,189,248,0.3);border-radius:8px;padding:12px;margin-bottom:14px;">
          <div style="font-size:11px;color:#94a3b8;margin-bottom:6px;">Template đang chọn:</div>
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
            <b id="tplCurrentNameDisplay" style="color:#f8fafc;font-size:13px;">--</b>
            <button id="btnOverwriteTemplate" class="btn-header" style="background:#2962ff;border-color:#38bdf8;color:#fff;font-weight:700;padding:5px 12px;">
              💾 Lưu đè (Save)
            </button>
          </div>
        </div>

        <div style="background:rgba(255,255,255,0.03);border:1px solid #2b3347;border-radius:8px;padding:12px;">
          <div style="font-size:11px;color:#94a3b8;margin-bottom:6px;">Hoặc lưu thành Template mới (Save As):</div>
          <div style="display:flex;gap:8px;">
            <input type="text" id="inputNewTemplateName" placeholder="VD: NAS100_Scalp_Pro" style="flex:1;background:#0f172a;border:1px solid #334155;color:#f8fafc;border-radius:6px;padding:6px 10px;font-size:12px;">
            <button id="btnSaveAsNewTemplate" class="btn-header" style="background:rgba(16,185,129,0.22);border-color:#10b981;color:#6ee7b7;font-weight:700;padding:6px 12px;">
              📝 Save As
            </button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    modal.querySelector('#btnCloseSaveTpl').addEventListener('click', () => modal.classList.remove('open'));
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.classList.remove('open');
    });
    modal.querySelector('#btnOverwriteTemplate').addEventListener('click', async () => {
      const targetName = this.activeTemplateName || (this.templateSelect ? this.templateSelect.value : '');
      if (!targetName) return;
      await this.executeSaveTemplate(targetName);
      modal.classList.remove('open');
    });
    modal.querySelector('#btnSaveAsNewTemplate').addEventListener('click', async () => {
      const inp = modal.querySelector('#inputNewTemplateName');
      const newName = (inp ? inp.value : '').trim();
      if (!newName) {
        if (inp) inp.focus();
        return;
      }
      await this.executeSaveTemplate(newName);
      modal.classList.remove('open');
    });
    return modal;
  }

  async promptSaveNewTemplate() {
    await this.fetchConfigSilent();
    const modal = this.ensureSaveTemplateModal();
    const currentName = (this.templateSelect && this.templateSelect.value) || this.activeTemplateName || '';
    const overwriteBox = modal.querySelector('#tplOverwriteBox');
    const nameDisp = modal.querySelector('#tplCurrentNameDisplay');
    const inp = modal.querySelector('#inputNewTemplateName');

    if (currentName) {
      this.activeTemplateName = currentName;
      if (overwriteBox) overwriteBox.style.display = 'block';
      if (nameDisp) nameDisp.innerText = currentName;
    } else {
      if (overwriteBox) overwriteBox.style.display = 'none';
    }
    if (inp) {
      inp.value = currentName ? `${currentName}_Copy` : '';
    }
    modal.classList.add('open');
  }

  async executeSaveTemplate(name) {
    try {
      const resp = await fetch('/api/templates/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, config: this.currentConfig })
      });
      const res = await resp.json();
      if (res.success) {
        const savedName = res.name || name;
        this.activeTemplateName = savedName;
        localStorage.setItem('activeTemplateName', savedName);
        if (this.app && this.app.chartManager) {
          localStorage.setItem(`templateMeta_${savedName}`, JSON.stringify({
            subWindowHeights: this.app.chartManager.subWindowHeights,
            subWindowOrder: this.app.chartManager.subWindowOrder
          }));
        }
        await this.loadTemplatesList(savedName);
        if (this.app && this.app.chartManager) {
          this.app.chartManager.showToast(`💾 Đã lưu Template "${savedName}" thành công!`);
        }
      }
    } catch (e) {
      console.error('Error saving template:', e);
    }
  }

  /* =========================================================================
     TRADINGVIEW-STYLE PER-INDICATOR SETTINGS MODAL (INPUTS & STYLE)
     ========================================================================= */
  async openIndicatorSettings(key) {
    if (!this.currentConfig || !this.currentConfig[key]) {
      await this.fetchConfigSilent();
    }
    const cfg = this.currentConfig[key];
    if (!cfg || !this.settingsModal) return;

    this.editingKey = key;
    this.editingDraft = JSON.parse(JSON.stringify(cfg));

    const titleEl = document.getElementById('indSettingsTitle');
    const tfBadge = document.getElementById('indSettingsTfBadge');
    const typeName = String(cfg.type || key).toUpperCase();

    if (titleEl) titleEl.innerText = `${typeName} (${key.toUpperCase()})`;
    if (tfBadge) tfBadge.innerText = (cfg.timeframe || 'TF3').toUpperCase();

    this.switchSettingsTab('inputs');
    this.renderSettingsPanels();
    this.settingsModal.classList.add('open');
  }

  closeIndicatorSettings() {
    if (this.settingsModal) {
      this.settingsModal.classList.remove('open');
    }
    this.editingKey = null;
    this.editingDraft = null;
  }

  switchSettingsTab(tab) {
    if (tab === 'inputs') {
      if (this.tvTabInputs) this.tvTabInputs.classList.add('active');
      if (this.tvTabStyle) this.tvTabStyle.classList.remove('active');
      if (this.tvPanelInputs) this.tvPanelInputs.classList.add('active');
      if (this.tvPanelStyle) this.tvPanelStyle.classList.remove('active');
    } else {
      if (this.tvTabStyle) this.tvTabStyle.classList.add('active');
      if (this.tvTabInputs) this.tvTabInputs.classList.remove('active');
      if (this.tvPanelStyle) this.tvPanelStyle.classList.add('active');
      if (this.tvPanelInputs) this.tvPanelInputs.classList.remove('active');
    }
  }

  renderSettingsPanels() {
    if (!this.editingDraft || !this.tvPanelInputs || !this.tvPanelStyle) return;
    const cfg = this.editingDraft;
    const type = String(cfg.type || '').toUpperCase();

    // 1. INPUTS TAB
    let inputsHtml = `
      <div class="tv-setting-row">
        <span class="tv-setting-label">Timeframe (Khung hiển thị)</span>
        <select id="tvIn_timeframe" class="tv-select">
          <option value="TF1" ${(cfg.timeframe || '').toUpperCase() === 'TF1' ? 'selected' : ''}>TF1 (Khung Lớn)</option>
          <option value="TF2" ${(cfg.timeframe || '').toUpperCase() === 'TF2' ? 'selected' : ''}>TF2 (Cấu Trúc)</option>
          <option value="TF3" ${(cfg.timeframe || '').toUpperCase() === 'TF3' ? 'selected' : ''}>TF3 (Thực Thi)</option>
        </select>
      </div>
    `;

    if (type === 'EMA' || type === 'SMA' || type === 'ATR') {
      inputsHtml += `
        <div class="tv-setting-row">
          <span class="tv-setting-label">Length (Period)</span>
          <input type="number" id="tvIn_period" class="tv-input-num" min="1" max="500" value="${cfg.period || 20}">
        </div>
      `;
    } else if (type === 'BB') {
      inputsHtml += `
        <div class="tv-setting-row">
          <span class="tv-setting-label">Length (Period)</span>
          <input type="number" id="tvIn_period" class="tv-input-num" min="2" max="200" value="${cfg.period || 20}">
        </div>
        <div class="tv-setting-row">
          <span class="tv-setting-label">StdDev (Multiplier)</span>
          <input type="number" id="tvIn_std_dev" class="tv-input-num" min="0.5" max="5" step="0.1" value="${cfg.std_dev || 2.0}">
        </div>
      `;
    } else if (type === 'STOCH') {
      inputsHtml += `
        <div class="tv-setting-row">
          <span class="tv-setting-label">%K Length</span>
          <input type="number" id="tvIn_k" class="tv-input-num" min="1" max="100" value="${cfg.k || 14}">
        </div>
        <div class="tv-setting-row">
          <span class="tv-setting-label">%K Smoothing</span>
          <input type="number" id="tvIn_smooth_k" class="tv-input-num" min="1" max="50" value="${cfg.smooth_k || 3}">
        </div>
        <div class="tv-setting-row">
          <span class="tv-setting-label">%D Smoothing</span>
          <input type="number" id="tvIn_d" class="tv-input-num" min="1" max="50" value="${cfg.d || 3}">
        </div>
      `;
    } else if (type === 'RSI' || type === 'RSI_MA9_WMA45') {
      inputsHtml += `
        <div class="tv-setting-row">
          <span class="tv-setting-label">RSI Length</span>
          <input type="number" id="tvIn_period" class="tv-input-num" min="2" max="100" value="${cfg.period || 14}">
        </div>
        <div class="tv-setting-row">
          <span class="tv-setting-label">SMA Length (MA9)</span>
          <input type="number" id="tvIn_ma9_period" class="tv-input-num" min="1" max="100" value="${cfg.ma9_period || 9}">
        </div>
        <div class="tv-setting-row">
          <span class="tv-setting-label">WMA Length (WMA45)</span>
          <input type="number" id="tvIn_wma45_period" class="tv-input-num" min="1" max="200" value="${cfg.wma45_period || 45}">
        </div>
      `;
    } else if (type === 'MACD') {
      inputsHtml += `
        <div class="tv-setting-row">
          <span class="tv-setting-label">Fast Length</span>
          <input type="number" id="tvIn_fast" class="tv-input-num" min="1" max="100" value="${cfg.fast || 12}">
        </div>
        <div class="tv-setting-row">
          <span class="tv-setting-label">Slow Length</span>
          <input type="number" id="tvIn_slow" class="tv-input-num" min="1" max="200" value="${cfg.slow || 26}">
        </div>
        <div class="tv-setting-row">
          <span class="tv-setting-label">Signal Smoothing</span>
          <input type="number" id="tvIn_signal" class="tv-input-num" min="1" max="100" value="${cfg.signal || 9}">
        </div>
      `;
    } else if (type === 'SUPERTREND') {
      inputsHtml += `
        <div class="tv-setting-row">
          <span class="tv-setting-label">ATR Length</span>
          <input type="number" id="tvIn_period" class="tv-input-num" min="1" max="100" value="${cfg.period || 10}">
        </div>
        <div class="tv-setting-row">
          <span class="tv-setting-label">Factor (Multiplier)</span>
          <input type="number" id="tvIn_multiplier" class="tv-input-num" min="0.5" max="10" step="0.1" value="${cfg.multiplier || 3.0}">
        </div>
      `;
    } else if (type === 'OB') {
      inputsHtml += `
        <div class="tv-setting-row">
          <span class="tv-setting-label">Left Bars</span>
          <input type="number" id="tvIn_left" class="tv-input-num" min="1" max="50" value="${cfg.left || 5}">
        </div>
        <div class="tv-setting-row">
          <span class="tv-setting-label">Right Bars</span>
          <input type="number" id="tvIn_right" class="tv-input-num" min="1" max="50" value="${cfg.right || 5}">
        </div>
      `;
    } else {
      inputsHtml += `<div style="font-size:12px; color:#94a3b8;">Chỉ báo tự động theo cấu trúc nến (${type}).</div>`;
    }
    this.tvPanelInputs.innerHTML = inputsHtml;

    // 2. STYLE TAB
    const lineStyleSelect = (id, curVal = 'solid') => `
      <select id="${id}" class="tv-select" style="min-width:92px;">
        <option value="solid" ${curVal === 'solid' ? 'selected' : ''}>Solid (Liền)</option>
        <option value="dashed" ${curVal === 'dashed' ? 'selected' : ''}>Dashed (Đứt)</option>
        <option value="dotted" ${curVal === 'dotted' ? 'selected' : ''}>Dotted (Chấm)</option>
      </select>
    `;
    const widthSelect = (id, curVal = 2) => `
      <select id="${id}" class="tv-select" style="min-width:66px;">
        <option value="1" ${Number(curVal) === 1 ? 'selected' : ''}>1px</option>
        <option value="1.5" ${Number(curVal) === 1.5 ? 'selected' : ''}>1.5px</option>
        <option value="2" ${Number(curVal) === 2 ? 'selected' : ''}>2px</option>
        <option value="3" ${Number(curVal) === 3 ? 'selected' : ''}>3px</option>
        <option value="4" ${Number(curVal) === 4 ? 'selected' : ''}>4px</option>
      </select>
    `;

    let styleHtml = `
      <div class="tv-setting-row">
        <span class="tv-setting-label">Hiển thị trên Chart (Visible)</span>
        <input type="checkbox" id="tvSt_enabled" ${cfg.enabled ? 'checked' : ''} style="width:18px;height:18px;cursor:pointer;">
      </div>
    `;

    if (type === 'STOCH') {
      styleHtml += `
        <div class="tv-setting-row">
          <span class="tv-setting-label">%K Line</span>
          <div class="tv-setting-control">
            <input type="color" id="tvSt_color_k" class="tv-color-picker" value="${cfg.color_k || '#10b981'}">
            ${widthSelect('tvSt_width_k', cfg.width_k || 1.5)}
            ${lineStyleSelect('tvSt_style_k', cfg.style_k || 'solid')}
          </div>
        </div>
        <div class="tv-setting-row">
          <span class="tv-setting-label">%D Line</span>
          <div class="tv-setting-control">
            <input type="color" id="tvSt_color_d" class="tv-color-picker" value="${cfg.color_d || '#ef4444'}">
            ${widthSelect('tvSt_width_d', cfg.width_d || 1.5)}
            ${lineStyleSelect('tvSt_style_d', cfg.style_d || 'solid')}
          </div>
        </div>
      `;
    } else if (type === 'RSI' || type === 'RSI_MA9_WMA45') {
      styleHtml += `
        <div class="tv-setting-row">
          <span class="tv-setting-label">RSI (14) Line</span>
          <div class="tv-setting-control">
            <input type="color" id="tvSt_color" class="tv-color-picker" value="${cfg.color || '#7e57c2'}">
            ${widthSelect('tvSt_lineWidth', cfg.lineWidth || 2)}
            ${lineStyleSelect('tvSt_lineStyle', cfg.lineStyle || 'solid')}
          </div>
        </div>
        <div class="tv-setting-row">
          <span class="tv-setting-label">SMA (9) Line</span>
          <div class="tv-setting-control">
            <input type="color" id="tvSt_color_ma9" class="tv-color-picker" value="${cfg.color_ma9 || '#fdd835'}">
            ${widthSelect('tvSt_width_ma9', cfg.width_ma9 || 1.5)}
            ${lineStyleSelect('tvSt_style_ma9', cfg.style_ma9 || 'solid')}
          </div>
        </div>
        <div class="tv-setting-row">
          <span class="tv-setting-label">WMA (45) Line</span>
          <div class="tv-setting-control">
            <input type="color" id="tvSt_color_wma45" class="tv-color-picker" value="${cfg.color_wma45 || '#f23645'}">
            ${widthSelect('tvSt_width_wma45', cfg.width_wma45 || 1.5)}
            ${lineStyleSelect('tvSt_style_wma45', cfg.style_wma45 || 'solid')}
          </div>
        </div>
      `;
    } else if (type === 'MACD') {
      styleHtml += `
        <div class="tv-setting-row">
          <span class="tv-setting-label">MACD Line</span>
          <div class="tv-setting-control">
            <input type="color" id="tvSt_color_macd" class="tv-color-picker" value="${cfg.color_macd || '#2962ff'}">
            ${widthSelect('tvSt_width_macd', cfg.width_macd || 1.5)}
            ${lineStyleSelect('tvSt_style_macd', cfg.style_macd || 'solid')}
          </div>
        </div>
        <div class="tv-setting-row">
          <span class="tv-setting-label">Signal Line</span>
          <div class="tv-setting-control">
            <input type="color" id="tvSt_color_signal" class="tv-color-picker" value="${cfg.color_signal || '#ff6d00'}">
            ${widthSelect('tvSt_width_signal', cfg.width_signal || 1.5)}
            ${lineStyleSelect('tvSt_style_signal', cfg.style_signal || 'solid')}
          </div>
        </div>
      `;
    } else if (type === 'BB') {
      styleHtml += `
        <div class="tv-setting-row">
          <span class="tv-setting-label">Bands Color & Width</span>
          <div class="tv-setting-control">
            <input type="color" id="tvSt_color" class="tv-color-picker" value="${cfg.color || '#a855f7'}">
            ${widthSelect('tvSt_lineWidth', cfg.lineWidth || 1)}
            ${lineStyleSelect('tvSt_lineStyle', cfg.lineStyle || 'solid')}
          </div>
        </div>
      `;
    } else {
      const defWidth = (cfg.period || 20) >= 100 ? 3 : 2;
      styleHtml += `
        <div class="tv-setting-row">
          <span class="tv-setting-label">Plot Color & Line</span>
          <div class="tv-setting-control">
            <input type="color" id="tvSt_color" class="tv-color-picker" value="${cfg.color || '#3b82f6'}">
            ${widthSelect('tvSt_lineWidth', cfg.lineWidth || defWidth)}
            ${lineStyleSelect('tvSt_lineStyle', cfg.lineStyle || 'solid')}
          </div>
        </div>
      `;
    }

    this.tvPanelStyle.innerHTML = styleHtml;
  }

  resetIndicatorDefaults() {
    if (!this.editingDraft) return;
    const type = String(this.editingDraft.type || '').toUpperCase();
    const tf = this.editingDraft.timeframe || 'TF3';

    if (type === 'STOCH') {
      this.editingDraft = { ...this.editingDraft, timeframe: tf, k: 14, d: 3, smooth_k: 3, color_k: '#10b981', width_k: 1.5, style_k: 'solid', color_d: '#ef4444', width_d: 1.5, style_d: 'solid' };
    } else if (type === 'RSI' || type === 'RSI_MA9_WMA45') {
      this.editingDraft = { ...this.editingDraft, timeframe: tf, period: 14, ma9_period: 9, wma45_period: 45, color: '#7e57c2', lineWidth: 2, lineStyle: 'solid', color_ma9: '#fdd835', width_ma9: 1.5, style_ma9: 'solid', color_wma45: '#f23645', width_wma45: 1.5, style_wma45: 'solid' };
    } else if (type === 'MACD') {
      this.editingDraft = { ...this.editingDraft, timeframe: tf, fast: 12, slow: 26, signal: 9, color_macd: '#2962ff', width_macd: 1.5, style_macd: 'solid', color_signal: '#ff6d00', width_signal: 1.5, style_signal: 'solid' };
    } else if (type === 'BB') {
      this.editingDraft = { ...this.editingDraft, timeframe: tf, period: 20, std_dev: 2.0, color: '#a855f7', lineWidth: 1, lineStyle: 'solid' };
    } else if (type === 'EMA' || type === 'SMA') {
      this.editingDraft = { ...this.editingDraft, timeframe: tf, lineWidth: (this.editingDraft.period || 20) >= 100 ? 3 : 2, lineStyle: 'solid' };
    } else if (type === 'SUPERTREND') {
      this.editingDraft = { ...this.editingDraft, timeframe: tf, period: 10, multiplier: 3.0, color: '#089981', lineWidth: 2, lineStyle: 'solid' };
    }
    this.renderSettingsPanels();
  }

  async applyIndicatorSettings() {
    if (!this.editingKey || !this.editingDraft) return;
    const cfg = this.editingDraft;

    const getNum = (id, fallback, isFloat = false) => {
      const el = document.getElementById(id);
      if (!el) return fallback;
      const val = isFloat ? parseFloat(el.value) : parseInt(el.value, 10);
      return isNaN(val) ? fallback : val;
    };
    const getVal = (id, fallback) => {
      const el = document.getElementById(id);
      return el ? el.value : fallback;
    };

    // Read Inputs
    cfg.timeframe = getVal('tvIn_timeframe', cfg.timeframe || 'TF3');
    if (document.getElementById('tvIn_period')) cfg.period = getNum('tvIn_period', cfg.period || 14);
    if (document.getElementById('tvIn_std_dev')) cfg.std_dev = getNum('tvIn_std_dev', cfg.std_dev || 2.0, true);
    if (document.getElementById('tvIn_k')) cfg.k = getNum('tvIn_k', cfg.k || 14);
    if (document.getElementById('tvIn_smooth_k')) cfg.smooth_k = getNum('tvIn_smooth_k', cfg.smooth_k || 3);
    if (document.getElementById('tvIn_d')) cfg.d = getNum('tvIn_d', cfg.d || 3);
    if (document.getElementById('tvIn_ma9_period')) cfg.ma9_period = getNum('tvIn_ma9_period', cfg.ma9_period || 9);
    if (document.getElementById('tvIn_wma45_period')) cfg.wma45_period = getNum('tvIn_wma45_period', cfg.wma45_period || 45);
    if (document.getElementById('tvIn_fast')) cfg.fast = getNum('tvIn_fast', cfg.fast || 12);
    if (document.getElementById('tvIn_slow')) cfg.slow = getNum('tvIn_slow', cfg.slow || 26);
    if (document.getElementById('tvIn_signal')) cfg.signal = getNum('tvIn_signal', cfg.signal || 9);
    if (document.getElementById('tvIn_multiplier')) cfg.multiplier = getNum('tvIn_multiplier', cfg.multiplier || 3.0, true);
    if (document.getElementById('tvIn_left')) cfg.left = getNum('tvIn_left', cfg.left || 5);
    if (document.getElementById('tvIn_right')) cfg.right = getNum('tvIn_right', cfg.right || 5);

    // Read Style
    const enEl = document.getElementById('tvSt_enabled');
    if (enEl) cfg.enabled = enEl.checked;
    if (document.getElementById('tvSt_color')) cfg.color = getVal('tvSt_color', cfg.color);
    if (document.getElementById('tvSt_lineWidth')) cfg.lineWidth = getNum('tvSt_lineWidth', cfg.lineWidth || 2, true);
    if (document.getElementById('tvSt_lineStyle')) cfg.lineStyle = getVal('tvSt_lineStyle', cfg.lineStyle || 'solid');

    if (document.getElementById('tvSt_color_k')) cfg.color_k = getVal('tvSt_color_k', '#10b981');
    if (document.getElementById('tvSt_width_k')) cfg.width_k = getNum('tvSt_width_k', 1.5, true);
    if (document.getElementById('tvSt_style_k')) cfg.style_k = getVal('tvSt_style_k', 'solid');
    if (document.getElementById('tvSt_color_d')) cfg.color_d = getVal('tvSt_color_d', '#ef4444');
    if (document.getElementById('tvSt_width_d')) cfg.width_d = getNum('tvSt_width_d', 1.5, true);
    if (document.getElementById('tvSt_style_d')) cfg.style_d = getVal('tvSt_style_d', 'solid');

    if (document.getElementById('tvSt_color_ma9')) cfg.color_ma9 = getVal('tvSt_color_ma9', '#fdd835');
    if (document.getElementById('tvSt_width_ma9')) cfg.width_ma9 = getNum('tvSt_width_ma9', 1.5, true);
    if (document.getElementById('tvSt_style_ma9')) cfg.style_ma9 = getVal('tvSt_style_ma9', 'solid');
    if (document.getElementById('tvSt_color_wma45')) cfg.color_wma45 = getVal('tvSt_color_wma45', '#f23645');
    if (document.getElementById('tvSt_width_wma45')) cfg.width_wma45 = getNum('tvSt_width_wma45', 1.5, true);
    if (document.getElementById('tvSt_style_wma45')) cfg.style_wma45 = getVal('tvSt_style_wma45', 'solid');

    if (document.getElementById('tvSt_color_macd')) cfg.color_macd = getVal('tvSt_color_macd', '#2962ff');
    if (document.getElementById('tvSt_width_macd')) cfg.width_macd = getNum('tvSt_width_macd', 1.5, true);
    if (document.getElementById('tvSt_style_macd')) cfg.style_macd = getVal('tvSt_style_macd', 'solid');
    if (document.getElementById('tvSt_color_signal')) cfg.color_signal = getVal('tvSt_color_signal', '#ff6d00');
    if (document.getElementById('tvSt_width_signal')) cfg.width_signal = getNum('tvSt_width_signal', 1.5, true);
    if (document.getElementById('tvSt_style_signal')) cfg.style_signal = getVal('tvSt_style_signal', 'solid');

    this.currentConfig[this.editingKey] = cfg;

    try {
      await fetch('/api/indicators/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.currentConfig)
      });
      this.closeIndicatorSettings();
      if (this.modal && this.modal.classList.contains('open')) {
        this.renderConfigUI();
      }
      await this.app.refreshState();
      if (this.app && this.app.chartManager) {
        this.app.chartManager.showToast(`⚙️ Đã cập nhật cấu hình ${cfg.type} (${cfg.timeframe})!`);
      }
    } catch (e) {
      console.error('Error applying indicator settings:', e);
    }
  }

  async toggleIndicatorVisibility(key) {
    if (!this.currentConfig || !this.currentConfig[key]) {
      await this.fetchConfigSilent();
    }
    if (!this.currentConfig[key]) return;
    this.currentConfig[key].enabled = !this.currentConfig[key].enabled;
    try {
      await fetch('/api/indicators/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.currentConfig)
      });
      await this.app.refreshState();
    } catch (e) {
      console.error('Error toggling indicator visibility:', e);
    }
  }

  async removeIndicator(key) {
    if (!this.currentConfig || !this.currentConfig[key]) {
      await this.fetchConfigSilent();
    }
    if (!this.currentConfig[key]) return;
    delete this.currentConfig[key];
    try {
      await fetch('/api/indicators/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.currentConfig)
      });
      await this.app.refreshState();
    } catch (e) {
      console.error('Error removing indicator:', e);
    }
  }
}

window.IndicatorsManager = IndicatorsManager;
