import math

import numpy as np

from .blackscholes import gregas, preco, vol_implicita


def calcular_gregas(cadeia, taxa, q=0.0):
    """Adiciona iv, fonte_iv, preco_bs e gregas a uma cadeia. taxa em % a.a. base 252."""
    df = cadeia.reset_index(drop=True)
    r = math.log(1 + taxa / 100)
    S = df['spot'].to_numpy(float)
    K = df['strike'].to_numpy(float)
    T = df['du'].to_numpy(float) / 252
    call = (df['tipo'] == 'CALL').to_numpy()

    data_ref = df['data_ultimo'].max()
    atual = (df['data_ultimo'] == data_ref).to_numpy()
    df['iv'] = vol_implicita(np.where(atual, df['preco'], np.nan), S, K, T, r, q, call)
    df['fonte_iv'] = np.where(df['iv'].isna(), None, 'mercado')

    df['otm'] = np.where(call, K >= S, K <= S)
    smiles = {}
    for venc, g in df[df['fonte_iv'] == 'mercado'].groupby('vencimento'):
        pontos = g[g['otm']] if g['otm'].any() else g
        smiles[venc] = pontos.groupby('strike')['iv'].mean()
    du_venc = df.groupby('vencimento')['du'].first()
    for venc, g in df.groupby('vencimento'):
        if not smiles:
            break
        origem = venc if venc in smiles else min(smiles, key=lambda v: abs(du_venc[v] - du_venc[venc]))
        smile = smiles[origem]
        falta = g.index[g['iv'].isna()]
        df.loc[falta, 'iv'] = np.interp(df.loc[falta, 'strike'], smile.index, smile.values)
        df.loc[falta, 'fonte_iv'] = 'smile' if origem == venc else f'smile {origem:%Y-%m-%d}'
    df = df.drop(columns='otm')

    vol = df['iv'].to_numpy(float)
    with np.errstate(all='ignore'):
        df['preco_bs'] = preco(S, K, T, r, q, vol, call)
        for nome, valor in gregas(S, K, T, r, q, vol, call).items():
            df[nome] = valor
    df.attrs.update(taxa=taxa, q=q, data_ref=data_ref)
    return df
