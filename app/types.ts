import type { Trade } from "./components/TradesTable";

export interface DashboardData {
  updated_at: string;
  account_balance: number;
  net_pnl: number;
  win_rate: number;
  profit_factor: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  max_drawdown: number;
  expectancy: number;
  trades: Trade[];
}
