"""
sovereign/engine.py — Pine Template Engine
Équivalent de Sovereign : context + templates -> Pine scripts générés.

Usage :
    from sovereign.engine import PineEngine
    engine = PineEngine()
    code = engine.render("strategy_base", title="KB_AUTO_V1", use_rsi=True)
    engine.save(code, "pine_scripts/strategies/kb_auto_v1.pine")
"""
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from sovereign.context import load as load_context

TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR    = Path(__file__).parent.parent / "pine_scripts" / "strategies"


class PineEngine:
    def __init__(self):
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )
        self._context = load_context()

    def reload_context(self):
        """Re-poll toutes les sources de données (comme Sovereign poll DB + S3)."""
        self._context = load_context()

    def render(self, template_name: str, **overrides) -> str:
        """
        Rend un template Pine avec context + overrides.
        template_name : nom sans extension (ex: 'strategy_base')
        overrides     : valeurs qui écrasent le context (params spécifiques)
        """
        tmpl = self._env.get_template(f"{template_name}.pine.j2")

        # Construire le contexte final : defaults + context + overrides
        params = {**self._context.get("common_params", {}), **overrides.pop("params", {})}
        ctx = {
            **self._context,
            "params":          params,
            "generated_at":    datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "context_summary": self._summary(),
            "position_pct":    10,
            "use_rsi":         False,
            "title":           "KB_AUTO",
        }
        ctx.update(overrides)
        return tmpl.render(**ctx)

    def save(self, code: str, filename: str | None = None, template_name: str = "strategy_base") -> Path:
        """Écrit le Pine généré dans pine_scripts/strategies/."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        name = filename or f"kb_sovereign_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pine"
        if not name.endswith(".pine"):
            name = f"{name}.pine"
        out = OUTPUT_DIR / name
        out.write_text(code, encoding="utf-8")
        print(f"[SOVEREIGN] Généré → {out}")
        return out

    def generate(self, template_name: str = "strategy_base", filename: str | None = None, **overrides) -> Path:
        """Render + save en une passe."""
        code = self.render(template_name, **overrides)
        return self.save(code, filename, template_name)

    def _summary(self) -> str:
        best = self._context.get("best_strategies", [])
        if best:
            top = best[0]
            m = top.get("metrics", {})
            return f"best={top.get('name','?')} {m.get('monthly_return_pct',0):.1f}%/mo"
        return "no backtest data"


# CLI rapide : python -m sovereign.engine
if __name__ == "__main__":
    import sys
    engine = PineEngine()
    overrides = {}
    if "--rsi" in sys.argv:
        overrides["use_rsi"] = True
    title = next((sys.argv[i+1] for i, a in enumerate(sys.argv) if a == "--title"), "KB_SOVEREIGN")
    path = engine.generate(title=title, **overrides)
    print(f"Script Pine généré : {path}")
