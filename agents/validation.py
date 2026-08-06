"""
validation.py — Garde-fous anti-overfitting pour la boucle d'exploration.

3 outils, indépendants du moteur de backtest (on lui passe run_backtest en
paramètre pour éviter tout import circulaire avec strategy_explorer.py) :

1. walk_forward_split   — sépare in-sample / out-of-sample, jamais mélangés.
2. deflated_sharpe_ratio — corrige le Sharpe du meilleur candidat pour le
                            biais de sélection (on a déjà testé N variantes,
                            le meilleur des N gagne un peu par hasard).
3. monte_carlo_stability — perturbe les params du gagnant, revérifie que la
                            perf ne s'effondre pas au moindre changement.
"""
import copy
import math
import random

import pandas as pd


# ── 1. Walk-forward OOS ─────────────────────────────────────────────────────

def walk_forward_split(backtest_fn, df_1h: pd.DataFrame, params: dict, holdout_frac: float = 0.3) -> dict:
    """
    Découpe chronologiquement : premiers (1-holdout_frac) = in-sample,
    derniers holdout_frac = out-of-sample. Jamais optimisé sur l'OOS.
    """
    n = len(df_1h)
    split = int(n * (1 - holdout_frac))
    df_is = df_1h.iloc[:split]
    df_oos = df_1h.iloc[split:]

    return {
        "is": backtest_fn(df_is, params),
        "oos": backtest_fn(df_oos, params),
    }


def oos_degradation_pct(is_result: dict, oos_result: dict):
    """% de perte de perf mensuelle IS -> OOS. None si pas comparable."""
    if "error" in is_result or "error" in oos_result:
        return None
    is_m = is_result.get("monthly_return_pct", 0)
    oos_m = oos_result.get("monthly_return_pct", 0)
    if is_m == 0:
        return None
    return round((oos_m - is_m) / abs(is_m) * 100, 1)


# ── 2. Deflated Sharpe Ratio (Bailey & López de Prado, 2014) ───────────────

_EULER_MASCHERONI = 0.5772156649


def deflated_sharpe_ratio(observed_sharpe: float, trial_sharpes: list, n_obs: int,
                          skew: float = 0.0, kurtosis: float = 3.0):
    """
    Probabilité (0-1) que le meilleur Sharpe observé reflète un vrai edge,
    pas juste le meilleur tirage parmi N essais testés. < 0.95 = pas fiable.

    ⚠️ UNITÉS — `observed_sharpe` et `trial_sharpes` doivent être exprimés à la
    MÊME fréquence que `n_obs` : un Sharpe par barre avec un nombre de barres,
    jamais un Sharpe annualisé avec un nombre de barres. Mélanger les deux fait
    exploser le z-score et la fonction renvoie 1.0 quoi qu'il arrive.

    Correctif du 2026-07-25 — le dénominateur valait `sharpe_std / √(n_obs-1)`,
    c'est-à-dire la dispersion INTER-ESSAIS divisée par la racine du nombre
    d'observations (~140 sur 9 ans de 4H). L'erreur-type se retrouvait ~140 fois
    trop petite, le z-score saturait, et la fonction renvoyait 1.0 pour un Sharpe
    de 0.05 sur 100 essais comme pour un Sharpe de 7.5. La porte G4 laissait donc
    tout passer — précisément le contrôle censé empêcher le sur-apprentissage du
    sweep KB_*.

    La bonne quantité est l'erreur-type du Sharpe estimé (Bailey & López de
    Prado, 2014), qui dépend de la longueur de série et des moments d'ordre 3 et
    4 des rendements :

        SE(SR) = √[ (1 − γ₃·SR + (γ₄−1)/4·SR²) / (n−1) ]

    Les valeurs par défaut (γ₃=0, γ₄=3) correspondent à l'hypothèse gaussienne.
    Renseigner l'asymétrie et l'aplatissement réels durcit le test sur les
    séries à queues épaisses — le cas des rendements crypto.
    """
    n_trials = len(trial_sharpes)
    if n_trials < 2:
        return None
    sharpe_std = pd.Series(trial_sharpes).std()
    if not sharpe_std or pd.isna(sharpe_std):
        return None
    if n_obs < 2:
        return None

    expected_max = sharpe_std * (
        (1 - _EULER_MASCHERONI) * _norm_ppf(1 - 1 / n_trials)
        + _EULER_MASCHERONI * _norm_ppf(1 - 1 / (n_trials * math.e))
    )

    variance = (1 - skew * observed_sharpe
                + (kurtosis - 1) / 4 * observed_sharpe ** 2) / (n_obs - 1)
    if variance <= 0:
        return None
    se = math.sqrt(variance)

    z = (observed_sharpe - expected_max) / se
    return round(_norm_cdf(z), 3)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_ppf(p: float) -> float:
    """Inverse CDF normale, approximation Beasley-Springer-Moro (pas de dépendance scipy)."""
    if p <= 0:
        return -8.0
    if p >= 1:
        return 8.0
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    p_low = 0.02425
    p_high = 1 - p_low
    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
               (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
            ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)


# ── 3. Monte Carlo stability ────────────────────────────────────────────────

def monte_carlo_stability(backtest_fn, df_1h: pd.DataFrame, params: dict,
                           n_sims: int = 15, perturb_pct: float = 0.1) -> dict:
    """
    Perturbe chaque param numérique de ±perturb_pct aléatoirement, re-backteste
    n_sims fois. Une vraie edge survit à un léger changement de params ;
    une stratégie overfit s'effondre.
    """
    baseline = backtest_fn(df_1h, params)
    if "error" in baseline:
        return {"error": baseline["error"]}
    baseline_monthly = baseline.get("monthly_return_pct", 0)

    numeric_keys = [
        k for k, v in params.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool) and not k.startswith("_")
    ]

    results = []
    n_failures = 0
    for _ in range(n_sims):
        p = copy.deepcopy(params)
        for k in numeric_keys:
            factor = 1 + random.uniform(-perturb_pct, perturb_pct)
            p[k] = max(1, round(p[k] * factor)) if isinstance(p[k], int) else round(p[k] * factor, 3)
        r = backtest_fn(df_1h, p)
        if "error" not in r:
            results.append(r.get("monthly_return_pct", 0))
        else:
            n_failures += 1

    if not results:
        return {"error": f"Aucune simulation valide ({n_failures}/{n_sims} échouées)",
                "n_failures": n_failures, "n_sims": n_sims}

    if n_failures / n_sims > 0.5:
        return {
            "error": (f"Trop de simulations échouées ({n_failures}/{n_sims}) — "
                      "stratégie fragile ou données insuffisantes pour le G5"),
            "n_failures": n_failures, "n_sims": n_sims,
        }

    stable = [r for r in results if baseline_monthly <= 0 or r >= 0.5 * baseline_monthly]
    return {
        "baseline_monthly_pct": baseline_monthly,
        "mc_mean_pct": round(sum(results) / len(results), 2),
        "mc_std_pct": round(float(pd.Series(results).std()), 2),
        "mc_stability_pct": round(len(stable) / len(results) * 100, 1),
        "n_sims": len(results),
        "n_failures": n_failures,
    }
