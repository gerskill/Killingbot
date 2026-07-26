import { promises as fs } from "fs";
import path from "path";
import AppShell from "./components/AppShell";
import type { DashboardData } from "./types";

export const revalidate = 60;

async function getData(): Promise<DashboardData> {
  const filePath = path.join(process.cwd(), "public", "trades.json");
  try {
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return {
      updated_at: new Date().toISOString(),
      account_balance: 25000,
      net_pnl: 0,
      win_rate: 0,
      profit_factor: 0,
      total_trades: 0,
      winning_trades: 0,
      losing_trades: 0,
      max_drawdown: 0,
      expectancy: 0,
      trades: [],
    };
  }
}

export default async function Page() {
  const data = await getData();
  return <AppShell data={data} />;
}
