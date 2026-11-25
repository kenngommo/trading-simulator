@echo off
chcp 65001 >nul
title Quan Su Chien Luoc - Live Realtime Forecast Radar (H4/H1 + M15/M5)
echo ===============================================================================
echo   QUAN SU CHIEN LUOC - LIVE REALTIME FORECAST RADAR (H4 ANCHOR + M15 TRIGGER)
echo ===============================================================================
python -X utf8 live_forecast_radar.py --symbols XAUUSD,EURUSD,GBPUSD,USDJPY,GBPJPY,BTCUSD --tf H4_M15 --loop 60 --notify
pause
