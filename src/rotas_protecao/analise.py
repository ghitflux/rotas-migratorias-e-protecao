"""Cada tabela do estudo sai de uma função daqui. Entrada: o extrato de `dados.carregar()`."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from rotas_protecao import dados, estatistica

N_REAMOSTRAS = 4000
SEMENTE = 19
PASSO_DIAS = 0.25  # cada amostra vale 6 horas
ESTADIA_MINIMA = 4  # amostras (24 h) para dizer que o animal usou uma jurisdição
ORDEM = ["albatroz", "elefante", "couro", "cabecuda", "baleia"]


def _pesos(n: int, rng: np.random.Generator) -> np.ndarray:
    return estatistica.pesos_de_bootstrap(n, N_REAMOSTRAS, rng)


def alto_mar_ao_sul_de_60(base: dict) -> pd.DataFrame:
    """Quanto do tempo em alto-mar fica na área do Tratado da Antártida (ao sul de 60°S), por espécie."""
    linhas = []
    for especie in ORDEM:
        parte = base["grade_1grau"][base["grade_1grau"]["especie"] == especie]
        sul = parte[parte["lat_sul"] < -60]
        total, mar = float(parte["dias"].sum()), float(parte["dias_em_alto_mar"].sum())
        linhas.append(
            {
                "especie": especie,
                "parte_do_tempo_total": float(sul["dias_em_alto_mar"].sum()) / total,
                "alto_mar_ao_norte_de_60_no_tempo_total": (mar - float(sul["dias_em_alto_mar"].sum())) / total,
                "parte_do_tempo_em_alto_mar": float(sul["dias_em_alto_mar"].sum()) / mar if mar > 0 else np.nan,
            }
        )
    return pd.DataFrame(linhas)


def alto_mar_na_area_do_oceano(grade) -> float:
    """Fração da área de mar da grade que é alto-mar (cada célula pesa pelo cosseno da latitude).

    Serve de conferência da grade: o valor conhecido é de pouco mais de 60% da superfície do oceano.
    """
    n_lat = grade.codigos.shape[0]
    lat = -90.0 + (np.arange(n_lat) + 0.5) * grade.resolucao
    peso = np.cos(np.radians(lat))[:, None]
    mar = ~grade.terra
    return float((peso * ((grade.codigos == 0) & mar)).sum() / (peso * mar).sum())


def descricao(base: dict) -> dict:
    """Quantos animais, quantos dias, quantas posições, por espécie e por conjunto."""
    ind = base["individuos"]
    por_especie = {}
    for especie in ORDEM:
        parte = ind[ind["especie"] == especie]
        por_especie[especie] = {
            "nome": base["especies"][especie]["comum"],
            "cientifico": base["especies"][especie]["cientifico"],
            "individuos": int(len(parte)),
            "dias_rastreados": round(float(parte["dias_rastreados"].sum()), 0),
            "anos_de_animal": round(float(parte["dias_rastreados"].sum()) / 365.25, 1),
            "duracao_mediana_dias": round(float(parte["dias_rastreados"].median()), 1),
            "duracao_p10_dias": round(float(parte["dias_rastreados"].quantile(0.10)), 1),
            "duracao_p90_dias": round(float(parte["dias_rastreados"].quantile(0.90)), 1),
            "registros": int(parte["registros"].sum()),
            "fracao_do_tempo_em_falhas": round(float(parte["dias_em_falhas"].sum() / parte["dias_do_primeiro_ao_ultimo"].sum()), 4),
            "fracao_das_amostras_em_terra": round(float(parte["amostras_em_terra"].sum() * PASSO_DIAS / parte["dias_rastreados"].sum()), 4),
            "passo_diario_mediano_km": round(float(parte["passo_diario_mediano_km"].median()), 1),
            "distancia_maxima_mediana_km": round(float(parte["distancia_maxima_da_marcacao_km"].median()), 0),
            "ano_inicial": int(parte["ano_inicio"].min()),
            "ano_final": int(parte["ano_inicio"].max()),
            "conjuntos": int(parte["conjunto"].nunique()),
            "populacoes": sorted(parte["populacao"].unique()),
            "marcados_em_alto_mar": round(float((parte["codigo_da_marcacao"] == 0).mean()), 4),
        }
    return por_especie


def alto_mar_por_especie(base: dict, rng: np.random.Generator) -> pd.DataFrame:
    """Fração em alto-mar pelo tempo (método) e pela contagem de registros (linha de base), por espécie."""
    linhas = []
    for especie in ORDEM:
        tempo, ficha = dados.matriz_por_grupo(base, especie, "amostras")
        pontos, _ = dados.matriz_por_grupo(base, especie, "pontos_brutos")
        pesos = _pesos(len(ficha), rng)
        t_mar, t_total = tempo[0].to_numpy(), tempo.sum(axis=1).to_numpy()
        p_mar, p_total = pontos[0].to_numpy(), pontos.sum(axis=1).to_numpy()
        por_tempo = estatistica.bootstrap_da_fracao(t_mar, t_total, pesos)
        por_pontos = estatistica.bootstrap_da_fracao(p_mar, p_total, pesos)
        ingenuo = estatistica.intervalo_ingenuo_por_pontos(p_mar.sum(), p_total.sum())
        diferenca = estatistica.bootstrap_da_diferenca(t_mar, t_total, p_mar, p_total, pesos)
        fracoes = t_mar / t_total
        # Decomposição do erro da contagem: a mesma conta por registros, mas com cada animal pesando pelo
        # seu tempo. O que sobra de diferença para o tempo vem de dentro de cada trajetória (transmissão
        # desigual ao longo do caminho); o resto vem de quem transmite mais pesar mais.
        hibrido = float(np.sum(t_total * p_mar / p_total) / t_total.sum())
        linhas.append(
            {
                "especie": especie,
                "nome": base["especies"][especie]["comum"],
                "individuos": len(ficha),
                "tempo": por_tempo["estimativa"],
                "tempo_inf": por_tempo["inferior"],
                "tempo_sup": por_tempo["superior"],
                "pontos": por_pontos["estimativa"],
                "pontos_inf_por_individuo": por_pontos["inferior"],
                "pontos_sup_por_individuo": por_pontos["superior"],
                "pontos_inf_ingenuo": ingenuo[0],
                "pontos_sup_ingenuo": ingenuo[1],
                # quantas vezes o intervalo honesto (por indivíduo) é mais largo que o ingênuo, na mesma conta
                "razao_das_larguras": (por_pontos["superior"] - por_pontos["inferior"]) / (ingenuo[1] - ingenuo[0]),
                "diferenca": diferenca["estimativa"],
                "diferenca_inf": diferenca["inferior"],
                "diferenca_sup": diferenca["superior"],
                "erro_dentro_de_cada_animal": por_tempo["estimativa"] - hibrido,
                "erro_de_quem_transmite_mais": hibrido - por_pontos["estimativa"],
                "media_por_individuo": estatistica.fracao_media_por_individuo(t_mar, t_total),
                "mediana_por_individuo": float(np.median(fracoes)),
                "individuos_que_foram_ao_alto_mar": float(np.mean(tempo[0].to_numpy() >= ESTADIA_MINIMA)),
                "individuos_com_mais_da_metade_em_alto_mar": float(np.mean(fracoes > 0.5)),
            }
        )
    return pd.DataFrame(linhas)


def tempo_por_jurisdicao(base: dict, rng: np.random.Generator) -> pd.DataFrame:
    """A tabela reutilizável: fração do tempo de cada espécie em cada jurisdição, com intervalo."""
    nomes = base["nome_do_grupo"]
    linhas = []
    for especie in ORDEM:
        tempo, ficha = dados.matriz_por_grupo(base, especie, "amostras")
        pontos, _ = dados.matriz_por_grupo(base, especie, "pontos_brutos")
        pesos = _pesos(len(ficha), rng)
        total = tempo.sum(axis=1).to_numpy()
        for grupo in tempo.columns:
            coluna = tempo[grupo].to_numpy()
            if coluna.sum() == 0:
                continue
            r = estatistica.bootstrap_da_fracao(coluna, total, pesos)
            linhas.append(
                {
                    "especie": base["especies"][especie]["cientifico"],
                    "nome_comum": base["especies"][especie]["comum"],
                    "jurisdicao": nomes[grupo],
                    "tipo": "alto-mar" if grupo == 0 else ("disputa ou regime conjunto" if ": " in nomes[grupo] else "ZEE"),
                    "fracao_do_tempo": round(r["estimativa"], 5),
                    "ic95_inferior": round(r["inferior"], 5),
                    "ic95_superior": round(r["superior"], 5),
                    "fracao_dos_registros": round(float(pontos[grupo].sum() / pontos.to_numpy().sum()) if grupo in pontos.columns else 0.0, 5),
                    "dias_de_animal": round(float(coluna.sum() * PASSO_DIAS), 1),
                    "individuos_que_usaram": int((coluna >= ESTADIA_MINIMA).sum()),
                    "individuos_da_especie": len(ficha),
                    "chave_especie": especie,
                }
            )
    tabela = pd.DataFrame(linhas)
    return tabela.sort_values(["chave_especie", "fracao_do_tempo"], ascending=[True, False], kind="stable").reset_index(drop=True)


def zonas_principais(base: dict, quantas: int = 6) -> pd.DataFrame:
    """As zonas (polígonos da fonte, com o nome do território) com mais tempo em cada espécie.

    A tabela por país soma territórios distantes: "França" pode ser Kerguelen, Crozet ou a Reunião.
    """
    nomes = base["jurisdicoes"].set_index("codigo")["geoname"]
    linhas = []
    for especie in ORDEM:
        ficha = base["individuos"][base["individuos"]["especie"] == especie]
        tempo = base["tempo"][base["tempo"]["individuo"].isin(ficha["individuo"])]
        total = tempo["amostras"].sum()
        por_zona = tempo[tempo["codigo"] != 0].groupby("codigo").agg(amostras=("amostras", "sum"), individuos=("amostras", lambda s: int((s >= ESTADIA_MINIMA).sum())))
        for codigo, linha in por_zona.sort_values("amostras", ascending=False).head(quantas).iterrows():
            linhas.append({"especie": especie, "zona": nomes[codigo], "fracao_do_tempo": float(linha["amostras"] / total), "individuos_que_usaram": int(linha["individuos"])})
    return pd.DataFrame(linhas)


def vies_de_marcacao(base: dict, rng: np.random.Generator) -> pd.DataFrame:
    """Fração em alto-mar descartando as primeiras semanas de cada trajetória."""
    linhas = []
    for especie in ORDEM:
        for corte in (0, 14, 28, 56):
            coluna = "amostras" if corte == 0 else f"amostras_corte{corte}"
            tempo, ficha = dados.matriz_por_grupo(base, especie, coluna)
            total = tempo.sum(axis=1).to_numpy()
            sobrou = total > 0
            pesos = _pesos(int(sobrou.sum()), rng)
            r = estatistica.bootstrap_da_fracao(tempo[0].to_numpy()[sobrou], total[sobrou], pesos)
            linhas.append({"especie": especie, "dias_descartados": corte, "individuos": int(sobrou.sum()), "dias_de_animal": float(total.sum() * PASSO_DIAS), **r})
    return pd.DataFrame(linhas)


def curva_semanal(base: dict, minimo_de_individuos: int = 5) -> pd.DataFrame:
    """Fração das amostras em alto-mar por semana desde a marcação (só semanas com animais suficientes)."""
    s = base["semanas"].copy()
    s["fracao_em_alto_mar"] = s["amostras_em_alto_mar"] / s["amostras"]
    return s[s["individuos"] >= minimo_de_individuos].reset_index(drop=True)


def sensibilidade(base: dict, rng: np.random.Generator) -> pd.DataFrame:
    """Como a fração em alto-mar muda com as escolhas: falhas, duração mínima e peso de cada animal."""
    linhas = []
    for especie in ORDEM:
        tempo, ficha = dados.matriz_por_grupo(base, especie, "amostras")
        mar, total = tempo[0].to_numpy(), tempo.sum(axis=1).to_numpy()
        dias = ficha["dias_rastreados"].to_numpy()

        def linha(variante: str, m: np.ndarray, t: np.ndarray) -> dict:
            pesos = _pesos(len(t), rng)
            return {"especie": especie, "variante": variante, "individuos": len(t), **estatistica.bootstrap_da_fracao(m, t, pesos)}

        linhas.append(linha("principal: falha máxima de 10 dias, tempo somado", mar, total))
        for nome, rotulo in (("falha3", "falha máxima de 3 dias"), ("semlimite", "interpolando por cima de qualquer falha")):
            outra, _ = dados.matriz_por_grupo(base, especie, nome)
            t = outra.sum(axis=1).to_numpy()
            linhas.append(linha(rotulo, outra[0].to_numpy()[t > 0], t[t > 0]))
        for minimo in (30, 90, 180):
            escolhidos = dias >= minimo
            if escolhidos.sum() >= 5:
                linhas.append(linha(f"só animais com {minimo} dias ou mais", mar[escolhidos], total[escolhidos]))
        fracoes = mar / total
        pesos = _pesos(len(total), rng)
        medias = (pesos @ fracoes) / pesos.sum(axis=1)
        inferior, superior = estatistica.intervalo(medias)
        linhas.append({"especie": especie, "variante": "média por indivíduo (cada animal pesa igual)", "individuos": len(total), "estimativa": float(fracoes.mean()), "inferior": inferior, "superior": superior})
    return pd.DataFrame(linhas)


def duracao_e_alto_mar(base: dict) -> pd.DataFrame:
    """Animais rastreados por menos tempo aparecem menos em alto-mar? Correlação de postos por espécie."""
    linhas = []
    for especie in ORDEM:
        tempo, ficha = dados.matriz_por_grupo(base, especie, "amostras")
        fracoes = tempo[0].to_numpy() / tempo.sum(axis=1).to_numpy()
        dias = ficha["dias_rastreados"].to_numpy()
        rho, p = stats.spearmanr(dias, fracoes)
        curtos = dias < np.median(dias)
        linhas.append(
            {
                "especie": especie,
                "spearman": float(rho),
                "p_valor": float(p),
                "alto_mar_dos_mais_curtos": float(tempo[0].to_numpy()[curtos].sum() / tempo.sum(axis=1).to_numpy()[curtos].sum()),
                "alto_mar_dos_mais_longos": float(tempo[0].to_numpy()[~curtos].sum() / tempo.sum(axis=1).to_numpy()[~curtos].sum()),
                "duracao_mediana_dias": float(np.median(dias)),
            }
        )
    return pd.DataFrame(linhas)


def por_populacao(base: dict, rng: np.random.Generator) -> pd.DataFrame:
    """A mesma espécie, população a população: o número da espécie depende de onde se marcou."""
    linhas = []
    for especie in ORDEM:
        tempo, ficha = dados.matriz_por_grupo(base, especie, "amostras")
        for populacao, parte in ficha.groupby("populacao"):
            m = tempo.loc[parte.index]
            pesos = _pesos(len(parte), rng)
            r = estatistica.bootstrap_da_fracao(m[0].to_numpy(), m.sum(axis=1).to_numpy(), pesos)
            linhas.append({"especie": especie, "populacao": populacao, "individuos": len(parte), "dias_de_animal": float(m.to_numpy().sum() * PASSO_DIAS), **r})
    return pd.DataFrame(linhas)


def jurisdicoes_por_individuo(base: dict) -> pd.DataFrame:
    """Quantas jurisdições nacionais (com pelo menos 24 h de permanência) cada animal usou."""
    linhas = []
    for especie in ORDEM:
        tempo, ficha = dados.matriz_por_grupo(base, especie, "amostras")
        nacionais = tempo.drop(columns=[0])
        n = (nacionais >= ESTADIA_MINIMA).sum(axis=1).to_numpy()
        usou_mar = tempo[0].to_numpy() >= ESTADIA_MINIMA
        linhas.append(
            {
                "especie": especie,
                "individuos": len(n),
                "media": float(n.mean()),
                "mediana": float(np.median(n)),
                "maximo": int(n.max()),
                "nenhuma": float(np.mean(n == 0)),
                "uma": float(np.mean(n == 1)),
                "duas_ou_mais": float(np.mean(n >= 2)),
                "tres_ou_mais": float(np.mean(n >= 3)),
                "mais_de_um_regime": float(np.mean((n + usou_mar) >= 2)),
                "distribuicao": {int(k): int(v) for k, v in zip(*np.unique(n, return_counts=True))},
            }
        )
    return pd.DataFrame(linhas)


def conexoes(base: dict, minimo_de_individuos: int = 2) -> pd.DataFrame:
    """Pares de jurisdições nacionais usados pelo mesmo animal: quem compartilha animais com quem."""
    nomes = base["nome_do_grupo"]
    linhas = []
    for especie in ORDEM:
        tempo, _ = dados.matriz_por_grupo(base, especie, "amostras")
        usou = (tempo.drop(columns=[0]) >= ESTADIA_MINIMA).astype(int)
        usou = usou.loc[:, usou.sum(axis=0) > 0]
        juntos = usou.T.to_numpy() @ usou.to_numpy()
        grupos = list(usou.columns)
        for a in range(len(grupos)):
            for b in range(a + 1, len(grupos)):
                if juntos[a, b] >= minimo_de_individuos:
                    linhas.append(
                        {
                            "especie": especie,
                            "jurisdicao_a": nomes[grupos[a]],
                            "jurisdicao_b": nomes[grupos[b]],
                            "individuos_em_comum": int(juntos[a, b]),
                            "individuos_em_a": int(juntos[a, a]),
                            "individuos_em_b": int(juntos[b, b]),
                        }
                    )
    tabela = pd.DataFrame(linhas)
    return tabela.sort_values(["individuos_em_comum"], ascending=False, kind="stable").reset_index(drop=True)


def travessias(base: dict) -> pd.DataFrame:
    """Passagens diretas de uma jurisdição a outra (ou ao alto-mar), somando os dois sentidos."""
    nomes = base["nome_do_grupo"]
    t = base["travessias"].copy()
    t["a"] = t[["de_grupo", "para_grupo"]].min(axis=1)
    t["b"] = t[["de_grupo", "para_grupo"]].max(axis=1)
    soma = t.groupby(["especie", "a", "b"], as_index=False).agg(travessias=("travessias", "sum"), individuos_no_maximo=("individuos", "sum"))
    soma["entre"] = soma["a"].map(nomes)
    soma["e"] = soma["b"].map(nomes)
    return soma.sort_values("travessias", ascending=False, kind="stable").reset_index(drop=True)[["especie", "entre", "e", "travessias"]]


def contra_o_acaso(base: dict, rng: np.random.Generator) -> pd.DataFrame:
    """Alto-mar observado contra o das caminhadas aleatórias que partem do mesmo ponto, com os mesmos passos."""
    linhas = []
    for especie in ORDEM:
        ficha = base["individuos"][base["individuos"]["especie"] == especie]
        for coluna, rotulo in (("altomar_nulo_sem_memoria", "sem memória"), ("altomar_nulo_persistente", "com persistência")):
            parte = ficha[ficha[coluna].notna() & ficha["altomar_diario"].notna()]
            n = parte["amostras_diarias"].to_numpy(dtype=float)
            observado, nulo_ = parte["altomar_diario"].to_numpy() * n, parte[coluna].to_numpy() * n
            pesos = _pesos(len(parte), rng)
            d = estatistica.bootstrap_da_diferenca(observado, n, nulo_, n, pesos)
            linhas.append(
                {
                    "especie": especie,
                    "caminhada": rotulo,
                    "individuos": len(parte),
                    "observado": estatistica.fracao_agrupada(observado, n),
                    "acaso": estatistica.fracao_agrupada(nulo_, n),
                    "diferenca": d["estimativa"],
                    "diferenca_inf": d["inferior"],
                    "diferenca_sup": d["superior"],
                    "individuos_acima_do_acaso": float(np.mean(parte["altomar_diario"] > parte[coluna])),
                }
            )
    return pd.DataFrame(linhas)


def oceano_aproximado(lat: float, lon: float) -> str:
    """Nome aproximado da bacia de um ponto (regra simples de latitude e longitude, só para rotular)."""
    if lat < -60:
        return "Oceano Austral"
    if 30 <= lat <= 46 and -6 <= lon <= 36:
        return "Mediterrâneo"
    if lat < -40:
        return "Oceano Austral" if lat < -50 else ("Atlântico Sul" if -70 <= lon < 20 else ("Índico Sul" if 20 <= lon < 147 else "Pacífico Sul"))
    if -70 <= lon < 20 or (lat > 8 and -100 <= lon < -70) or (lat > 0 and -70 <= lon < 20):
        return "Atlântico Norte" if lat >= 0 else "Atlântico Sul"
    if 20 <= lon < 100 or (lat < -10 and 100 <= lon < 130):
        return "Índico"
    return "Pacífico Norte" if lat >= 0 else "Pacífico Sul"


def _rotulo_do_bloco(lat: int, lon: int, tamanho: int) -> str:
    def faixa(valor: int, positivo: str, negativo: str) -> str:
        a, b = valor, valor + tamanho
        if a >= 0:
            return f"{a}° a {b}°{positivo}"
        return f"{-b}° a {-a}°{negativo}"

    return f"{faixa(lat, 'N', 'S')}, {faixa(lon, 'L', 'O')}"


def trechos_de_alto_mar(base: dict, tamanho: int = 10, quantos: int = 3) -> pd.DataFrame:
    """Blocos de 10 graus de alto-mar com mais dias de animal, por espécie."""
    g = base["grade_1grau"].copy()
    g["bloco_lat"] = (np.floor(g["lat_sul"] / tamanho) * tamanho).astype(int)
    g["bloco_lon"] = (np.floor(g["lon_oeste"] / tamanho) * tamanho).astype(int)
    linhas = []
    for especie in ORDEM:
        parte = g[g["especie"] == especie]
        total_mar, total = parte["dias_em_alto_mar"].sum(), parte["dias"].sum()
        blocos = parte.groupby(["bloco_lat", "bloco_lon"], as_index=False).agg(dias_em_alto_mar=("dias_em_alto_mar", "sum"), individuos_max_por_celula=("individuos", "max"))
        for _, b in blocos.sort_values("dias_em_alto_mar", ascending=False).head(quantos).iterrows():
            if b["dias_em_alto_mar"] <= 0:
                continue
            linhas.append(
                {
                    "especie": especie,
                    "bloco": _rotulo_do_bloco(int(b["bloco_lat"]), int(b["bloco_lon"]), tamanho),
                    "oceano": oceano_aproximado(b["bloco_lat"] + tamanho / 2, b["bloco_lon"] + tamanho / 2),
                    "dias_em_alto_mar": float(b["dias_em_alto_mar"]),
                    "parte_do_alto_mar_da_especie": float(b["dias_em_alto_mar"] / total_mar) if total_mar > 0 else np.nan,
                    "parte_do_tempo_da_especie": float(b["dias_em_alto_mar"] / total),
                    "individuos_na_celula_mais_usada": int(b["individuos_max_por_celula"]),
                }
            )
    return pd.DataFrame(linhas)


def concentracao_do_alto_mar(base: dict) -> pd.DataFrame:
    """Em quantas células de 1 grau cabe metade do tempo em alto-mar de cada espécie."""
    linhas = []
    for especie in ORDEM:
        parte = base["grade_1grau"][(base["grade_1grau"]["especie"] == especie) & (base["grade_1grau"]["dias_em_alto_mar"] > 0)]
        dias = np.sort(parte["dias_em_alto_mar"].to_numpy())[::-1]
        if len(dias) == 0:
            continue
        acumulado = np.cumsum(dias) / dias.sum()
        linhas.append({"especie": especie, "celulas_com_alto_mar": int(len(dias)), "celulas_para_metade_do_tempo": int(np.searchsorted(acumulado, 0.5) + 1)})
    return pd.DataFrame(linhas)
