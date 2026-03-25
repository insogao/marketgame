const CHART_EPOCH = 1_700_000_000;

const state = {
  session: null,
  chart: null,
  candleSeries: null,
  volumeSeries: null,
  barInterval: "10s",
  colorMode: "cn",
  bars: [],
  trades: [],
  latestTrade: null,
  websocket: null,
  reconnectTimer: null,
  reconnectAttempts: 0,
};

const els = {};

document.addEventListener("DOMContentLoaded", () => {
  cacheElements();
  bindEvents();
  hydrate().catch((error) => {
    console.error("Failed to hydrate session state", error);
    setConnectionState("offline");
  });
  initChart();
  connectWebSocket();
});

function cacheElements() {
  const ids = [
    "session-status",
    "session-details",
    "speed-readout",
    "transport-readout",
    "connection-state",
    "seed-input",
    "symbol-input",
    "duration-input",
    "speed-select",
    "color-mode-select",
    "chart-symbol",
    "chart-legend",
    "last-trade-price",
    "last-trade-meta",
    "best-bid",
    "best-bid-size",
    "best-ask",
    "best-ask-size",
    "bar-count",
    "event-count",
    "trade-tape",
    "accounts-body",
    "chart",
  ];

  for (const id of ids) {
    els[id] = document.getElementById(id);
  }
}

function bindEvents() {
  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.action;
      if (action === "start") {
        runCommand("/api/session/start", {
          seed: Number(els["seed-input"].value || 7),
          symbol: normalizeSymbol(els["symbol-input"].value),
          duration_seconds: Number(els["duration-input"].value || 300),
        });
      } else if (action === "pause") {
        runCommand("/api/session/pause");
      } else if (action === "resume") {
        runCommand("/api/session/resume");
      } else if (action === "reset") {
        runCommand("/api/session/reset");
      }
    });
  });

  els["speed-select"].addEventListener("change", () => {
    runCommand("/api/session/speed", { speed: Number(els["speed-select"].value) });
  });

  els["color-mode-select"].addEventListener("change", () => {
    state.colorMode = String(els["color-mode-select"].value || "cn");
    applyColorScheme();
    renderBars(state.bars);
  });
}

async function hydrate() {
  const response = await fetch("/api/session/state", { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`state request failed: ${response.status}`);
  }
  const payload = await response.json();
  applySnapshot(extractPayload(payload));
  setConnectionState("connected");
}

function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${protocol}//${window.location.host}/ws/session`);
  state.websocket = socket;

  socket.addEventListener("open", () => {
    state.reconnectAttempts = 0;
    setConnectionState("connected");
  });

  socket.addEventListener("message", (event) => {
    try {
      const message = JSON.parse(event.data);
      if (message.type === "snapshot") {
        applySnapshot(extractPayload(message.payload));
      } else if (message.type === "event") {
        applyEvent(extractPayload(message.payload));
      } else if (message.type === "status") {
        applyStatus(extractPayload(message.payload));
      }
    } catch (error) {
      console.error("Failed to process websocket message", error);
    }
  });

  socket.addEventListener("close", () => {
    setConnectionState("disconnected");
    scheduleReconnect();
  });

  socket.addEventListener("error", () => {
    setConnectionState("offline");
  });
}

function scheduleReconnect() {
  if (state.reconnectTimer) {
    return;
  }
  const delay = Math.min(4000, 500 * 2 ** state.reconnectAttempts);
  state.reconnectAttempts += 1;
  state.reconnectTimer = window.setTimeout(() => {
    state.reconnectTimer = null;
    connectWebSocket();
  }, delay);
}

function applySnapshot(snapshot) {
  if (!snapshot) {
    return;
  }

  state.session = snapshot;
  state.barInterval = snapshot.bar_interval || state.barInterval;
  state.bars = Array.isArray(snapshot.bars) ? snapshot.bars.slice() : state.bars;
  state.trades = getTradesFromSnapshot(snapshot);
  state.latestTrade = snapshot.latest_trade || state.latestTrade;

  renderHeader(snapshot);
  renderLatestMarket(snapshot);
  renderBars(state.bars);
  renderTrades(state.trades);
  renderAccounts(snapshot.agent_accounts || {});
}

function applyEvent(event) {
  if (!event) {
    return;
  }

  if (event.event_type === "TRADE_PRINT") {
    const trade = normalizeTrade(event);
    state.latestTrade = trade;
    state.trades = [trade, ...state.trades.filter((item) => item.trade_id !== trade.trade_id)].slice(0, 24);
    state.bars = upsertBarFromTrade(state.bars, trade);
    prependTrade(trade);
    renderBars(state.bars);
    renderLatestMarket({
      latest_trade: trade,
      quote: state.session?.quote || null,
      bars: state.bars,
      processed_events: (state.session?.processed_events || 0) + 1,
    });
  } else if (event.event_type === "QUOTE") {
    const quote = normalizeQuote(event);
    state.session = {
      ...(state.session || {}),
      quote,
    };
    renderLatestMarket({
      latest_trade: state.latestTrade,
      quote,
      bars: state.bars,
      processed_events: state.session?.processed_events || 0,
    });
  } else if (event.event_type === "SESSION_STATE") {
    applyStatus(event.payload);
  }
}

function applyStatus(payload) {
  if (!payload) {
    return;
  }
  state.session = {
    ...(state.session || {}),
    ...payload,
  };
  renderHeader(state.session);
}

function renderHeader(snapshot) {
  const status = String(snapshot.status || "idle");
  els["session-status"].textContent = titleCase(status);
  els["session-details"].textContent = [
    snapshot.session_id ? `Session ${snapshot.session_id}` : "Waiting for a session.",
    snapshot.symbol ? `Symbol ${snapshot.symbol}` : null,
  ]
    .filter(Boolean)
    .join(" | ");
  els["speed-readout"].textContent = `${Number(snapshot.speed || 1).toFixed(1)}x`;
  els["transport-readout"].textContent = `${Number(snapshot.processed_events || 0)} events processed`;
  els["chart-symbol"].textContent = snapshot.symbol || "FOO";
  els["chart-legend"].textContent = `${state.barInterval} candles with volume below`;
  els["duration-input"].value = String(snapshot.duration_seconds || 300);
  els["bar-count"].textContent = String(Array.isArray(snapshot.bars) ? snapshot.bars.length : 0);
  els["event-count"].textContent = `${Number(snapshot.processed_events || 0)} events processed`;
  els["speed-select"].value = String(snapshot.speed || 1);
}

function renderLatestMarket(snapshot) {
  const latestTrade = normalizeTrade(snapshot.latest_trade || state.latestTrade);
  const quote = normalizeQuote(snapshot.quote || state.session?.quote);

  if (latestTrade) {
    els["last-trade-price"].textContent = formatMoney(latestTrade.price);
    els["last-trade-meta"].textContent = `${formatQty(latestTrade.qty)} @ ${formatClock(latestTrade.ts)} | ${latestTrade.symbol}`;
  } else {
    els["last-trade-price"].textContent = "--";
    els["last-trade-meta"].textContent = "Awaiting trade prints.";
  }

  if (quote) {
    els["best-bid"].textContent = quote.best_bid == null ? "--" : formatMoney(quote.best_bid);
    els["best-ask"].textContent = quote.best_ask == null ? "--" : formatMoney(quote.best_ask);
    els["best-bid-size"].textContent = `Size ${formatQty(quote.bid_size || 0)}`;
    els["best-ask-size"].textContent = `Size ${formatQty(quote.ask_size || 0)}`;
  }
}

function renderTrades(trades) {
  els["trade-tape"].replaceChildren(...trades.slice(0, 24).map(createTradeRow));
}

function prependTrade(trade) {
  const row = createTradeRow(trade);
  const tape = els["trade-tape"];
  tape.prepend(row);
  while (tape.children.length > 24) {
    tape.removeChild(tape.lastElementChild);
  }
}

function renderAccounts(accounts) {
  const rows = Object.entries(accounts)
    .map(([agentId, account]) => {
      const cash = Number(account.cash ?? 0);
      const position = account.positions || {};
      const openOrders = Array.isArray(account.open_orders) ? account.open_orders.length : 0;
      return `
        <tr>
          <td>${escapeHtml(agentId)}</td>
          <td class="${cash < 0 ? "negative" : "positive"}">${formatMoney(cash)}</td>
          <td>${escapeHtml(renderPositions(position))}</td>
          <td>${formatQty(openOrders)}</td>
        </tr>
      `;
    })
    .join("");
  els["accounts-body"].innerHTML = rows || `<tr><td colspan="4">No accounts available yet.</td></tr>`;
}

function renderBars(bars) {
  if (!state.candleSeries || !state.volumeSeries) {
    return;
  }
  const mapped = bars.map((bar) => ({
    time: normalizeChartTime(bar.end_ts ?? bar.ts ?? bar.time),
    open: Number(bar.open),
    high: Number(bar.high),
    low: Number(bar.low),
    close: Number(bar.close),
  }));
  state.candleSeries.setData(mapped);
  const volumeData = bars.map((bar) => ({
    time: normalizeChartTime(bar.end_ts ?? bar.ts ?? bar.time),
    value: Number(bar.volume || 0),
    color: Number(bar.close) >= Number(bar.open) ? currentPalette().upVolume : currentPalette().downVolume,
  }));
  state.volumeSeries.setData(volumeData);
}

function initChart() {
  if (!window.LightweightCharts || !els.chart) {
    if (els.chart) {
      els.chart.textContent = "Chart library failed to load.";
    }
    return;
  }

  const chart = window.LightweightCharts.createChart(els.chart, {
    width: els.chart.clientWidth,
    height: Math.max(420, els.chart.clientHeight),
    layout: {
      background: { color: "rgba(0, 0, 0, 0)" },
      textColor: "#d8e3f4",
      fontFamily: '"Space Grotesk", "Segoe UI", sans-serif',
    },
    grid: {
      vertLines: { color: "rgba(133, 154, 193, 0.08)" },
      horzLines: { color: "rgba(133, 154, 193, 0.08)" },
    },
    rightPriceScale: { borderColor: "rgba(133, 154, 193, 0.18)" },
    timeScale: {
      borderColor: "rgba(133, 154, 193, 0.18)",
      timeVisible: true,
      secondsVisible: true,
    },
    crosshair: {
      mode: window.LightweightCharts.CrosshairMode.Normal,
    },
  });

  const candleSeries = chart.addCandlestickSeries({
    priceLineVisible: false,
    lastValueVisible: false,
  });

  const volumeSeries = chart.addHistogramSeries({
    priceScaleId: "",
    priceFormat: {
      type: "volume",
    },
    priceLineVisible: false,
    lastValueVisible: false,
    color: "#76d0ff",
    base: 0,
  });
  volumeSeries.priceScale().applyOptions({
    scaleMargins: {
      top: 0.72,
      bottom: 0,
    },
  });

  chart.timeScale().fitContent();

  state.chart = chart;
  state.candleSeries = candleSeries;
  state.volumeSeries = volumeSeries;
  applyColorScheme();

  window.addEventListener("resize", () => {
    chart.applyOptions({
      width: els.chart.clientWidth,
      height: Math.max(420, els.chart.clientHeight),
    });
  });
}

function upsertBarFromTrade(bars, trade) {
  if (!trade) {
    return bars;
  }

  const intervalSeconds = intervalToSeconds(state.barInterval);
  const bucketStart = Math.floor(Number(trade.ts) / intervalSeconds) * intervalSeconds;
  const bucketEnd = bucketStart + intervalSeconds;
  const time = normalizeChartTime(bucketEnd);
  const price = Number(trade.price);
  const qty = Number(trade.qty || 0);
  const last = bars[bars.length - 1];

  if (!last) {
    return [
      {
        time,
        start_ts: bucketStart,
        end_ts: bucketEnd,
        open: price,
        high: price,
        low: price,
        close: price,
        volume: qty,
      },
    ];
  }

  const lastTime = normalizeChartTime(last.end_ts ?? last.ts ?? last.time);
  if (time < lastTime) {
    return bars;
  }

  if (time === lastTime) {
    const updated = {
      ...last,
      high: Math.max(Number(last.high), price),
      low: Math.min(Number(last.low), price),
      close: price,
      volume: Number(last.volume || 0) + qty,
    };
    return [...bars.slice(0, -1), updated];
  }

  return [
    ...bars,
    {
      time,
      start_ts: bucketStart,
      end_ts: bucketEnd,
      open: price,
      high: price,
      low: price,
      close: price,
      volume: qty,
    },
  ];
}

async function runCommand(path, body) {
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : "{}",
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.message || `Request failed: ${response.status}`);
    }
    const data = extractPayload(payload);
    if (data) {
      applyStatus(data);
      if (data.latest_trade || data.quote || data.bars) {
        applySnapshot(data);
      }
    }
  } catch (error) {
    console.error(error);
  }
}

function extractPayload(value) {
  if (!value) {
    return value;
  }
  if (value.payload && typeof value.payload === "object") {
    return value.payload;
  }
  return value;
}

function getTradesFromSnapshot(snapshot) {
  if (!snapshot) {
    return [];
  }
  if (Array.isArray(snapshot.trades)) {
    return snapshot.trades.map(normalizeTrade).filter(Boolean).reverse();
  }
  if (state.latestTrade) {
    return [state.latestTrade];
  }
  return [];
}

function createTradeRow(trade) {
  const row = document.createElement("div");
  row.className = `trade-row trade-row--${normalizeSide(trade.side)}`;
  row.innerHTML = `
    <strong>${escapeHtml(formatMoney(trade.price))}</strong>
    <span>${escapeHtml(trade.symbol || "FOO")} | ${escapeHtml(formatClock(trade.ts))}</span>
    <span>${escapeHtml(formatQty(trade.qty))}</span>
    <span>${escapeHtml(normalizeSide(trade.side).toUpperCase())}</span>
  `;
  return row;
}

function normalizeTrade(trade) {
  if (!trade || typeof trade !== "object") {
    return null;
  }
  return {
    trade_id: trade.trade_id || trade.event_id || trade.id || "",
    symbol: trade.symbol || trade.payload?.symbol || "",
    price: Number(trade.price ?? trade.payload?.price ?? 0),
    qty: Number(trade.qty ?? trade.payload?.qty ?? 0),
    ts: Number(trade.ts ?? trade.payload?.ts ?? 0),
    side: trade.side || trade.payload?.side || "buy",
    buy_order_id: trade.buy_order_id || trade.payload?.buy_order_id || "",
    sell_order_id: trade.sell_order_id || trade.payload?.sell_order_id || "",
  };
}

function normalizeQuote(quote) {
  if (!quote || typeof quote !== "object") {
    return null;
  }
  return {
    symbol: quote.symbol || quote.payload?.symbol || "",
    best_bid: quote.best_bid ?? quote.bid ?? quote.payload?.bid ?? null,
    best_ask: quote.best_ask ?? quote.ask ?? quote.payload?.ask ?? null,
    bid_size: Number(quote.bid_size ?? quote.payload?.bid_size ?? 0),
    ask_size: Number(quote.ask_size ?? quote.payload?.ask_size ?? 0),
    ts: Number(quote.ts ?? quote.payload?.ts ?? 0),
  };
}

function normalizeSymbol(value) {
  return String(value || "FOO").trim().toUpperCase().slice(0, 16) || "FOO";
}

function normalizeSide(value) {
  const side = String(value || "").toLowerCase();
  return side === "sell" ? "sell" : "buy";
}

function setConnectionState(value) {
  els["connection-state"].textContent = titleCase(value);
}

function titleCase(value) {
  return String(value)
    .replace(/[_-]/g, " ")
    .split(" ")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatMoney(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number)) {
    return "--";
  }
  return number.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatQty(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number)) {
    return "--";
  }
  return number.toLocaleString();
}

function formatClock(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number)) {
    return "--";
  }
  const minutes = Math.floor(number / 60);
  const seconds = Math.floor(number % 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function normalizeTime(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number) || number <= 0) {
    return 1;
  }
  return number;
}

function normalizeChartTime(value) {
  return CHART_EPOCH + normalizeTime(value);
}

function intervalToSeconds(interval) {
  const value = String(interval || "10s");
  if (value.endsWith("s")) {
    return Number(value.slice(0, -1)) || 10;
  }
  if (value.endsWith("m")) {
    return (Number(value.slice(0, -1)) || 1) * 60;
  }
  if (value.endsWith("h")) {
    return (Number(value.slice(0, -1)) || 1) * 3600;
  }
  return Number(value) || 10;
}

function currentPalette() {
  if (state.colorMode === "intl") {
    return {
      up: "#72f0a3",
      down: "#ff6b6b",
      upVolume: "rgba(114, 240, 163, 0.72)",
      downVolume: "rgba(255, 107, 107, 0.72)",
    };
  }
  return {
    up: "#ff5b7f",
    down: "#3ddc97",
    upVolume: "rgba(255, 91, 127, 0.72)",
    downVolume: "rgba(61, 220, 151, 0.72)",
  };
}

function applyColorScheme() {
  if (!state.candleSeries || !state.volumeSeries) {
    return;
  }
  const palette = currentPalette();
  state.candleSeries.applyOptions({
    upColor: palette.up,
    downColor: palette.down,
    borderUpColor: palette.up,
    borderDownColor: palette.down,
    wickUpColor: palette.up,
    wickDownColor: palette.down,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  state.volumeSeries.applyOptions({
    priceLineVisible: false,
    lastValueVisible: false,
  });
}

function renderPositions(positions) {
  const entries = Object.entries(positions || {});
  if (!entries.length) {
    return "Flat";
  }
  return entries
    .map(([symbol, qty]) => `${symbol}:${Number(qty).toLocaleString()}`)
    .join(" ");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
