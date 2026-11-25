/**
 * Enhanced Trade Panel:
 * Supports Market & Pending Orders (Limit / Stop), Risk $ Auto-Lot Calculation,
 * R:R Auto-TP calculation, and Multi-Position Batch Order Splitting.
 */

class TradePanel {
  constructor(app) {
    this.app = app;
    this.orderTypeSelect = document.getElementById('orderTypeSelect');
    this.pendingPriceRow = document.getElementById('pendingPriceRow');
    this.inputPendingPrice = document.getElementById('inputPendingPrice');
    
    this.lotsInput = document.getElementById('inputLots');
    this.inputRiskUsd = document.getElementById('inputRiskUsd');
    this.slInput = document.getElementById('inputSL');
    this.tpInput = document.getElementById('inputTP');
    this.inputNumPositions = document.getElementById('inputNumPositions');

    this.btnBuy = document.getElementById('btnBuy');
    this.btnSell = document.getElementById('btnSell');
    this.btnCloseAll = document.getElementById('btnCloseAll');
    
    this.positionsContainer = document.getElementById('tabPositions') || document.getElementById('positionsContainer');
    this.pendingContainer = document.getElementById('tabPending') || document.getElementById('pendingContainer');
    this.historyContainer = document.getElementById('tabHistory') || document.getElementById('historyContainer');

    this.floatingPnlVal = document.getElementById('floatingPnlVal');
    this.floatingPosCount = document.getElementById('floatingPosCount');

    this.buyPriceLabel = document.getElementById('buyPriceLabel');
    this.sellPriceLabel = document.getElementById('sellPriceLabel');

    this.bindEvents();
  }


  bindEvents() {
    if (this.orderTypeSelect) {
      this.orderTypeSelect.addEventListener('change', () => this.handleOrderTypeChange());
    }

    if (this.btnBuy) {
      this.btnBuy.addEventListener('click', () => this.executeAction('BUY'));
    }
    if (this.btnSell) {
      this.btnSell.addEventListener('click', () => this.executeAction('SELL'));
    }
    if (this.btnCloseAll) {
      this.btnCloseAll.addEventListener('click', () => this.closeAll());
    }

    // Auto calculate Lot Size from Risk USD
    if (this.inputRiskUsd) {
      this.inputRiskUsd.addEventListener('input', () => this.recalcLotFromRisk());
    }
    if (this.slInput) {
      this.slInput.addEventListener('input', () => this.recalcLotFromRisk());
    }
    if (this.inputPendingPrice) {
      this.inputPendingPrice.addEventListener('input', () => this.recalcLotFromRisk());
    }

    // R:R Quick TP Buttons
    const rrButtons = document.querySelectorAll('.btn-rr');
    rrButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const rr = parseFloat(e.target.getAttribute('data-rr')) || 2.0;
        this.calculateTPFromRR(rr);
      });
    });

    // Tab switcher (Positions vs Pending vs History)
    const tabs = document.querySelectorAll('.sidebar-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', (e) => {
        tabs.forEach(t => t.classList.remove('active'));
        e.target.classList.add('active');
        const target = e.target.getAttribute('data-tab');
        document.getElementById('tabPositions').style.display = target === 'positions' ? 'flex' : 'none';
        document.getElementById('tabPending').style.display = target === 'pending' ? 'flex' : 'none';
        document.getElementById('tabHistory').style.display = target === 'history' ? 'flex' : 'none';
      });
    });
  }

  getDigits() {
    if (this.app.state && this.app.state.symbol_info && this.app.state.symbol_info.digits !== undefined) {
      return this.app.state.symbol_info.digits;
    }
    const sym = (this.app.state && this.app.state.symbol) || '';
    if (sym.includes('JPY')) return 3;
    if (sym.includes('XAU') || sym.includes('GOLD') || sym.includes('XAG') || sym.includes('SILVER') || sym.includes('INDEX') || sym.includes('30') || sym.includes('100')) return 2;
    if (sym.length === 6 && (sym.endsWith('USD') || sym.startsWith('USD') || sym.endsWith('GBP') || sym.startsWith('EUR'))) return 5;
    return 2;
  }

  handleOrderTypeChange() {
    const val = this.orderTypeSelect.value;
    const isPending = val !== 'MARKET';
    const d = this.getDigits();
    const stepVal = (10 ** -d).toFixed(d);

    if (this.pendingPriceRow) {
      this.pendingPriceRow.style.display = isPending ? 'flex' : 'none';
    }
    if (this.inputPendingPrice) {
      this.inputPendingPrice.step = stepVal;
    }
    if (this.slInput) this.slInput.step = stepVal;
    if (this.tpInput) this.tpInput.step = stepVal;

    if (isPending && !this.inputPendingPrice.value && this.app.state) {
      this.inputPendingPrice.value = this.app.state.current_price.toFixed(d);
    }

    // Update Action Button Labels
    if (val === 'MARKET') {
      this.btnBuy.innerHTML = `<span>BUY MARKET</span><span class="btn-sub-price" id="buyPriceLabel">${this.app.state ? this.app.state.current_price.toFixed(d) : '--'}</span>`;
      this.btnSell.innerHTML = `<span>SELL MARKET</span><span class="btn-sub-price" id="sellPriceLabel">${this.app.state ? this.app.state.current_price.toFixed(d) : '--'}</span>`;
      this.btnBuy.style.display = 'flex';
      this.btnSell.style.display = 'flex';
    } else if (val === 'BUY_LIMIT' || val === 'BUY_STOP') {
      this.btnBuy.innerHTML = `<span>ĐẶT ${val.replace('_', ' ')}</span>`;
      this.btnBuy.style.display = 'flex';
      this.btnSell.style.display = 'none';
    } else if (val === 'SELL_LIMIT' || val === 'SELL_STOP') {
      this.btnSell.innerHTML = `<span>ĐẶT ${val.replace('_', ' ')}</span>`;
      this.btnSell.style.display = 'flex';
      this.btnBuy.style.display = 'none';
    }
  }

  async recalcLotFromRisk() {
    const riskUsd = parseFloat(this.inputRiskUsd.value);
    const sl = parseFloat(this.slInput.value);
    if (!riskUsd || riskUsd <= 0 || !sl || sl <= 0 || !this.app.state) return;

    const orderType = this.orderTypeSelect ? this.orderTypeSelect.value : 'MARKET';
    const entry = (orderType !== 'MARKET' && parseFloat(this.inputPendingPrice.value)) 
      ? parseFloat(this.inputPendingPrice.value) 
      : this.app.state.current_price;

    try {
      const resp = await fetch('/api/calc_lots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ risk_usd: riskUsd, entry_price: entry, sl_price: sl })
      });
      const res = await resp.json();
      if (res.success && res.lots) {
        this.lotsInput.value = res.lots;
      }
    } catch (e) {
      console.error('Error calculating lots:', e);
    }
  }

  calculateTPFromRR(rrRatio) {
    const sl = parseFloat(this.slInput.value);
    if (!sl || !this.app.state) {
      alert('Vui lòng điền giá Stop Loss (SL) trước để tự tính TP theo R:R.');
      return;
    }

    const orderType = this.orderTypeSelect ? this.orderTypeSelect.value : 'MARKET';
    const entry = (orderType !== 'MARKET' && parseFloat(this.inputPendingPrice.value)) 
      ? parseFloat(this.inputPendingPrice.value) 
      : this.app.state.current_price;

    const isBuy = orderType.includes('BUY') || (orderType === 'MARKET' && entry >= sl);
    const slDistance = Math.abs(entry - sl);
    const d = this.getDigits();

    if (isBuy) {
      this.tpInput.value = (entry + (slDistance * rrRatio)).toFixed(d);
    } else {
      this.tpInput.value = (entry - (slDistance * rrRatio)).toFixed(d);
    }
  }

  async executeAction(side) {
    const orderTypeSelected = this.orderTypeSelect ? this.orderTypeSelect.value : 'MARKET';
    let finalType = side;
    if (orderTypeSelected !== 'MARKET') {
      finalType = orderTypeSelected;
    }

    const lots = parseFloat(this.lotsInput.value) || 0.1;
    const sl = parseFloat(this.slInput.value) || null;
    const tp = parseFloat(this.tpInput.value) || null;
    const pendingPrice = (orderTypeSelected !== 'MARKET') ? (parseFloat(this.inputPendingPrice.value) || null) : null;
    const numPositions = parseInt(this.inputNumPositions ? this.inputNumPositions.value : '1') || 1;

    // Generate RR list for batch positions (e.g. 1:1, 1:2, 1:3...)
    const rrList = [];
    for (let i = 1; i <= numPositions; i++) {
      rrList.push(i * 1.0);
    }

    try {
      const resp = await fetch('/api/order/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: finalType,
          lots: lots,
          sl: sl,
          tp: tp,
          pending_price: pendingPrice,
          num_positions: numPositions,
          rr_list: rrList
        })
      });
      const res = await resp.json();
      if (res.success) {
        await this.app.refreshState();
      }
    } catch (e) {
      console.error('Error executing order:', e);
    }
  }

  async cancelPending(orderId) {
    try {
      const resp = await fetch('/api/order/cancel_pending', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: orderId })
      });
      const res = await resp.json();
      if (res.success) {
        await this.app.refreshState();
      }
    } catch (e) {
      console.error('Error canceling pending order:', e);
    }
  }

  async closeOrder(posId) {
    try {
      const resp = await fetch('/api/order/close', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: posId })
      });
      const res = await resp.json();
      if (res.success) {
        await this.app.refreshState();
      }
    } catch (e) {
      console.error('Error closing order:', e);
    }
  }

  async closeAll() {
    try {
      const resp = await fetch('/api/order/close_all', { method: 'POST' });
      const res = await resp.json();
      if (res.success) {
        await this.app.refreshState();
      }
    } catch (e) {
      console.error('Error closing all orders:', e);
    }
  }

  updateUI(state) {
    if (!state) return;
    const price = state.current_price;
    const orderType = this.orderTypeSelect ? this.orderTypeSelect.value : 'MARKET';
    const d = this.getDigits();
    const stepVal = (10 ** -d).toFixed(d);

    if (this.inputPendingPrice) this.inputPendingPrice.step = stepVal;
    if (this.slInput) this.slInput.step = stepVal;
    if (this.tpInput) this.tpInput.step = stepVal;

    if (orderType === 'MARKET') {
      if (this.buyPriceLabel) this.buyPriceLabel.innerText = price.toFixed(d);
      if (this.sellPriceLabel) this.sellPriceLabel.innerText = price.toFixed(d);
    }

    // 1. Render Open Positions & Compute Floating PnL
    const positions = state.account.open_positions || [];
    let totalFloatingPnl = 0;
    let totalFloatingLots = 0;
    let totalFloatingPips = 0;

    positions.forEach(pos => {
      totalFloatingPnl += pos.pnl || 0;
      totalFloatingLots += pos.lots || 0;
      totalFloatingPips += pos.pnl_pips || 0;
    });

    // Update Floating PnL Badge in bottom-right corner of execution chart
    if (this.floatingPnlVal) {
      const sign = totalFloatingPnl >= 0 ? '+' : '';
      this.floatingPnlVal.innerText = `${sign}$${totalFloatingPnl.toFixed(2)} (${sign}${totalFloatingPips.toFixed(1)}p)`;
      this.floatingPnlVal.style.color = positions.length === 0 ? 'var(--text-muted)' : (totalFloatingPnl >= 0 ? '#10b981' : '#ef4444');
    }
    if (this.floatingPosCount) {
      this.floatingPosCount.innerText = `${positions.length} Lệnh (${totalFloatingLots.toFixed(2)}L)`;
    }

    if (this.positionsContainer) {
      const badgeTab = document.getElementById('countPositions');
      if (badgeTab) badgeTab.innerText = positions.length ? `(${positions.length})` : '';

      if (positions.length === 0) {
        this.positionsContainer.innerHTML = `<div style="text-align:center;color:var(--text-dim);font-size:12px;padding:24px;">Chưa có lệnh mở nào</div>`;
      } else {
        this.positionsContainer.innerHTML = '';
        positions.forEach(pos => {
          const card = document.createElement('div');
          const isBuy = pos.type === 'BUY';
          const pnlClass = pos.pnl >= 0 ? 'bull' : 'bear';
          const pnlSign = pos.pnl >= 0 ? '+' : '';

          card.className = `position-card ${isBuy ? 'buy' : 'sell'}`;
          card.innerHTML = `
            <div class="pos-header">
              <span style="font-weight:700;color:${isBuy ? 'var(--color-bull)' : 'var(--color-bear)'};">${pos.type} ${pos.lots} Lots</span>
              <span class="pos-pnl metric-value ${pnlClass}">${pnlSign}$${pos.pnl.toFixed(2)} (${pnlSign}${pos.pnl_pips}p)</span>
            </div>
            <div class="pos-details">
              <span>Entry: <b>${Number(pos.open_price).toFixed(d)}</b></span>
              <span>SL: ${pos.sl ? Number(pos.sl).toFixed(d) : '--'} | TP: ${pos.tp ? Number(pos.tp).toFixed(d) : '--'}</span>
            </div>
            <div class="pos-actions">
              <button class="btn-pos-action close-red" onclick="window.app.tradePanel.closeOrder('${pos.id}')">Đóng lệnh (Close)</button>
            </div>
          `;
          this.positionsContainer.appendChild(card);
        });
      }
    }

    // 2. Render Pending Orders
    if (this.pendingContainer) {
      const pending = state.account.pending_orders || [];
      const badgePending = document.getElementById('countPending');
      if (badgePending) badgePending.innerText = pending.length ? `(${pending.length})` : '';

      if (pending.length === 0) {
        this.pendingContainer.innerHTML = `<div style="text-align:center;color:var(--text-dim);font-size:12px;padding:24px;">Không có lệnh chờ</div>`;
      } else {
        this.pendingContainer.innerHTML = '';
        pending.forEach(p => {
          const card = document.createElement('div');
          const isBuy = p.type.includes('BUY');
          card.className = `position-card ${isBuy ? 'buy' : 'sell'}`;
          card.innerHTML = `
            <div class="pos-header">
              <span style="color:var(--color-warning);font-weight:700;">⏳ ${p.type} ${p.lots} Lots</span>
              <span class="metric-value">@ ${Number(p.target_price).toFixed(d)}</span>
            </div>
            <div class="pos-details">
              <span>SL: ${p.sl ? Number(p.sl).toFixed(d) : '--'} | TP: ${p.tp ? Number(p.tp).toFixed(d) : '--'}</span>
            </div>
            <div class="pos-actions">
              <button class="btn-pos-action close-red" onclick="window.app.tradePanel.cancelPending('${p.id}')">Hủy lệnh chờ</button>
            </div>
          `;
          this.pendingContainer.appendChild(card);
        });
      }
    }

    // 3. Render Closed History with Statistics & Details
    if (this.historyContainer) {
      const closed = state.account.closed_positions || [];
      if (closed.length === 0) {
        this.historyContainer.innerHTML = `<div style="text-align:center;color:var(--text-dim);font-size:12px;padding:24px;">Chưa có lịch sử giao dịch</div>`;
      } else {
        const totalProfit = closed.reduce((acc, c) => acc + (c.pnl || 0), 0);
        const winCount = closed.filter(c => c.pnl > 0).length;
        const winRate = ((winCount / closed.length) * 100).toFixed(1);
        const sign = totalProfit >= 0 ? '+' : '';

        let html = `
          <div style="background:var(--bg-secondary);border:1px solid var(--border-color);border-radius:var(--radius-md);padding:8px 12px;margin-bottom:8px;font-size:11px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
              <span style="color:var(--text-muted);">Tổng số lệnh đã đóng:</span>
              <b>${closed.length}</b>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
              <span style="color:var(--text-muted);">Thắng / Thua:</span>
              <b style="color:#10b981;">${winCount}W</b> / <b style="color:#ef4444;">${closed.length - winCount}L</b> (${winRate}%)
            </div>
            <div style="display:flex;justify-content:space-between;">
              <span style="color:var(--text-muted);">Lợi nhuận tích lũy:</span>
              <b style="color:${totalProfit >= 0 ? '#10b981' : '#ef4444'};font-size:12px;">${sign}$${totalProfit.toFixed(2)}</b>
            </div>
          </div>
        `;

        closed.slice().reverse().forEach(c => {
          const isBuy = c.type === 'BUY';
          const isWin = c.pnl >= 0;
          const pnlClass = isWin ? 'bull' : 'bear';
          const pnlSign = isWin ? '+' : '';
          const reasonColor = c.exit_reason?.includes('TP') ? '#10b981' : (c.exit_reason?.includes('SL') ? '#ef4444' : 'var(--text-muted)');

          html += `
            <div class="position-card ${isBuy ? 'buy' : 'sell'}" style="margin-bottom:6px;">
              <div class="pos-header">
                <span style="font-weight:700;color:${isBuy ? 'var(--color-bull)' : 'var(--color-bear)'};">${c.type} ${c.lots}L</span>
                <span class="metric-value ${pnlClass}" style="font-size:13px;font-weight:700;">${pnlSign}$${c.pnl.toFixed(2)} (${pnlSign}${c.pnl_pips}p)</span>
              </div>
              <div class="pos-details" style="margin-top:4px;font-size:11px;">
                <span>Giá: <b>${c.open_price}</b> ➔ <b>${c.close_price}</b></span>
                <span style="color:${reasonColor};font-weight:700;">[${c.exit_reason || 'Đóng'}]</span>
              </div>
            </div>
          `;
        });
        this.historyContainer.innerHTML = html;
      }
    }

    // 4. Update Header Metrics
    const stats = state.stats;
    const elBalance = document.getElementById('metricBalance');
    const elEquity = document.getElementById('metricEquity');
    const elPnL = document.getElementById('metricPnL');
    const elWinRate = document.getElementById('metricWinRate');
    const elTrades = document.getElementById('metricTrades');

    if (elBalance) elBalance.innerText = `$${state.account.balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    if (elEquity) elEquity.innerText = `$${state.account.equity.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    if (elPnL) {
      const pnl = state.account.equity - state.account.initial_balance;
      const sign = pnl >= 0 ? '+' : '';
      elPnL.className = `metric-value ${pnl >= 0 ? 'bull' : 'bear'}`;
      elPnL.innerText = `${sign}$${pnl.toFixed(2)} (${sign}${stats.net_profit_pct}%)`;
    }
    if (elWinRate) elWinRate.innerText = `${stats.win_rate}% (${stats.won_trades}/${stats.total_trades})`;
    if (elTrades) elTrades.innerText = `${stats.total_trades}`;
  }
}

window.TradePanel = TradePanel;

