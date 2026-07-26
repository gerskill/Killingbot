"use client";
import { useRef, useState } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const SUGGESTIONS = [
  "Analyse mon win rate actuel",
  "Comment améliorer le profit factor ?",
  "Explique le drawdown maximum",
  "Quand activer KB_15m vs KB_1h ?",
];

export default function ChatView() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function send(text: string) {
    if (!text.trim() || loading) return;

    const userMsg: Message = { role: "user", content: text };
    const next = [...messages, userMsg];
    setMessages(next);
    setInput("");
    setLoading(true);

    const assistantMsg: Message = { role: "assistant", content: "" };
    setMessages([...next, assistantMsg]);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: next }),
      });

      if (!res.ok || !res.body) {
        const err = await res.json().catch(() => ({ error: "Erreur serveur" }));
        setMessages([...next, { role: "assistant", content: `❌ ${err.error}` }]);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let full = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        full += decoder.decode(value, { stream: true });
        setMessages([...next, { role: "assistant", content: full }]);
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
      }
    } catch {
      setMessages([...next, { role: "assistant", content: "❌ Connexion échouée. Vérifiez ANTHROPIC_API_KEY dans .env.local" }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-slate-100">Claude IA — Analyste Trading</h2>
        <p className="text-sm text-slate-500 mt-0.5">Analyse contextuelle basée sur vos données réelles</p>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 pr-1 mb-4">
        {messages.length === 0 && (
          <div className="space-y-6">
            <div className="rounded-xl border border-blue-500/20 bg-blue-900/10 p-5">
              <p className="text-sm text-blue-300">
                ✦ Claude a accès à vos métriques live (P&L, win rate, drawdown, trades récents).
                Posez des questions sur votre performance ou vos stratégies.
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-widest mb-3">Suggestions</p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="text-sm px-3 py-2 rounded-lg border border-[#1e2d45] text-slate-300 hover:bg-[#1e2d45]/50 hover:text-slate-100 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-[#0d1526] border border-[#1e2d45] text-slate-200"
              }`}
            >
              {msg.role === "assistant" && msg.content === "" && loading ? (
                <span className="flex gap-1">
                  <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:300ms]" />
                </span>
              ) : msg.content}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); send(input); }}
        className="flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Posez une question sur votre trading..."
          className="flex-1 rounded-xl border border-[#1e2d45] bg-[#0d1526] px-4 py-3 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/50"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="px-5 py-3 rounded-xl bg-blue-600 text-white text-sm font-medium disabled:opacity-40 hover:bg-blue-500 transition-colors"
        >
          Envoyer
        </button>
      </form>
    </div>
  );
}
