"use client";
import { useState } from "react";

export type View = "dashboard" | "backtests" | "strategies" | "chat";

interface Props {
  current: View;
  onChange: (v: View) => void;
}

const NAV: { id: View; label: string; icon: string }[] = [
  { id: "dashboard", label: "Dashboard", icon: "⬛" },
  { id: "backtests", label: "Backtests", icon: "📊" },
  { id: "strategies", label: "Stratégies", icon: "🎯" },
  { id: "chat", label: "Claude IA", icon: "✦" },
];

export default function Sidebar({ current, onChange }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Mobile hamburger */}
      <button
        className="fixed top-4 left-4 z-50 md:hidden bg-[#0d1526] border border-[#1e2d45] rounded-lg p-2"
        onClick={() => setOpen(!open)}
        aria-label="Menu"
      >
        <span className="block w-5 h-0.5 bg-slate-300 mb-1" />
        <span className="block w-5 h-0.5 bg-slate-300 mb-1" />
        <span className="block w-5 h-0.5 bg-slate-300" />
      </button>

      {/* Overlay mobile */}
      {open && (
        <div
          className="fixed inset-0 bg-black/60 z-40 md:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed top-0 left-0 h-full w-56 bg-[#0a1020] border-r border-[#1e2d45] z-40 flex flex-col transition-transform duration-200
          ${open ? "translate-x-0" : "-translate-x-full"} md:translate-x-0 md:static md:block`}
      >
        {/* Logo */}
        <div className="px-5 py-5 border-b border-[#1e2d45]">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-bold text-slate-100 text-sm tracking-tight">Killingbot</span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">TraderMorin × aiedge</p>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 px-3 space-y-1">
          {NAV.map((item) => (
            <button
              key={item.id}
              onClick={() => { onChange(item.id); setOpen(false); }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-left transition-colors
                ${current === item.id
                  ? "bg-blue-600/20 text-blue-300 font-medium"
                  : "text-slate-400 hover:bg-[#1e2d45]/50 hover:text-slate-200"
                }`}
            >
              <span className="text-base leading-none">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-[#1e2d45]">
          <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-xs font-bold">LIVE</span>
          <p className="text-xs text-slate-600 mt-1">KB_LOOSE_RR2.5_RR3.0</p>
        </div>
      </aside>
    </>
  );
}
