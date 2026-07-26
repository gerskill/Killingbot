"""
Isolation des positions entre stratégies.

Scénario couvert : deux stratégies visant le même symbole. Sans isolation, la
seconde est soit rejetée à l'ouverture, soit supprimée à la clôture de la
première — dans ce dernier cas sans qu'aucun trade ne soit écrit, donc avec
perte silencieuse du PnL.

Bug d'origine (corrigé le 2026-07-25) : `close_from_signal` filtrait sur le seul
symbole et retirait *toutes* les positions de cet actif tout en n'écrivant qu'un
seul trade.

    pytest tests/test_position_isolation.py -v
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import paper_executor as pe


def _position(symbol: str, strategy_id: str | None, qty: float = 0.5,
              entry: float = 64_000.0) -> dict:
    pos = {
        "symbol": symbol, "side": "long", "qty": qty,
        "entry_price": entry, "sl": entry - 1_000, "tp1": entry + 1_000,
        "tp2": entry + 2_000, "tp1_done": False, "setup": "TEST", "tf": "240",
        "opened_at": "2026-07-25T08:00:00", "regime_at_entry": "TRENDING",
    }
    if strategy_id is not None:
        pos["strategy_id"] = strategy_id
    return pos


def _n_trades(csv_path: Path) -> int:
    if not csv_path.exists():
        return 0
    return max(0, len(csv_path.read_text().strip().splitlines()) - 1)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Isole positions et CSV — ne touche jamais aux fichiers de production."""
    monkeypatch.setattr(pe, "POSITIONS_FILE", tmp_path / "positions.json")
    monkeypatch.setattr(pe, "TRADES_CSV", tmp_path / "trades.csv")
    # Prix Binance indisponible → repli sur le prix du payload, test hors réseau.
    monkeypatch.setattr(pe, "_last_price_and_atr",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    return tmp_path


def test_close_ne_touche_que_sa_propre_position(sandbox):
    """Le bug d'origine : 2 positions supprimées, 1 seul trade écrit."""
    pe._save_positions([
        _position("BTCUSDT", "ppst4h", qty=0.5, entry=64_000),
        _position("BTCUSDT", "meanrev", qty=0.3, entry=64_200),
    ])

    result = pe.close_from_signal(
        {"ticker": "BTCUSDT", "price": "64500", "strategy_id": "ppst4h"})

    remaining = pe._load_positions()
    assert result["closed"] is True
    assert len(remaining) == 1, "la position de l'autre stratégie a été supprimée"
    assert pe._strategy_of(remaining[0]) == "meanrev"
    assert _n_trades(sandbox / "trades.csv") == 1


def test_aucune_position_disparait_sans_trade(sandbox):
    """Invariant central : positions retirées == trades écrits."""
    pe._save_positions([
        _position("BTCUSDT", "ppst4h"),
        _position("BTCUSDT", "meanrev"),
        _position("ETHUSDT", "ppst4h"),
    ])
    before = len(pe._load_positions())

    pe.close_from_signal({"ticker": "BTCUSDT", "price": "64500", "strategy_id": "ppst4h"})

    removed = before - len(pe._load_positions())
    assert removed == _n_trades(sandbox / "trades.csv") == 1


def test_close_sans_position_correspondante_est_inoffensif(sandbox):
    """Un exit d'une stratégie sans position ne doit rien fermer."""
    pe._save_positions([_position("BTCUSDT", "meanrev")])

    result = pe.close_from_signal(
        {"ticker": "BTCUSDT", "price": "64500", "strategy_id": "ppst4h"})

    assert result["closed"] is False
    assert "meanrev" in result["reason"], "le message doit nommer les positions existantes"
    assert len(pe._load_positions()) == 1


def test_signal_legacy_ne_touche_pas_une_strategie_nommee(sandbox):
    """L'alerte OOS en cours (setup B, non routée) doit rester cloisonnée."""
    pe._save_positions([_position("BTCUSDT", "ppst4h")])

    result = pe.close_from_signal({"ticker": "BTCUSDT", "price": "64500"})

    assert result["closed"] is False
    assert len(pe._load_positions()) == 1


def test_position_sans_strategy_id_est_legacy(sandbox):
    """Les positions antérieures à la migration restent adressables."""
    pe._save_positions([_position("BTCUSDT", None)])

    result = pe.close_from_signal({"ticker": "BTCUSDT", "price": "64500"})

    assert result["closed"] is True
    assert pe._load_positions() == []


def test_deux_strategies_peuvent_ouvrir_le_meme_symbole(sandbox, monkeypatch):
    """Sans isolation, la seconde stratégie était silencieusement rejetée."""
    monkeypatch.setattr(pe, "_last_price_and_atr", lambda *a, **k: (64_000.0, 500.0))
    monkeypatch.setattr(pe, "_load_config", lambda: {
        "deploy_state": "paper",
        "strategy": {"risk_params": {"sl_atr_mult": 1.5, "tp1_rr": 1.5,
                                     "tp2_rr": 3.0, "risk_per_trade_pct": 1.0}},
    })
    pe._save_positions([])

    first = pe.open_from_signal(
        {"ticker": "BTCUSDT", "dir": "long", "strategy_id": "ppst4h", "setup": "A"})
    second = pe.open_from_signal(
        {"ticker": "BTCUSDT", "dir": "long", "strategy_id": "meanrev", "setup": "B"})

    assert first["opened"] is True
    assert second["opened"] is True, "la 2e stratégie a été rejetée à tort"
    assert len(pe._load_positions()) == 2


def test_meme_strategie_ne_double_pas_sa_position(sandbox, monkeypatch):
    """Une alerte répétée ne doit pas empiler deux fois la même position."""
    monkeypatch.setattr(pe, "_last_price_and_atr", lambda *a, **k: (64_000.0, 500.0))
    monkeypatch.setattr(pe, "_load_config", lambda: {
        "deploy_state": "paper",
        "strategy": {"risk_params": {"sl_atr_mult": 1.5, "tp1_rr": 1.5,
                                     "tp2_rr": 3.0, "risk_per_trade_pct": 1.0}},
    })
    pe._save_positions([])

    pe.open_from_signal({"ticker": "BTCUSDT", "dir": "long", "strategy_id": "ppst4h"})
    duplicate = pe.open_from_signal({"ticker": "BTCUSDT", "dir": "long", "strategy_id": "ppst4h"})

    assert duplicate["opened"] is False
    assert "ppst4h" in duplicate["reason"]
    assert len(pe._load_positions()) == 1


def test_plafond_portefeuille_respecte(sandbox, monkeypatch):
    """Le plafond global protège le portefeuille, toutes stratégies confondues."""
    monkeypatch.setattr(pe, "_last_price_and_atr", lambda *a, **k: (64_000.0, 500.0))
    monkeypatch.setattr(pe, "_load_config", lambda: {
        "deploy_state": "paper",
        "strategy": {"risk_params": {"sl_atr_mult": 1.5, "tp1_rr": 1.5,
                                     "tp2_rr": 3.0, "risk_per_trade_pct": 1.0}},
    })
    pe._save_positions([
        _position("BTCUSDT", "s1"), _position("ETHUSDT", "s2"), _position("SOLUSDT", "s3"),
    ])

    result = pe.open_from_signal(
        {"ticker": "LINKUSDT", "dir": "long", "strategy_id": "s4"})

    assert result["opened"] is False
    assert "portefeuille" in result["reason"]


def test_trade_csv_porte_le_strategy_id(sandbox):
    """Sans cette colonne, l'analyse hebdo mélange toutes les stratégies."""
    pe._save_positions([_position("BTCUSDT", "ppst4h")])
    pe.close_from_signal({"ticker": "BTCUSDT", "price": "64500", "strategy_id": "ppst4h"})

    content = (sandbox / "trades.csv").read_text()
    assert "strategy_id" in content.splitlines()[0]
    assert "ppst4h" in content.splitlines()[1]
