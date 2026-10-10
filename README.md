# brazil-options

Cadeia de opções de ações da B3 num DataFrame do pandas, com volatilidade implícita e gregas.

Os preços vêm do [opcoes.net.br](https://opcoes.net.br). Lá, vol implícita e gregas são só para assinantes. Aqui elas são calculadas por Black-Scholes a partir do último negócio de cada série.

## Instalação

```bash
pip install git+https://github.com/antoniobrych/brazil-options
```

Python 3.9 ou mais novo. Dependências: numpy, pandas, requests e scipy.

## Uso

```python
from brazil_options import OpcoesB3

b3 = OpcoesB3()
b3.vencimentos('PETR4')
```

```
vencimento  du  mensal
2026-10-16   4    True
2026-10-23   9   False
2026-10-30  14   False
2026-11-06  18   False
2026-11-13  23   False
2026-11-19  27    True
```

```python
df = b3.gregas('PETR4', '2026-11-19')
```

Recorte perto do dinheiro, com spot a R$ 56,00 e CDI a 13,65%:

```
   ativo tipo  strike  preco     iv fonte_iv   delta  gamma   theta   vega
PETRK571 CALL   55.91   3.05 0.3588  mercado  0.5750 0.0596 -0.0625 0.0718
PETRK576 CALL   56.41   2.80 0.3592  mercado  0.5451 0.0602 -0.0624 0.0727
PETRK581 CALL   56.91   2.56 0.3590  mercado  0.5153 0.0606 -0.0619 0.0731
PETRW571  PUT   55.91   2.30 0.3729  mercado -0.4260 0.0574 -0.0363 0.0719
PETRW576  PUT   56.41   2.53 0.3714  mercado -0.4548 0.0582 -0.0357 0.0727
PETRW581  PUT   56.91   2.78 0.3706  mercado -0.4837 0.0587 -0.0350 0.0731
```

Outras chamadas:

| chamada | retorna |
|---|---|
| `b3.gregas('PETR4')` | todos os vencimentos |
| `b3.gregas('PETR4', ['2026-11-19', '2026-12-18'])` | uma lista de vencimentos |
| `b3.gregas('PETR4', taxa=14.0)` | taxa fixa em % a.a. (o padrão é o CDI do dia) |
| `b3.cadeia('VALE3', '2026-11-19')` | só as cotações, sem vol nem gregas |
| `b3.cdi()` | CDI anualizado do dia, em % |

O ticker vai sem `.SA`. Se vier com, o sufixo é removido.

## Colunas

| coluna | conteúdo |
|---|---|
| `subjacente` | ação-objeto |
| `vencimento` | data de vencimento |
| `du` | dias úteis até o vencimento |
| `ativo` | código da opção |
| `tipo` | `CALL` ou `PUT` |
| `modelo` | `A` (americana) ou `E` (europeia) |
| `formador` | se a série tem formador de mercado |
| `moneyness` | `ITM`, `ATM` ou `OTM` |
| `strike` | preço de exercício |
| `spot` | preço da ação usado no cálculo |
| `preco` | último negócio da opção |
| `data_ultimo` | data do último negócio |
| `negocios`, `volume` | número de negócios e volume financeiro, como informados pelo site |
| `iv` | volatilidade implícita anual (0.36 = 36%) |
| `fonte_iv` | `mercado`, `smile` ou `smile AAAA-MM-DD` (ver abaixo) |
| `preco_bs` | prêmio teórico com a `iv` da linha |
| `delta` | variação do prêmio por R$ 1 no spot |
| `gamma` | variação do delta por R$ 1 no spot |
| `theta` | variação do prêmio por dia útil, em R$ |
| `vega` | variação do prêmio por 1 ponto de vol, em R$ |
| `rho` | variação do prêmio por 1 ponto de taxa, em R$ |

`df.attrs` guarda a taxa, o `q` e a data de referência dos preços.

## Como o cálculo é feito

**Spot.** Sai da própria resposta do site: strike / (1 + distância % do strike). Assim fica coerente com os preços das opções e não depende de outra fonte.

**Prazo.** Dias úteis / 252, usando os dias úteis que o site informa para cada vencimento. Em fim de semana soma-se 1, para que as cotações de sexta contem o pregão do dia do vencimento.

**Taxa.** CDI anualizado do dia (série 4389 do Banco Central), convertido para taxa contínua com `ln(1 + CDI)`.

**Dividendos.** `q = 0` por padrão, porque a B3 desconta os proventos do strike das opções. Dá para passar outro valor em `b3.gregas(..., q=0.05)`.

**Vol implícita.** Bissecção sobre Black-Scholes, só para opções negociadas no último pregão. Um preço de semanas atrás contra o spot de hoje daria uma vol sem sentido, então essas linhas ficam sem vol própria. O mesmo vale para prêmios abaixo do valor intrínseco.

**Linhas sem vol própria.** Recebem a vol do smile do mesmo vencimento, montado com as opções OTM que têm vol de mercado. A interpolação é linear no strike e constante além das pontas. Um vencimento sem nenhum negócio usa o smile do vencimento mais próximo em dias úteis. A coluna `fonte_iv` diz de onde veio cada vol.

## Limitações

- O site limita requisições: bloqueia rajadas de três ou quatro seguidas e tem uma cota por janela de 3 horas. A biblioteca espera 2,5 s entre chamadas e respeita o `Retry-After`. Um vencimento custa duas requisições. Todos os vencimentos de PETR4 custam cerca de 31 e levam uns 2 minutos.
- O modelo é europeu. Para puts americanas, vol e gregas são aproximações.
- A taxa é a mesma para todos os prazos, sem usar a curva de DI.
- O preço é o último negócio, não o meio do book. Durante o pregão, um negócio da manhã é comparado com o spot do momento.
- A API do site não é documentada. Se o formato mudar, a biblioteca quebra.

## Black-Scholes avulso

As funções de cálculo aceitam números ou arrays do numpy:

```python
import math
from brazil_options import preco, vol_implicita, gregas

r = math.log(1.1365)
T = 27 / 252

p = preco(56.0, 58.0, T, r, 0.0, 0.35, call=True)       # 2.0254
vol_implicita(p, 56.0, 58.0, T, r, 0.0, call=True)      # 0.35
gregas(56.0, 58.0, T, r, 0.0, 0.35, call=True)
# {'delta': 0.4485, 'gamma': 0.0617, 'theta': -0.0587, 'vega': 0.0725, 'rho': 0.0247}
```

`calcular_gregas(df, taxa)` também é exportada, para quem tem uma cadeia de outra fonte com as colunas `vencimento`, `du`, `tipo`, `strike`, `spot`, `preco` e `data_ultimo`.

## Testes

```bash
pip install -e ".[dev]"
pytest
```

## Aviso

Projeto independente, sem vínculo com o opcoes.net.br ou com a B3. Não é recomendação de investimento.

## Licença

MIT
