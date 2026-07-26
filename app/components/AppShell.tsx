"use client";
import { useState } from "react";
import Sidebar, { type View } from "./Sidebar";
import DashboardView from "../views/DashboardView";
import BacktestsView from "../views/BacktestsView";
import StrategiesView from "../views/StrategiesView";
import ChatView from "../views/ChatView";
import TradingViewWidget from "./TradingViewWidget";
import type { DashboardData } from "../types";

interface Props {
  data: DashboardData;
}

const CHART_SYMBOLS: Record<string, string> = {
  "BTC": "BINANCE:BTCUSDT",
  "SOL": "BINANCE:SOLUSDT",
  "ETH": "BINANCE:ETHUSDT",
  "GOLD": "OANDA:XAUUSD",
  "NAS100": "NASDAQ:QQQ",
};

const SYMBOLS = Object.keys(CHART_SYMBOLS);

export default function AppShell({ data }: Props) {
  const [view, setView] = useState<View>("dashboard");
  const [chartSymbol, setChartSymbol] = useState("BTC");

  return (
    <div className="flex h-screen overflow-hidden bg-[#060b14]">
      <Sidebar current={view} onChange={setView} />

      <div className="flex-1 flex flex-col overflow-hidden md:flex-row">
        {/* Main content */}
        <main className="flex-1 overflow-y-auto px-6 py-6 md:pl-8">
          {view === "dashboard" && <DashboardView data={data} />}
          {view === "backtests" && <BacktestsView />}
          {view === "strategies" && <StrategiesView />}
          {view === "chat" && <ChatView />}
        </main>

        {/* TradingView chart — right panel on dashboard/backtests */}
        {(view === "dashboard" || view === "backtests") && (
          <aside className="hidden xl:flex flex-col border-l border-[#1e2d45] bg-[#0a1020]" style={{ width: 520 }}>
            <div className="flex items-center gap-2 px-4 py-3 border-b border-[#1e2d45]">
              <span className="text-xs text-slate-500 uppercase tracking-widest">Chart</span>
              <div className="flex gap-1 ml-auto">
                {SYMBOLS.map((sym) => (
                  <button
                    key={sym}
                    onClick={() => setChartSymbol(sym)}
                    className={`text-xs px-2 py-1 rounded transition-colors ${
                      chartSymbol === sym
                        ? "bg-blue-600 text-white"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {sym}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex-1">
              <TradingViewWidget symbol={CHART_SYMBOLS[chartSymbol]} interval="240" />
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
