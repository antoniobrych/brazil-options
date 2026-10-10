import math

import numpy as np
import pytest

from brazil_options import gregas, preco, vol_implicita

S, K, T, R, Q, VOL = 56.0, 58.0, 27 / 252, math.log(1.1365), 0.02, 0.35


@pytest.mark.parametrize('call', [True, False])
def test_vol_implicita_recupera_a_vol(call):
    premio = preco(S, K, T, R, Q, VOL, call)
    assert vol_implicita(premio, S, K, T, R, Q, call) == pytest.approx(VOL, abs=1e-9)


def test_paridade_put_call():
    c = preco(S, K, T, R, Q, VOL, True)
    p = preco(S, K, T, R, Q, VOL, False)
    assert c - p == pytest.approx(S * math.exp(-Q * T) - K * math.exp(-R * T))


def test_premio_fora_dos_limites_vira_nan():
    piso = S * math.exp(-Q * T) - 50.0 * math.exp(-R * T)
    assert np.isnan(vol_implicita(0.0, S, K, T, R, Q, True))
    assert np.isnan(vol_implicita(S + 1, S, K, T, R, Q, True))
    assert np.isnan(vol_implicita(piso - 0.5, S, 50.0, T, R, Q, True))


def test_vetorizado():
    strikes = np.array([50.0, 56.0, 62.0])
    calls = np.array([True, False, True])
    premios = preco(S, strikes, T, R, Q, VOL, calls)
    assert np.allclose(vol_implicita(premios, S, strikes, T, R, Q, calls), VOL)


@pytest.mark.parametrize('call', [True, False])
def test_gregas_batem_com_diferencas_finitas(call):
    g = gregas(S, K, T, R, Q, VOL, call)
    h = 1e-4

    def p(s=S, t=T, r=R, v=VOL):
        return preco(s, K, t, r, Q, v, call)

    assert g['delta'] == pytest.approx((p(s=S + h) - p(s=S - h)) / (2 * h), rel=1e-6)
    assert g['gamma'] == pytest.approx((p(s=S + h) - 2 * p() + p(s=S - h)) / h ** 2, rel=1e-4)
    assert g['vega'] == pytest.approx((p(v=VOL + h) - p(v=VOL - h)) / (2 * h) / 100, rel=1e-6)
    assert g['rho'] == pytest.approx((p(r=R + h) - p(r=R - h)) / (2 * h) / 100, rel=1e-6)
    assert g['theta'] == pytest.approx(-(p(t=T + h) - p(t=T - h)) / (2 * h) / 252, rel=1e-6)
