import numpy as np
from scipy.stats import norm


def _d1_d2(S, K, T, r, q, vol):
    raiz = np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + vol ** 2 / 2) * T) / (vol * raiz)
    return d1, d1 - vol * raiz


def preco(S, K, T, r, q, vol, call):
    """Prêmio Black-Scholes. T em anos, r e q contínuos, call=True/False."""
    d1, d2 = _d1_d2(S, K, T, r, q, vol)
    c = S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    p = K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)
    return np.where(call, c, p)[()]


def vol_implicita(premio, S, K, T, r, q, call, vol_min=1e-3, vol_max=5.0, iteracoes=80):
    """Vol implícita por bissecção. NaN quando o prêmio sai dos limites de arbitragem."""
    premio, S, K, T = (np.asarray(x, dtype=float) for x in (premio, S, K, T))
    call = np.asarray(call, dtype=bool)
    forma = np.broadcast(premio, S, K, T, call).shape
    lo = np.full(forma, vol_min)
    hi = np.full(forma, vol_max)
    with np.errstate(all='ignore'):
        valido = (premio > 0) & (T > 0)
        valido &= (preco(S, K, T, r, q, lo, call) < premio) & (preco(S, K, T, r, q, hi, call) > premio)
        for _ in range(iteracoes):
            meio = (lo + hi) / 2
            acima = preco(S, K, T, r, q, meio, call) > premio
            hi = np.where(acima, meio, hi)
            lo = np.where(acima, lo, meio)
    return np.where(valido, (lo + hi) / 2, np.nan)[()]


def gregas(S, K, T, r, q, vol, call):
    """Delta, gamma, theta (por dia útil), vega e rho (por 1 p.p.)."""
    d1, d2 = _d1_d2(S, K, T, r, q, vol)
    eq, er, pdf = np.exp(-q * T), np.exp(-r * T), norm.pdf(d1)
    decaimento = -S * eq * pdf * vol / (2 * np.sqrt(T))
    theta_call = decaimento - r * K * er * norm.cdf(d2) + q * S * eq * norm.cdf(d1)
    theta_put = decaimento + r * K * er * norm.cdf(-d2) - q * S * eq * norm.cdf(-d1)
    return {
        'delta': np.where(call, eq * norm.cdf(d1), -eq * norm.cdf(-d1))[()],
        'gamma': (eq * pdf / (S * vol * np.sqrt(T)))[()],
        'theta': (np.where(call, theta_call, theta_put) / 252)[()],
        'vega': (S * eq * pdf * np.sqrt(T) / 100)[()],
        'rho': (np.where(call, K * T * er * norm.cdf(d2), -K * T * er * norm.cdf(-d2)) / 100)[()],
    }
