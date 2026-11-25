# EMA 9 / 21 Crossover + Buy/Sell Signals
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
