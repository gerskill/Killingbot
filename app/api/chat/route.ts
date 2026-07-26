import Anthropic from "@anthropic-ai/sdk";
import { NextRequest } from "next/server";
import { promises as fs } from "fs";
import path from "path";

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

async function getTradesContext(): Promise<string> {
  try {
    const filePath = path.join(process.cwd(), "public", "trades.json");
    const raw = await fs.readFile(filePath, "utf-8");
    const data = JSON.parse(raw);
    const recentTrades = (data.trades ?? []).slice(-10);
    return `
Account balance: $${data.account_balance}
Net P&L: $${data.net_pnl}
Win rate: ${data.win_rate}%
Profit factor: ${data.profit_factor}
Total trades: ${data.total_trades}
Max drawdown: ${data.max_drawdown}%
Recent trades (last 10): ${JSON.stringify(recentTrades, null, 2)}
`;
  } catch {
    return "No trade data available.";
  }
}

export async function POST(req: NextRequest) {
  const { messages } = await req.json();

  if (!process.env.ANTHROPIC_API_KEY) {
    return new Response(
      JSON.stringify({ error: "ANTHROPIC_API_KEY not configured. Add it to .env.local" }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }

  const tradesContext = await getTradesContext();

  const systemPrompt = `You are an expert trading analyst for the Killingbot system — a systematic crypto/forex trading bot using the KB_LOOSE_RR2.5_RR3.0 strategy (EMA 7/21 crossover, Kijun 26, ATR 1.5x multiplier, cooldown 3 bars, risk 1%/trade on a $25,000 account).

Current portfolio data:
${tradesContext}

You analyze performance metrics, suggest strategy improvements, explain drawdowns, and help the trader understand their results. Be concise, data-driven, and use the actual numbers above when relevant. Respond in the same language as the user (French or English).`;

  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      try {
        const response = await client.messages.stream({
          model: "claude-sonnet-4-6",
          max_tokens: 1024,
          system: systemPrompt,
          messages: messages.map((m: { role: string; content: string }) => ({
            role: m.role as "user" | "assistant",
            content: m.content,
          })),
        });

        for await (const chunk of response) {
          if (
            chunk.type === "content_block_delta" &&
            chunk.delta.type === "text_delta"
          ) {
            controller.enqueue(encoder.encode(chunk.delta.text));
          }
        }
        controller.close();
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Unknown error";
        controller.enqueue(encoder.encode(`\n[Error: ${msg}]`));
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
