#!/bin/bash
# Auto-lance TradingView en mode debug (CDP port 9222)
# Appelé automatiquement par le MCP Claude au démarrage
PORT="${1:-9222}"
pkill -f "TradingView.app/Contents/MacOS/TradingView" 2>/dev/null
sleep 2
"/Applications/TradingView.app/Contents/MacOS/TradingView" --remote-debugging-port=$PORT &
echo "TradingView lancé en mode debug (port $PORT) — PID: $!"
