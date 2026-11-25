/**
 * MultiChartManager:
 * - Dual Timeframe (H4 & M15) with Zero Gap Responsive Fill
 * - Draggable Vertical Height Resizers (Splitters) for Chart & Sub-windows
 * - 3 EMAs (21, 50, 200) with disabled horizontal projection lines (priceLineVisible: false)
 * - Sub-windows for RSI (14) & Stochastic (5,3,3) on BOTH H4 & M15
 * - Divergence Visualizer & Copilot Setup Overlay
 */

const chartTheme = {
  layout: {
    background: { type: 'solid', color: '#12151c' },
    textColor: '#94a3b8',
    fontSize: 11,
    fontFamily: "'JetBrains Mono', 'Inter', sans-serif"
  },
  grid: {
    vertLines: { color: 'rgba(43, 51, 71, 0.3)' },
    horzLines: { color: 'rgba(43, 51, 71, 0.3)' }
  },
  crosshair: {
    mode: LightweightCharts.CrosshairMode.Normal,
    vertLine: { color: '#3b82f6', width: 1, style: 2 },
    horzLine: { color: '#3b82f6', width: 1, style: 2 }
  },
  timeScale: {
    borderColor: '#2b3347',
    timeVisible: true,
    secondsVisible: false
  },
  rightPriceScale: {
    borderColor: '#2b3347',
    scaleMargins: { top: 0.08, bottom: 0.12 }
  }
};

const candleStyle = {
  upColor: '#089981',
  downColor: '#f23645',
  borderVisible: false,
  wickUpColor: '#089981',
  wickDownColor: '#f23645'
};

class MultiChartManager {
  constructor() {
    // Containers
    this.containerH4 = document.getElementById('chartH4') || document.getElementById('chartTF1');
    this.containerTF2 = document.getElementById('chartTF2');
    this.containerM15 = document.getElementById('chartM15') || document.getElementById('chartTF3');
    this.containerRSI_H4 = document.getElementById('subChartRSI_H4');
    this.containerStoch_H4 = document.getElementById('subChartStoch_H4');
    this.containerMACD_H4 = document.getElementById('subChartMACD_H4');
    this.containerRSI_TF2 = document.getElementById('subChartRSI_TF2');
    this.containerStoch_TF2 = document.getElementById('subChartStoch_TF2');
    this.containerMACD_TF2 = document.getElementById('subChartMACD_TF2');
    this.containerRSI = document.getElementById('subChartRSI');
    this.containerStoch = document.getElementById('subChartStoch');
    this.containerMACD = document.getElementById('subChartMACD');
    this.chartAreaContainer = document.getElementById('chartAreaContainer');
    this.layoutSelect = document.getElementById('layoutSelect');
    this.btnFitTF1 = document.getElementById('btnFitTF1');
    this.btnFitTF2 = document.getElementById('btnFitTF2');
    this.btnFitTF3 = document.getElementById('btnFitTF3');

    // Chart Instances
    this.chartH4 = null; // TF1
    this.chartTF2 = null; // TF2
    this.chartM15 = null; // TF3
    this.chartRSI_H4 = null;
    this.chartStoch_H4 = null;
    this.chartMACD_H4 = null;
    this.chartRSI_TF2 = null;
    this.chartStoch_TF2 = null;
    this.chartMACD_TF2 = null;
    this.chartRSI = null;
    this.chartStoch = null;
    this.chartMACD = null;

    // Series
    this.seriesH4 = null;
    this.seriesTF2 = null;
    this.seriesM15 = null;
    
    // RSI & MA lines for each TF
    this.seriesRSI_H4 = null;
    this.seriesRSI_MA9_H4 = null;
    this.seriesRSI_WMA45_H4 = null;
    this.seriesRSI_TF2 = null;
    this.seriesRSI_MA9_TF2 = null;
    this.seriesRSI_WMA45_TF2 = null;
    this.seriesRSI = null;
    this.seriesRSI_MA9 = null;
    this.seriesRSI_WMA45 = null;

    // Stochastic series for each TF (14, 3, 3)
    this.seriesStochK_H4 = null;
    this.seriesStochD_H4 = null;
    this.seriesStochK_TF2 = null;
    this.seriesStochD_TF2 = null;
    this.seriesStochK = null;
    this.seriesStochD = null;

    // MACD series for each TF (12, 26, 9)
    this.seriesMACD_Hist_H4 = null;
    this.seriesMACD_Line_H4 = null;
    this.seriesMACD_Sig_H4 = null;
    this.seriesMACD_Hist_TF2 = null;
    this.seriesMACD_Line_TF2 = null;
    this.seriesMACD_Sig_TF2 = null;
    this.seriesMACD_Hist = null;
    this.seriesMACD_Line = null;
    this.seriesMACD_Sig = null;

    this.indicatorSeries = {
      H4: {},
      TF1: {},
      TF2: {},
      M15: {},
      TF3: {}
    };

    this.orderLines = [];
    this.eaLines = [];
    this.currentPrice = 0;
    this.cursorPrice = 0;
    this.lastCandlesM15Count = 0;
    this.lastCandlesTF2Count = 0;
    this.lastCandlesH4Count = 0;
    this.tf1Name = "H4";
    this.tf2Name = "H1";
    this.tf3Name = "M15";
    this.isAutoCenter = false; // Center mode (50% center)
    this.isPinPrice = true;   // Pin mode (MT5 Shift Pin) - BẬT MẶC ĐỊNH
    this.shiftPins = { H4: null, TF2: null, M15: null };
    this.shiftOffsetBars = { H4: 5, TF2: 5, M15: 5 };
    this.isDraggingPin = false;
    this.isProgrammaticScroll = false;
    this.btnCenterChart = document.getElementById('btnCenterChart');
    this.btnPinPrice = document.getElementById('btnPinPrice');
    this.btnResetScale = document.getElementById('btnResetScale');
    this.btnToggleDynamicSlTp = document.getElementById('btnToggleDynamicSlTp');

    // Crosshair Sync and State Caches
    this.rawCandlesH4 = [];
    this.rawCandlesTF2 = [];
    this.rawCandlesM15 = [];
    this.isSyncingCrosshair = false;
    this.lastForecast = null;
    
    // DYNAMIC SL/TP: ALWAYS FALSE/OFF BY DEFAULT!
    const savedDynamicSlTp = localStorage.getItem('enableDynamicSlTp');
    this.showFutureProjection = (savedDynamicSlTp === 'true');

    this.initCharts();
    this.initMT5ShiftPins();
    this.setupTimeScaleSync();
    this.setupResetViewButtons();
    this.setupResizeObserver();
    this.setupDraggableResizers();
    this.setupContextMenu();
    this.setupPinAndCenterButtons();
    this.setupPinPriceButton();
    this.setupFitButtons();
    this.setupDoubleClicks();
    this.setupLayoutSelector();
    this.updateDynamicSlTpUI();
    this.initDashboardConfig();
    this.startCandleCountdownTimer();
  }





  initCharts() {
    // ==========================================
    // 1. TF1 / H4 (Khung Lớn Nhất / Macro Context)
    // ==========================================
    this.chartH4 = LightweightCharts.createChart(this.containerH4, {
      ...chartTheme,
      width: this.containerH4.clientWidth,
      height: this.containerH4.clientHeight || 280
    });
    this.seriesH4 = this.chartH4.addCandlestickSeries(candleStyle);

    // 1b. Macro HTF Future Probabilistic Projection Series
    this.seriesFutureCandlesH4 = this.chartH4.addCandlestickSeries({
      upColor: 'rgba(16, 185, 129, 0.42)',
      downColor: 'rgba(239, 68, 68, 0.42)',
      borderVisible: true,
      borderUpColor: '#10b981',
      borderDownColor: '#ef4444',
      wickUpColor: 'rgba(16, 185, 129, 0.80)',
      wickDownColor: 'rgba(239, 68, 68, 0.80)',
      priceLineVisible: false,
      lastValueVisible: false
    });
    this.seriesFutureUpBandH4 = this.chartH4.addLineSeries({
      color: 'rgba(16, 185, 129, 0.65)',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false
    });
    this.seriesFutureDnBandH4 = this.chartH4.addLineSeries({
      color: 'rgba(239, 68, 68, 0.65)',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false
    });
    this.seriesFutureMeanLineH4 = this.chartH4.addLineSeries({
      color: '#f59e0b',
      lineWidth: 2,
      lineStyle: LightweightCharts.LineStyle.Dotted,
      priceLineVisible: false,
      lastValueVisible: false
    });
    this.macroFutureLinesH4 = [];

    // Sub 1: H4 Stochastic Sub-window (14, 3, 3) - %K Green, %D Red
    if (this.containerStoch_H4) {
      this.chartStoch_H4 = LightweightCharts.createChart(this.containerStoch_H4, {
        ...chartTheme,
        width: this.containerStoch_H4.clientWidth,
        height: this.containerStoch_H4.clientHeight || 80,
        rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } }
      });
      this.seriesStochK_H4 = this.chartStoch_H4.addLineSeries({
        color: '#10b981',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false,
        autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } })
      });
      this.seriesStochD_H4 = this.chartStoch_H4.addLineSeries({
        color: '#ef4444',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false
      });
      this.seriesStochK_H4.createPriceLine({ price: 90, color: '#ef4444', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesStochK_H4.createPriceLine({ price: 70, color: '#64748b', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesStochK_H4.createPriceLine({ price: 30, color: '#64748b', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesStochK_H4.createPriceLine({ price: 10, color: '#ef4444', lineStyle: 2, title: '', axisLabelVisible: false });
    }

    // Sub 2: H4 RSI Sub-window (RSI 14 + SMA 9 + WMA 45)
    if (this.containerRSI_H4) {
      this.chartRSI_H4 = LightweightCharts.createChart(this.containerRSI_H4, {
        ...chartTheme,
        width: this.containerRSI_H4.clientWidth,
        height: this.containerRSI_H4.clientHeight || 80,
        rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } }
      });
      this.seriesRSI_H4 = this.chartRSI_H4.addLineSeries({
        color: '#7e57c2',
        lineWidth: 2,
        title: '',
        priceLineVisible: false,
        autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } })
      });
      this.seriesRSI_MA9_H4 = this.chartRSI_H4.addLineSeries({
        color: '#fdd835',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false
      });
      this.seriesRSI_WMA45_H4 = this.chartRSI_H4.addLineSeries({
        color: '#f23645',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false
      });
      this.seriesRSI_H4.createPriceLine({ price: 90, color: '#ef4444', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesRSI_H4.createPriceLine({ price: 70, color: '#64748b', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesRSI_H4.createPriceLine({ price: 30, color: '#64748b', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesRSI_H4.createPriceLine({ price: 10, color: '#ef4444', lineStyle: 2, title: '', axisLabelVisible: false });
    }

    // Sub 3: H4 MACD Sub-window (12, 26, 9)
    if (this.containerMACD_H4) {
      this.chartMACD_H4 = LightweightCharts.createChart(this.containerMACD_H4, {
        ...chartTheme,
        width: this.containerMACD_H4.clientWidth,
        height: this.containerMACD_H4.clientHeight || 75,
        rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } }
      });
      this.seriesMACD_Hist_H4 = this.chartMACD_H4.addHistogramSeries({
        priceLineVisible: false,
        lastValueVisible: true
      });
      this.seriesMACD_Line_H4 = this.chartMACD_H4.addLineSeries({
        color: '#2962ff',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false,
        lastValueVisible: true
      });
      this.seriesMACD_Sig_H4 = this.chartMACD_H4.addLineSeries({
        color: '#ff6d00',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false,
        lastValueVisible: true
      });
      this.chartMACD_H4.addLineSeries().createPriceLine({ price: 0, color: '#475569', lineStyle: 2, title: '', axisLabelVisible: false });
    }

    // ==========================================
    // 2. TF2 / H1 (Khung Cấu Trúc / Intermediate)
    // ==========================================
    if (this.containerTF2) {
      this.chartTF2 = LightweightCharts.createChart(this.containerTF2, {
        ...chartTheme,
        width: this.containerTF2.clientWidth,
        height: this.containerTF2.clientHeight || 280
      });
      this.seriesTF2 = this.chartTF2.addCandlestickSeries(candleStyle);
    }

    // Sub 1: TF2 Stochastic Sub-window (14, 3, 3)
    if (this.containerStoch_TF2) {
      this.chartStoch_TF2 = LightweightCharts.createChart(this.containerStoch_TF2, {
        ...chartTheme,
        width: this.containerTF2.clientWidth,
        height: this.containerStoch_TF2.clientHeight || 80,
        rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } }
      });
      this.seriesStochK_TF2 = this.chartStoch_TF2.addLineSeries({
        color: '#10b981',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false,
        autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } })
      });
      this.seriesStochD_TF2 = this.chartStoch_TF2.addLineSeries({
        color: '#ef4444',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false
      });
      this.seriesStochK_TF2.createPriceLine({ price: 90, color: '#ef4444', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesStochK_TF2.createPriceLine({ price: 70, color: '#64748b', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesStochK_TF2.createPriceLine({ price: 30, color: '#64748b', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesStochK_TF2.createPriceLine({ price: 10, color: '#ef4444', lineStyle: 2, title: '', axisLabelVisible: false });
    }

    // Sub 2: TF2 RSI Sub-window (RSI 14 + SMA 9 + WMA 45)
    if (this.containerRSI_TF2) {
      this.chartRSI_TF2 = LightweightCharts.createChart(this.containerRSI_TF2, {
        ...chartTheme,
        width: this.containerTF2.clientWidth,
        height: this.containerRSI_TF2.clientHeight || 80,
        rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } }
      });
      this.seriesRSI_TF2 = this.chartRSI_TF2.addLineSeries({
        color: '#7e57c2',
        lineWidth: 2,
        title: '',
        priceLineVisible: false,
        autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } })
      });
      this.seriesRSI_MA9_TF2 = this.chartRSI_TF2.addLineSeries({
        color: '#fdd835',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false
      });
      this.seriesRSI_WMA45_TF2 = this.chartRSI_TF2.addLineSeries({
        color: '#f23645',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false
      });
      this.seriesRSI_TF2.createPriceLine({ price: 90, color: '#ef4444', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesRSI_TF2.createPriceLine({ price: 70, color: '#64748b', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesRSI_TF2.createPriceLine({ price: 30, color: '#64748b', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesRSI_TF2.createPriceLine({ price: 10, color: '#ef4444', lineStyle: 2, title: '', axisLabelVisible: false });
    }

    // Sub 3: TF2 MACD Sub-window (12, 26, 9)
    if (this.containerMACD_TF2) {
      this.chartMACD_TF2 = LightweightCharts.createChart(this.containerMACD_TF2, {
        ...chartTheme,
        width: this.containerMACD_TF2.clientWidth,
        height: this.containerMACD_TF2.clientHeight || 75,
        rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } }
      });
      this.seriesMACD_Hist_TF2 = this.chartMACD_TF2.addHistogramSeries({
        priceLineVisible: false,
        lastValueVisible: true
      });
      this.seriesMACD_Line_TF2 = this.chartMACD_TF2.addLineSeries({
        color: '#2962ff',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false,
        lastValueVisible: true
      });
      this.seriesMACD_Sig_TF2 = this.chartMACD_TF2.addLineSeries({
        color: '#ff6d00',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false,
        lastValueVisible: true
      });
      this.chartMACD_TF2.addLineSeries().createPriceLine({ price: 0, color: '#475569', lineStyle: 2, title: '', axisLabelVisible: false });
    }

    // ==========================================
    // 3. TF3 / M15 (Khung Thực Thi / Execution)
    // ==========================================
    this.chartM15 = LightweightCharts.createChart(this.containerM15, {
      ...chartTheme,
      width: this.containerM15.clientWidth,
      height: this.containerM15.clientHeight || 280
    });
    this.seriesM15 = this.chartM15.addCandlestickSeries(candleStyle);

    // 4b. Future Probabilistic Projection Candlestick & Probability Fan Series
    this.seriesFutureCandles = this.chartM15.addCandlestickSeries({
      upColor: 'rgba(16, 185, 129, 0.38)',
      downColor: 'rgba(239, 68, 68, 0.38)',
      borderVisible: true,
      borderUpColor: '#10b981',
      borderDownColor: '#ef4444',
      wickUpColor: 'rgba(16, 185, 129, 0.75)',
      wickDownColor: 'rgba(239, 68, 68, 0.75)',
      priceLineVisible: false,
      lastValueVisible: false
    });
    this.seriesFutureUpBand = this.chartM15.addLineSeries({
      color: 'rgba(16, 185, 129, 0.65)',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false
    });
    this.seriesFutureDnBand = this.chartM15.addLineSeries({
      color: 'rgba(239, 68, 68, 0.65)',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false
    });
    this.seriesFutureMeanLine = this.chartM15.addLineSeries({
      color: '#a855f7',
      lineWidth: 2,
      lineStyle: LightweightCharts.LineStyle.Dotted,
      priceLineVisible: false,
      lastValueVisible: false
    });
    this.futureProjectionLines = [];

    // Sub 1: M15 Stochastic Sub-window (14, 3, 3)
    if (this.containerStoch) {
      this.chartStoch = LightweightCharts.createChart(this.containerStoch, {
        ...chartTheme,
        width: this.containerStoch.clientWidth,
        height: this.containerStoch.clientHeight || 80,
        rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } }
      });
      this.seriesStochK = this.chartStoch.addLineSeries({
        color: '#10b981',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false,
        autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } })
      });
      this.seriesStochD = this.chartStoch.addLineSeries({
        color: '#ef4444',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false
      });
      this.seriesStochK.createPriceLine({ price: 90, color: '#ef4444', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesStochK.createPriceLine({ price: 70, color: '#64748b', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesStochK.createPriceLine({ price: 30, color: '#64748b', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesStochK.createPriceLine({ price: 10, color: '#ef4444', lineStyle: 2, title: '', axisLabelVisible: false });
    }

    // Sub 2: M15 RSI Sub-window (RSI 14 + SMA 9 + WMA 45)
    if (this.containerRSI) {
      this.chartRSI = LightweightCharts.createChart(this.containerRSI, {
        ...chartTheme,
        width: this.containerRSI.clientWidth,
        height: this.containerRSI.clientHeight || 80,
        rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } }
      });
      this.seriesRSI = this.chartRSI.addLineSeries({
        color: '#7e57c2',
        lineWidth: 2,
        title: '',
        priceLineVisible: false,
        autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } })
      });
      this.seriesRSI_MA9 = this.chartRSI.addLineSeries({
        color: '#fdd835',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false
      });
      this.seriesRSI_WMA45 = this.chartRSI.addLineSeries({
        color: '#f23645',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false
      });
      this.seriesRSI.createPriceLine({ price: 90, color: '#ef4444', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesRSI.createPriceLine({ price: 70, color: '#64748b', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesRSI.createPriceLine({ price: 30, color: '#64748b', lineStyle: 2, title: '', axisLabelVisible: false });
      this.seriesRSI.createPriceLine({ price: 10, color: '#ef4444', lineStyle: 2, title: '', axisLabelVisible: false });
    }

    // Sub 3: M15 MACD Sub-window (12, 26, 9)
    if (this.containerMACD) {
      this.chartMACD = LightweightCharts.createChart(this.containerMACD, {
        ...chartTheme,
        width: this.containerMACD.clientWidth,
        height: this.containerMACD.clientHeight || 75,
        rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } }
      });
      this.seriesMACD_Hist = this.chartMACD.addHistogramSeries({
        priceLineVisible: false,
        lastValueVisible: true
      });
      this.seriesMACD_Line = this.chartMACD.addLineSeries({
        color: '#2962ff',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false,
        lastValueVisible: true
      });
      this.seriesMACD_Sig = this.chartMACD.addLineSeries({
        color: '#ff6d00',
        lineWidth: 1.5,
        title: '',
        priceLineVisible: false,
        lastValueVisible: true
      });
      this.chartMACD.addLineSeries().createPriceLine({ price: 0, color: '#475569', lineStyle: 2, title: '', axisLabelVisible: false });
    }

    this.setupCrosshairSync();
    
    // Auto trigger initial resize after DOM layout
    setTimeout(() => this.resizeAll(), 100);
  }

  findNearestCandle(candles, time) {
    if (!candles || candles.length === 0) return null;
    let low = 0;
    let high = candles.length - 1;
    let best = candles[0];
    while (low <= high) {
      const mid = (low + high) >> 1;
      const t = candles[mid].time;
      if (t === time) {
        return candles[mid];
      } else if (t < time) {
        best = candles[mid];
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }
    return best;
  }

  setupCrosshairSync() {
    this.activeHoverChart = null;
    if (this.containerM15) {
      this.containerM15.addEventListener('mouseenter', () => { this.activeHoverChart = 'M15'; });
      this.containerM15.addEventListener('mousemove', () => { this.activeHoverChart = 'M15'; });
    }
    if (this.containerTF2) {
      this.containerTF2.addEventListener('mouseenter', () => { this.activeHoverChart = 'TF2'; });
      this.containerTF2.addEventListener('mousemove', () => { this.activeHoverChart = 'TF2'; });
    }
    if (this.containerH4) {
      this.containerH4.addEventListener('mouseenter', () => { this.activeHoverChart = 'H4'; });
      this.containerH4.addEventListener('mousemove', () => { this.activeHoverChart = 'H4'; });
    }

    // 1. Hover on Execution Chart (M15 / TF3) -> Sync to Structure (TF2) and HTF (TF1)
    if (this.chartM15) {
      this.chartM15.subscribeCrosshairMove((param) => {
        if (this.isSyncingCrosshair || this.activeHoverChart !== 'M15') return;
        this.isSyncingCrosshair = true;
        try {
          if (param.point && this.seriesM15) {
            try {
              const p = this.seriesM15.coordinateToPrice(param.point.y);
              if (p !== null && !isNaN(p)) {
                this.hoveredPriceM15 = p;
              }
            } catch (e) {}
          }

          if (!param.point || !param.time) {
            if (this.chartTF2) this.chartTF2.clearCrosshairPosition();
            if (this.chartH4) this.chartH4.clearCrosshairPosition();
            return;
          }

          const sData = param.seriesData ? param.seriesData.get(this.seriesM15) : null;
          if (sData) {
            this.updateOHLCDisplay('M15', sData);
          }

          const targetPrice = (this.hoveredPriceM15 !== null && !isNaN(this.hoveredPriceM15))
            ? this.hoveredPriceM15
            : (sData ? sData.close : null);

          // Sync crosshair to TF2
          if (this.chartTF2 && this.seriesTF2 && this.rawCandlesTF2 && this.rawCandlesTF2.length > 0) {
            const cTF2 = this.findNearestCandle(this.rawCandlesTF2, param.time);
            if (cTF2) {
              const p2 = targetPrice !== null ? targetPrice : cTF2.close;
              this.chartTF2.setCrosshairPosition(p2, cTF2.time, this.seriesTF2);
              this.updateOHLCDisplay('TF2', cTF2);
            }
          }

          // Sync crosshair to H4 (TF1)
          if (this.chartH4 && this.seriesH4 && this.rawCandlesH4 && this.rawCandlesH4.length > 0) {
            const cH4 = this.findNearestCandle(this.rawCandlesH4, param.time);
            if (cH4) {
              const p1 = targetPrice !== null ? targetPrice : cH4.close;
              this.chartH4.setCrosshairPosition(p1, cH4.time, this.seriesH4);
              this.updateOHLCDisplay('H4', cH4);
            }
          }
        } catch (e) {
          // ignore
        } finally {
          this.isSyncingCrosshair = false;
        }
      });
    }

    // 2. Hover on Structure Chart (TF2 / H1) -> Sync to TF3 and TF1
    if (this.chartTF2) {
      this.chartTF2.subscribeCrosshairMove((param) => {
        if (this.isSyncingCrosshair || this.activeHoverChart !== 'TF2') return;
        this.isSyncingCrosshair = true;
        try {
          if (param.point && this.seriesTF2) {
            try {
              const p = this.seriesTF2.coordinateToPrice(param.point.y);
              if (p !== null && !isNaN(p)) {
                this.hoveredPriceTF2 = p;
              }
            } catch (e) {}
          }

          if (!param.point || !param.time) {
            if (this.chartM15) this.chartM15.clearCrosshairPosition();
            if (this.chartH4) this.chartH4.clearCrosshairPosition();
            return;
          }

          const sData = param.seriesData ? param.seriesData.get(this.seriesTF2) : null;
          if (sData) {
            this.updateOHLCDisplay('TF2', sData);
          }

          const targetPrice = (this.hoveredPriceTF2 !== null && !isNaN(this.hoveredPriceTF2))
            ? this.hoveredPriceTF2
            : (sData ? sData.close : null);

          // Sync crosshair to M15 (TF3)
          if (this.chartM15 && this.seriesM15 && this.rawCandlesM15 && this.rawCandlesM15.length > 0) {
            const cM15 = this.findNearestCandle(this.rawCandlesM15, param.time);
            if (cM15) {
              const p3 = targetPrice !== null ? targetPrice : cM15.close;
              this.chartM15.setCrosshairPosition(p3, cM15.time, this.seriesM15);
              this.updateOHLCDisplay('M15', cM15);
            }
          }

          // Sync crosshair to H4 (TF1)
          if (this.chartH4 && this.seriesH4 && this.rawCandlesH4 && this.rawCandlesH4.length > 0) {
            const cH4 = this.findNearestCandle(this.rawCandlesH4, param.time);
            if (cH4) {
              const p1 = targetPrice !== null ? targetPrice : cH4.close;
              this.chartH4.setCrosshairPosition(p1, cH4.time, this.seriesH4);
              this.updateOHLCDisplay('H4', cH4);
            }
          }
        } catch (e) {
          // ignore
        } finally {
          this.isSyncingCrosshair = false;
        }
      });
    }

    // 3. Hover on Macro HTF Chart (H4 / TF1) -> Sync to TF2 and TF3
    if (this.chartH4) {
      this.chartH4.subscribeCrosshairMove((param) => {
        if (this.isSyncingCrosshair || this.activeHoverChart !== 'H4') return;
        this.isSyncingCrosshair = true;
        try {
          if (param.point && this.seriesH4) {
            try {
              const p = this.seriesH4.coordinateToPrice(param.point.y);
              if (p !== null && !isNaN(p)) {
                this.hoveredPriceH4 = p;
              }
            } catch (e) {}
          }

          if (!param.point || !param.time) {
            if (this.chartM15) this.chartM15.clearCrosshairPosition();
            if (this.chartTF2) this.chartTF2.clearCrosshairPosition();
            return;
          }

          const sData = param.seriesData ? param.seriesData.get(this.seriesH4) : null;
          if (sData) {
            this.updateOHLCDisplay('H4', sData);
          }

          const targetPrice = (this.hoveredPriceH4 !== null && !isNaN(this.hoveredPriceH4))
            ? this.hoveredPriceH4
            : (sData ? sData.close : null);

          // Sync crosshair to M15 (TF3)
          if (this.chartM15 && this.seriesM15 && this.rawCandlesM15 && this.rawCandlesM15.length > 0) {
            const cM15 = this.findNearestCandle(this.rawCandlesM15, param.time);
            if (cM15) {
              const p3 = targetPrice !== null ? targetPrice : cM15.close;
              this.chartM15.setCrosshairPosition(p3, cM15.time, this.seriesM15);
              this.updateOHLCDisplay('M15', cM15);
            }
          }

          // Sync crosshair to TF2
          if (this.chartTF2 && this.seriesTF2 && this.rawCandlesTF2 && this.rawCandlesTF2.length > 0) {
            const cTF2 = this.findNearestCandle(this.rawCandlesTF2, param.time);
            if (cTF2) {
              const p2 = targetPrice !== null ? targetPrice : cTF2.close;
              this.chartTF2.setCrosshairPosition(p2, cTF2.time, this.seriesTF2);
              this.updateOHLCDisplay('TF2', cTF2);
            }
          }
        } catch (e) {
          // ignore
        } finally {
          this.isSyncingCrosshair = false;
        }
      });
    }

    // 4. Mouse leave listeners to cleanly clear all crosshairs
    const clearAllCrosshairs = () => {
      this.activeHoverChart = null;
      if (this.isSyncingCrosshair) return;
      this.isSyncingCrosshair = true;
      try {
        if (this.chartM15) this.chartM15.clearCrosshairPosition();
        if (this.chartTF2) this.chartTF2.clearCrosshairPosition();
        if (this.chartH4) this.chartH4.clearCrosshairPosition();
      } catch (e) {}
      finally {
        this.isSyncingCrosshair = false;
      }
    };

    if (this.containerM15) this.containerM15.addEventListener('mouseleave', clearAllCrosshairs);
    if (this.containerTF2) this.containerTF2.addEventListener('mouseleave', clearAllCrosshairs);
    if (this.containerH4) this.containerH4.addEventListener('mouseleave', clearAllCrosshairs);
  }

  setupLayoutSelector() {
    if (this.layoutSelect && this.chartAreaContainer) {
      this.layoutSelect.addEventListener('change', (e) => {
        const val = e.target.value;
        this.chartAreaContainer.classList.remove('layout-1', 'layout-2', 'layout-3');
        if (val === '1_CHART') {
          this.chartAreaContainer.classList.add('layout-1');
        } else if (val === '2_CHARTS') {
          this.chartAreaContainer.classList.add('layout-2');
        } else {
          this.chartAreaContainer.classList.add('layout-3');
        }
        setTimeout(() => this.resizeAll(), 50);
      });
    }
  }

  applyLiveTick(bidPrice) {
    if (!bidPrice || isNaN(bidPrice) || bidPrice <= 0) return;
    this.currentPrice = bidPrice;

    const tickSeries = (series, arr, tfLabel) => {
      if (!series || !arr || arr.length === 0) return;
      const last = arr[arr.length - 1];
      if (!last) return;
      last.close = bidPrice;
      if (bidPrice > last.high) last.high = bidPrice;
      if (bidPrice < last.low) last.low = bidPrice;
      try {
        series.update(last);
        this.updateOHLCDisplay(tfLabel, last);
      } catch (e) {}
    };

    tickSeries(this.seriesH4, this.rawCandlesH4, 'H4');
    tickSeries(this.seriesTF2, this.rawCandlesTF2, 'TF2');
    tickSeries(this.seriesM15, this.rawCandlesM15, 'M15');
  }

  updateOHLCDisplay(tf, candle) {
    const targetEl = document.getElementById(`ohlc${tf}`);
    if (!targetEl || !candle) return;
    if (candle.time) {
      this.updateLegendValuesAtTime(tf, candle.time);
    }
    targetEl.innerHTML = `
      <span>O: <b>${candle.open}</b></span>
      <span>H: <b>${candle.high}</b></span>
      <span>L: <b>${candle.low}</b></span>
      <span>C: <b>${candle.close}</b></span>
    `;
  }

  centerCharts() {
    try {
      if (this.isPinPrice) {
        this.applyPinPriceScroll();
      } else {
        this.applyCenterFollowScroll();
      }
    } catch (e) {
      console.error('Error centering charts:', e);
    }
  }

  getVisibleBarsCount(chart, container) {
    try {
      const range = chart.timeScale().getVisibleLogicalRange();
      if (range && range.to !== undefined && range.from !== undefined) {
        const diff = range.to - range.from;
        if (diff > 10 && diff < 600) return Math.round(diff);
      }
    } catch (e) {}
    const w = container ? (container.clientWidth || 600) : 600;
    return Math.max(20, Math.round(w / 10));
  }

  getBarsCount(key) {
    if (key === 'H4') return this.lastCandlesH4Count || 0;
    if (key === 'TF2') return this.lastCandlesTF2Count || 0;
    if (key === 'M15') return this.lastCandlesM15Count || 0;
    return 0;
  }

  /* =========================================================================
     MT5 CHART SHIFT PIN SYSTEM & TIME-SCALE SYNCHRONIZATION
     ========================================================================= */
  initMT5ShiftPins() {
    const panes = [
      { key: 'H4', container: this.containerH4, chart: this.chartH4, subRsi: this.chartRSI_H4, subStoch: this.chartStoch_H4, subMacd: this.chartMACD_H4 },
      { key: 'TF2', container: this.containerTF2, chart: this.chartTF2, subRsi: this.chartRSI_TF2, subStoch: this.chartStoch_TF2, subMacd: this.chartMACD_TF2 },
      { key: 'M15', container: this.containerM15, chart: this.chartM15, subRsi: this.chartRSI, subStoch: this.chartStoch, subMacd: this.chartMACD }
    ];

    panes.forEach(({ key, container, chart, subRsi, subStoch, subMacd }) => {
      if (!container) return;

      let pin = container.querySelector('.mt5-chart-shift-pin');
      if (!pin) {
        pin = document.createElement('div');
        pin.className = 'mt5-chart-shift-pin';
        pin.id = `shiftPin_${key}`;
        pin.title = 'Thanh Ghim MT5: Kéo để dời lề nến (Chart Shift)';
        pin.innerHTML = `
          <div class="shift-pin-head">
            <span class="shift-pin-arrow">▼</span>
            <span class="shift-pin-tag">GHIM</span>
          </div>
          <div class="shift-pin-line"></div>
        `;
        container.appendChild(pin);
      }
      this.shiftPins[key] = pin;

      const head = pin.querySelector('.shift-pin-head');
      if (!head) return;

      let isDragging = false;

      const onMouseDown = (e) => {
        e.preventDefault();
        e.stopPropagation();
        isDragging = true;
        this.isDraggingPin = true;
        head.classList.add('dragging');
        document.body.style.cursor = 'ew-resize';

        const onMouseMove = (moveEvent) => {
          if (!isDragging) return;
          const rect = container.getBoundingClientRect();
          const canvasW = container.clientWidth;
          let mouseX = moveEvent.clientX - rect.left;
          mouseX = Math.max(30, Math.min(canvasW - 65, mouseX));

          pin.style.display = 'block';
          pin.style.left = `${mouseX}px`;

          const range = chart.timeScale().getVisibleLogicalRange();
          const lastCount = this.getBarsCount(key);
          if (range && range.to > range.from && lastCount > 0) {
            const span = range.to - range.from;
            const rightMarginRatio = Math.max(0.02, (canvasW - mouseX) / canvasW);
            const rightOffsetBars = Math.max(1, Math.round(span * rightMarginRatio));
            this.shiftOffsetBars[key] = rightOffsetBars;
            this.isPinPrice = true;
            this.isAutoCenter = false;

            const lastIdx = lastCount - 1;
            const to = lastIdx + rightOffsetBars;
            const from = to - span;

            this.isProgrammaticScroll = true;
            chart.timeScale().setVisibleLogicalRange({ from, to });
            if (subRsi) {
              try { subRsi.timeScale().setVisibleLogicalRange({ from, to }); } catch (err) {}
            }
            if (subStoch) {
              try { subStoch.timeScale().setVisibleLogicalRange({ from, to }); } catch (err) {}
            }
            if (subMacd) {
              try { subMacd.timeScale().setVisibleLogicalRange({ from, to }); } catch (err) {}
            }
            this.isProgrammaticScroll = false;
          }
        };

        const onMouseUp = () => {
          isDragging = false;
          this.isDraggingPin = false;
          head.classList.remove('dragging');
          document.body.style.cursor = '';
          window.removeEventListener('mousemove', onMouseMove);
          window.removeEventListener('mouseup', onMouseUp);
          this.updateShiftPinPosition(key);
        };

        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
      };

      head.addEventListener('mousedown', onMouseDown);
      head.addEventListener('touchstart', (e) => {
        if (e.touches.length === 1) {
          const fakeEvent = {
            clientX: e.touches[0].clientX,
            preventDefault: () => e.preventDefault(),
            stopPropagation: () => e.stopPropagation()
          };
          onMouseDown(fakeEvent);
        }
      }, { passive: false });
    });
  }

  setupTimeScaleSync() {
    const syncTargets = [
      { key: 'H4', chart: this.chartH4, subRsi: this.chartRSI_H4, subStoch: this.chartStoch_H4, subMacd: this.chartMACD_H4, btnId: 'btnResetView_H4' },
      { key: 'TF2', chart: this.chartTF2, subRsi: this.chartRSI_TF2, subStoch: this.chartStoch_TF2, subMacd: this.chartMACD_TF2, btnId: 'btnResetView_TF2' },
      { key: 'M15', chart: this.chartM15, subRsi: this.chartRSI, subStoch: this.chartStoch, subMacd: this.chartMACD, btnId: 'btnResetView_M15' }
    ];

    syncTargets.forEach(({ key, chart, subRsi, subStoch, subMacd, btnId }) => {
      if (!chart) return;
      chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (!range) return;

        // 1. Synchronize Sub-charts (Stoch, RSI & MACD) in lockstep
        if (subStoch) {
          try { subStoch.timeScale().setVisibleLogicalRange(range); } catch (e) {}
        }
        if (subRsi) {
          try { subRsi.timeScale().setVisibleLogicalRange(range); } catch (e) {}
        }
        if (subMacd) {
          try { subMacd.timeScale().setVisibleLogicalRange(range); } catch (e) {}
        }

        const lastCount = this.getBarsCount(key);
        const resetBtn = document.getElementById(btnId);

        // 2. Toggle "Reset chart view" button (TradingView style):
        // Shows when user scrolled back into past or zoomed away from the right offset
        if (resetBtn && lastCount > 0 && range.to !== undefined) {
          const lastIdx = lastCount - 1;
          const offset = range.to - lastIdx;
          // If latest candle is scrolled away to the right (> 2 bars off) or scrolled into deep history
          if (offset < 2 || offset > 25) {
            resetBtn.classList.add('visible');
          } else {
            resetBtn.classList.remove('visible');
          }
        }

        // 3. Detect manual user panning/dragging to update shift offset ONLY when user is actually interacting (NOT during setData/replay!)
        const isReplaying = window.app && window.app.replayController && window.app.replayController.isPlaying;
        if (!this.isProgrammaticScroll && !this.isDraggingPin && !isReplaying) {
          if (lastCount > 0 && range.to !== undefined) {
            const lastIdx = lastCount - 1;
            const offset = range.to - lastIdx;
            if (offset >= 0) {
              const span = Math.max(20, range.to - range.from);
              const maxAllowed = Math.max(15, Math.round(span * 0.45));
              this.shiftOffsetBars[key] = Math.max(1, Math.min(maxAllowed, Math.round(offset)));
              this.isPinPrice = true;
              this.isAutoCenter = false;
              if (this.btnPinPrice) {
                this.btnPinPrice.classList.add('active');
                this.btnPinPrice.style.borderColor = '#38bdf8';
                this.btnPinPrice.style.color = '#38bdf8';
              }
              if (this.btnCenterChart) {
                this.btnCenterChart.classList.remove('active');
                this.btnCenterChart.style.borderColor = '';
                this.btnCenterChart.style.color = '';
              }
            }
          }
          this.updateShiftPinPosition(key);
        }
      });
    });
  }

  setupResetViewButtons() {
    const tfs = [
      { key: 'H4', btnId: 'btnResetView_H4' },
      { key: 'TF2', btnId: 'btnResetView_TF2' },
      { key: 'M15', btnId: 'btnResetView_M15' }
    ];

    tfs.forEach(({ key, btnId }) => {
      const btn = document.getElementById(btnId);
      if (!btn) return;
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.resetChartView(key);
      });
    });

    // TradingView Standard Hotkey: Alt+R resets view for all charts!
    window.addEventListener('keydown', (e) => {
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
      if (e.altKey && (e.key === 'r' || e.key === 'R')) {
        e.preventDefault();
        ['H4', 'TF2', 'M15'].forEach(k => this.resetChartView(k));
        this.showToast('🔄 Đã Reset Chart View (Alt+R): Tự căn lề phải GHIM:5 & Auto-Scale!');
      }
    });
  }

  resetChartView(key) {
    let chart = null;
    let subRsi = null;
    let subStoch = null;
    let subMacd = null;

    if (key === 'H4') {
      chart = this.chartH4; subRsi = this.chartRSI_H4; subStoch = this.chartStoch_H4; subMacd = this.chartMACD_H4;
    } else if (key === 'TF2') {
      chart = this.chartTF2; subRsi = this.chartRSI_TF2; subStoch = this.chartStoch_TF2; subMacd = this.chartMACD_TF2;
    } else {
      chart = this.chartM15; subRsi = this.chartRSI; subStoch = this.chartStoch; subMacd = this.chartMACD;
    }
    if (!chart) return;

    try {
      // 1. Reset Price Scale to autoScale
      chart.priceScale('right').applyOptions({ autoScale: true });
      if (subRsi) subRsi.priceScale('right').applyOptions({ autoScale: true });
      if (subStoch) subStoch.priceScale('right').applyOptions({ autoScale: true });
      if (subMacd) subMacd.priceScale('right').applyOptions({ autoScale: true });

      // 2. Set margin offset: latest candle 5 bars from right edge (default GHIM:5)
      this.shiftOffsetBars[key] = 5;
      const lastCount = this.getBarsCount(key);
      if (lastCount > 0) {
        const lastIdx = lastCount - 1;
        const range = chart.timeScale().getVisibleLogicalRange();
        const span = (range && range.to > range.from) ? (range.to - range.from) : 80;
        const to = lastIdx + 5;
        const from = to - span;

        this.isProgrammaticScroll = true;
        chart.timeScale().setVisibleLogicalRange({ from, to });
        if (subStoch) try { subStoch.timeScale().setVisibleLogicalRange({ from, to }); } catch (e) {}
        if (subRsi) try { subRsi.timeScale().setVisibleLogicalRange({ from, to }); } catch (e) {}
        if (subMacd) try { subMacd.timeScale().setVisibleLogicalRange({ from, to }); } catch (e) {}
        this.isProgrammaticScroll = false;
      }

      // 3. Hide reset button
      const btn = document.getElementById(`btnResetView_${key}`);
      if (btn) btn.classList.remove('visible');

      this.updateShiftPinPosition(key);
    } catch (err) {
      console.warn(`Error resetting chart view for ${key}:`, err);
    }
  }

  updateShiftPinPosition(key) {
    try {
      const pin = this.shiftPins[key];
      let chart = null;
      let container = null;
      let count = 0;

      if (key === 'H4') {
        chart = this.chartH4; container = this.containerH4; count = this.lastCandlesH4Count;
      } else if (key === 'TF2') {
        chart = this.chartTF2; container = this.containerTF2; count = this.lastCandlesTF2Count;
      } else if (key === 'M15') {
        chart = this.chartM15; container = this.containerM15; count = this.lastCandlesM15Count;
      }

      if (!pin || !chart || !container || count <= 0) {
        if (pin) pin.style.display = 'none';
        return;
      }

      const lastIdx = count - 1;
      const coord = chart.timeScale().logicalToCoordinate(lastIdx);
      if (coord !== null && !isNaN(coord) && coord >= 0 && coord <= container.clientWidth - 50) {
        pin.style.display = 'block';
        pin.style.left = `${Math.round(coord)}px`;
        const tag = pin.querySelector('.shift-pin-tag');
        if (tag) {
          const offset = this.shiftOffsetBars[key] || 0;
          tag.textContent = offset > 0 ? `GHIM:${offset}` : 'GHIM';
        }
      } else if (coord !== null && !isNaN(coord) && coord > container.clientWidth - 50) {
        // Candle is scrolled past the right edge
        pin.style.display = 'block';
        pin.style.left = `${container.clientWidth - 55}px`;
      } else {
        pin.style.display = 'none';
      }
    } catch (e) {
      // ignore
    }
  }

  updateAllShiftPins() {
    this.updateShiftPinPosition('H4');
    this.updateShiftPinPosition('TF2');
    this.updateShiftPinPosition('M15');
  }

  applyCenterFollowScroll() {
    try {
      this.isProgrammaticScroll = true;
      const targets = [
        { key: 'H4', chart: this.chartH4, subRsi: this.chartRSI_H4, subStoch: this.chartStoch_H4, subMacd: this.chartMACD_H4, count: this.lastCandlesH4Count, defaultSpan: 60 },
        { key: 'TF2', chart: this.chartTF2, subRsi: this.chartRSI_TF2, subStoch: this.chartStoch_TF2, subMacd: this.chartMACD_TF2, count: this.lastCandlesTF2Count, defaultSpan: 70 },
        { key: 'M15', chart: this.chartM15, subRsi: this.chartRSI, subStoch: this.chartStoch, subMacd: this.chartMACD, count: this.lastCandlesM15Count, defaultSpan: 80 }
      ];

      targets.forEach(({ key, chart, subRsi, subStoch, subMacd, count, defaultSpan }) => {
        if (!chart || count <= 0) return;
        const lastIdx = count - 1;
        const currentRange = chart.timeScale().getVisibleLogicalRange();
        const span = (currentRange && currentRange.to > currentRange.from)
          ? Math.max(20, Math.round(currentRange.to - currentRange.from))
          : defaultSpan;
        // Center 95%: latest candle sits at 95% from left (5% right margin)
        const rightPad = Math.max(3, Math.round(span * 0.05));
        const to = lastIdx + rightPad;
        const from = to - span;

        chart.timeScale().setVisibleLogicalRange({ from, to });
        if (subRsi) {
          try { subRsi.timeScale().setVisibleLogicalRange({ from, to }); } catch (e) {}
        }
        if (subStoch) {
          try { subStoch.timeScale().setVisibleLogicalRange({ from, to }); } catch (e) {}
        }
        if (subMacd) {
          try { subMacd.timeScale().setVisibleLogicalRange({ from, to }); } catch (e) {}
        }
      });
    } catch (e) {
      console.warn('Center follow error:', e);
    } finally {
      this.isProgrammaticScroll = false;
      this.updateAllShiftPins();
    }
  }

  applyPinPriceScroll() {
    try {
      this.isProgrammaticScroll = true;
      const targets = [
        { key: 'H4', chart: this.chartH4, subRsi: this.chartRSI_H4, subStoch: this.chartStoch_H4, subMacd: this.chartMACD_H4, count: this.lastCandlesH4Count, defaultSpan: 60 },
        { key: 'TF2', chart: this.chartTF2, subRsi: this.chartRSI_TF2, subStoch: this.chartStoch_TF2, subMacd: this.chartMACD_TF2, count: this.lastCandlesTF2Count, defaultSpan: 70 },
        { key: 'M15', chart: this.chartM15, subRsi: this.chartRSI, subStoch: this.chartStoch, subMacd: this.chartMACD, count: this.lastCandlesM15Count, defaultSpan: 80 }
      ];

      targets.forEach(({ key, chart, subRsi, subStoch, subMacd, count, defaultSpan }) => {
        if (!chart || count <= 0) return;
        const lastIdx = count - 1;
        const currentRange = chart.timeScale().getVisibleLogicalRange();
        const span = (currentRange && currentRange.to > currentRange.from)
          ? Math.max(20, Math.round(currentRange.to - currentRange.from))
          : defaultSpan;

        let rightOffset = this.shiftOffsetBars[key];
        if (rightOffset == null || rightOffset < 1) {
          // Default MT5 Shift Pin = 5 bars
          rightOffset = 5;
          this.shiftOffsetBars[key] = rightOffset;
        }

        const to = lastIdx + rightOffset;
        const from = to - span;

        chart.timeScale().setVisibleLogicalRange({ from, to });
        if (subRsi) {
          try { subRsi.timeScale().setVisibleLogicalRange({ from, to }); } catch (e) {}
        }
        if (subStoch) {
          try { subStoch.timeScale().setVisibleLogicalRange({ from, to }); } catch (e) {}
        }
        if (subMacd) {
          try { subMacd.timeScale().setVisibleLogicalRange({ from, to }); } catch (e) {}
        }
      });
    } catch (e) {
      console.warn('Pin price scroll error:', e);
    } finally {
      this.isProgrammaticScroll = false;
      this.updateAllShiftPins();
    }
  }

  setupPinAndCenterButtons() {
    // 1. Center Button (50% middle)
    if (this.btnCenterChart) {
      this.btnCenterChart.addEventListener('click', () => {
        if (this.isAutoCenter) {
          this.isAutoCenter = false;
          this.btnCenterChart.classList.remove('active');
          this.btnCenterChart.style.borderColor = '';
          this.btnCenterChart.style.color = '';
          this.showToast('🔓 Tắt Center (Chế độ cuộn tự do)');
        } else {
          this.isAutoCenter = true;
          this.isPinPrice = false;
          this.btnCenterChart.classList.add('active');
          this.btnCenterChart.style.borderColor = '#38bdf8';
          this.btnCenterChart.style.color = '#38bdf8';
          if (this.btnPinPrice) {
            this.btnPinPrice.classList.remove('active');
            this.btnPinPrice.style.borderColor = '';
            this.btnPinPrice.style.color = '';
          }
          this.applyCenterFollowScroll();
          this.showToast('🎯 Đã BẬT Center (95% - Sát lề phải)');
        }
      });
    }

    // 2. Pin Giá Button (MT5 Shift)
    if (this.btnPinPrice) {
      this.btnPinPrice.addEventListener('click', () => {
        if (this.isPinPrice) {
          // If already on: Reset pins to default 5 bars
          this.shiftOffsetBars = { H4: 5, TF2: 5, M15: 5 };
          this.applyPinPriceScroll();
          this.showToast('📌 Đã đặt lại Thanh Ghim về mặc định (GHIM:5)');
        } else {
          this.isPinPrice = true;
          this.isAutoCenter = false;
          this.btnPinPrice.classList.add('active');
          this.btnPinPrice.style.borderColor = '#38bdf8';
          this.btnPinPrice.style.color = '#38bdf8';
          if (this.btnCenterChart) {
            this.btnCenterChart.classList.remove('active');
            this.btnCenterChart.style.borderColor = '';
            this.btnCenterChart.style.color = '';
          }
          this.applyPinPriceScroll();
          this.showToast('📌 Đã BẬT Thanh Ghim MT5 (Nến dừng tại ghim, giá cũ đẩy ra ngoài)');
        }
      });
    }

    // 3. Reset Price Scale & Center Button
    if (this.btnResetScale) {
      this.btnResetScale.addEventListener('click', () => {
        this.resetPriceScaleAndCenter();
      });
    }
  }

  setupFitButtons() {
    if (this.btnFitTF1) this.btnFitTF1.addEventListener('click', () => this.fitChart('TF1'));
    if (this.btnFitTF2) this.btnFitTF2.addEventListener('click', () => this.fitChart('TF2'));
    if (this.btnFitTF3) this.btnFitTF3.addEventListener('click', () => this.fitChart('TF3'));
  }

  fitChart(tf) {
    let chart = null;
    let count = 0;
    let subRsi = null;
    let subStoch = null;
    let subMacd = null;
    let tfLabel = tf;

    if (tf === 'TF1' || tf === 'H4') {
      chart = this.chartH4;
      count = this.lastCandlesH4Count;
      subRsi = this.chartRSI_H4;
      subStoch = this.chartStoch_H4;
      subMacd = this.chartMACD_H4;
      tfLabel = this.tf1Name || 'TF1';
    } else if (tf === 'TF2' || tf === 'H1') {
      chart = this.chartTF2;
      count = this.lastCandlesTF2Count;
      subRsi = this.chartRSI_TF2;
      subStoch = this.chartStoch_TF2;
      subMacd = this.chartMACD_TF2;
      tfLabel = this.tf2Name || 'TF2';
    } else {
      chart = this.chartM15;
      count = this.lastCandlesM15Count;
      subRsi = this.chartRSI;
      subStoch = this.chartStoch;
      subMacd = this.chartMACD;
      tfLabel = this.tf3Name || 'TF3';
    }

    if (!chart) return;

    try {
      // 1. Auto-scale price scale
      chart.priceScale('right').applyOptions({ autoScale: true });
      if (subRsi) subRsi.priceScale('right').applyOptions({ autoScale: true });
      if (subStoch) subStoch.priceScale('right').applyOptions({ autoScale: true });
      if (subMacd) subMacd.priceScale('right').applyOptions({ autoScale: true });

      // 2. Set visible logical range with optimal span (~70-90 bars) & default GHIM:5
      if (count > 0) {
        const lastIdx = count - 1;
        const span = Math.min(count, 80);
        const rightMargin = 5;
        const from = Math.max(0, lastIdx - (span - rightMargin));
        const to = lastIdx + rightMargin;

        this.isProgrammaticScroll = true;
        chart.timeScale().setVisibleLogicalRange({ from, to });
        if (subRsi) subRsi.timeScale().setVisibleLogicalRange({ from, to });
        if (subStoch) subStoch.timeScale().setVisibleLogicalRange({ from, to });
        if (subMacd) subMacd.timeScale().setVisibleLogicalRange({ from, to });
        this.isProgrammaticScroll = false;
      } else {
        chart.timeScale().fitContent();
        if (subRsi) subRsi.timeScale().fitContent();
        if (subStoch) subStoch.timeScale().fitContent();
        if (subMacd) subMacd.timeScale().fitContent();
      }
      this.showToast(`⤢ Đã căn chỉnh Fit biểu đồ ${tfLabel}!`);
    } catch (e) {
      console.warn('fitChart error:', e);
    }
  }

  resetPriceScaleAndCenter() {
    try {
      this.fitChart('TF1');
      this.fitChart('TF2');
      this.fitChart('TF3');

      this.isAutoCenter = false;
      this.isPinPrice = true;
      if (this.btnPinPrice) {
        this.btnPinPrice.classList.add('active');
        this.btnPinPrice.style.borderColor = '#38bdf8';
        this.btnPinPrice.style.color = '#38bdf8';
      }
      if (this.btnCenterChart) {
        this.btnCenterChart.classList.remove('active');
        this.btnCenterChart.style.borderColor = '';
        this.btnCenterChart.style.color = '';
      }
      this.applyPinPriceScroll();
      this.showToast('🔄 Đã Fit & Căn chỉnh toàn bộ 3 khung theo Thanh Ghim MT5!');
    } catch (e) {
      console.warn('Reset price scale error:', e);
    }
  }

  setupDoubleClicks() {
    // Double click on charts fits that specific chart
    if (this.containerM15) {
      this.containerM15.addEventListener('dblclick', () => this.fitChart('TF3'));
    }
    if (this.containerTF2) {
      this.containerTF2.addEventListener('dblclick', () => this.fitChart('TF2'));
    }
    if (this.containerH4) {
      this.containerH4.addEventListener('dblclick', () => this.fitChart('TF1'));
    }

    // Keyboard shortcut Z to reset scale
    window.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;
      if (e.key === 'z' || e.key === 'Z') {
        this.resetPriceScaleAndCenter();
      }
    });
  }


  updateData(state) {
    if (!state) return;

    if (state.tf1_name) this.tf1Name = state.tf1_name;
    if (state.tf2_name) this.tf2Name = state.tf2_name;
    if (state.tf3_name) this.tf3Name = state.tf3_name;

    const b1 = document.getElementById('badgeTF1');
    if (b1) b1.innerText = this.tf1Name;
    const b2 = document.getElementById('badgeTF2');
    if (b2) b2.innerText = this.tf2Name;
    const b3 = document.getElementById('badgeTF3');
    if (b3) b3.innerText = this.tf3Name;

    const tf1Data = state.candles_tf1 || state.candles_h4;
    const tf2Data = state.candles_tf2;
    const tf3Data = state.candles_tf3 || state.candles_m15;

    this.rawCandlesH4 = tf1Data || [];
    this.rawCandlesTF2 = tf2Data || [];
    this.rawCandlesM15 = tf3Data || [];

    // 1. Update Candles for all 3 timeframes (guarded by isProgrammaticScroll so setData never drifts shiftOffsetBars!)
    this.isProgrammaticScroll = true;
    try {
      try {
        if (tf1Data && tf1Data.length > 0 && this.seriesH4) {
          this.seriesH4.setData(tf1Data);
          this.lastCandlesH4Count = tf1Data.length;
          const latestH4 = tf1Data[tf1Data.length - 1];
          this.updateOHLCDisplay('H4', latestH4);
        }
      } catch (e) {
        console.warn('Error setting TF1 candles:', e);
      }

      try {
        if (tf2Data && tf2Data.length > 0 && this.seriesTF2) {
          this.seriesTF2.setData(tf2Data);
          this.lastCandlesTF2Count = tf2Data.length;
          const latestTF2 = tf2Data[tf2Data.length - 1];
          this.updateOHLCDisplay('TF2', latestTF2);
        }
      } catch (e) {
        console.warn('Error setting TF2 candles:', e);
      }

      try {
        if (tf3Data && tf3Data.length > 0 && this.seriesM15) {
          this.seriesM15.setData(tf3Data);
          this.lastCandlesM15Count = tf3Data.length;
          const latestM15 = tf3Data[tf3Data.length - 1];
          this.currentPrice = latestM15.close;
          this.updateOHLCDisplay('M15', latestM15);
        }
      } catch (e) {
        console.warn('Error setting TF3 candles:', e);
      }

      // 2. Update Indicators & Divergences
      try {
        this.renderIndicators(state.indicators);
      } catch (e) {
        console.warn('Error rendering indicators:', e);
      }
    } finally {
      this.isProgrammaticScroll = false;
    }

    // 2b. Update 4-Pillar MTF Master Dashboard (TradingView Style)
    try {
      if (state.mtf_dashboard) {
        this.renderMTFMasterDashboard(state.mtf_dashboard);
      }
    } catch (e) {
      console.warn('Error rendering MTF master dashboard:', e);
    }

    // 3. Update Copilot Setup Banner
    try {
      this.renderCopilotBanner(state.copilot_signals);
    } catch (e) {
      console.warn('Error rendering copilot banner:', e);
    }

    // 4. Update Visual Order & Pending Lines
    try {
      this.renderOrderAndPendingLines(
        state.account ? state.account.open_positions : [],
        state.account ? state.account.pending_orders : []
      );
    } catch (e) {
      console.warn('Error rendering order lines:', e);
    }

    // 4b. Render Future Probabilistic Candles & Probability Fan
    try {
      this.renderProbabilisticFutureProjection(state.probabilistic_forecast);
    } catch (e) {
      console.warn('Error rendering future probabilistic projection:', e);
    }

    // 5. Dynamic Auto-Scroll: Pin Giá (MT5 Shift) or Center (50%)
    try {
      if (this.isPinPrice) {
        this.applyPinPriceScroll();
      } else if (this.isAutoCenter) {
        this.applyCenterFollowScroll();
      }
    } catch (e) {
      console.warn('Error applying auto scroll:', e);
    }
  }




  renderIndicators(indicators) {
    if (!indicators) return;
    this._latestIndicatorsData = indicators;
    const markersByTf = { TF1: [], TF2: [], TF3: [] };

    // Clean up series that are no longer active
    const activeKeys = new Set(Object.keys(indicators));
    for (const [tfK, sMap] of Object.entries(this.indicatorSeries)) {
      for (const [sKey, sInst] of Object.entries(sMap)) {
        const baseKey = sKey.replace(/(_mid|_up|_low|_plot_\d+)$/, '');
        if (!activeKeys.has(baseKey) && !activeKeys.has(sKey)) {
          try {
            sInst.setData([]);
            sInst.applyOptions({ lastValueVisible: false });
          } catch (e) {}
        }
      }
    }

    for (const [key, item] of Object.entries(indicators)) {
      const cfg = item.config;
      const data = item.data;
      const tf = cfg.timeframe || 'M15';
      const tfUpper = String(tf).toUpperCase();
      
      let targetChart = this.chartM15;
      let targetSeries = this.seriesM15;
      let tfKey = 'TF3';
      
      if (tfUpper === 'TF1' || tfUpper === 'CHART1') {
        targetChart = this.chartH4;
        targetSeries = this.seriesH4;
        tfKey = 'TF1';
      } else if (tfUpper === 'TF2' || tfUpper === 'CHART2') {
        targetChart = this.chartTF2 || this.chartM15;
        targetSeries = this.seriesTF2 || this.seriesM15;
        tfKey = 'TF2';
      } else if (tfUpper === 'TF3' || tfUpper === 'CHART3') {
        targetChart = this.chartM15;
        targetSeries = this.seriesM15;
        tfKey = 'TF3';
      } else if (tfUpper === 'H4' || tfUpper === (this.tf1Name || '').toUpperCase()) {
        targetChart = this.chartH4;
        targetSeries = this.seriesH4;
        tfKey = 'TF1';
      } else if (tfUpper === 'H1' || tfUpper === (this.tf2Name || '').toUpperCase()) {
        targetChart = this.chartTF2 || this.chartM15;
        targetSeries = this.seriesTF2 || this.seriesM15;
        tfKey = 'TF2';
      } else {
        targetChart = this.chartM15;
        targetSeries = this.seriesM15;
        tfKey = 'TF3';
      }

      if (!this.indicatorSeries[tfKey]) {
        this.indicatorSeries[tfKey] = {};
      }

      if (cfg.type === 'EMA' || cfg.type === 'SMA' || cfg.type === 'VWAP') {
        const lineColor = cfg.color || (cfg.type === 'VWAP' ? '#f59e0b' : '#3b82f6');
        const lineW = cfg.lineWidth || ((cfg.period || 20) >= 100 ? 3 : 2);
        const lineS = this.parseLineStyle(cfg.lineStyle);
        if (!this.indicatorSeries[tfKey][key]) {
          this.indicatorSeries[tfKey][key] = targetChart.addLineSeries({
            color: lineColor,
            lineWidth: lineW,
            lineStyle: lineS,
            title: '',
            priceLineVisible: false,
            lastValueVisible: true
          });
        } else {
          this.indicatorSeries[tfKey][key].applyOptions({
            color: lineColor,
            lineWidth: lineW,
            lineStyle: lineS,
            title: '',
            priceLineVisible: false,
            lastValueVisible: true
          });
        }
        if (data && Array.isArray(data)) {
          this.indicatorSeries[tfKey][key].setData(data);
        }
      } else if (cfg.type === 'BB') {
        const bbColor = cfg.color || '#a855f7';
        const bbW = cfg.lineWidth || 1;
        const bbS = this.parseLineStyle(cfg.lineStyle);
        if (!this.indicatorSeries[tfKey][`${key}_mid`]) {
          this.indicatorSeries[tfKey][`${key}_mid`] = targetChart.addLineSeries({
            color: bbColor, lineWidth: bbW, lineStyle: LightweightCharts.LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false
          });
          this.indicatorSeries[tfKey][`${key}_up`] = targetChart.addLineSeries({
            color: bbColor, lineWidth: bbW, lineStyle: bbS, priceLineVisible: false, lastValueVisible: false
          });
          this.indicatorSeries[tfKey][`${key}_low`] = targetChart.addLineSeries({
            color: bbColor, lineWidth: bbW, lineStyle: bbS, priceLineVisible: false, lastValueVisible: false
          });
        } else {
          this.indicatorSeries[tfKey][`${key}_mid`].applyOptions({ color: bbColor, lineWidth: bbW });
          this.indicatorSeries[tfKey][`${key}_up`].applyOptions({ color: bbColor, lineWidth: bbW, lineStyle: bbS });
          this.indicatorSeries[tfKey][`${key}_low`].applyOptions({ color: bbColor, lineWidth: bbW, lineStyle: bbS });
        }
        if (data && data.middle) {
          this.indicatorSeries[tfKey][`${key}_mid`].setData(data.middle);
          this.indicatorSeries[tfKey][`${key}_up`].setData(data.upper);
          this.indicatorSeries[tfKey][`${key}_low`].setData(data.lower);
        }
      } else if (cfg.type === 'SUPERTREND') {
        const stColor = cfg.color || '#089981';
        const stW = cfg.lineWidth || 2;
        const stS = this.parseLineStyle(cfg.lineStyle);
        if (!this.indicatorSeries[tfKey][key]) {
          this.indicatorSeries[tfKey][key] = targetChart.addLineSeries({
            color: stColor,
            lineWidth: stW,
            lineStyle: stS,
            priceLineVisible: false,
            lastValueVisible: false
          });
        } else {
          this.indicatorSeries[tfKey][key].applyOptions({ color: stColor, lineWidth: stW, lineStyle: stS });
        }
        if (data && data.supertrend) {
          this.indicatorSeries[tfKey][key].setData(data.supertrend.map(x => ({ time: x.time, value: x.value })));
        }
      } else if (cfg.type === 'RSI') {
        const rCol = cfg.color || '#7e57c2';
        const rW = cfg.lineWidth || 2;
        const rS = this.parseLineStyle(cfg.lineStyle);
        if (tfKey === 'TF1' && this.seriesRSI_H4 && Array.isArray(data)) {
          this.seriesRSI_H4.applyOptions({ color: rCol, lineWidth: rW, lineStyle: rS });
          this.seriesRSI_H4.setData(data);
        } else if (tfKey === 'TF2' && this.seriesRSI_TF2 && Array.isArray(data)) {
          this.seriesRSI_TF2.applyOptions({ color: rCol, lineWidth: rW, lineStyle: rS });
          this.seriesRSI_TF2.setData(data);
        } else if (this.seriesRSI && Array.isArray(data)) {
          this.seriesRSI.applyOptions({ color: rCol, lineWidth: rW, lineStyle: rS });
          this.seriesRSI.setData(data);
        }
      } else if (cfg.type === 'RSI_MA9_WMA45') {
        const rCol = cfg.color || '#7e57c2', rW = cfg.lineWidth || 2, rS = this.parseLineStyle(cfg.lineStyle);
        const mCol = cfg.color_ma9 || '#fdd835', mW = cfg.width_ma9 || 1.5, mS = this.parseLineStyle(cfg.style_ma9);
        const wCol = cfg.color_wma45 || '#f23645', wW = cfg.width_wma45 || 1.5, wS = this.parseLineStyle(cfg.style_wma45);
        if (tfKey === 'TF1') {
          if (this.seriesRSI_H4 && data && data.rsi) { this.seriesRSI_H4.applyOptions({ color: rCol, lineWidth: rW, lineStyle: rS }); this.seriesRSI_H4.setData(data.rsi); }
          if (this.seriesRSI_MA9_H4 && data && data.ma9) { this.seriesRSI_MA9_H4.applyOptions({ color: mCol, lineWidth: mW, lineStyle: mS }); this.seriesRSI_MA9_H4.setData(data.ma9); }
          if (this.seriesRSI_WMA45_H4 && data && data.wma45) { this.seriesRSI_WMA45_H4.applyOptions({ color: wCol, lineWidth: wW, lineStyle: wS }); this.seriesRSI_WMA45_H4.setData(data.wma45); }
        } else if (tfKey === 'TF2') {
          if (this.seriesRSI_TF2 && data && data.rsi) { this.seriesRSI_TF2.applyOptions({ color: rCol, lineWidth: rW, lineStyle: rS }); this.seriesRSI_TF2.setData(data.rsi); }
          if (this.seriesRSI_MA9_TF2 && data && data.ma9) { this.seriesRSI_MA9_TF2.applyOptions({ color: mCol, lineWidth: mW, lineStyle: mS }); this.seriesRSI_MA9_TF2.setData(data.ma9); }
          if (this.seriesRSI_WMA45_TF2 && data && data.wma45) { this.seriesRSI_WMA45_TF2.applyOptions({ color: wCol, lineWidth: wW, lineStyle: wS }); this.seriesRSI_WMA45_TF2.setData(data.wma45); }
        } else {
          if (this.seriesRSI && data && data.rsi) { this.seriesRSI.applyOptions({ color: rCol, lineWidth: rW, lineStyle: rS }); this.seriesRSI.setData(data.rsi); }
          if (this.seriesRSI_MA9 && data && data.ma9) { this.seriesRSI_MA9.applyOptions({ color: mCol, lineWidth: mW, lineStyle: mS }); this.seriesRSI_MA9.setData(data.ma9); }
          if (this.seriesRSI_WMA45 && data && data.wma45) { this.seriesRSI_WMA45.applyOptions({ color: wCol, lineWidth: wW, lineStyle: wS }); this.seriesRSI_WMA45.setData(data.wma45); }
        }
      } else if (cfg.type === 'STOCH') {
        const kCol = cfg.color_k || '#10b981', kW = cfg.width_k || 1.5, kS = this.parseLineStyle(cfg.style_k);
        const dCol = cfg.color_d || '#ef4444', dW = cfg.width_d || 1.5, dS = this.parseLineStyle(cfg.style_d);
        if (tfKey === 'TF1' && this.seriesStochK_H4) {
          if (data && data.k) { this.seriesStochK_H4.applyOptions({ color: kCol, lineWidth: kW, lineStyle: kS }); this.seriesStochK_H4.setData(data.k); }
          if (data && data.d) { this.seriesStochD_H4.applyOptions({ color: dCol, lineWidth: dW, lineStyle: dS }); this.seriesStochD_H4.setData(data.d); }
        } else if (tfKey === 'TF2' && this.seriesStochK_TF2) {
          if (data && data.k) { this.seriesStochK_TF2.applyOptions({ color: kCol, lineWidth: kW, lineStyle: kS }); this.seriesStochK_TF2.setData(data.k); }
          if (data && data.d) { this.seriesStochD_TF2.applyOptions({ color: dCol, lineWidth: dW, lineStyle: dS }); this.seriesStochD_TF2.setData(data.d); }
        } else if (this.seriesStochK) {
          if (data && data.k) { this.seriesStochK.applyOptions({ color: kCol, lineWidth: kW, lineStyle: kS }); this.seriesStochK.setData(data.k); }
          if (data && data.d) { this.seriesStochD.applyOptions({ color: dCol, lineWidth: dW, lineStyle: dS }); this.seriesStochD.setData(data.d); }
        }
      } else if (cfg.type === 'MACD') {
        const mCol = cfg.color_macd || '#2962ff', mW = cfg.width_macd || 1.5, mS = this.parseLineStyle(cfg.style_macd);
        const sCol = cfg.color_signal || '#ff6d00', sW = cfg.width_signal || 1.5, sS = this.parseLineStyle(cfg.style_signal);
        if (tfKey === 'TF1') {
          if (this.seriesMACD_Hist_H4 && data && data.histogram) this.seriesMACD_Hist_H4.setData(data.histogram);
          if (this.seriesMACD_Line_H4 && data && data.macd) { this.seriesMACD_Line_H4.applyOptions({ color: mCol, lineWidth: mW, lineStyle: mS }); this.seriesMACD_Line_H4.setData(data.macd); }
          if (this.seriesMACD_Sig_H4 && data && data.signal) { this.seriesMACD_Sig_H4.applyOptions({ color: sCol, lineWidth: sW, lineStyle: sS }); this.seriesMACD_Sig_H4.setData(data.signal); }
        } else if (tfKey === 'TF2') {
          if (this.seriesMACD_Hist_TF2 && data && data.histogram) this.seriesMACD_Hist_TF2.setData(data.histogram);
          if (this.seriesMACD_Line_TF2 && data && data.macd) { this.seriesMACD_Line_TF2.applyOptions({ color: mCol, lineWidth: mW, lineStyle: mS }); this.seriesMACD_Line_TF2.setData(data.macd); }
          if (this.seriesMACD_Sig_TF2 && data && data.signal) { this.seriesMACD_Sig_TF2.applyOptions({ color: sCol, lineWidth: sW, lineStyle: sS }); this.seriesMACD_Sig_TF2.setData(data.signal); }
        } else {
          if (this.seriesMACD_Hist && data && data.histogram) this.seriesMACD_Hist.setData(data.histogram);
          if (this.seriesMACD_Line && data && data.macd) { this.seriesMACD_Line.applyOptions({ color: mCol, lineWidth: mW, lineStyle: mS }); this.seriesMACD_Line.setData(data.macd); }
          if (this.seriesMACD_Sig && data && data.signal) { this.seriesMACD_Sig.applyOptions({ color: sCol, lineWidth: sW, lineStyle: sS }); this.seriesMACD_Sig.setData(data.signal); }
        }
      } else if (cfg.type === 'DIVERGENCE') {
        if (data && data.divergences) {
          for (const d of data.divergences) {
            if (!d || !d.time2) continue;
            const isBull = d.side === 'BUY';
            markersByTf[tfKey].push({
              time: d.time2,
              position: isBull ? 'belowBar' : 'aboveBar',
              color: isBull ? '#089981' : '#f23645',
              shape: isBull ? 'arrowUp' : 'arrowDown',
              text: `DIV ${d.indicator || ''}`
            });
          }
        }
      } else if (cfg.type === 'MTF_SIGNALS') {
        if (data && Array.isArray(data)) {
          for (const s of data) {
            if (!s || !s.time) continue;
            const isBuy = s.type === 'MTF_BUY';
            markersByTf[tfKey].push({
              time: s.time,
              position: isBuy ? 'belowBar' : 'aboveBar',
              color: isBuy ? '#00e676' : '#ff5252',
              shape: isBuy ? 'arrowUp' : 'arrowDown',
              text: isBuy ? '▲ MTF BUY' : '▼ MTF SELL'
            });
          }
        }
      } else if (cfg.type === 'CUSTOM_SCRIPT') {
        if (data && data.success) {
          if (Array.isArray(data.plots)) {
            data.plots.forEach((pl, idx) => {
              const sKey = `${key}_plot_${idx}`;
              const pCol = pl.color || '#38bdf8';
              const pW = pl.lineWidth || 2;
              const pS = this.parseLineStyle(pl.lineStyle);
              if (!this.indicatorSeries[tfKey][sKey]) {
                this.indicatorSeries[tfKey][sKey] = targetChart.addLineSeries({
                  color: pCol,
                  lineWidth: pW,
                  lineStyle: pS,
                  title: '',
                  priceLineVisible: false,
                  lastValueVisible: true
                });
              } else {
                this.indicatorSeries[tfKey][sKey].applyOptions({ color: pCol, lineWidth: pW, lineStyle: pS, title: '', lastValueVisible: true });
              }
              if (Array.isArray(pl.data)) {
                this.indicatorSeries[tfKey][sKey].setData(pl.data);
              }
            });
          }
          if (Array.isArray(data.markers)) {
            for (const m of data.markers) {
              if (!m || !m.time) continue;
              markersByTf[tfKey].push({
                time: m.time,
                position: m.position || 'belowBar',
                color: m.color || '#10b981',
                shape: m.shape || 'arrowUp',
                text: m.text || 'SIG'
              });
            }
          }
        }
      }
    }

    // Apply merged markers (DIVERGENCE + MTF_SIGNALS) cleanly once per TF (or clear if empty)
    const applyMergedMarkers = (series, list) => {
      if (!series) return;
      if (!list || list.length === 0) {
        try { series.setMarkers([]); } catch (e) {}
        return;
      }
      list.sort((a, b) => a.time - b.time);
      const unique = [];
      const seen = new Set();
      for (const m of list) {
        const key = `${m.time}_${m.position}`;
        if (!seen.has(key)) {
          seen.add(key);
          unique.push(m);
        }
      }
      try { series.setMarkers(unique); } catch (e) {}
    };
    applyMergedMarkers(this.seriesH4, markersByTf.TF1);
    applyMergedMarkers(this.seriesTF2, markersByTf.TF2);
    applyMergedMarkers(this.seriesM15, markersByTf.TF3);

    // Clear sub-chart series if their indicator was disabled or deleted
    const n1 = (this.tf1Name || '').toUpperCase();
    const n2 = (this.tf2Name || '').toUpperCase();
    const n3 = (this.tf3Name || '').toUpperCase();
    const hasSub = (tfK, types) => Object.values(indicators).some(it => {
      const t = String(it.config.timeframe || '').toUpperCase();
      const matchTf = (tfK === 'TF1' && (t === 'TF1' || t === 'CHART1' || t === 'H4' || t === n1)) ||
                      (tfK === 'TF2' && (t === 'TF2' || t === 'CHART2' || t === 'H1' || t === n2)) ||
                      (tfK === 'TF3' && (t === 'TF3' || t === 'CHART3' || t === 'M15' || t === 'M5' || t === n3));
      return matchTf && types.includes(String(it.config.type || '').toUpperCase());
    });
    if (!hasSub('TF1', ['STOCH'])) { try { this.seriesStochK_H4.setData([]); this.seriesStochD_H4.setData([]); } catch (e) {} }
    if (!hasSub('TF2', ['STOCH'])) { try { this.seriesStochK_TF2.setData([]); this.seriesStochD_TF2.setData([]); } catch (e) {} }
    if (!hasSub('TF3', ['STOCH'])) { try { this.seriesStochK.setData([]); this.seriesStochD.setData([]); } catch (e) {} }
    if (!hasSub('TF1', ['RSI', 'RSI_MA9_WMA45'])) { try { this.seriesRSI_H4.setData([]); this.seriesRSI_MA9_H4.setData([]); this.seriesRSI_WMA45_H4.setData([]); } catch (e) {} }
    if (!hasSub('TF2', ['RSI', 'RSI_MA9_WMA45'])) { try { this.seriesRSI_TF2.setData([]); this.seriesRSI_MA9_TF2.setData([]); this.seriesRSI_WMA45_TF2.setData([]); } catch (e) {} }
    if (!hasSub('TF3', ['RSI', 'RSI_MA9_WMA45'])) { try { this.seriesRSI.setData([]); this.seriesRSI_MA9.setData([]); this.seriesRSI_WMA45.setData([]); } catch (e) {} }
    if (!hasSub('TF1', ['MACD'])) { try { this.seriesMACD_Hist_H4.setData([]); this.seriesMACD_Line_H4.setData([]); this.seriesMACD_Sig_H4.setData([]); } catch (e) {} }
    if (!hasSub('TF2', ['MACD'])) { try { this.seriesMACD_Hist_TF2.setData([]); this.seriesMACD_Line_TF2.setData([]); this.seriesMACD_Sig_TF2.setData([]); } catch (e) {} }
    if (!hasSub('TF3', ['MACD'])) { try { this.seriesMACD_Hist.setData([]); this.seriesMACD_Line.setData([]); this.seriesMACD_Sig.setData([]); } catch (e) {} }

    // Render TradingView-style interactive indicator legends on all charts & sub-charts
    this.renderIndicatorLegends(indicators);
  }

  updateLegendValuesAtTime(tf, targetTime) {
    if (!this._latestIndicatorsData || !targetTime) return;
    const tfKey = tf === 'H4' ? 'TF1' : (tf === 'TF2' ? 'TF2' : 'TF3');

    const findVal = (arr, t) => {
      if (!Array.isArray(arr) || arr.length === 0) return null;
      let lo = 0, hi = arr.length - 1, best = null;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        if (arr[mid].time === t) return arr[mid].value;
        if (arr[mid].time < t) { best = arr[mid].value; lo = mid + 1; }
        else { hi = mid - 1; }
      }
      return best;
    };

    for (const [key, item] of Object.entries(this._latestIndicatorsData)) {
      const n1 = (this.tf1Name || '').toUpperCase();
      const n2 = (this.tf2Name || '').toUpperCase();
      const cfg = item.config || {};
      const tfU = String(cfg.timeframe || 'TF3').toUpperCase();
      const itemTf = (tfU === 'TF1' || tfU === 'CHART1' || tfU === 'H4' || tfU === n1) ? 'TF1' :
                     ((tfU === 'TF2' || tfU === 'CHART2' || tfU === 'H1' || tfU === n2) ? 'TF2' : 'TF3');
      if (itemTf !== tfKey) continue;

      const rowEl = document.querySelector(`.tv-legend-item[data-key="${key}"] .tv-legend-values`);
      if (!rowEl) continue;

      const data = item.data;
      const typeU = String(cfg.type || '').toUpperCase();
      let html = '';
      if (typeU === 'EMA' || typeU === 'SMA' || typeU === 'ATR') {
        const v = findVal(data, targetTime);
        if (v !== null) html = `<span style="color:${cfg.color || '#3b82f6'}">${Number(v).toFixed(2)}</span>`;
      } else if (typeU === 'STOCH' && data) {
        const kv = findVal(data.k, targetTime);
        const dv = findVal(data.d, targetTime);
        if (kv !== null) html += `<span style="color:${cfg.color_k || '#10b981'}">${Number(kv).toFixed(2)}</span>`;
        if (dv !== null) html += `<span style="color:${cfg.color_d || '#ef4444'}">${Number(dv).toFixed(2)}</span>`;
      } else if ((typeU === 'RSI' || typeU === 'RSI_MA9_WMA45') && data) {
        const rv = findVal(data.rsi, targetTime);
        const mv = findVal(data.ma9, targetTime);
        const wv = findVal(data.wma45, targetTime);
        if (rv !== null) html += `<span style="color:${cfg.color || '#7e57c2'}">${Number(rv).toFixed(2)}</span>`;
        if (mv !== null) html += `<span style="color:${cfg.color_ma9 || '#fdd835'}">${Number(mv).toFixed(2)}</span>`;
        if (wv !== null) html += `<span style="color:${cfg.color_wma45 || '#f23645'}">${Number(wv).toFixed(2)}</span>`;
      } else if (typeU === 'MACD' && data) {
        const hv = findVal(data.histogram, targetTime);
        const mv = findVal(data.macd, targetTime);
        const sv = findVal(data.signal, targetTime);
        if (hv !== null) html += `<span style="color:#ef5350">${Number(hv).toFixed(2)}</span>`;
        if (mv !== null) html += `<span style="color:${cfg.color_macd || '#2962ff'}">${Number(mv).toFixed(2)}</span>`;
        if (sv !== null) html += `<span style="color:${cfg.color_signal || '#ff6d00'}">${Number(sv).toFixed(2)}</span>`;
      }
      if (html) rowEl.innerHTML = html;
    }
  }

  startCandleCountdownTimer() {
    const tfSeconds = { M1: 60, M5: 300, M15: 900, M30: 1800, H1: 3600, H4: 14400, D1: 86400 };
    const fmt = (sec) => {
      if (sec <= 0) return '00:00';
      const h = Math.floor(sec / 3600);
      const m = Math.floor((sec % 3600) / 60);
      const s = sec % 60;
      const pad = (n) => String(n).padStart(2, '0');
      return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
    };
    setInterval(() => {
      const isLive = window.app && window.app.liveRealtimeActive;
      const nowSec = Math.floor(Date.now() / 1000);
      const pairs = [
        { id: 'countdownTF1', name: this.tf1Name },
        { id: 'countdownTF2', name: this.tf2Name },
        { id: 'countdownTF3', name: this.tf3Name }
      ];
      for (const p of pairs) {
        const el = document.getElementById(p.id);
        if (!el) continue;
        if (!isLive) {
          el.innerText = '';
          el.style.display = 'none';
          continue;
        }
        const dur = tfSeconds[String(p.name || 'M15').toUpperCase()] || 900;
        const rem = dur - (nowSec % dur);
        el.innerText = `⏱ ${fmt(rem)}`;
        el.style.display = 'inline-block';
      }
    }, 1000);
  }

  parseLineStyle(styleStr) {
    if (styleStr === 'dashed') return LightweightCharts.LineStyle.Dashed;
    if (styleStr === 'dotted') return LightweightCharts.LineStyle.Dotted;
    return LightweightCharts.LineStyle.Solid;
  }

  renderIndicatorLegends(activeIndicatorsData) {
    const allCfg = (window.app && window.app.indicatorsManager && window.app.indicatorsManager.currentConfig && Object.keys(window.app.indicatorsManager.currentConfig).length > 0)
      ? window.app.indicatorsManager.currentConfig
      : {};

    // Merge activeIndicatorsData into source map
    const merged = { ...allCfg };
    if (activeIndicatorsData) {
      for (const [k, v] of Object.entries(activeIndicatorsData)) {
        if (!merged[k]) merged[k] = v.config;
      }
    }

    const buckets = {
      TF1: { main: [], stoch: [], rsi: [], macd: [] },
      TF2: { main: [], stoch: [], rsi: [], macd: [] },
      TF3: { main: [], stoch: [], rsi: [], macd: [] }
    };

    const n1 = (this.tf1Name || '').toUpperCase();
    const n2 = (this.tf2Name || '').toUpperCase();
    for (const [key, cfg] of Object.entries(merged)) {
      if (!cfg) continue;
      const tfU = String(cfg.timeframe || 'TF3').toUpperCase();
      let tfK = 'TF3';
      if (tfU === 'TF1' || tfU === 'CHART1' || tfU === 'H4' || tfU === n1) tfK = 'TF1';
      else if (tfU === 'TF2' || tfU === 'CHART2' || tfU === 'H1' || tfU === n2) tfK = 'TF2';

      const typeU = String(cfg.type || '').toUpperCase();
      const liveData = activeIndicatorsData && activeIndicatorsData[key] ? activeIndicatorsData[key].data : null;
      const entry = { key, cfg, liveData };

      if (typeU === 'STOCH') buckets[tfK].stoch.push(entry);
      else if (typeU === 'RSI' || typeU === 'RSI_MA9_WMA45') buckets[tfK].rsi.push(entry);
      else if (typeU === 'MACD') buckets[tfK].macd.push(entry);
      else buckets[tfK].main.push(entry);
    }

    const mountLegend = (container, items, isMainChart, legendId) => {
      if (!container) return;
      let el = container.querySelector(`#${legendId}`);
      if (!el) {
        el = document.createElement('div');
        el.id = legendId;
        el.className = `tv-legend-overlay ${isMainChart ? 'main-chart-legend' : ''}`;
        container.appendChild(el);
      }

      if (!items || items.length === 0) {
        el.innerHTML = '';
        return;
      }

      const buildItemHtml = ({ key, cfg, liveData }) => {
        const typeU = String(cfg.type || '').toUpperCase();
        let label = typeU;
        let params = '';
        let valHtml = '';

        if (typeU === 'EMA' || typeU === 'SMA' || typeU === 'ATR') {
          label = typeU;
          params = `${cfg.period || 20}`;
          const last = Array.isArray(liveData) && liveData.length ? liveData[liveData.length - 1].value : null;
          if (last !== null) valHtml = `<span style="color:${cfg.color || '#3b82f6'}">${Number(last).toFixed(2)}</span>`;
        } else if (typeU === 'BB') {
          label = 'BB';
          params = `${cfg.period || 20} ${cfg.std_dev || 2}`;
        } else if (typeU === 'STOCH') {
          label = 'Stoch';
          params = `${cfg.k || 14} ${cfg.smooth_k || 3} ${cfg.d || 3}`;
          const kVal = liveData && liveData.k && liveData.k.length ? liveData.k[liveData.k.length - 1].value : null;
          const dVal = liveData && liveData.d && liveData.d.length ? liveData.d[liveData.d.length - 1].value : null;
          if (kVal !== null) valHtml += `<span style="color:${cfg.color_k || '#10b981'}">${Number(kVal).toFixed(2)}</span>`;
          if (dVal !== null) valHtml += `<span style="color:${cfg.color_d || '#ef4444'}">${Number(dVal).toFixed(2)}</span>`;
        } else if (typeU === 'RSI' || typeU === 'RSI_MA9_WMA45') {
          label = 'RSI_MA9_WMA45';
          params = `${cfg.period || 14} ${cfg.ma9_period || 9} ${cfg.wma45_period || 45}`;
          const rVal = liveData && liveData.rsi && liveData.rsi.length ? liveData.rsi[liveData.rsi.length - 1].value : null;
          const mVal = liveData && liveData.ma9 && liveData.ma9.length ? liveData.ma9[liveData.ma9.length - 1].value : null;
          const wVal = liveData && liveData.wma45 && liveData.wma45.length ? liveData.wma45[liveData.wma45.length - 1].value : null;
          if (rVal !== null) valHtml += `<span style="color:${cfg.color || '#7e57c2'}">${Number(rVal).toFixed(2)}</span>`;
          if (mVal !== null) valHtml += `<span style="color:${cfg.color_ma9 || '#fdd835'}">${Number(mVal).toFixed(2)}</span>`;
          if (wVal !== null) valHtml += `<span style="color:${cfg.color_wma45 || '#f23645'}">${Number(wVal).toFixed(2)}</span>`;
        } else if (typeU === 'MACD') {
          label = 'MACD';
          params = `${cfg.fast || 12} ${cfg.slow || 26} ${cfg.signal || 9}`;
          const hVal = liveData && liveData.histogram && liveData.histogram.length ? liveData.histogram[liveData.histogram.length - 1].value : null;
          const mVal = liveData && liveData.macd && liveData.macd.length ? liveData.macd[liveData.macd.length - 1].value : null;
          const sVal = liveData && liveData.signal && liveData.signal.length ? liveData.signal[liveData.signal.length - 1].value : null;
          if (hVal !== null) valHtml += `<span style="color:#ef5350">${Number(hVal).toFixed(2)}</span>`;
          if (mVal !== null) valHtml += `<span style="color:${cfg.color_macd || '#2962ff'}">${Number(mVal).toFixed(2)}</span>`;
          if (sVal !== null) valHtml += `<span style="color:${cfg.color_signal || '#ff6d00'}">${Number(sVal).toFixed(2)}</span>`;
        }

        const isOff = !cfg.enabled;
        return `
          <div class="tv-legend-item ${isOff ? 'disabled' : ''}" data-key="${key}" ondblclick="window.app.indicatorsManager.openIndicatorSettings('${key}')">
            <span class="tv-legend-title">${label}</span>
            <span class="tv-legend-params">${params}</span>
            <span class="tv-legend-values">${valHtml}</span>
            <div class="tv-legend-actions">
              <button class="tv-legend-btn" title="${isOff ? 'Hiện chỉ báo' : 'Ẩn chỉ báo'}" onclick="event.stopPropagation(); window.app.indicatorsManager.toggleIndicatorVisibility('${key}')">${isOff ? '🙈' : '👁️'}</button>
              <button class="tv-legend-btn" title="Cấu hình (Settings)" onclick="event.stopPropagation(); window.app.indicatorsManager.openIndicatorSettings('${key}')">⚙️</button>
              <button class="tv-legend-btn del" title="Xóa chỉ báo" onclick="event.stopPropagation(); window.app.indicatorsManager.removeIndicator('${key}')">✕</button>
            </div>
          </div>
        `;
      };

      const tfTag = legendId.includes('TF1') ? 'TF1' : (legendId.includes('TF2') ? 'TF2' : 'TF3');
      if (!this._legendCollapsed) {
        try {
          const saved = localStorage.getItem('tvLegendCollapsed');
          this._legendCollapsed = saved ? JSON.parse(saved) : { TF1: true, TF2: true, TF3: true };
        } catch (e) {
          this._legendCollapsed = { TF1: true, TF2: true, TF3: true };
        }
      }
      const isCollapsed = !!this._legendCollapsed[tfTag];

      if (isMainChart) {
        el.innerHTML = `
          <button class="tv-legend-toggle-btn" id="btnToggle_${legendId}" title="Bấm để ẩn/hiện tên chỉ báo trên cửa sổ chính và các cửa sổ phụ">
            📊 Chỉ báo (${items.length}) ${isCollapsed ? '▸' : '▾'}
          </button>
          <div class="tv-legend-list ${isCollapsed ? 'collapsed' : ''}">
            ${items.map(buildItemHtml).join('')}
          </div>
        `;
        const btnToggle = el.querySelector(`#btnToggle_${legendId}`);
        if (btnToggle) {
          btnToggle.onclick = (e) => {
            e.stopPropagation();
            this._legendCollapsed[tfTag] = !this._legendCollapsed[tfTag];
            try { localStorage.setItem('tvLegendCollapsed', JSON.stringify(this._legendCollapsed)); } catch (err) {}
            const nowCollapsed = this._legendCollapsed[tfTag];
            const list = el.querySelector('.tv-legend-list');
            if (list) list.classList.toggle('collapsed', nowCollapsed);
            btnToggle.innerHTML = `📊 Chỉ báo (${items.length}) ${nowCollapsed ? '▸' : '▾'}`;
            // Sync collapse/expand to all sub-window legends in the same column (TradingView behavior!)
            ['legendStoch_', 'legendRsi_', 'legendMacd_'].forEach(prefix => {
              const subList = document.querySelector(`#${prefix}${tfTag} .tv-legend-list`);
              if (subList) subList.classList.toggle('collapsed', nowCollapsed);
            });
          };
        }
      } else {
        el.innerHTML = `<div class="tv-legend-list ${isCollapsed ? 'collapsed' : ''}">${items.map(buildItemHtml).join('')}</div>`;
      }
    };

    mountLegend(this.containerH4, buckets.TF1.main, true, 'legendMain_TF1');
    mountLegend(this.containerStoch_H4, buckets.TF1.stoch, false, 'legendStoch_TF1');
    mountLegend(this.containerRSI_H4, buckets.TF1.rsi, false, 'legendRsi_TF1');
    mountLegend(this.containerMACD_H4, buckets.TF1.macd, false, 'legendMacd_TF1');

    mountLegend(this.containerTF2, buckets.TF2.main, true, 'legendMain_TF2');
    mountLegend(this.containerStoch_TF2, buckets.TF2.stoch, false, 'legendStoch_TF2');
    mountLegend(this.containerRSI_TF2, buckets.TF2.rsi, false, 'legendRsi_TF2');
    mountLegend(this.containerMACD_TF2, buckets.TF2.macd, false, 'legendMacd_TF2');

    mountLegend(this.containerM15, buckets.TF3.main, true, 'legendMain_TF3');
    mountLegend(this.containerStoch, buckets.TF3.stoch, false, 'legendStoch_TF3');
    mountLegend(this.containerRSI, buckets.TF3.rsi, false, 'legendRsi_TF3');
    mountLegend(this.containerMACD, buckets.TF3.macd, false, 'legendMacd_TF3');
  }

  renderMTFSignals(signals, tfKey, targetSeries) {
    if (!signals || !Array.isArray(signals) || !targetSeries) return;
    const markers = [];
    for (const s of signals) {
      if (!s || !s.time) continue;
      const isBuy = s.type === 'MTF_BUY';
      markers.push({
        time: s.time,
        position: isBuy ? 'belowBar' : 'aboveBar',
        color: isBuy ? '#00e676' : '#ff5252',
        shape: isBuy ? 'arrowUp' : 'arrowDown',
        text: isBuy ? '▲ MTF BUY' : '▼ MTF SELL'
      });
    }
    if (markers.length > 0) {
      markers.sort((a, b) => a.time - b.time);
      try {
        targetSeries.setMarkers(markers);
      } catch (e) {
        console.warn('Error setting MTF signals on ' + tfKey, e);
      }
    }
  }

  renderMTFMasterDashboard(dashData) {
    const container = document.getElementById('mtfMasterDashboard');
    if (!container || !dashData) return;

    this.lastMtfDashData = dashData;
    const cfg = this.mtfDashConfig || this.getDefaultDashConfig();

    if (!cfg.visible) {
      container.style.display = 'none';
      return;
    }

    const symbol = dashData.symbol || 'SYMBOL';
    const verdict = dashData.verdict || 'NEUTRAL';
    const verdictColor = dashData.verdict_color || '#94a3b8';
    const title = dashData.title || `[${symbol} LIVE] * ${verdict}`;
    const rows = dashData.rows || [];
    const footerText = dashData.footer_text || dashData.summary_votes || '';
    const radarText = dashData.radar_text || dashData.radar_15m || '';

    let html = `
      <div class="mtf-dash-banner" id="mtfDashDragHandle" style="background-color: ${verdictColor};" title="Kéo để di chuyển Dashboard">
        <span>${title}</span>
        <div class="mtf-dash-actions">
          <button class="mtf-dash-btn" id="btnDashCollapse" title="${cfg.collapsed ? 'Mở rộng bảng' : 'Thu gọn thành 1 dòng'}">${cfg.collapsed ? '▾' : '—'}</button>
          <button class="mtf-dash-btn" id="btnDashCfgGear" title="Cấu hình Dashboard (Vị trí, Cỡ chữ, Ẩn/Hiện)">⚙️</button>
          <button class="mtf-dash-btn" id="btnDashHide" title="Ẩn Dashboard (Mở lại bằng nút ⚙️ Dash ở góc trên)">✕</button>
        </div>
      </div>
      <table class="mtf-dash-table">
        <thead>
          <tr>
            <th>TF</th>
            <th>1.EMA 5/12</th>
            <th>2.STOCH</th>
            <th>3.RSI+WMA45</th>
            <th>4.MACD</th>
            <th>VOTE</th>
          </tr>
        </thead>
        <tbody>
    `;

    for (const r of rows) {
      const p1 = r.ema_str || r.p1_label || '--';
      const p2 = r.stoch_str || r.p2_label || '--';
      const p3 = r.rsi_str || r.p3_label || '--';
      const p4 = r.macd_str || r.p4_label || '--';
      const rowCol = r.color || (r.dir < 0 ? '#ef4444' : (r.dir > 0 ? '#10b981' : '#f59e0b'));

      html += `
        <tr>
          <td class="tf-col">${r.tf}</td>
          <td style="color: ${p1.startsWith('v') ? '#ef4444' : (p1.startsWith('^') ? '#10b981' : rowCol)}; font-weight: 600;">${p1}</td>
          <td style="color: ${p2.startsWith('v') ? '#ef4444' : (p2.startsWith('^') ? '#10b981' : rowCol)}; font-weight: 600;">${p2}</td>
          <td style="color: ${p3.startsWith('v') ? '#ef4444' : (p3.startsWith('^') ? '#10b981' : rowCol)}; font-weight: 600;">${p3}</td>
          <td style="color: ${p4.startsWith('v') ? '#ef4444' : (p4.startsWith('^') ? '#10b981' : rowCol)}; font-weight: 600;">${p4}</td>
          <td class="vote-col" style="color: ${rowCol}; font-weight: 700;">${r.vote}</td>
        </tr>
      `;
    }

    const showFooter = cfg.showFooter !== false;
    const showRadar = cfg.showRadar !== false;

    html += `
        </tbody>
      </table>
      ${(showFooter || showRadar) ? `
      <div class="mtf-dash-footer">
        ${showFooter ? `<div>${footerText}</div>` : ''}
        ${showRadar ? `<div class="mtf-dash-radar">${radarText}</div>` : ''}
      </div>` : ''}
    `;

    container.innerHTML = html;
    container.style.display = 'block';
    this.applyDashboardStyleAndPosition();
    this.bindDashboardBannerEvents();
  }

  getDefaultDashConfig() {
    return {
      visible: true,
      collapsed: false,
      position: 'top-left',
      size: 'small',
      opacity: 92,
      showRadar: true,
      showFooter: true,
      customX: null,
      customY: null
    };
  }

  initDashboardConfig() {
    try {
      const saved = localStorage.getItem('mtfDashboardConfig');
      this.mtfDashConfig = saved ? { ...this.getDefaultDashConfig(), ...JSON.parse(saved) } : this.getDefaultDashConfig();
    } catch (e) {
      this.mtfDashConfig = this.getDefaultDashConfig();
    }

    const btnDashSettings = document.getElementById('btnDashSettings');
    if (btnDashSettings) {
      btnDashSettings.addEventListener('click', () => this.openDashboardSettings());
    }

    const btnClose = document.getElementById('btnCloseDashSettings');
    const btnCancel = document.getElementById('btnDashSettingsCancel');
    const btnOk = document.getElementById('btnDashSettingsOk');
    const btnReset = document.getElementById('btnDashSettingsReset');
    const opRange = document.getElementById('dashCfg_opacity');
    const opVal = document.getElementById('dashCfg_opacityVal');

    if (btnClose) btnClose.addEventListener('click', () => this.closeDashboardSettings());
    if (btnCancel) btnCancel.addEventListener('click', () => this.closeDashboardSettings());
    if (btnOk) btnOk.addEventListener('click', () => this.applyDashboardSettings());
    if (btnReset) btnReset.addEventListener('click', () => this.resetDashboardSettings());
    if (opRange && opVal) {
      opRange.addEventListener('input', () => { opVal.innerText = `${opRange.value}%`; });
    }
  }

  saveDashboardConfig() {
    try {
      localStorage.setItem('mtfDashboardConfig', JSON.stringify(this.mtfDashConfig));
    } catch (e) {}
  }

  applyDashboardStyleAndPosition() {
    const container = document.getElementById('mtfMasterDashboard');
    if (!container) return;
    const cfg = this.mtfDashConfig || this.getDefaultDashConfig();

    container.classList.remove('size-tiny', 'size-small', 'size-normal', 'collapsed');
    container.classList.add(`size-${cfg.size || 'small'}`);
    if (cfg.collapsed) container.classList.add('collapsed');

    const op = Math.max(0.35, Math.min(1.0, (cfg.opacity || 92) / 100));
    container.style.background = `rgba(18, 22, 32, ${op})`;

    // Reset positioning styles first
    container.style.top = '';
    container.style.bottom = '';
    container.style.left = '';
    container.style.right = '';

    const pos = cfg.position || 'top-left';
    if (pos === 'custom' && cfg.customX !== null && cfg.customY !== null) {
      container.style.left = `${cfg.customX}px`;
      container.style.top = `${cfg.customY}px`;
    } else if (pos === 'top-right') {
      container.style.top = '8px';
      container.style.right = '60px';
    } else if (pos === 'bottom-left') {
      container.style.bottom = '28px';
      container.style.left = '8px';
    } else if (pos === 'bottom-right') {
      container.style.bottom = '28px';
      container.style.right = '60px';
    } else {
      // top-left: right below "📊 Chỉ báo (9)" legend toggle!
      container.style.top = '34px';
      container.style.left = '8px';
    }
  }

  bindDashboardBannerEvents() {
    const container = document.getElementById('mtfMasterDashboard');
    const handle = document.getElementById('mtfDashDragHandle');
    const btnCollapse = document.getElementById('btnDashCollapse');
    const btnGear = document.getElementById('btnDashCfgGear');
    const btnHide = document.getElementById('btnDashHide');

    if (btnCollapse) {
      btnCollapse.onclick = (e) => {
        e.stopPropagation();
        this.mtfDashConfig.collapsed = !this.mtfDashConfig.collapsed;
        this.saveDashboardConfig();
        if (this.lastMtfDashData) this.renderMTFMasterDashboard(this.lastMtfDashData);
      };
    }

    if (btnGear) {
      btnGear.onclick = (e) => {
        e.stopPropagation();
        this.openDashboardSettings();
      };
    }

    if (btnHide) {
      btnHide.onclick = (e) => {
        e.stopPropagation();
        this.mtfDashConfig.visible = false;
        this.saveDashboardConfig();
        if (container) container.style.display = 'none';
        this.showToast('📊 Đã ẩn MTF Dashboard. Bấm "⚙️ Dash" trên tiêu đề khung HTF để bật lại.');
      };
    }

    // Drag to move freely inside #chartH4
    if (handle && container && this.containerH4) {
      let dragging = false;
      let startX = 0, startY = 0, origLeft = 0, origTop = 0;

      handle.onmousedown = (e) => {
        if (e.target.closest('button')) return;
        e.preventDefault();
        e.stopPropagation();
        dragging = true;
        startX = e.clientX;
        startY = e.clientY;
        origLeft = container.offsetLeft;
        origTop = container.offsetTop;

        const onMove = (ev) => {
          if (!dragging) return;
          const dx = ev.clientX - startX;
          const dy = ev.clientY - startY;
          const maxW = Math.max(20, this.containerH4.clientWidth - container.offsetWidth - 10);
          const maxH = Math.max(20, this.containerH4.clientHeight - container.offsetHeight - 10);
          const nx = Math.max(4, Math.min(maxW, origLeft + dx));
          const ny = Math.max(4, Math.min(maxH, origTop + dy));
          container.style.right = '';
          container.style.bottom = '';
          container.style.left = `${nx}px`;
          container.style.top = `${ny}px`;
          this.mtfDashConfig.position = 'custom';
          this.mtfDashConfig.customX = nx;
          this.mtfDashConfig.customY = ny;
        };

        const onUp = () => {
          if (dragging) {
            dragging = false;
            this.saveDashboardConfig();
          }
          window.removeEventListener('mousemove', onMove);
          window.removeEventListener('mouseup', onUp);
        };

        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
      };
    }
  }

  openDashboardSettings() {
    const modal = document.getElementById('dashSettingsModal');
    if (!modal) return;
    const cfg = this.mtfDashConfig || this.getDefaultDashConfig();

    const setChk = (id, val) => { const el = document.getElementById(id); if (el) el.checked = !!val; };
    const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };

    setChk('dashCfg_visible', cfg.visible);
    setChk('dashCfg_collapsed', cfg.collapsed);
    setVal('dashCfg_position', cfg.position || 'top-left');
    setVal('dashCfg_size', cfg.size || 'small');
    setVal('dashCfg_opacity', cfg.opacity || 92);
    const opVal = document.getElementById('dashCfg_opacityVal');
    if (opVal) opVal.innerText = `${cfg.opacity || 92}%`;
    setChk('dashCfg_showRadar', cfg.showRadar !== false);
    setChk('dashCfg_showFooter', cfg.showFooter !== false);

    modal.classList.add('open');
  }

  closeDashboardSettings() {
    const modal = document.getElementById('dashSettingsModal');
    if (modal) modal.classList.remove('open');
  }

  applyDashboardSettings() {
    const getChk = (id, fb) => { const el = document.getElementById(id); return el ? el.checked : fb; };
    const getVal = (id, fb) => { const el = document.getElementById(id); return el ? el.value : fb; };

    this.mtfDashConfig.visible = getChk('dashCfg_visible', true);
    this.mtfDashConfig.collapsed = getChk('dashCfg_collapsed', false);
    this.mtfDashConfig.position = getVal('dashCfg_position', 'top-left');
    this.mtfDashConfig.size = getVal('dashCfg_size', 'small');
    this.mtfDashConfig.opacity = parseInt(getVal('dashCfg_opacity', '92'), 10) || 92;
    this.mtfDashConfig.showRadar = getChk('dashCfg_showRadar', true);
    this.mtfDashConfig.showFooter = getChk('dashCfg_showFooter', true);

    this.saveDashboardConfig();
    if (this.lastMtfDashData) {
      this.renderMTFMasterDashboard(this.lastMtfDashData);
    } else {
      this.applyDashboardStyleAndPosition();
    }
    this.closeDashboardSettings();
    this.showToast('⚙️ Đã lưu cấu hình MTF Dashboard!');
  }

  resetDashboardSettings() {
    this.mtfDashConfig = this.getDefaultDashConfig();
    this.saveDashboardConfig();
    this.openDashboardSettings();
    if (this.lastMtfDashData) this.renderMTFMasterDashboard(this.lastMtfDashData);
  }

  renderDivergenceMarkers(divergences, tf, customTargetSeries) {
    if (!divergences || divergences.length === 0) return;

    const targetSeries = customTargetSeries || (tf === 'H4' || tf === 'TF1' ? this.seriesH4 : this.seriesM15);
    if (!targetSeries) return;
    const markers = [];

    for (const d of divergences) {
      if (!d || !d.time2) continue;
      const isBull = d.side === 'BUY';
      markers.push({
        time: d.time2,
        position: isBull ? 'belowBar' : 'aboveBar',
        color: isBull ? '#089981' : '#f23645',
        shape: isBull ? 'arrowUp' : 'arrowDown',
        text: `DIV ${d.indicator || ''}`
      });
    }

    if (markers.length > 0) {
      // LightweightCharts MANDATORY: markers must be strictly sorted by time ascending
      markers.sort((a, b) => a.time - b.time);
      const uniqueMarkers = [];
      const seenTimes = new Set();
      for (const m of markers) {
        if (!seenTimes.has(m.time)) {
          seenTimes.add(m.time);
          uniqueMarkers.push(m);
        }
      }
      try {
        targetSeries.setMarkers(uniqueMarkers);
      } catch (e) {
        console.warn('Error setting markers on ' + tf, e);
      }
    }
  }

  renderCopilotBanner(signals) {
    if (!this.copilotBanner) return;
    const sig = signals ? (signals.M15 || signals.H4) : null;
    
    if (sig) {
      const isBull = sig.side === 'BUY';
      const color = isBull ? 'var(--color-bull)' : 'var(--color-bear)';
      this.copilotBanner.style.display = 'flex';
      this.copilotBanner.innerHTML = `
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="font-size:16px;">🤖</span>
          <span style="font-weight:700;color:${color};">${sig.label}</span>
          <span style="font-size:11px;color:var(--text-muted);">| Entry: <b>${sig.entry}</b> | SL: <b>${sig.sl}</b> | TP: <b>${sig.tp1}</b> (1:1.5)</span>
        </div>
        <button class="btn-pos-action" style="background:var(--color-accent);color:white;padding:4px 10px;font-weight:600;" 
          onclick="window.app.applyCopilotSetup('${sig.side}', ${sig.entry}, ${sig.sl}, ${sig.tp1})">
          ⚡ Áp dụng Setup
        </button>
      `;
    } else {
      this.copilotBanner.style.display = 'none';
    }
  }

  renderOrderAndPendingLines(positions, pendingOrders) {
    if (this.orderLines && this.orderLines.length > 0) {
      for (const line of this.orderLines) {
        try {
          this.seriesM15.removePriceLine(line);
        } catch (e) {}
      }
      this.orderLines = [];
    }

    if (positions && positions.length > 0) {
      for (const pos of positions) {
        const isBuy = pos.type === 'BUY';
        const entryLine = this.seriesM15.createPriceLine({
          price: pos.open_price,
          color: isBuy ? '#089981' : '#f23645',
          lineWidth: 2,
          lineStyle: LightweightCharts.LineStyle.Solid,
          title: `${pos.type} ${pos.lots}L @ ${pos.open_price}`
        });
        this.orderLines.push(entryLine);

        if (pos.sl) {
          const slLine = this.seriesM15.createPriceLine({
            price: pos.sl,
            color: '#f23645',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            title: `SL: ${pos.sl}`
          });
          this.orderLines.push(slLine);
        }

        if (pos.tp) {
          const tpLine = this.seriesM15.createPriceLine({
            price: pos.tp,
            color: '#089981',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            title: `TP: ${pos.tp}`
          });
          this.orderLines.push(tpLine);
        }
      }
    }

    if (pendingOrders && pendingOrders.length > 0) {
      for (const pOrder of pendingOrders) {
        const pLine = this.seriesM15.createPriceLine({
          price: pOrder.target_price,
          color: '#f59e0b',
          lineWidth: 2,
          lineStyle: LightweightCharts.LineStyle.Dotted,
          title: `⏳ ${pOrder.type} ${pOrder.lots}L @ ${pOrder.target_price}`
        });
        this.orderLines.push(pLine);

        if (pOrder.sl) {
          const pSlLine = this.seriesM15.createPriceLine({
            price: pOrder.sl,
            color: '#f23645',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            title: `P-SL: ${pOrder.sl}`
          });
          this.orderLines.push(pSlLine);
        }

        if (pOrder.tp) {
          const pTpLine = this.seriesM15.createPriceLine({
            price: pOrder.tp,
            color: '#089981',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            title: `P-TP: ${pOrder.tp}`
          });
          this.orderLines.push(pTpLine);
        }
      }
    }
  }

  updateDynamicSlTpUI() {
    const btn = document.getElementById('btnToggleDynamicSlTp');
    const txt = document.getElementById('dynamicSlTpStatusText');
    if (this.showFutureProjection) {
      if (btn) {
        btn.classList.add('active');
        btn.style.borderColor = '#10b981';
        btn.style.color = '#10b981';
      }
      if (txt) txt.innerText = 'Dynamic SL/TP: BẬT';
    } else {
      if (btn) {
        btn.classList.remove('active');
        btn.style.borderColor = '#64748b';
        btn.style.color = '#94a3b8';
      }
      if (txt) txt.innerText = 'Dynamic SL/TP: TẮT';
      this.clearFutureProjection();
    }
  }

  toggleDynamicSlTp() {
    this.showFutureProjection = !this.showFutureProjection;
    localStorage.setItem('enableDynamicSlTp', this.showFutureProjection ? 'true' : 'false');
    this.updateDynamicSlTpUI();

    if (this.showFutureProjection) {
      this.showToast('🎯 Đã BẬT hiển thị Dynamic SL/TP & Dự báo!');
      if (this.lastForecast) {
        this.renderProbabilisticFutureProjection(this.lastForecast);
      }
    } else {
      this.showToast('🎯 Đã TẮT hiển thị Dynamic SL/TP & Dự báo');
      this.clearFutureProjection();
    }
    return this.showFutureProjection;
  }

  clearFutureProjection() {
    if (this.futureProjectionLines && this.futureProjectionLines.length > 0 && this.seriesM15) {
      for (const line of this.futureProjectionLines) {
        try {
          this.seriesM15.removePriceLine(line);
        } catch (e) {}
      }
      this.futureProjectionLines = [];
    }
    if (this.macroFutureLinesH4 && this.macroFutureLinesH4.length > 0 && this.seriesH4) {
      for (const line of this.macroFutureLinesH4) {
        try {
          this.seriesH4.removePriceLine(line);
        } catch (e) {}
      }
      this.macroFutureLinesH4 = [];
    }
    if (this.seriesFutureCandles) {
      this.seriesFutureCandles.setData([]);
      try { this.seriesFutureCandles.setMarkers([]); } catch (e) {}
    }
    if (this.seriesFutureUpBand) this.seriesFutureUpBand.setData([]);
    if (this.seriesFutureDnBand) this.seriesFutureDnBand.setData([]);
    if (this.seriesFutureMeanLine) this.seriesFutureMeanLine.setData([]);
    if (this.seriesFutureCandlesH4) {
      this.seriesFutureCandlesH4.setData([]);
      try { this.seriesFutureCandlesH4.setMarkers([]); } catch (e) {}
    }
    if (this.seriesFutureUpBandH4) this.seriesFutureUpBandH4.setData([]);
    if (this.seriesFutureDnBandH4) this.seriesFutureDnBandH4.setData([]);
    if (this.seriesFutureMeanLineH4) this.seriesFutureMeanLineH4.setData([]);
  }

  renderProbabilisticFutureProjection(fc) {
    this.lastForecast = fc;
    if (this.futureProjectionLines && this.futureProjectionLines.length > 0 && this.seriesM15) {
      for (const line of this.futureProjectionLines) {
        try {
          this.seriesM15.removePriceLine(line);
        } catch (e) {}
      }
      this.futureProjectionLines = [];
    }
    if (this.macroFutureLinesH4 && this.macroFutureLinesH4.length > 0 && this.seriesH4) {
      for (const line of this.macroFutureLinesH4) {
        try {
          this.seriesH4.removePriceLine(line);
        } catch (e) {}
      }
      this.macroFutureLinesH4 = [];
    }

    if (!this.showFutureProjection || !fc || !fc.future_candles || fc.future_candles.length === 0) {
      this.clearFutureProjection();
      return;
    }

    // 0. Render Tier-1 Macro HTF Future Projected Candles on H4/H1 Left Chart
    if (this.seriesFutureCandlesH4 && fc.macro_future_candles && fc.macro_future_candles.length > 0) {
      const mCandles = fc.macro_future_candles.map(c => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close
      }));
      this.seriesFutureCandlesH4.setData(mCandles);

      const lastMac = fc.macro_future_candles[fc.macro_future_candles.length - 1];
      const mUp = (fc.macro_prob_up_pct ?? fc.prob_up_pct ?? 33.3).toFixed(1);
      const mDn = (fc.macro_prob_down_pct ?? fc.prob_down_pct ?? 33.3).toFixed(1);
      const mDom = fc.macro_dominant_scenario || (parseFloat(mUp) >= parseFloat(mDn) ? 'UP' : 'DOWN');
      const isMacUp = mDom === 'UP' || parseFloat(mUp) >= parseFloat(mDn);

      this.seriesFutureCandlesH4.setMarkers([
        {
          time: lastMac.time,
          position: isMacUp ? 'aboveBar' : 'belowBar',
          color: mDom === 'UP' ? '#10b981' : (mDom === 'DOWN' ? '#ef4444' : '#f59e0b'),
          shape: isMacUp ? 'arrowUp' : 'arrowDown',
          text: `🏛️ HTF +${fc.macro_future_candles.length}B: 🟢UP ${mUp}% | 🔴DN ${mDn}%`
        }
      ]);

      if (this.seriesFutureUpBandH4 && fc.macro_future_up_band) {
        this.seriesFutureUpBandH4.setData(fc.macro_future_up_band);
      }
      if (this.seriesFutureDnBandH4 && fc.macro_future_dn_band) {
        this.seriesFutureDnBandH4.setData(fc.macro_future_dn_band);
      }
      if (this.seriesFutureMeanLineH4 && fc.macro_future_mean_line) {
        this.seriesFutureMeanLineH4.setData(fc.macro_future_mean_line);
      }
    } else if (this.seriesFutureCandlesH4) {
      this.seriesFutureCandlesH4.setData([]);
      if (this.seriesFutureUpBandH4) this.seriesFutureUpBandH4.setData([]);
      if (this.seriesFutureDnBandH4) this.seriesFutureDnBandH4.setData([]);
      if (this.seriesFutureMeanLineH4) this.seriesFutureMeanLineH4.setData([]);
    }

    // 1. Set Future Projected Candlesticks (H bars ahead) on M15/M5 Right Chart
    if (this.seriesFutureCandles) {
      const fCandles = fc.future_candles.map(c => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close
      }));
      this.seriesFutureCandles.setData(fCandles);

      const lastFut = fc.future_candles[fc.future_candles.length - 1];
      const pUp = (fc.prob_up_pct ?? 33.3).toFixed(1);
      const pDn = (fc.prob_down_pct ?? 33.3).toFixed(1);
      const pSw = (fc.prob_sideway_pct ?? 33.4).toFixed(1);
      const domDir = fc.dominant_scenario || (pUp >= pDn ? 'UP' : 'DOWN');
      const isUpDom = domDir === 'UP' || parseFloat(pUp) >= parseFloat(pDn);
      const tacBadge = fc.tactical_status && fc.tactical_status.includes('PULLBACK') ? '🌊HỒI-CHỜ' : '⚡ĐỒNG PHA';

      this.seriesFutureCandles.setMarkers([
        {
          time: lastFut.time,
          position: isUpDom ? 'aboveBar' : 'belowBar',
          color: domDir === 'UP' ? '#10b981' : (domDir === 'DOWN' ? '#ef4444' : '#f59e0b'),
          shape: isUpDom ? 'arrowUp' : 'arrowDown',
          text: `🔮 [${tacBadge}] 🟢UP ${pUp}% | 🔴DN ${pDn}% | ⚪SW ${pSw}%`
        }
      ]);
    }

    // 2. Set Probability Cone Fan Lines (Upper Bullish Target, Lower Bearish Target, Expected Trajectory)
    if (this.seriesFutureUpBand && fc.future_up_band) {
      this.seriesFutureUpBand.setData(fc.future_up_band);
    }
    if (this.seriesFutureDnBand && fc.future_dn_band) {
      this.seriesFutureDnBand.setData(fc.future_dn_band);
    }
    if (this.seriesFutureMeanLine && fc.future_mean_line) {
      this.seriesFutureMeanLine.setData(fc.future_mean_line);
    }

    // 3. Draw Probability Target Price Lines on Right Axis
    if (this.seriesM15 && fc.future_candles.length > 0) {
      const lastFut = fc.future_candles[fc.future_candles.length - 1];
      const pUp = (fc.prob_up_pct ?? 33.3).toFixed(1);
      const pDn = (fc.prob_down_pct ?? 33.3).toFixed(1);
      const pSw = (fc.prob_sideway_pct ?? 33.4).toFixed(1);

      if (lastFut.upper_target) {
        const upLine = this.seriesM15.createPriceLine({
          price: lastFut.upper_target,
          color: 'rgba(16, 185, 129, 0.75)',
          lineWidth: 1,
          lineStyle: LightweightCharts.LineStyle.Dotted,
          title: `🟢 UP ${pUp}% (+${fc.expected_wave_atr || 1.5} ATR)`
        });
        this.futureProjectionLines.push(upLine);
      }
      if (lastFut.lower_target) {
        const dnLine = this.seriesM15.createPriceLine({
          price: lastFut.lower_target,
          color: 'rgba(239, 68, 68, 0.75)',
          lineWidth: 1,
          lineStyle: LightweightCharts.LineStyle.Dotted,
          title: `🔴 DN ${pDn}% | ⚪ SW ${pSw}%`
        });
        this.futureProjectionLines.push(dnLine);
      }
    }
  }

  renderEABasketLines(eaStatus) {
    if (this.eaLines && this.eaLines.length > 0) {
      for (const line of this.eaLines) {
        try {
          this.seriesM15.removePriceLine(line);
        } catch (e) {}
      }
      this.eaLines = [];
    }

    if (!eaStatus) return;

    // BUY BASKET
    if (eaStatus.buy_basket && eaStatus.buy_basket.active_orders > 0) {
      if (eaStatus.buy_basket.be_price > 0) {
        const beLine = this.seriesM15.createPriceLine({
          price: eaStatus.buy_basket.be_price,
          color: '#38bdf8',
          lineWidth: 2,
          lineStyle: LightweightCharts.LineStyle.Dashed,
          title: `BUY BE: ${eaStatus.buy_basket.be_price}`
        });
        this.eaLines.push(beLine);
      }
      if (eaStatus.buy_basket.tp_price > 0) {
        const tpLine = this.seriesM15.createPriceLine({
          price: eaStatus.buy_basket.tp_price,
          color: '#10b981',
          lineWidth: 2,
          lineStyle: LightweightCharts.LineStyle.Dashed,
          title: `BUY TP: ${eaStatus.buy_basket.tp_price} (+${eaStatus.buy_basket.dist_to_tp_pips}p)`
        });
        this.eaLines.push(tpLine);
      }
    }

    // SELL BASKET
    if (eaStatus.sell_basket && eaStatus.sell_basket.active_orders > 0) {
      if (eaStatus.sell_basket.be_price > 0) {
        const beLine = this.seriesM15.createPriceLine({
          price: eaStatus.sell_basket.be_price,
          color: '#f59e0b',
          lineWidth: 2,
          lineStyle: LightweightCharts.LineStyle.Dashed,
          title: `SELL BE: ${eaStatus.sell_basket.be_price}`
        });
        this.eaLines.push(beLine);
      }
      if (eaStatus.sell_basket.tp_price > 0) {
        const tpLine = this.seriesM15.createPriceLine({
          price: eaStatus.sell_basket.tp_price,
          color: '#10b981',
          lineWidth: 2,
          lineStyle: LightweightCharts.LineStyle.Dashed,
          title: `SELL TP: ${eaStatus.sell_basket.tp_price} (+${eaStatus.sell_basket.dist_to_tp_pips}p)`
        });
        this.eaLines.push(tpLine);
      }
    }
  }

  updateTimeframeBadges(macroTf = 'H1', execTf = 'M5') {
    const paneH4Badge = document.querySelector('#paneH4 .timeframe-badge');
    if (paneH4Badge) {
      paneH4Badge.textContent = `${macroTf} (Macro Trend & Filter)`;
    }
    const paneM15Badge = document.querySelector('#paneM15 .timeframe-badge');
    if (paneM15Badge) {
      paneM15Badge.textContent = `${execTf} (Execution & EA Replay)`;
    }
  }

  resizeAll() {
    if (this.chartH4 && this.containerH4) {
      this.chartH4.resize(this.containerH4.clientWidth, this.containerH4.clientHeight);
    }
    if (this.chartTF2 && this.containerTF2) {
      this.chartTF2.resize(this.containerTF2.clientWidth, this.containerTF2.clientHeight);
    }
    if (this.chartM15 && this.containerM15) {
      this.chartM15.resize(this.containerM15.clientWidth, this.containerM15.clientHeight);
    }

    // Stoch Sub-charts
    if (this.chartStoch_H4 && this.containerStoch_H4) {
      this.chartStoch_H4.resize(this.containerH4.clientWidth, this.containerStoch_H4.clientHeight);
    }
    if (this.chartStoch_TF2 && this.containerStoch_TF2) {
      this.chartStoch_TF2.resize(this.containerTF2.clientWidth, this.containerStoch_TF2.clientHeight);
    }
    if (this.chartStoch && this.containerStoch) {
      this.chartStoch.resize(this.containerM15.clientWidth, this.containerStoch.clientHeight);
    }

    // RSI Sub-charts
    if (this.chartRSI_H4 && this.containerRSI_H4) {
      this.chartRSI_H4.resize(this.containerH4.clientWidth, this.containerRSI_H4.clientHeight);
    }
    if (this.chartRSI_TF2 && this.containerRSI_TF2) {
      this.chartRSI_TF2.resize(this.containerTF2.clientWidth, this.containerRSI_TF2.clientHeight);
    }
    if (this.chartRSI && this.containerRSI) {
      this.chartRSI.resize(this.containerM15.clientWidth, this.containerRSI.clientHeight);
    }

    // MACD Sub-charts
    if (this.chartMACD_H4 && this.containerMACD_H4) {
      this.chartMACD_H4.resize(this.containerH4.clientWidth, this.containerMACD_H4.clientHeight);
    }
    if (this.chartMACD_TF2 && this.containerMACD_TF2) {
      this.chartMACD_TF2.resize(this.containerTF2.clientWidth, this.containerMACD_TF2.clientHeight);
    }
    if (this.chartMACD && this.containerMACD) {
      this.chartMACD.resize(this.containerM15.clientWidth, this.containerMACD.clientHeight);
    }

    this.updateAllShiftPins();
    if (window.app && window.app.drawingTools && window.app.drawingTools.renderAll) {
      window.app.drawingTools.renderAll();
    }
  }

  setupDraggableResizers() {
    // Load saved sub-window heights & order from localStorage
    try {
      this.subWindowHeights = JSON.parse(localStorage.getItem('subWindowHeights') || 'null') || { stoch: 70, rsi: 70, macd: 70 };
    } catch (e) {
      this.subWindowHeights = { stoch: 70, rsi: 70, macd: 70 };
    }
    try {
      const savedOrder = JSON.parse(localStorage.getItem('subWindowOrder') || 'null');
      this.subWindowOrder = (Array.isArray(savedOrder) && savedOrder.length === 3) ? savedOrder : ['stoch', 'rsi', 'macd'];
    } catch (e) {
      this.subWindowOrder = ['stoch', 'rsi', 'macd'];
    }

    const subPaneGroups = {
      stoch: ['subChartStoch_H4', 'subChartStoch_TF2', 'subChartStoch'],
      rsi: ['subChartRSI_H4', 'subChartRSI_TF2', 'subChartRSI'],
      macd: ['subChartMACD_H4', 'subChartMACD_TF2', 'subChartMACD']
    };

    // Restore saved heights immediately (Stoch & RSI bounded 0-100: min 70px, can only enlarge!)
    Object.keys(subPaneGroups).forEach(subKey => {
      const minH = (subKey === 'stoch' || subKey === 'rsi') ? 70 : 45;
      const h = Math.max(minH, Math.min(260, Number(this.subWindowHeights[subKey]) || 70));
      this.subWindowHeights[subKey] = h;
      subPaneGroups[subKey].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.height = `${h}px`;
      });
    });

    const bindSyncedResizer = (resizerId, subKey, targetPaneIds, isBelow) => {
      const resizer = document.getElementById(resizerId);
      const targetPanes = targetPaneIds.map(id => document.getElementById(id)).filter(Boolean);
      if (!resizer || targetPanes.length === 0) return;

      let isDragging = false;
      let startY = 0;
      let startHeight = 0;
      let lastHeight = 70;

      resizer.addEventListener('mousedown', (e) => {
        isDragging = true;
        startY = e.clientY;
        startHeight = targetPanes[0].clientHeight;
        lastHeight = startHeight;
        resizer.classList.add('active');
        document.body.style.cursor = 'row-resize';
        document.body.style.userSelect = 'none';
      });

      window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        const deltaY = e.clientY - startY;
        const minH = (subKey === 'stoch' || subKey === 'rsi') ? 70 : 45;
        let newH = isBelow ? startHeight - deltaY : startHeight + deltaY;
        newH = Math.max(minH, Math.min(260, newH));
        lastHeight = newH;
        targetPanes.forEach(pane => {
          pane.style.height = `${newH}px`;
        });
        this.resizeAll();
      });

      window.addEventListener('mouseup', () => {
        if (isDragging) {
          isDragging = false;
          resizer.classList.remove('active');
          document.body.style.cursor = '';
          document.body.style.userSelect = '';
          this.subWindowHeights[subKey] = Math.round(lastHeight);
          try {
            localStorage.setItem('subWindowHeights', JSON.stringify(this.subWindowHeights));
          } catch (err) {}
          this.resizeAll();
        }
      });
    };

    // Resizer 1: Stoch panes
    bindSyncedResizer('resizerH4_1', 'stoch', subPaneGroups.stoch, true);
    bindSyncedResizer('resizerTF2_1', 'stoch', subPaneGroups.stoch, true);
    bindSyncedResizer('resizerM15_1', 'stoch', subPaneGroups.stoch, true);

    // Resizer 2: RSI panes
    bindSyncedResizer('resizerH4_2', 'rsi', subPaneGroups.rsi, true);
    bindSyncedResizer('resizerTF2_2', 'rsi', subPaneGroups.rsi, true);
    bindSyncedResizer('resizerM15_2', 'rsi', subPaneGroups.rsi, true);

    // Resizer 3: MACD panes
    bindSyncedResizer('resizerH4_3', 'macd', subPaneGroups.macd, true);
    bindSyncedResizer('resizerTF2_3', 'macd', subPaneGroups.macd, true);
    bindSyncedResizer('resizerM15_3', 'macd', subPaneGroups.macd, true);

    // Apply saved sub-window order & inject ▲/▼ reorder controls
    this.initSubWindowReorderControls();
    this.applySubWindowOrder();
  }

  initSubWindowReorderControls() {
    const subMap = [
      { subKey: 'stoch', ids: ['subChartStoch_H4', 'subChartStoch_TF2', 'subChartStoch'] },
      { subKey: 'rsi', ids: ['subChartRSI_H4', 'subChartRSI_TF2', 'subChartRSI'] },
      { subKey: 'macd', ids: ['subChartMACD_H4', 'subChartMACD_TF2', 'subChartMACD'] }
    ];

    subMap.forEach(({ subKey, ids }) => {
      ids.forEach(id => {
        const el = document.getElementById(id);
        if (!el || el.querySelector('.sub-reorder-controls')) return;
        const ctrl = document.createElement('div');
        ctrl.className = 'sub-reorder-controls';
        ctrl.innerHTML = `
          <button class="sub-reorder-btn" data-dir="up" title="Đẩy cửa sổ ${subKey.toUpperCase()} lên trên">▲</button>
          <button class="sub-reorder-btn" data-dir="down" title="Đẩy cửa sổ ${subKey.toUpperCase()} xuống dưới">▼</button>
        `;
        ctrl.querySelector('[data-dir="up"]').addEventListener('click', (e) => {
          e.stopPropagation();
          this.moveSubWindow(subKey, -1);
        });
        ctrl.querySelector('[data-dir="down"]').addEventListener('click', (e) => {
          e.stopPropagation();
          this.moveSubWindow(subKey, 1);
        });
        el.appendChild(ctrl);
      });
    });
  }

  moveSubWindow(subKey, delta) {
    const idx = this.subWindowOrder.indexOf(subKey);
    if (idx === -1) return;
    const targetIdx = idx + delta;
    if (targetIdx < 0 || targetIdx >= this.subWindowOrder.length) return;

    const copy = [...this.subWindowOrder];
    const [item] = copy.splice(idx, 1);
    copy.splice(targetIdx, 0, item);
    this.subWindowOrder = copy;

    try {
      localStorage.setItem('subWindowOrder', JSON.stringify(this.subWindowOrder));
    } catch (e) {}

    this.applySubWindowOrder();
    this.showToast(`↕️ Thứ tự sub-window: ${this.subWindowOrder.map(s => s.toUpperCase()).join(' → ')}`);
  }

  applySubWindowOrder() {
    const paneDefs = [
      {
        parentId: 'paneH4',
        pairs: {
          stoch: ['resizerH4_1', 'subChartStoch_H4'],
          rsi: ['resizerH4_2', 'subChartRSI_H4'],
          macd: ['resizerH4_3', 'subChartMACD_H4']
        }
      },
      {
        parentId: 'paneTF2',
        pairs: {
          stoch: ['resizerTF2_1', 'subChartStoch_TF2'],
          rsi: ['resizerTF2_2', 'subChartRSI_TF2'],
          macd: ['resizerTF2_3', 'subChartMACD_TF2']
        }
      },
      {
        parentId: 'paneM15',
        pairs: {
          stoch: ['resizerM15_1', 'subChartStoch'],
          rsi: ['resizerM15_2', 'subChartRSI'],
          macd: ['resizerM15_3', 'subChartMACD']
        }
      }
    ];

    paneDefs.forEach(({ parentId, pairs }) => {
      const parent = document.getElementById(parentId);
      if (!parent) return;
      this.subWindowOrder.forEach(subKey => {
        const [resId, subId] = pairs[subKey] || [];
        const resEl = resId ? document.getElementById(resId) : null;
        const subEl = subId ? document.getElementById(subId) : null;
        if (resEl) parent.appendChild(resEl);
        if (subEl) parent.appendChild(subEl);
      });
    });

    setTimeout(() => this.resizeAll(), 40);
  }

  setupPinPriceButton() {
    window.addEventListener('keydown', (e) => {
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
      if (e.key === 'p' || e.key === 'P') {
        e.preventDefault();
        if (this.btnPinPrice) this.btnPinPrice.click();
      }
    });
  }

  setupContextMenu() {
    const menu = document.getElementById('chartContextMenu');
    const valCurrent = document.getElementById('ctxValCurrent');
    const valCursor = document.getElementById('ctxValCursor');
    const valSetEntry = document.getElementById('ctxSetEntryVal');
    const valSetSL = document.getElementById('ctxSetSLVal');
    const valSetTP = document.getElementById('ctxSetTPVal');
    if (!menu) return;

    const handleContextMenu = (e, series, container, tf) => {
      e.preventDefault();
      
      let priceAtY = null;
      // 1. Try hovered price from crosshair move
      if (tf === 'M15' && this.hoveredPriceM15 && !isNaN(this.hoveredPriceM15)) {
        priceAtY = this.hoveredPriceM15;
      } else if (tf === 'H4' && this.hoveredPriceH4 && !isNaN(this.hoveredPriceH4)) {
        priceAtY = this.hoveredPriceH4;
      }

      // 2. Fallback to direct coordinate-to-price conversion
      if (!priceAtY || isNaN(priceAtY)) {
        const canvas = container.querySelector('canvas') || container;
        const rect = canvas.getBoundingClientRect();
        const y = e.clientY - rect.top;
        try {
          priceAtY = series.coordinateToPrice(y);
        } catch (err) {}
      }

      if (!priceAtY || isNaN(priceAtY)) {
        priceAtY = this.currentPrice;
      }

      const isForex = priceAtY < 10 && priceAtY > 0.1;
      const decimals = isForex ? 5 : 2;
      const formattedCursorPrice = Number(priceAtY).toFixed(decimals);
      const formattedCurrentPrice = Number(this.currentPrice).toFixed(decimals);

      this.cursorPrice = parseFloat(formattedCursorPrice);

      if (valCursor) valCursor.innerText = formattedCursorPrice;
      if (valSetEntry) valSetEntry.innerText = formattedCursorPrice;
      if (valSetSL) valSetSL.innerText = formattedCursorPrice;
      if (valSetTP) valSetTP.innerText = formattedCursorPrice;
      if (valCurrent) valCurrent.innerText = formattedCurrentPrice;

      // Positioning inside viewport
      const menuWidth = 260;
      const menuHeight = 220;
      let posX = e.clientX;
      let posY = e.clientY;

      if (posX + menuWidth > window.innerWidth) posX = window.innerWidth - menuWidth - 10;
      if (posY + menuHeight > window.innerHeight) posY = window.innerHeight - menuHeight - 10;

      menu.style.left = `${posX}px`;
      menu.style.top = `${posY}px`;
      menu.style.display = 'block';
    };

    if (this.containerM15) {
      this.containerM15.addEventListener('contextmenu', (e) => handleContextMenu(e, this.seriesM15, this.containerM15, 'M15'));
    }
    if (this.containerH4) {
      this.containerH4.addEventListener('contextmenu', (e) => handleContextMenu(e, this.seriesH4, this.containerH4, 'H4'));
    }

    // Hide context menu on click outside or Escape
    window.addEventListener('click', () => {
      if (menu) menu.style.display = 'none';
    });
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && menu) menu.style.display = 'none';
    });

    // Action: Copy Cursor Price
    const btnCopyCur = document.getElementById('ctxCopyCursorPrice');
    if (btnCopyCur) {
      btnCopyCur.addEventListener('click', () => {
        this.copyToClipboard(this.cursorPrice, 'Đã sao chép Giá Tại Chuột');
      });
    }

    // Action: Set Entry to Mouse Price
    const btnSetEntry = document.getElementById('ctxSetEntry');
    if (btnSetEntry) {
      btnSetEntry.addEventListener('click', () => {
        const input = document.getElementById('inputPendingPrice');
        const orderTypeSelect = document.getElementById('orderTypeSelect');
        const pendingPriceRow = document.getElementById('pendingPriceRow');
        
        if (input) {
          input.value = this.cursorPrice;
          if (pendingPriceRow) pendingPriceRow.style.display = 'flex';
          
          if (orderTypeSelect && orderTypeSelect.value === 'MARKET') {
            if (this.cursorPrice < this.currentPrice) {
              orderTypeSelect.value = 'BUY_LIMIT';
            } else {
              orderTypeSelect.value = 'SELL_LIMIT';
            }
            if (window.app && window.app.tradePanel) {
              window.app.tradePanel.handleOrderTypeChange();
            }
          }
          this.showToast(`⚡ Đã đặt Entry tại chuột: ${this.cursorPrice}`);
        }
      });
    }

    // Action: Set SL to Mouse Price
    const btnSetSL = document.getElementById('ctxSetSL');
    if (btnSetSL) {
      btnSetSL.addEventListener('click', () => {
        const input = document.getElementById('inputSL');
        if (input) {
          input.value = this.cursorPrice;
          if (window.app && window.app.tradePanel) {
            window.app.tradePanel.recalcLotFromRisk();
          }
          this.showToast(`🛑 Đã đặt Stop Loss tại chuột: ${this.cursorPrice}`);
        }
      });
    }

    // Action: Set TP to Mouse Price
    const btnSetTP = document.getElementById('ctxSetTP');
    if (btnSetTP) {
      btnSetTP.addEventListener('click', () => {
        const input = document.getElementById('inputTP');
        if (input) {
          input.value = this.cursorPrice;
          this.showToast(`🎯 Đã đặt Take Profit tại chuột: ${this.cursorPrice}`);
        }
      });
    }

    // Action: Copy Current Market Price
    const btnCopyCurr = document.getElementById('ctxCopyCurrentPrice');
    if (btnCopyCurr) {
      btnCopyCurr.addEventListener('click', () => {
        const isForex = this.currentPrice < 10 && this.currentPrice > 0.1;
        const decimals = isForex ? 5 : 2;
        this.copyToClipboard(Number(this.currentPrice).toFixed(decimals), 'Đã sao chép Giá Hiện Tại');
      });
    }
  }

  copyToClipboard(text, label = 'Đã sao chép giá') {
    if (!text) return;
    navigator.clipboard.writeText(String(text)).then(() => {
      this.showToast(`📋 ${label}: ${text}`);
    }).catch(() => {
      // Fallback
      const tempInput = document.createElement('input');
      tempInput.value = text;
      document.body.appendChild(tempInput);
      tempInput.select();
      document.execCommand('copy');
      document.body.removeChild(tempInput);
      this.showToast(`📋 ${label}: ${text}`);
    });
  }

  showToast(message) {
    const toast = document.getElementById('appToast');
    if (!toast) return;
    toast.innerText = message;
    toast.classList.add('show');
    if (this._toastTimer) clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      toast.classList.remove('show');
    }, 2200);
  }

  setupResizeObserver() {
    window.addEventListener('resize', () => this.resizeAll());
    if (window.ResizeObserver) {
      const ro = new ResizeObserver(() => this.resizeAll());
      if (this.containerH4) ro.observe(this.containerH4);
      if (this.containerTF2) ro.observe(this.containerTF2);
      if (this.containerM15) ro.observe(this.containerM15);
    }
  }
}


window.MultiChartManager = MultiChartManager;
