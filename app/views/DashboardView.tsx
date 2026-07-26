import StatCard from "../components/StatCard";
import TradesTable from "../components/TradesTable";
import PnLChart from "../components/PnLChart";
import SetupBreakdown from "../components/SetupBreakdown";
import type { DashboardData } from "../types";

export default function DashboardView({ data }: { data: DashboardData }) {
  const pnlSign = data.net_pnl >= 0 ? "+" : "";
  const updatedAt = new Date(data.updated_at).toLocaleString("fr-FR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-slate-500 uppercase tracking-widest">
          <span>KB_LOOSE_RR2.5_RR3.0</span>
          <span className="text-slate-600">·</span>
          <span>Risk 1%/trade · $25,000 base</span>
        </div>
        <span className="text-xs text-slate-600">màj {updatedAt}</span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Net P&L"
          value={`${pnlSign}$${Math.abs(data.net_pnl).toLocaleString("en-US", { minimumFractionDigits: 0 })}`}
          sub={`${pnlSign}${((data.net_pnl / 25000) * 100).toFixed(1)}% depuis $25k`}
          trend={data.net_pnl >= 0 ? "up" : "down"}
          accent={data.net_pnl >= 0 ? "text-emerald-400" : "text-red-400"}
        />
        <StatCard
          label="Win Rate"
          value={`${data.win_rate}%`}
          sub={`${data.winning_trades}W / ${data.losing_trades}L — ${data.total_trades} trades`}
          trend={data.win_rate >= 50 ? "up" : "down"}
        />
        <StatCard
          label="Profit Factor"
          value={data.profit_factor > 0 ? data.profit_factor.toFixed(2) : "—"}
          sub="Target: 2.0+"
          trend={data.profit_factor >= 2 ? "up" : "neutral"}
        />
        <StatCard
          label="Max Drawdown"
          value={data.max_drawdown > 0 ? `-${data.max_drawdown.toFixed(1)}%` : "—"}
          sub="depuis $25k"
          trend="neutral"
        />
      </div>

      <PnLChart trades={data.trades} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <SetupBreakdown trades={data.trades} />
        </div>
        <div className="flex flex-col gap-4">
          <StatCard label="Expectancy" value={data.expectancy ? `+$${data.expectancy.toFixed(2)}` : "—"} sub="par trade" trend="up" accent="text-blue-400" />
          <StatCard label="Sharpe" value="7.51" sub="KB_1h benchmark" trend="up" />
          <StatCard label="Stratégie" value="KB_LOOSE" sub="RR2.5×RR3.0" trend="up" />
        </div>
      </div>

      <TradesTable trades={data.trades} />

      <div className="flex flex-wrap gap-2 text-xs">
        <span className="text-slate-600">Active strategy:</span>
        {["KB_LOOSE_RR2.5_RR3.0", "EMA 7/21", "Kijun 26", "ATR 1.5x", "Cooldown 3"].map((tag) => (
          <span key={tag} className="px-2 py-0.5 rounded border border-[#1e2d45] text-slate-400">{tag}</span>
        ))}
      </div>
    </div>
  );
}
