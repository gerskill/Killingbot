"use client";
import { useEffect, useRef } from "react";

interface Props {
  symbol?: string;
  interval?: string;
}

export default function TradingViewWidget({ symbol = "BINANCE:BTCUSDT", interval = "240" }: Props) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current || container.current.querySelector("iframe")) return;

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.type = "text/javascript";
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol,
      interval,
      timezone: "Europe/Paris",
      theme: "dark",
      style: "1",
      locale: "fr",
      hide_side_toolbar: false,
      allow_symbol_change: true,
      studies: ["RSI@tv-basicstudies", "MASimple@tv-basicstudies"],
      support_host: "https://www.tradingview.com",
      backgroundColor: "#0d1526",
      gridColor: "#1e2d45",
    });

    container.current.appendChild(script);
  }, [symbol, interval]);

  return (
    <div className="tradingview-widget-container" ref={container} style={{ height: "100%", width: "100%" }}>
      <div className="tradingview-widget-container__widget" style={{ height: "100%", width: "100%" }} />
    </div>
  );
}
