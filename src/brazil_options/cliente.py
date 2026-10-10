import time
from datetime import date

import pandas as pd
import requests

from .calculo import calcular_gregas

COLUNAS = ['subjacente', 'vencimento', 'du', 'ativo', 'tipo', 'modelo', 'formador', 'moneyness',
           'strike', 'spot', 'preco', 'data_ultimo', 'negocios', 'volume']


class OpcoesB3:
    """Cliente do opcoes.net.br. intervalo: segundos entre requisições."""

    URL = 'https://opcoes.net.br/listaopcoes/completa'
    URL_CDI = 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados/ultimos/1?formato=json'

    def __init__(self, intervalo=2.5, tentativas=6, timeout=30):
        self.intervalo = intervalo
        self.tentativas = tentativas
        self.timeout = timeout
        self.sessao = requests.Session()
        self.sessao.headers['User-Agent'] = 'Mozilla/5.0 (compatible; brazil-options)'
        self._ultima = 0.0

    def vencimentos(self, ativo):
        """Vencimentos com opções listadas, dias úteis até cada um e se é mensal."""
        ativo = _ticker(ativo)
        dados = self._get_opcoes({'idAcao': ativo, 'listarVencimentos': 'true', 'cotacoes': 'true'})
        lista = dados.get('vencimentos') or []
        if not lista:
            raise ValueError(f'nenhuma opção encontrada para {ativo}')
        ajuste = 1 if date.today().weekday() >= 5 else 0
        return pd.DataFrame({
            'vencimento': pd.to_datetime([v['value'] for v in lista]),
            'du': [int(v['dataAttributes']['du']) + ajuste for v in lista],
            'mensal': [v['dataAttributes'].get('m') == '1' for v in lista],
        })

    def cadeia(self, ativo, vencimentos=None):
        """Cotações de um vencimento, de uma lista deles ou de todos (None)."""
        ativo = _ticker(ativo)
        venc = self.vencimentos(ativo)
        if vencimentos is not None:
            if isinstance(vencimentos, (str, date)):
                vencimentos = [vencimentos]
            pedidos = set(pd.to_datetime(list(vencimentos)))
            invalidos = pedidos - set(venc['vencimento'])
            if invalidos:
                raise ValueError(f'vencimentos sem opções de {ativo}: '
                                 f'{sorted(d.strftime("%Y-%m-%d") for d in invalidos)}')
            venc = venc[venc['vencimento'].isin(pedidos)]
        partes = [self._cadeia_vencimento(ativo, v, du) for v, du in zip(venc['vencimento'], venc['du'])]
        return pd.concat(partes, ignore_index=True)

    def gregas(self, ativo, vencimentos=None, taxa=None, q=0.0):
        """Cadeia com vol implícita e gregas. taxa em % a.a. (padrão: CDI do dia)."""
        cadeia = self.cadeia(ativo, vencimentos)
        return calcular_gregas(cadeia, self.cdi() if taxa is None else taxa, q)

    def cdi(self):
        """CDI anualizado base 252, em %."""
        r = self.sessao.get(self.URL_CDI, timeout=self.timeout)
        r.raise_for_status()
        return float(r.json()[-1]['valor'])

    def _cadeia_vencimento(self, ativo, vencimento, du):
        dados = self._get_opcoes({'idAcao': ativo, 'listarVencimentos': 'false', 'cotacoes': 'true',
                                  'vencimentos': vencimento.strftime('%Y-%m-%d')})
        linhas = [[ativo, vencimento, du, i[0].split('_')[0], i[2], i[3], bool(i[1]), i[4],
                   i[5], i[6], i[8], i[11], i[9], i[10]] for i in dados['cotacoesOpcoes']]
        df = pd.DataFrame(linhas, columns=['subjacente', 'vencimento', 'du', 'ativo', 'tipo', 'modelo',
                                           'formador', 'moneyness', 'strike', 'distancia', 'preco',
                                           'data_ultimo', 'negocios', 'volume'])
        for coluna in ['strike', 'distancia', 'preco', 'negocios', 'volume']:
            df[coluna] = pd.to_numeric(df[coluna], errors='coerce')
        df['data_ultimo'] = pd.to_datetime(df['data_ultimo'])
        df['spot'] = (df['strike'] / (1 + df['distancia'])).median()
        return df[COLUNAS]

    def _get_opcoes(self, params):
        for _ in range(self.tentativas):
            espera = self._ultima + self.intervalo - time.monotonic()
            if espera > 0:
                time.sleep(espera)
            r = self.sessao.get(self.URL, params=params, timeout=self.timeout)
            self._ultima = time.monotonic()
            if r.status_code != 429:
                r.raise_for_status()
                return r.json()['data']
            time.sleep(_segundos(r.headers.get('Retry-After')))
        r.raise_for_status()


def _ticker(ativo):
    ativo = ativo.strip().upper()
    return ativo[:-3] if ativo.endswith('.SA') else ativo


def _segundos(retry_after):
    try:
        return float(retry_after)
    except (TypeError, ValueError):
        return 5.0
