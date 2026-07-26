const STRATEGIES = [
  {
    id: "kb-loose-rr2.5-rr3",
    name: "KB_LOOSE_RR2.5_RR3.0",
    file: "pine_scripts/strategies/kb_sovereign_v1.pine",
    ret: "8.0%/mois",
    wr: "66%",
    sharpe: 7.06,
    dd: "-12.2%",
    trades: 231,
    rank: 1,
    tags: ["EMA 7/21", "Kijun 26", "ATR 1.5x"],
  },
  {
    id: "kb-1h",
    name: "KB_1h",
    file: "pine_scripts/strategies/killingbot_intraday_v1.pine",
    ret: "7.9%/mois",
    wr: "67%",
    sharpe: 7.51,
    dd: "-6.1%",
    trades: 420,
    rank: 2,
    tags: ["1H", "EMA 7/21", "Cooldown 3"],
  },
  {
    id: "kb-15m",
    name: "KB_15m",
    file: "pine_scripts/strategies/killingbot_intraday_v1.pine",
    ret: "7.9%/mois",
    wr: "67%",
    sharpe: 7.57,
    dd: "-5.7%",
    trades: 414,
    rank: 4,
    tags: ["15m", "Lowest DD"],
  },
  {
    id: "pp-st-btc-4h",
    name: "PP-ST + EMA200 + ADX",
    file: "pp_st_btc_4h_final.pine",
    ret: "+2947% (2020–2026)",
    wr: "—",
    sharpe: 0,
    dd: "-24.53%",
    trades: 59,
    rank: 0,
    tags: ["BTC 4H", "ADX≥20", "Trailing"],
    champion: true,
  },
  {
    id: "kb-loose-rsi",
    name: "KB_LOOSE_RSI",
    file: "pine_scripts/strategies/kb_sovereign_v1.pine",
    ret: "7.0%/mois",
    wr: "70%",
    sharpe: 8.16,
    dd: "-10.4%",
    trades: 230,
    rank: 10,
    tags: ["RSI filter", "Best Sharpe"],
  },
  {
    id: "stoic-confluence",
    name: "STOIC Confluence",
    file: "pine_scripts/strategies/stoic_confluence_strategy.pine",
    ret: "—",
    wr: "—",
    sharpe: 0,
    dd: "—",
    trades: 0,
    rank: 99,
    tags: ["Multi-TF", "Spring", "Wyckoff"],
    experimental: true,
  },
];

export default function StrategiesView() {
  const sorted = [...STRATEGIES].sort((a, b) => a.rank - b.rank);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-100">Bibliothèque de Stratégies</h2>
        <p className="text-sm text-slate-500 mt-1">{STRATEGIES.length} stratégies — params communs: EMA 7/21, Kijun 26, ATR 14 mult 1.5, Cooldown 3</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {sorted.map((s) => (
          <div
            key={s.id}
            className={`rounded-xl border p-5 ${
              s.champion
                ? "border-yellow-500/40 bg-yellow-900/10"
                : s.experimental
                ? "border-purple-500/30 bg-purple-900/10"
                : "border-[#1e2d45] bg-[#0d1526]"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="flex items-center gap-2">
                  {s.champion && <span className="text-xs bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 px-2 py-0.5 rounded-full">⭐ CHAMPION</span>}
                  {s.experimental && <span className="text-xs bg-purple-500/20 text-purple-300 border border-purple-500/30 px-2 py-0.5 rounded-full">🔬 EXPÉRIMENTAL</span>}
                  {!s.champion && !s.experimental && s.rank > 0 && (
                    <span className="text-xs text-slate-500">#{s.rank}</span>
                  )}
                </div>
                <p className="font-semibold text-slate-100 mt-1">{s.name}</p>
                <p className="text-xs text-slate-500 mt-0.5 font-mono">{s.file}</p>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3 mt-4 text-center">
              <div>
                <p className="text-xs text-slate-500">Retour</p>
                <p className="font-bold text-sm text-emerald-400 mt-0.5">{s.ret}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Win Rate</p>
                <p className="font-bold text-sm text-slate-200 mt-0.5">{s.wr}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Sharpe</p>
                <p className="font-bold text-sm text-blue-400 mt-0.5">{s.sharpe > 0 ? s.sharpe.toFixed(2) : "—"}</p>
              </div>
            </div>

            <div className="flex flex-wrap gap-1.5 mt-4">
              {s.tags.map((tag) => (
                <span key={tag} className="text-xs px-2 py-0.5 rounded border border-[#1e2d45] text-slate-400">{tag}</span>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-[#1e2d45] bg-[#0d1526]/50 p-5">
        <p className="text-xs text-slate-500 font-medium uppercase tracking-widest mb-3">Params communs — Top Strategies</p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm text-slate-300">
          {[
            ["EMA fast/slow", "7/21"],
            ["Kijun", "26"],
            ["ATR", "14, mult 1.5"],
            ["EMA min sep.", "0.15%"],
            ["Cooldown", "3 bars"],
            ["ATR min", "0.3%"],
          ].map(([k, v]) => (
            <div key={k} className="flex justify-between gap-2">
              <span className="text-slate-500">{k}</span>
              <span className="font-mono text-slate-200">{v}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
