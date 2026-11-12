"""Monta analise.ipynb com nbformat. Depois de montar, execute:

    uv run python scripts/montar_notebook.py
    uv run jupyter nbconvert --to notebook --execute --inplace analise.ipynb

O notebook é uma narrativa fina: lê o extrato de data/ e chama as funções de src/rotas_protecao/analise.py,
as mesmas que scripts/rodar_analise.py usa para gerar reports/resultados.json.
"""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

RAIZ = Path(__file__).resolve().parents[1]

CELULAS: list[tuple[str, str]] = [
    ("md", """# Quanto do caminho de um animal marinho migratório passa por águas de algum país, e quanto por alto-mar?

Tartarugas, tubarões-baleia, elefantes-marinhos e albatrozes cruzam oceanos inteiros. Proteger a praia de desova ou
a colônia não protege a rota. A decisão que este estudo informa: para que espécies, e em que trechos de oceano, a
cooperação entre países (ou a proteção em alto-mar) importa mais.

O caminho: (1) reconstruir a trajetória de cada animal a partir de posições de satélite públicas; (2) medir a
fração do **tempo** em cada jurisdição, e não a fração dos registros; (3) dar a incerteza reamostrando animais
inteiros; (4) testar o viés do local de marcação; (5) comparar com uma caminhada aleatória.

É análise de dado público agregado, feita por um profissional de dados, não por um biólogo. As trajetórias são
reconstruídas em `scripts/baixar_dados.py` (as posições não podem ser versionadas); aqui a análise parte do extrato
agregado em `data/`."""),
    ("code", """import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import display

from rotas_protecao import analise, dados, geodesia, graficos, trajetoria

pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_colwidth", 80)
base = dados.carregar()
rng = np.random.default_rng(analise.SEMENTE)
nomes = {e: f["comum"] for e, f in base["especies"].items()}


def mostrar(figura):
    display(figura)
    plt.close(figura)


print("Coleta:", base["coleta"]["data_da_coleta"])"""),
    ("md", """## 1. Os dados: quem foi rastreado

O OBIS distribui rastreamentos por satélite como registros de ocorrência. Só servem os conjuntos que guardam o
identificador do animal. A tabela mostra os conjuntos usados, com a licença de cada um, e o funil de limpeza."""),
    ("code", """conjuntos = pd.DataFrame(base["coleta"]["conjuntos"]).T[["especie", "populacao", "registros", "licenca", "titulo"]]
display(conjuntos)
display(pd.DataFrame(base["coleta"]["funil"]).T.fillna(0).astype(int))
display(pd.DataFrame(analise.descricao(base)).T.drop(columns=["populacoes"]))"""),
    ("md", """## 2. O método numa trajetória de brinquedo

Antes dos dados reais, o erro que o método evita. Um animal anda para leste no equador a 4 km/h: passa 100 horas de
um lado de uma fronteira e 100 horas do outro, mas o transmissor manda dez vezes mais posições no primeiro trecho.
A contagem de posições diz que ele quase não esteve do outro lado; a interpolação regular no tempo devolve a
metade."""),
    ("code", """grau_km = 2 * np.pi * geodesia.RAIO_KM / 360
horas = np.concatenate([np.arange(0, 100, 1.0), np.arange(100, 201, 10.0)])
lon = horas * 4.0 / grau_km
fronteira = 100 * 4.0 / grau_km
regular = trajetoria.interpolar_regular(horas, np.zeros_like(horas), lon, passo_h=1.0)
print(f"fração além da fronteira, contando posições: {np.mean(lon >= fronteira):.1%}")
print(f"fração além da fronteira, pelo tempo:        {np.mean(regular['lon'] >= fronteira):.1%}")"""),
    ("md", """## 3. Tempo, não pontos

Para cada espécie: a fração em alto-mar pelo tempo rastreado (amostras de 6 horas ao longo da trajetória, sem
interpolar por cima de falhas de mais de 10 dias) e pela contagem dos registros brutos. O intervalo do método
reamostra animais inteiros. A tabela mostra também o intervalo ingênuo, que trata cada registro como independente."""),
    ("code", """alto_mar = analise.alto_mar_por_especie(base, rng)
display(alto_mar.set_index("nome")[["individuos", "tempo", "tempo_inf", "tempo_sup", "pontos", "pontos_inf_ingenuo", "pontos_sup_ingenuo", "diferenca", "diferenca_inf", "diferenca_sup"]])
# De onde vem a diferença: de dentro de cada trajetória, ou de quem transmite mais pesar mais?
display(alto_mar.set_index("nome")[["diferenca", "erro_dentro_de_cada_animal", "erro_de_quem_transmite_mais"]])
mostrar(graficos.tempo_x_pontos(alto_mar, "Fração em alto-mar: pelo tempo e pela contagem de registros", "Barra de erro: IC 95% por bootstrap de indivíduos."))"""),
    ("code", """mostrar(graficos.mapa_do_tempo(base["grade_1grau"], base["costa"], "Onde os animais rastreados estiveram", "Células de 1°. Azul: maior parte do tempo em alto-mar. Laranja: em águas de algum país."))"""),
    ("md", """## 4. Em que jurisdições

A tabela completa está em `reports/tempo_por_jurisdicao.csv`. Abaixo, as seis primeiras de cada espécie."""),
    ("code", """jurisdicoes = analise.tempo_por_jurisdicao(base, rng)
display(jurisdicoes.groupby("chave_especie", sort=False).head(6).set_index(["nome_comum", "jurisdicao"])[["tipo", "fracao_do_tempo", "ic95_inferior", "ic95_superior", "fracao_dos_registros", "individuos_que_usaram"]])
mostrar(graficos.jurisdicoes(jurisdicoes, analise.ORDEM, "As cinco jurisdições com mais tempo em cada espécie", "Barra de erro: IC 95% por bootstrap de indivíduos."))"""),
    ("md", """## 5. O viés de onde se marca

Os animais são marcados perto da costa: na praia de desova, na colônia, no ponto de agregação. O começo de toda
trajetória é costeiro por construção. Dois testes: a curva semana a semana desde a marcação, e a fração em alto-mar
refeita descartando os primeiros 14, 28 e 56 dias de cada animal."""),
    ("code", """mostrar(graficos.curva_desde_a_marcacao(analise.curva_semanal(base), nomes, "Fração em alto-mar por semana desde a marcação", "Semanas com 5 animais ou mais."))
marcacao = analise.vies_de_marcacao(base, rng)
display(marcacao.pivot(index="especie", columns="dias_descartados", values="estimativa").loc[analise.ORDEM])
display(marcacao.pivot(index="especie", columns="dias_descartados", values="individuos").loc[analise.ORDEM])"""),
    ("md", """## 6. Duração desigual, falhas de transmissão e populações

Três perguntas de robustez: o número muda se a regra para falhas de transmissão for outra? Muda se só entrarem
animais rastreados por muito tempo, ou se cada animal pesar igual? E muda de uma população para outra da mesma
espécie?"""),
    ("code", """sens = analise.sensibilidade(base, rng)
display(sens.pivot(index="variante", columns="especie", values="estimativa")[analise.ORDEM])
display(analise.duracao_e_alto_mar(base).set_index("especie"))
display(analise.por_populacao(base, rng).set_index(["especie", "populacao"]))"""),
    ("md", """## 7. Quantas jurisdições um animal usa, e quem compartilha animais com quem"""),
    ("code", """por_animal = analise.jurisdicoes_por_individuo(base)
display(por_animal.drop(columns=["distribuicao"]).set_index("especie"))
mostrar(graficos.jurisdicoes_por_animal(por_animal, nomes, analise.ORDEM, "Quantas jurisdições nacionais um mesmo animal usa", "Jurisdições em que o animal ficou 24 h ou mais."))
display(analise.conexoes(base).head(15))
display(analise.travessias(base).head(15))"""),
    ("md", """## 8. Contra o acaso

A hipótese nula: um animal que sai do mesmo ponto de marcação e dá passos do mesmo tamanho, sem destino. Duas
versões: sem memória (cada passo num rumo qualquer) e com persistência (os giros do próprio animal). Se o animal
real usa mais o alto-mar do que as caminhadas, o alto-mar não é só consequência de andar muito."""),
    ("code", """acaso = analise.contra_o_acaso(base, rng)
display(acaso.set_index(["especie", "caminhada"]))
mostrar(graficos.observado_x_acaso(acaso, nomes, analise.ORDEM, "Alto-mar observado e o das caminhadas aleatórias", "Fração dos dias em alto-mar."))"""),
    ("md", """## 9. Os trechos de alto-mar mais usados"""),
    ("code", """display(analise.trechos_de_alto_mar(base).set_index(["especie", "bloco"]))
display(analise.concentracao_do_alto_mar(base).set_index("especie"))"""),
    ("md", """## 10. O que levar daqui

- A resposta muda muito de uma espécie para outra, e dentro da mesma espécie de uma população para outra.
- Contar registros em vez de tempo empata em três das cinco espécies. Onde erra, o erro quase todo vem de animais
  com transmissor mais falante pesarem mais, e não de dentro de cada trajetória.
- O intervalo por indivíduo é muito mais largo do que o que se obtém tratando cada posição como independente.
- Contra a caminhada aleatória, o albatroz-errante usa o alto-mar um pouco menos do que o acaso: ele sempre volta
  à colônia. Uma hipótese nula sem retorno é ruim para animais assim, e o README diz isso.
- O README lista onde o estudo falha e o que faltaria para isto virar contribuição científica."""),
]


def main() -> None:
    caderno = new_notebook()
    caderno.cells = [new_markdown_cell(texto) if tipo == "md" else new_code_cell(texto) for tipo, texto in CELULAS]
    caderno.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    caderno.metadata["language_info"] = {"name": "python"}
    nbformat.write(caderno, RAIZ / "analise.ipynb")
    print(f"analise.ipynb montado com {len(caderno.cells)} células")


if __name__ == "__main__":
    main()
