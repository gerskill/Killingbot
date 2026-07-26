const BACKTESTS = [
  {
    id: "btc-4h-ppst-adx",
    name: "PP-ST + EMA200 + ADX≥20",
    symbol: "BTC/USDT",
    timeframe: "4H",
    period: "2020–2026",
    ret: "+2947%",
    dd: "24.53%",
    pf: "2.52",
    trades: 59,
    status: "champion" as const,
    badge: "⭐ BEST",
  },
  {
    id: "btc-4h-ppst",
    name: "PP-ST + EMA200",
    symbol: "BTC/USDT",
    timeframe: "4H",
    period: "2020–2026",
    ret: "+2039%",
    dd: "26.15%",
    pf: "2.09",
    trades: 71,
    status: "validated" as const,
    badge: "✓ Validé",
  },
  {
    id: "kb-loose-rr2.5",
    name: "KB_LOOSE_RR2.5_RR3.0",
    symbol: "MULTI",
    timeframe: "1H",
    period: "2024–2026",
    ret: "+8.0%/mois",
    dd: "12.2%",
    pf: "—",
    trades: 231,
    status: "validated" as const,
    badge: "✓ Top Sharpe",
  },
  {
    id: "sol-daily",
    name: "EMA × Kijun Trailing",
    symbol: "SOL/USDT",
    timeframe: "Daily",
    period: "2023+",
    ret: "+7.45%/mois",
    dd: "21.82%",
    pf: "1.984",
    trades: 0,
    status: "validated" as const,
    badge: "✓ Validé",
  },
  {
    id: "wms-v2",
    name: "WMS Score v2.1 (multi-indicateurs)",
    symbol: "BTC/USDT",
    timeframe: "4H",
    period: "2020–2026",
    ret: "-53.77%",
    dd: "70%",
    pf: "0.22",
    trades: 93,
    status: "failed" as const,
    badge: "✗ Échec",
  },
];

const statusStyle = {
  champion: "bg-yellow-500/10 text-yellow-300 border border-yellow-500/30",
  validated: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30",
  failed: "bg-red-500/10 text-red-400 border border-red-500/30",
};

export default function BacktestsView() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-100">Résultats de Backtests</h2>
        <p className="text-sm text-slate-500 mt-1">{BACKTESTS.length} stratégies testées — triées par performance</p>
      </div>

      <div className="space-y-3">
        {BACKTESTS.map((bt) => (
          <div key={bt.id} className="rounded-xl border border-[#1e2d45] bg-[#0d1526] p-5">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-slate-100">{bt.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusStyle[bt.status]}`}>
                    {bt.badge}
                  </span>
                </div>
                <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                  <span>{bt.symbol}</span>
                  <span>·</span>
                  <span>{bt.timeframe}</span>
                  <span>·</span>
                  <span>{bt.period}</span>
                  {bt.trades > 0 && <><span>·</span><span>{bt.trades} trades</span></>}
                </div>
              </div>

              <div className="grid grid-cols-3 gap-6 text-right shrink-0">
                <div>
                  <p className="text-xs text-slate-500 mb-0.5">Retour</p>
                  <p className={`font-bold tabular-nums text-sm ${bt.status === "failed" ? "text-red-400" : "text-emerald-400"}`}>{bt.ret}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-0.5">DD max</p>
                  <p className="font-bold tabular-nums text-sm text-slate-200">{bt.dd}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-0.5">Profit Factor</p>
                  <p className="font-bold tabular-nums text-sm text-slate-200">{bt.pf}</p>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-[#1e2d45] bg-[#0d1526]/50 p-5">
        <p className="text-xs text-slate-500 font-medium uppercase tracking-widest mb-3">Règle clé</p>
        <p className="text-sm text-slate-300">
          TP fixe = mauvais sur BTC. Fermeture sur reversal PP-ST capture +200–400% par trade.
          Aucun script TradingView "My Scripts" ne bat <code className="text-blue-300 bg-blue-900/20 px-1 rounded">pp_st_btc_4h_final.pine</code>.
        </p>
      </div>
    </div>
  );
}
