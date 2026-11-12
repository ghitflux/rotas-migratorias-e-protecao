"""Regera reports/resultados.json, reports/*.csv e reports/figuras/*.png a partir do extrato em data/.

    uv run python scripts/rodar_analise.py

Não usa rede nem data/brutos/. Semente fixa: rodar duas vezes dá os mesmos números.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from rotas_protecao import analise, dados, graficos, site  # noqa: E402
from rotas_protecao.estilo import milhar, percentual  # noqa: E402

REPORTS = RAIZ / "reports"
FIGURAS = REPORTS / "figuras"


def _registros(tabela, casas: int = 4) -> list[dict]:
    """DataFrame para lista de dicionários com números arredondados (o que vai para o JSON)."""
    saida = []
    for linha in tabela.to_dict(orient="records"):
        limpa = {}
        for chave, valor in linha.items():
            if isinstance(valor, (float, np.floating)):
                limpa[chave] = None if np.isnan(valor) else round(float(valor), casas)
            elif isinstance(valor, np.integer):
                limpa[chave] = int(valor)
            else:
                limpa[chave] = valor
        saida.append(limpa)
    return saida


def _salvar(figura, nome: str) -> None:
    figura.savefig(FIGURAS / nome)
    plt.close(figura)


def main() -> None:
    inicio = time.time()
    FIGURAS.mkdir(parents=True, exist_ok=True)
    base = dados.carregar()
    rng = np.random.default_rng(analise.SEMENTE)
    nomes = {e: f["comum"] for e, f in base["especies"].items()}

    descricao = analise.descricao(base)
    alto_mar = analise.alto_mar_por_especie(base, rng)
    jurisdicoes = analise.tempo_por_jurisdicao(base, rng)
    marcacao = analise.vies_de_marcacao(base, rng)
    curva = analise.curva_semanal(base)
    sensibilidade = analise.sensibilidade(base, rng)
    duracao = analise.duracao_e_alto_mar(base)
    populacoes = analise.por_populacao(base, rng)
    por_animal = analise.jurisdicoes_por_individuo(base)
    conexoes = analise.conexoes(base)
    travessias = analise.travessias(base)
    acaso = analise.contra_o_acaso(base, rng)
    trechos = analise.trechos_de_alto_mar(base)
    concentracao = analise.concentracao_do_alto_mar(base)
    sul_de_60 = analise.alto_mar_ao_sul_de_60(base)
    zonas = analise.zonas_principais(base)

    # Arquivos reutilizáveis
    jurisdicoes.drop(columns=["chave_especie"]).to_csv(REPORTS / "tempo_por_jurisdicao.csv", index=False)
    grade = base["grade_1grau"].copy()
    grade.insert(0, "especie_cientifico", grade["especie"].map({e: f["cientifico"] for e, f in base["especies"].items()}))
    grade.drop(columns=["especie"]).rename(columns={"especie_cientifico": "especie"}).to_csv(REPORTS / "grade_tempo_por_celula.csv", index=False)

    ind = base["individuos"]
    total_individuos, total_dias = len(ind), float(ind["dias_rastreados"].sum())
    geral = {
        "individuos": int(total_individuos),
        "especies": len(analise.ORDEM),
        "conjuntos": int(ind["conjunto"].nunique()),
        "anos_de_animal": round(total_dias / 365.25, 1),
        "registros_usados": int(ind["registros"].sum()),
        "registros_baixados": int(sum(f["registros_baixados"] for f in base["coleta"]["funil"].values())),
        "rastreamentos_baixados": int(sum(f["individuos_brutos"] for f in base["coleta"]["funil"].values())),
        "rastreamentos_curtos_demais": int(sum(f.get("individuos_curtos_demais", 0) for f in base["coleta"]["funil"].values())),
        "posicoes_tiradas_pelo_filtro_de_velocidade": int(sum(f["posicoes_tiradas_pelo_filtro_de_velocidade"] for f in base["coleta"]["funil"].values())),
        "licencas_dos_conjuntos": {lic: sum(1 for c in base["coleta"]["conjuntos"].values() if c["licenca"] == lic) for lic in sorted({c["licenca"] for c in base["coleta"]["conjuntos"].values()})},
        "ano_inicial": int(ind["ano_inicio"].min()),
        "ano_final": int(ind["ano_inicio"].max()),
        "alto_mar_na_area_do_oceano": round(analise.alto_mar_na_area_do_oceano(base["grade"]), 4),
        "jurisdicoes_nacionais_usadas": int((jurisdicoes["tipo"] != "alto-mar").groupby(jurisdicoes["jurisdicao"]).any().sum()),
    }

    resultados = {
        "coleta": {k: base["coleta"][k] for k in ("data_da_coleta", "conjuntos", "funil", "parametros")},
        "geral": geral,
        "descricao": descricao,
        "alto_mar_por_especie": _registros(alto_mar),
        "tempo_por_jurisdicao_principais": _registros(jurisdicoes.groupby("chave_especie", sort=False).head(6), 5),
        "vies_de_marcacao": _registros(marcacao),
        "curva_semanal": _registros(curva[curva["semana"] < 40]),
        "sensibilidade": _registros(sensibilidade),
        "duracao_e_alto_mar": _registros(duracao),
        "por_populacao": _registros(populacoes),
        "jurisdicoes_por_individuo": _registros(por_animal),
        "conexoes_principais": _registros(conexoes.head(25)),
        "travessias_principais": _registros(travessias.head(25)),
        "contra_o_acaso": _registros(acaso),
        "trechos_de_alto_mar": _registros(trechos),
        "concentracao_do_alto_mar": _registros(concentracao),
        "alto_mar_ao_sul_de_60": _registros(sul_de_60),
        "zonas_principais": _registros(zonas),
    }
    resultados["para_o_site"] = site.bloco(resultados)

    ordem = analise.ORDEM
    am = alto_mar.set_index("especie")
    maior, menor = am["tempo"].idxmax(), am["tempo"].idxmin()
    primeiras = int((jurisdicoes.groupby("chave_especie", sort=False).head(1)["tipo"] == "alto-mar").sum())
    pa = por_animal.set_index("especie")
    # acima ou abaixo do acaso: só quando o intervalo exclui zero nas duas caminhadas
    acima, abaixo = site.acima_e_abaixo_do_acaso(resultados["contra_o_acaso"], ordem)
    resultados["resumo_contra_o_acaso"] = {"acima_nas_duas_caminhadas": acima, "abaixo_nas_duas_caminhadas": abaixo}
    _salvar(
        graficos.tempo_x_pontos(
            alto_mar,
            f"O alto-mar vai de {percentual(am.loc[menor, 'tempo'])} a {percentual(am.loc[maior, 'tempo'])} do tempo rastreado, conforme a espécie",
            "Fração em alto-mar (fora de qualquer ZEE) pelo tempo rastreado e pela contagem de registros. Barra de erro: IC 95%.",
        ),
        "alto_mar_tempo_x_pontos.png",
    )
    _salvar(
        graficos.mapa_do_tempo(
            base["grade_1grau"], base["costa"],
            f"Onde estiveram os {milhar(geral['individuos'])} animais rastreados: {geral['anos_de_animal']:.0f} anos de animal",
            "Células de 1°. Azul: a maior parte do tempo na célula foi em alto-mar. Laranja: em águas de algum país.",
        ),
        "mapa_do_tempo.png",
    )  # fmt: skip
    _salvar(
        graficos.curva_desde_a_marcacao(
            curva, nomes,
            "As tartarugas levam meses para chegar ao alto-mar; albatrozes e elefantes-marinhos, dias",
            "Fração das amostras em alto-mar a cada semana desde a marcação (semanas com 5 animais ou mais).",
        ),
        "alto_mar_desde_a_marcacao.png",
    )  # fmt: skip
    _salvar(
        graficos.jurisdicoes(
            jurisdicoes, ordem,
            f"O alto-mar é onde {primeiras} das {len(ordem)} espécies passaram mais tempo",
            "As cinco jurisdições com mais tempo rastreado em cada espécie. Barra de erro: IC 95% por bootstrap de indivíduos.",
        ),
        "jurisdicoes_por_especie.png",
    )  # fmt: skip
    _salvar(
        graficos.observado_x_acaso(
            acaso, nomes, ordem,
            f"Mais alto-mar do que o acaso em {len(acima)} das {len(ordem)} espécies, menos em {len(abaixo)}",
            "Caminhadas aleatórias a partir do ponto de marcação, com os passos diários do próprio animal, sem entrar em terra.",
        ),
        "observado_x_acaso.png",
    )  # fmt: skip
    _salvar(
        graficos.jurisdicoes_por_animal(
            por_animal, nomes, ordem,
            f"{percentual(pa.loc['albatroz', 'duas_ou_mais'])} dos albatrozes e {percentual(pa.loc['couro', 'duas_ou_mais'])} das tartarugas-de-couro usaram águas de dois ou mais países",
            "Parte dos animais de cada espécie por número de jurisdições (ZEE ou área em disputa) em que ficou 24 h ou mais.",
        ),
        "jurisdicoes_por_animal.png",
    )  # fmt: skip

    (REPORTS / "resultados.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"reports/ regerado em {time.time() - inicio:.1f} s")
    print(alto_mar[["nome", "individuos", "tempo", "tempo_inf", "tempo_sup", "pontos", "diferenca"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
