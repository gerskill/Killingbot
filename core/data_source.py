"""
data_source.py — Couche d'accès unique aux données de marché.

RÈGLE FONDATRICE : la source du backtest doit être IDENTIQUE à celle de
l'exécution. Un backtest sur une source A déployé sur une source B n'est pas
interprétable. C'est la cause probable des 10 fausses stratégies du sweep KB_*
(backtest yfinance → exécution Binance).

Yahoo Finance est volontairement absent et ne doit pas être réintroduit.

Deux sources, deux natures :

  BINANCE     — programmatique. Python appelle l'API publique directement,
                sans clé, avec pagination (historique complet). Source de
                référence pour la crypto : c'est celle qu'utilise le filtre de
                régime et le paper executor en production.

  TRADINGVIEW — médiée par l'agent. Le MCP tradingview-desktop est un outil
                côté Claude, pas une bibliothèque Python : un script ne peut
                pas l'appeler. L'agent exporte les barres vers le cache disque,
                Python lit le cache. Couvre tout ce que TradingView couvre
                (actions, indices, forex, crypto d'autres exchanges).

  IBKR        — emplacement réservé, non connecté. Voir _fetch_ibkr().

Contrat de sortie, identique quelle que soit la source :

    DataFrame pandas
      index   : DatetimeIndex, UTC tz-aware, croissant, sans doublon
      colonnes: open, high, low, close, volume  (float64)
      barre horodatée à son OUVERTURE
      la barre courante incomplète est TOUJOURS retirée

Usage :
    from core.data_source import load

    df = load("BTCUSDT", "4h")                      # Binance, historique complet
    df = load("BTCUSDT", "4h", start="2020-01-01")  # borné
    df = load("NASDAQ:NVDA", "1h")                  # cache TradingView

CLI :
    python3 core/data_source.py BTCUSDT 4h
    python3 core/data_source.py --cache-status
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
CACHE_DIR = ROOT / "data" / "cache"

OHLCV = ["open", "high", "low", "close", "volume"]

# Binance : 1000 barres max par requête
_BINANCE_PAGE = 1000
_BINANCE_URL = "https://api.binance.com/api/v3/klines"

# Durée d'une barre, en millisecondes — sert à la pagination et à la détection
# de la barre incomplète.
_INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
    "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000, "6h": 21_600_000,
    "8h": 28_800_000, "12h": 43_200_000, "1d": 86_400_000, "1w": 604_800_000,
}

# Résolutions TradingView → intervalle canonique de ce module.
TV_RESOLUTION = {
    "1": "1m", "3": "3m", "5": "5m", "15": "15m", "30": "30m",
    "60": "1h", "120": "2h", "240": "4h", "360": "6h", "480": "8h",
    "720": "12h", "D": "1d", "1D": "1d", "W": "1w", "1W": "1w",
}


class DataSourceError(RuntimeError):
    """Données indisponibles ou non conformes au contrat."""


# ─────────────────────────────────────────────────────────────────────────────
# Normalisation — point de passage obligé de toute source
# ─────────────────────────────────────────────────────────────────────────────

def _normalize(df: pd.DataFrame, interval: str, drop_partial: bool = True) -> pd.DataFrame:
    """Applique le contrat de sortie. Toute source passe par ici.

    Retirer la barre en cours n'est pas cosmétique : une barre incomplète a un
    close qui bouge encore. La garder revient à décider sur une information qui
    n'existait pas au moment de la décision — un look-ahead silencieux.
    """
    missing = [c for c in OHLCV if c not in df.columns]
    if missing:
        raise DataSourceError(f"colonnes manquantes: {missing}")

    out = df.copy()
    for col in OHLCV:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("float64")

    if not isinstance(out.index, pd.DatetimeIndex):
        raise DataSourceError("index doit être un DatetimeIndex")
    out.index = out.index.tz_localize("UTC") if out.index.tz is None else out.index.tz_convert("UTC")

    out = out[OHLCV]
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out.dropna(subset=["open", "high", "low", "close"])

    if drop_partial and len(out):
        bar_ms = _INTERVAL_MS.get(interval)
        if bar_ms:
            now_ms = int(time.time() * 1000)
            last_open_ms = int(out.index[-1].timestamp() * 1000)
            if last_open_ms + bar_ms > now_ms:
                out = out.iloc[:-1]

    if out.empty:
        raise DataSourceError("aucune barre exploitable après normalisation")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Binance — programmatique, historique complet par pagination
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_binance_page(symbol: str, interval: str, start_ms: int, limit: int) -> list:
    url = f"{_BINANCE_URL}?symbol={symbol}&interval={interval}&startTime={start_ms}&limit={limit}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:  # rate limit : back-off puis nouvelle tentative
                time.sleep(2 ** attempt)
                continue
            raise DataSourceError(f"Binance HTTP {e.code} sur {symbol} {interval}") from e
        except Exception as e:
            if attempt == 2:
                raise DataSourceError(f"Binance injoignable ({e})") from e
            time.sleep(1 + attempt)
    return []


def _fetch_binance(symbol: str, interval: str, start: str | None, end: str | None) -> pd.DataFrame:
    """Historique complet Binance. API publique, sans clé."""
    if interval not in _INTERVAL_MS:
        raise DataSourceError(f"intervalle Binance inconnu: {interval!r}")

    start_ms = int(pd.Timestamp(start or "2017-01-01", tz="UTC").timestamp() * 1000)
    end_ms = int(pd.Timestamp(end, tz="UTC").timestamp() * 1000) if end else int(time.time() * 1000)
    bar_ms = _INTERVAL_MS[interval]

    rows: list = []
    cursor = start_ms
    while cursor < end_ms:
        page = _fetch_binance_page(symbol, interval, cursor, _BINANCE_PAGE)
        if not page:
            break
        rows.extend(page)
        last_open = int(page[-1][0])
        cursor = last_open + bar_ms
        if len(page) < _BINANCE_PAGE:
            break
        time.sleep(0.12)  # sous la limite de poids Binance

    if not rows:
        raise DataSourceError(f"Binance n'a renvoyé aucune barre pour {symbol} {interval}")

    df = pd.DataFrame(rows, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "qav", "trades", "tbb", "tbq", "ignore"])
    df.index = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return _normalize(df, interval)


# ─────────────────────────────────────────────────────────────────────────────
# TradingView — médiée par l'agent via cache disque
# ─────────────────────────────────────────────────────────────────────────────

def cache_path(symbol: str, interval: str, source: str = "TV") -> Path:
    safe = symbol.replace(":", "_").replace("/", "_")
    return CACHE_DIR / f"{source}_{safe}_{interval}.csv"


def write_cache(symbol: str, interval: str, bars: list[dict], source: str = "TV") -> Path:
    """Écrit un export MCP dans le cache. Appelé par l'agent, pas par le pipeline.

    `bars` : liste de dicts contenant au minimum time/open/high/low/close/volume.
    Le champ temps accepte un epoch (s ou ms) ou une chaîne ISO.
    """
    if not bars:
        raise DataSourceError("export vide — rien à mettre en cache")

    df = pd.DataFrame(bars)
    tcol = next((c for c in ("time", "timestamp", "ts", "datetime", "open_time") if c in df.columns), None)
    if tcol is None:
        raise DataSourceError(f"aucune colonne temporelle dans l'export: {list(df.columns)}")

    if pd.api.types.is_numeric_dtype(df[tcol]):
        unit = "ms" if df[tcol].iloc[0] > 1e11 else "s"
        df.index = pd.to_datetime(df[tcol], unit=unit, utc=True)
    else:
        df.index = pd.to_datetime(df[tcol], utc=True)

    if "volume" not in df.columns:
        df["volume"] = 0.0  # indices et certains flux FX n'ont pas de volume

    # drop_partial=False : l'agent exporte ce que TradingView affiche ; la barre
    # incomplète est retirée à la lecture, quand "maintenant" est connu.
    out = _normalize(df, interval, drop_partial=False)
    path = cache_path(symbol, interval, source)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index_label="ts")
    return path


def _fetch_cache(symbol: str, interval: str, source: str = "TV") -> pd.DataFrame:
    path = cache_path(symbol, interval, source)
    if not path.exists():
        raise DataSourceError(
            f"cache absent : {path.name}\n"
            f"  {symbol} n'est pas sur Binance — les barres doivent être exportées\n"
            f"  depuis TradingView par l'agent (MCP data_get_ohlcv → write_cache).\n"
            f"  Demander : « exporte {symbol} {interval} vers le cache »"
        )
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return _normalize(df, interval)


# ─────────────────────────────────────────────────────────────────────────────
# IBKR — emplacement réservé, non connecté
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_ibkr(symbol: str, interval: str, start, end) -> pd.DataFrame:
    """Non connecté par décision explicite (2026-07).

    Le branchement demande : compte IBKR, IB Gateway local en écoute (paper
    port 4002), et `ib_insync`. Aucun de ces éléments n'est en place. Quand ce
    sera le cas, implémenter ici et renvoyer via _normalize() — le reste du
    système n'a pas besoin de changer.
    """
    raise DataSourceError(
        "IBKR non connecté. Prérequis : compte IBKR, IB Gateway (paper 4002), "
        "ib_insync. Utiliser Binance (crypto) ou le cache TradingView en attendant."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

def resolve_source(symbol: str) -> str:
    """Choisit la source. Un symbole préfixé d'un exchange (BINANCE:, NASDAQ:,
    OANDA:…) vient de TradingView ; une paire nue cotée en stable est Binance."""
    if ":" in symbol:
        return "tradingview"
    if symbol.upper().endswith(("USDT", "USDC", "BUSD", "BTC", "ETH", "BNB")):
        return "binance"
    return "tradingview"


def load(symbol: str, interval: str, start: str | None = None,
         end: str | None = None, source: str = "auto") -> pd.DataFrame:
    """Charge l'OHLCV d'un symbole. Voir le contrat de sortie en tête de module."""
    interval = TV_RESOLUTION.get(interval, interval)
    src = resolve_source(symbol) if source == "auto" else source

    if src == "binance":
        df = _fetch_binance(symbol, interval, start, end)
    elif src == "tradingview":
        df = _fetch_cache(symbol, interval, "TV")
    elif src == "ibkr":
        df = _fetch_ibkr(symbol, interval, start, end)
    else:
        raise DataSourceError(f"source inconnue: {src!r} (binance|tradingview|ibkr)")

    if start:
        df = df[df.index >= pd.Timestamp(start, tz="UTC")]
    if end:
        df = df[df.index <= pd.Timestamp(end, tz="UTC")]
    if df.empty:
        raise DataSourceError(f"aucune barre dans la fenêtre demandée pour {symbol} {interval}")
    return df


def cache_status() -> list[dict]:
    """Inventaire du cache — ce que l'agent a déjà exporté."""
    if not CACHE_DIR.exists():
        return []
    out = []
    for p in sorted(CACHE_DIR.glob("*.csv")):
        try:
            df = pd.read_csv(p, index_col=0, parse_dates=True)
            out.append({
                "file": p.name, "bars": len(df),
                "from": str(df.index[0]), "to": str(df.index[-1]),
            })
        except Exception as e:
            out.append({"file": p.name, "error": str(e)[:80]})
    return out


if __name__ == "__main__":
    if "--cache-status" in sys.argv:
        print(json.dumps(cache_status(), indent=2, ensure_ascii=False))
        sys.exit(0)

    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    itv = sys.argv[2] if len(sys.argv) > 2 else "4h"
    frame = load(sym, itv)
    print(json.dumps({
        "symbol": sym, "interval": itv, "source": resolve_source(sym),
        "bars": len(frame),
        "from": str(frame.index[0]), "to": str(frame.index[-1]),
        "last_close": float(frame["close"].iloc[-1]),
        "tz": str(frame.index.tz),
    }, indent=2, ensure_ascii=False))
