"""Tabelas da análise conferidas num extrato sintético, montado em memória (sem arquivo e sem rede)."""

import numpy as np
import pandas as pd
import pytest

from rotas_protecao import analise, dados
from rotas_protecao.coleta import ESPECIES
from rotas_protecao.site import bloco

# grupos: 0 = alto-mar, 1 = Brasil, 2 = França, 3 = área em disputa
NOMES = pd.Series({0: dados.ALTO_MAR, 1: "Brasil", 2: "França", 3: "Área em disputa: Reino Unido / Argentina"})


def _base() -> dict:
    """Em cada espécie, três animais com amostras conhecidas (cada amostra vale 6 h).

    animal 1: 400 amostras, 300 em alto-mar e 100 no Brasil; registros brutos: 10 em alto-mar, 90 no Brasil
    animal 2: 100 amostras, todas no Brasil; registros: 50 no Brasil
    animal 3: 100 amostras: 40 Brasil, 40 França, 20 na área em disputa; registros: 10, 10, 0
    """
    individuos, tempo = [], []
    for especie in analise.ORDEM:
        modelos = [
            (400, {0: (300, 10), 1: (100, 90)}, 0.75, 0.30, 0.60),
            (100, {1: (100, 50)}, 0.0, 0.10, 0.20),
            (100, {1: (40, 10), 2: (40, 10), 3: (20, 0)}, 0.0, 0.10, 0.10),
        ]
        for k, (amostras, usos, diario, nulo_sem, nulo_com) in enumerate(modelos, 1):
            nome = f"{especie}_{k:04d}"
            individuos.append(
                {
                    "individuo": nome, "especie": especie, "conjunto": f"{especie}_c{min(k, 2)}", "populacao": "A" if k < 3 else "B",
                    "ano_inicio": 2000 + k, "registros": sum(p for _, p in usos.values()), "dias_rastreados": amostras / 4,
                    "dias_do_primeiro_ao_ultimo": amostras / 4 + 10, "dias_em_falhas": 10.0, "amostras_em_terra": 4,
                    "codigo_da_marcacao": 1, "passo_diario_mediano_km": 30.0, "distancia_maxima_da_marcacao_km": 1000.0,
                    "amostras_diarias": amostras // 4, "altomar_diario": diario, "altomar_nulo_sem_memoria": nulo_sem,
                    "altomar_nulo_persistente": nulo_com,
                }
            )  # fmt: skip
            for grupo, (a, p) in usos.items():
                tempo.append(
                    {
                        "individuo": nome, "codigo": grupo, "grupo": grupo, "amostras": a, "pontos_brutos": p,
                        "amostras_corte14": max(a - 56, 0) if grupo == 1 else a, "amostras_corte28": a, "amostras_corte56": a,
                        "falha3": a, "semlimite": a,
                    }
                )  # fmt: skip
    grade = pd.DataFrame(
        [{"especie": e, "lat_sul": -30, "lon_oeste": 10 + k, "dias": 20.0, "dias_em_alto_mar": d, "individuos": 2} for e in analise.ORDEM for k, d in enumerate([20.0, 5.0, 0.0])]
    )
    return {
        "especies": ESPECIES,
        "nome_do_grupo": NOMES,
        "individuos": pd.DataFrame(individuos),
        "tempo": pd.DataFrame(tempo),
        "travessias": pd.DataFrame({"especie": ["couro", "couro"], "de_grupo": [1, 0], "para_grupo": [0, 1], "travessias": [3, 2], "individuos": [1, 1]}),
        "semanas": pd.DataFrame({"especie": ["couro"] * 2, "semana": [0, 1], "amostras": [84, 56], "amostras_em_alto_mar": [0, 28], "individuos": [3, 5]}),
        "grade_1grau": grade,
    }


def test_matriz_por_grupo_tem_uma_linha_por_animal_e_coluna_do_alto_mar():
    matriz, ficha = dados.matriz_por_grupo(_base(), "couro")
    assert matriz.shape == (3, 4) and list(matriz.index) == list(ficha.index)
    assert matriz[0].tolist() == [300, 0, 0]
    assert matriz.sum(axis=1).tolist() == [400, 100, 100]


def test_alto_mar_pelo_tempo_e_pelos_pontos():
    tabela = analise.alto_mar_por_especie(_base(), np.random.default_rng(0)).set_index("especie")
    linha = tabela.loc["couro"]
    assert linha["tempo"] == pytest.approx(300 / 600)  # tempo somado
    assert linha["pontos"] == pytest.approx(10 / 170)  # registros somados
    assert linha["diferenca"] == pytest.approx(300 / 600 - 10 / 170)
    assert linha["media_por_individuo"] == pytest.approx(0.25)  # (0,75 + 0 + 0) / 3
    # os registros do animal 1 dizem 10% de alto-mar; com o peso do tempo dele: 400 x 0,1 / 600
    assert linha["erro_dentro_de_cada_animal"] == pytest.approx(0.5 - 40 / 600)
    assert linha["erro_de_quem_transmite_mais"] == pytest.approx(40 / 600 - 10 / 170)
    assert linha["erro_dentro_de_cada_animal"] + linha["erro_de_quem_transmite_mais"] == pytest.approx(linha["diferenca"])
    assert linha["individuos_que_foram_ao_alto_mar"] == pytest.approx(1 / 3)
    assert linha["tempo_inf"] <= linha["tempo"] <= linha["tempo_sup"]
    assert linha["pontos_sup_ingenuo"] - linha["pontos_inf_ingenuo"] < linha["tempo_sup"] - linha["tempo_inf"]


def test_tempo_por_jurisdicao_soma_um_e_classifica_o_tipo():
    tabela = analise.tempo_por_jurisdicao(_base(), np.random.default_rng(0))
    couro = tabela[tabela["chave_especie"] == "couro"].set_index("jurisdicao")
    assert couro["fracao_do_tempo"].sum() == pytest.approx(1.0, abs=1e-4)
    assert couro.loc["Brasil", "fracao_do_tempo"] == pytest.approx(240 / 600, abs=1e-5)
    assert couro.loc["Brasil", "individuos_que_usaram"] == 3
    assert couro.loc[dados.ALTO_MAR, "tipo"] == "alto-mar"
    assert couro.loc["Área em disputa: Reino Unido / Argentina", "tipo"] == "disputa ou regime conjunto"
    assert couro.loc["França", "dias_de_animal"] == pytest.approx(10.0)


def test_descartar_o_comeco_aumenta_o_alto_mar_quando_o_comeco_e_costeiro():
    tabela = analise.vies_de_marcacao(_base(), np.random.default_rng(0))
    couro = tabela[tabela["especie"] == "couro"].set_index("dias_descartados")
    assert couro.loc[0, "estimativa"] == pytest.approx(0.5)
    # sem 56 amostras do Brasil em cada animal: 300 / (600 - 56 - 56 - 40)
    assert couro.loc[14, "estimativa"] == pytest.approx(300 / 448)


def test_jurisdicoes_por_individuo():
    tabela = analise.jurisdicoes_por_individuo(_base()).set_index("especie")
    linha = tabela.loc["baleia"]
    assert linha["distribuicao"] == {1: 2, 3: 1}
    assert linha["maximo"] == 3 and linha["duas_ou_mais"] == pytest.approx(1 / 3)
    assert linha["mais_de_um_regime"] == pytest.approx(2 / 3)  # o animal 1 usa Brasil e alto-mar; o 3, três jurisdições


def test_conexoes_contam_animais_em_comum():
    tabela = analise.conexoes(_base(), minimo_de_individuos=1)
    couro = tabela[tabela["especie"] == "couro"]
    par = couro[(couro["jurisdicao_a"] == "Brasil") & (couro["jurisdicao_b"] == "França")].iloc[0]
    assert par["individuos_em_comum"] == 1 and par["individuos_em_a"] == 3 and par["individuos_em_b"] == 1
    assert len(couro) == 3  # Brasil-França, Brasil-disputa, França-disputa


def test_travessias_somam_os_dois_sentidos():
    tabela = analise.travessias(_base())
    assert tabela.iloc[0].to_dict() == {"especie": "couro", "entre": dados.ALTO_MAR, "e": "Brasil", "travessias": 5}


def test_contra_o_acaso_pesa_pelos_dias():
    tabela = analise.contra_o_acaso(_base(), np.random.default_rng(0))
    linha = tabela[(tabela["especie"] == "elefante") & (tabela["caminhada"] == "sem memória")].iloc[0]
    assert linha["observado"] == pytest.approx(0.75 * 100 / 150)
    assert linha["acaso"] == pytest.approx((0.30 * 100 + 0.10 * 25 + 0.10 * 25) / 150)
    assert linha["diferenca"] == pytest.approx(linha["observado"] - linha["acaso"])
    assert linha["individuos_acima_do_acaso"] == pytest.approx(1 / 3)


def test_sensibilidade_e_populacoes():
    base = _base()
    sens = analise.sensibilidade(base, np.random.default_rng(0))
    couro = sens[sens["especie"] == "couro"].set_index("variante")
    assert couro.loc["média por indivíduo (cada animal pesa igual)", "estimativa"] == pytest.approx(0.25)
    assert couro.loc["falha máxima de 3 dias", "estimativa"] == pytest.approx(0.5)
    pop = analise.por_populacao(base, np.random.default_rng(0))
    couro = pop[pop["especie"] == "couro"].set_index("populacao")
    assert couro.loc["A", "estimativa"] == pytest.approx(300 / 500) and couro.loc["B", "estimativa"] == 0.0


def test_trechos_de_alto_mar_e_rotulos():
    tabela = analise.trechos_de_alto_mar(_base())
    linha = tabela[tabela["especie"] == "couro"].iloc[0]
    assert linha["bloco"] == "20° a 30°S, 10° a 20°L"
    assert linha["dias_em_alto_mar"] == pytest.approx(25.0)
    assert linha["parte_do_tempo_da_especie"] == pytest.approx(25 / 60)
    conc = analise.concentracao_do_alto_mar(_base()).set_index("especie")
    assert conc.loc["couro", "celulas_para_metade_do_tempo"] == 1


def test_alto_mar_ao_sul_de_60_graus():
    base = _base()
    assert analise.alto_mar_ao_sul_de_60(base).set_index("especie").loc["couro", "parte_do_tempo_total"] == 0.0
    base["grade_1grau"] = pd.concat(
        [base["grade_1grau"], pd.DataFrame([{"especie": "couro", "lat_sul": -65, "lon_oeste": 0, "dias": 40.0, "dias_em_alto_mar": 40.0, "individuos": 1}])], ignore_index=True
    )
    linha = analise.alto_mar_ao_sul_de_60(base).set_index("especie").loc["couro"]
    assert linha["parte_do_tempo_total"] == pytest.approx(40 / 100)
    assert linha["parte_do_tempo_em_alto_mar"] == pytest.approx(40 / 65)


def test_zonas_principais_usam_o_nome_do_territorio():
    base = _base()
    base["jurisdicoes"] = pd.DataFrame({"codigo": [0, 1, 2, 3], "geoname": ["High seas", "Brazilian EEZ", "French EEZ (Réunion)", "Overlapping claim"]})
    zonas = analise.zonas_principais(base)
    couro = zonas[zonas["especie"] == "couro"]
    assert couro.iloc[0]["zona"] == "Brazilian EEZ" and couro.iloc[0]["fracao_do_tempo"] == pytest.approx(240 / 600)
    assert couro.iloc[0]["individuos_que_usaram"] == 3
    assert "High seas" not in set(couro["zona"])


@pytest.mark.parametrize(
    ("lat", "lon", "esperado"),
    [(-65, 10, "Oceano Austral"), (38, 15, "Mediterrâneo"), (30, -40, "Atlântico Norte"), (-25, -20, "Atlântico Sul"), (-20, 70, "Índico"), (30, -150, "Pacífico Norte"), (-15, 160, "Pacífico Sul")],
)
def test_oceano_aproximado(lat, lon, esperado):
    assert analise.oceano_aproximado(lat, lon) == esperado


def test_nome_do_grupo_traduz_paises_e_tipos():
    assert dados.nome_do_grupo("High seas") == dados.ALTO_MAR
    assert dados.nome_do_grupo("France") == "França"
    assert dados.nome_do_grupo("Overlapping claim: United Kingdom / Argentina") == "Área em disputa: Reino Unido / Argentina"
    assert dados.nome_do_grupo("Joint regime: Japan / South Korea") == "Regime conjunto: Japão / Coreia do Sul"
    assert dados.nome_do_grupo("Atlantis") == "Atlantis"


def test_bloco_do_site_respeita_o_formato():
    base = _base()
    rng = np.random.default_rng(0)
    registros = lambda t: t.to_dict(orient="records")  # noqa: E731
    r = {
        "alto_mar_por_especie": registros(analise.alto_mar_por_especie(base, rng)),
        "contra_o_acaso": registros(analise.contra_o_acaso(base, rng)),
        "geral": {"individuos": 15, "especies": 5, "conjuntos": 10, "ano_inicial": 2001, "ano_final": 2003},
        "coleta": {"data_da_coleta": "2026-11-12"},
    }
    b = bloco(r)
    for chave in ("numero_chave", "pergunta", "resultado", "detalhe", "dados"):
        assert set(b[chave]) == {"pt", "en", "es"}
    assert all(len(texto) <= 12 for texto in b["numero_chave"].values())
    g = b["grafico"]
    assert g["tipo"] == "barras" and len(g["series"]) == 2
    assert [s["papel"] for s in g["series"]] == ["principal", "base"]
    for serie in g["series"]:
        assert len(serie["pontos"]) == 5 and all(0 <= valor <= 1 for _, valor in serie["pontos"])
        assert all(len(serie["rotulos"][i]) == 5 for i in ("pt", "en", "es"))
    assert "12/11/2026" in b["dados"]["pt"] and "12 Nov 2026" in b["dados"]["en"]
