import math

import numpy as np
import pandas as pd
import pytest

from brazil_options import calcular_gregas, preco

SPOT, TAXA = 50.0, 13.65
HOJE = pd.Timestamp('2026-10-09')


def vol_do_smile(strike):
    return 0.30 + 0.5 * (strike / SPOT - 1) ** 2


def montar_cadeia(vencimento, du, negociada=True):
    r, t = math.log(1 + TAXA / 100), du / 252
    linhas = []
    for tipo in ['CALL', 'PUT']:
        for strike in np.arange(40.0, 61.0, 2.0):
            premio = float(preco(SPOT, strike, t, r, 0.0, vol_do_smile(strike), tipo == 'CALL'))
            linhas.append({
                'subjacente': 'TEST3', 'vencimento': pd.Timestamp(vencimento), 'du': du,
                'ativo': f'{tipo}{strike:.0f}', 'tipo': tipo, 'strike': strike, 'spot': SPOT,
                'preco': premio, 'data_ultimo': HOJE if negociada else pd.NaT,
            })
    return pd.DataFrame(linhas)


def test_iv_de_mercado_recupera_o_smile():
    df = calcular_gregas(montar_cadeia('2026-12-18', 47), TAXA)
    assert (df['fonte_iv'] == 'mercado').all()
    assert np.allclose(df['iv'], vol_do_smile(df['strike']), atol=1e-8)
    assert np.allclose(df['preco_bs'], df['preco'])


def test_preco_antigo_usa_o_smile():
    cadeia = montar_cadeia('2026-12-18', 47)
    antiga = cadeia['ativo'] == 'CALL52'
    cadeia.loc[antiga, 'data_ultimo'] = HOJE - pd.Timedelta(days=30)
    cadeia.loc[antiga, 'preco'] = 0.01
    df = calcular_gregas(cadeia, TAXA)
    linha = df[df['ativo'] == 'CALL52'].iloc[0]
    assert linha['fonte_iv'] == 'smile'
    assert linha['iv'] == pytest.approx((vol_do_smile(50.0) + vol_do_smile(54.0)) / 2, abs=1e-8)


def test_vencimento_sem_negocios_usa_o_mais_proximo():
    cadeia = pd.concat([
        montar_cadeia('2026-11-19', 27),
        montar_cadeia('2026-12-18', 47),
        montar_cadeia('2027-06-18', 168, negociada=False),
    ])
    df = calcular_gregas(cadeia, TAXA)
    sem_negocio = df[df['vencimento'] == '2027-06-18']
    assert (sem_negocio['fonte_iv'] == 'smile 2026-12-18').all()
    assert sem_negocio['delta'].notna().all()


def test_guarda_parametros_em_attrs():
    df = calcular_gregas(montar_cadeia('2026-12-18', 47), TAXA, q=0.01)
    assert df.attrs == {'taxa': TAXA, 'q': 0.01, 'data_ref': HOJE}
