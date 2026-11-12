"""Monta o extrato agregado em `data/` a partir das posições brutas em `data/brutos/`.

É aqui que as trajetórias são reconstruídas, porque as posições individuais não podem ser
versionadas (vários conjuntos são CC BY-NC). O que sai daqui não tem nenhuma posição de animal:

- `grade_jurisdicao.npz`, `jurisdicoes.csv`: a grade de 0,1 grau e a tabela de jurisdições;
- `individuos.csv`: uma linha por animal rastreado (duração, falhas, resultado das caminhadas nulas);
- `tempo_por_individuo.csv`: amostras de 6 h de cada animal em cada jurisdição, em várias variantes;
- `travessias.csv`: passagens de uma jurisdição a outra, por espécie;
- `semanas.csv`: fração em alto-mar por semana desde a marcação, por espécie;
- `grade_1grau.csv`: dias de animal por célula de 1 grau, por espécie;
- `coleta.json`: datas, conjuntos, licenças, funil de limpeza e parâmetros.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from rotas_protecao import coleta, geodesia, jurisdicao, nulo, trajetoria

PASSO_H = 6.0  # cada amostra da trajetória representa 6 horas
FALHA_MAXIMA_DIAS = 10.0  # falha de transmissão maior que isso não é interpolada
FALHAS_ALTERNATIVAS = {"falha3": 3.0, "semlimite": np.inf}
CORTES_DIAS = (14, 28, 56)  # descarte do começo da trajetória (viés do local de marcação)
MINIMO_POSICOES = 10
MINIMO_DIAS = 7.0
ESTADIA_MINIMA_AMOSTRAS = 4  # 24 h: menos que isso não conta como passagem por uma jurisdição
N_CAMINHADAS = 40
MINIMO_PASSOS_DIARIOS = 5
SEMENTE = 20261112
PADRAO_NOME_NO_EVENTO = re.compile(r"^(.*?)_\d{4}-\d{2}-\d{2}T")


# ---------------------------------------------------------------- jurisdição


def _rotulo_do_grupo(linha: dict) -> str:
    """Rótulo (no idioma da fonte) da categoria de jurisdição de um polígono de ZEE."""
    if linha["pol_type"] == "200NM":
        return linha["sovereign1"]
    paises = " / ".join(sorted(p for p in (linha["sovereign1"], linha["sovereign2"]) if p))
    return f"{linha['pol_type']}: {paises}"


def construir_grade(brutos: Path) -> tuple[jurisdicao.Grade, pd.DataFrame]:
    """Lê os polígonos baixados e monta a grade de 0,1 grau e a tabela de jurisdições."""
    from shapely.geometry import shape

    zee = json.loads((brutos / "marineregions_eez.geojson").read_text(encoding="utf-8"))["features"]
    alto_mar = json.loads((brutos / "marineregions_high_seas.geojson").read_text(encoding="utf-8"))["features"]
    terra = json.loads((brutos / "ne_50m_land.geojson").read_text(encoding="utf-8"))["features"]

    # As ZEE de 200 milhas entram primeiro; regimes conjuntos e áreas em disputa são pintados por cima.
    zee = sorted(zee, key=lambda f: (f["properties"]["pol_type"] != "200NM", f["properties"]["mrgid"]))
    linhas = [{"codigo": k, **f["properties"], "rotulo_fonte": _rotulo_do_grupo(f["properties"])} for k, f in enumerate(zee, 1)]
    tabela = pd.DataFrame([{"codigo": 0, "geoname": "High seas", "pol_type": "High seas", "rotulo_fonte": "High seas"}] + linhas)
    tabela["grupo"] = pd.factorize(tabela["rotulo_fonte"])[0]  # alto-mar = grupo 0
    grade = jurisdicao.montar_grade(
        [shape(f["geometry"]) for f in zee],
        [linha["codigo"] for linha in linhas],
        [shape(f["geometry"]) for f in alto_mar],
        [shape(f["geometry"]) for f in terra],
    )
    return grade, tabela


# ---------------------------------------------------------------- leitura


def ler_conjunto(brutos: Path, conjunto: dict) -> tuple[pd.DataFrame, dict]:
    """Posições de um conjunto, com o identificador do indivíduo e o tempo em horas. Devolve também o funil."""
    bruto = pd.read_csv(brutos / f"obis_{conjunto['chave']}.csv.gz", dtype=str, keep_default_na=False)
    funil = {"registros_baixados": len(bruto)}
    bruto = bruto[bruto["basisOfRecord"] == "MachineObservation"]
    funil["sem_ser_telemetria"] = funil["registros_baixados"] - len(bruto)
    if conjunto["individuo"] == "organismID":
        individuo = bruto["organismID"]
    elif conjunto["individuo"] == "eventID_nome":
        individuo = bruto["eventID"].str.extract(PADRAO_NOME_NO_EVENTO, expand=False).fillna("")
    else:
        individuo = bruto["occurrenceID"].str.split(":deployment:").str[0]
    tempo = pd.to_datetime(bruto["eventDate"], utc=True, format="ISO8601", errors="coerce")
    tabela = pd.DataFrame(
        {
            "individuo": individuo.to_numpy(),
            "t_h": (tempo - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds().to_numpy() / 3600.0,
            "lat": pd.to_numeric(bruto["decimalLatitude"], errors="coerce").to_numpy(),
            "lon": pd.to_numeric(bruto["decimalLongitude"], errors="coerce").to_numpy(),
        }
    )
    valido = (
        tabela["t_h"].notna()
        & tabela["lat"].between(-90, 90)
        & tabela["lon"].between(-180, 180)
        & ~((tabela["lat"] == 0) & (tabela["lon"] == 0))
        & (tabela["individuo"] != "")
    )
    funil["sem_data_coordenada_ou_individuo"] = int((~valido).sum())
    tabela = tabela[valido].copy()
    tabela["conjunto"] = conjunto["chave"]
    return tabela, funil


def tirar_individuos_repetidos(tabela: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Tira animais que aparecem em mais de um conjunto da mesma espécie.

    Dois sinais de repetição: o mesmo identificador em dois conjuntos, ou mais da metade das posições
    (mesma hora, mesma coordenada com duas casas) iguais às de outro animal. Fica a cópia com mais posições.
    """
    grupos = tabela.groupby(["conjunto", "individuo"], sort=True)
    tamanho = grupos.size().sort_values(ascending=False, kind="stable")
    assinatura = (np.round(tabela["t_h"]).astype(np.int64).astype(str) + "|" + tabela["lat"].round(2).astype(str) + "|" + tabela["lon"].round(2).astype(str))
    vistas: dict[str, tuple] = {}
    identificadores: set[str] = set()
    repetidos: list[tuple] = []
    for chave in tamanho.index:  # do maior para o menor
        linhas = grupos.indices[chave]
        marcas = assinatura.iloc[linhas].to_numpy()
        ja_vistas = sum(1 for m in marcas if m in vistas and vistas[m][0] != chave[0])
        if chave[1] in identificadores or ja_vistas > 0.5 * len(marcas):
            repetidos.append(chave)
            continue
        identificadores.add(chave[1])
        for m in marcas:
            vistas.setdefault(m, chave)
    if repetidos:
        indice = pd.MultiIndex.from_frame(tabela[["conjunto", "individuo"]])
        tabela = tabela[~indice.isin(repetidos)]
    return tabela, len(repetidos)


# ---------------------------------------------------------------- um indivíduo


def _contar(codigos: np.ndarray, n_codigos: int) -> np.ndarray:
    return np.bincount(codigos, minlength=n_codigos)


def processar_individuo(t_h, lat, lon, vmax_kmh: float, grade: jurisdicao.Grade, grupo_do_codigo: np.ndarray, rng: np.random.Generator) -> dict | None:
    """Reconstrói a trajetória de um animal e devolve só agregados (nenhuma posição)."""
    n_codigos = len(grupo_do_codigo)
    pontos_brutos = _contar(grade.classificar(lat, lon), n_codigos)
    t_h, lat, lon = trajetoria.juntar_simultaneas(t_h, lat, lon)
    n_instantes = len(t_h)
    fica = trajetoria.filtro_de_velocidade(t_h, lat, lon, vmax_kmh)
    t_h, lat, lon = t_h[fica], lat[fica], lon[fica]
    if len(t_h) < MINIMO_POSICOES:
        return None
    falha_h = FALHA_MAXIMA_DIAS * 24.0
    reg = trajetoria.interpolar_regular(t_h, lat, lon, PASSO_H, falha_h)
    if len(reg["t_h"]) * PASSO_H / 24.0 < MINIMO_DIAS:
        return None
    codigos = grade.classificar(reg["lat"], reg["lon"])
    desde_o_inicio_h = reg["t_h"] - t_h[0]

    contagens = {"amostras": _contar(codigos, n_codigos), "pontos_brutos": pontos_brutos}
    for corte in CORTES_DIAS:
        contagens[f"amostras_corte{corte}"] = _contar(codigos[desde_o_inicio_h >= corte * 24.0], n_codigos)
    for nome, dias in FALHAS_ALTERNATIVAS.items():
        outra = trajetoria.interpolar_regular(t_h, lat, lon, PASSO_H, dias * 24.0)
        contagens[nome] = _contar(grade.classificar(outra["lat"], outra["lon"]), n_codigos) if len(outra["t_h"]) else np.zeros(n_codigos, dtype=int)

    # Série diária para a caminhada aleatória: mesmos trechos, um ponto por dia.
    diaria = trajetoria.interpolar_regular(t_h, lat, lon, 24.0, falha_h)
    passos, giros = trajetoria.passos_e_giros(diaria["lat"], diaria["lon"], diaria["segmento"])
    alto_mar_do_codigo = grupo_do_codigo == 0
    nulos = {"altomar_diario": np.nan, "altomar_nulo_sem_memoria": np.nan, "altomar_nulo_persistente": np.nan}
    passos_validos = passos[passos > 0]
    if len(passos_validos) >= MINIMO_PASSOS_DIARIOS:
        n = len(diaria["t_h"])
        nulos["altomar_diario"] = float(alto_mar_do_codigo[grade.classificar(diaria["lat"], diaria["lon"])].mean())
        for nome, g in (("altomar_nulo_sem_memoria", None), ("altomar_nulo_persistente", giros)):
            if g is not None and len(g) < MINIMO_PASSOS_DIARIOS:
                continue
            la, lo = nulo.simular_caminhadas(diaria["lat"][0], diaria["lon"][0], passos_validos, n, N_CAMINHADAS, rng, giros=g, grade=grade)
            nulos[nome] = float(nulo.fracao_em_alto_mar(la, lo, grade, alto_mar_do_codigo).mean())

    grupos = grupo_do_codigo[codigos]
    estadias = trajetoria.corridas(grupos, reg["segmento"], minimo=ESTADIA_MINIMA_AMOSTRAS)
    travessias = Counter((a[0], b[0]) for a, b in zip(estadias[:-1], estadias[1:]) if a[1] == b[1] and a[0] != b[0])

    semana = np.floor(desde_o_inicio_h / 168.0).astype(int)
    em_alto_mar = grupos == 0
    i_lat = np.clip(np.floor(reg["lat"] + 90).astype(int), 0, 179)
    i_lon = np.mod(np.floor(reg["lon"] + 180).astype(int), 360)
    celula = i_lat * 360 + i_lon

    return {
        "contagens": contagens,
        "travessias": travessias,
        "semana": semana,
        "em_alto_mar": em_alto_mar,
        "celula": celula,
        "resumo": {
            "ano_inicio": int(pd.Timestamp(t_h[0] * 3600, unit="s").year),
            "registros": int(pontos_brutos.sum()),
            "instantes": n_instantes,
            "tirados_pelo_filtro": int((~fica).sum()),
            "dias_rastreados": len(reg["t_h"]) * PASSO_H / 24.0,
            "dias_do_primeiro_ao_ultimo": float(t_h[-1] - t_h[0]) / 24.0,
            "dias_em_falhas": trajetoria.tempo_em_falhas_h(t_h, falha_h) / 24.0,
            "trechos": int(reg["segmento"].max()) + 1,
            "amostras_em_terra": int(grade.em_terra(reg["lat"], reg["lon"]).sum()),
            "marcacao_lat_1grau": float(np.floor(lat[0])),
            "marcacao_lon_1grau": float(np.floor(lon[0])),
            "codigo_da_marcacao": int(grade.classificar(lat[0], lon[0])),
            "passo_diario_mediano_km": float(np.median(passos)) if len(passos) else np.nan,
            "distancia_maxima_da_marcacao_km": float(geodesia.distancia_km(lat[0], lon[0], lat, lon).max()),
            "passos_diarios": len(passos),
            "amostras_diarias": len(diaria["t_h"]),
            **nulos,
        },
    }


# ---------------------------------------------------------------- tudo


def montar_extrato(brutos: Path, destino: Path) -> None:
    brutos, destino = Path(brutos), Path(destino)
    print("Grade de jurisdição...")
    grade, jurisdicoes = construir_grade(brutos)
    jurisdicao.salvar(grade, destino / "grade_jurisdicao.npz")
    jurisdicoes.to_csv(destino / "jurisdicoes.csv", index=False)
    (destino / "costa_110m.geojson").write_bytes((brutos / "ne_110m_coastline.geojson").read_bytes())
    grupo_do_codigo = jurisdicoes["grupo"].to_numpy()
    n_codigos = len(grupo_do_codigo)

    rng = np.random.default_rng(SEMENTE)
    registro_bruto = json.loads((brutos / "coleta_bruta.json").read_text(encoding="utf-8"))
    individuos, tempos, funis = [], [], {}
    travessias: dict[tuple, list] = defaultdict(lambda: [0, 0])
    semanas: dict[tuple, list] = defaultdict(lambda: [0, 0, 0])
    celulas: dict[str, np.ndarray] = {}

    for especie, ficha in coleta.ESPECIES.items():
        print(f"{ficha['comum']}...")
        partes, funil = [], Counter()
        for conjunto in (c for c in coleta.CONJUNTOS if c["especie"] == especie):
            tabela, f = ler_conjunto(brutos, conjunto)
            partes.append(tabela)
            funil.update(f)
        posicoes = pd.concat(partes, ignore_index=True)
        funil["individuos_brutos"] = posicoes.groupby(["conjunto", "individuo"]).ngroups
        posicoes, funil["individuos_repetidos_entre_conjuntos"] = tirar_individuos_repetidos(posicoes)
        populacao = {c["chave"]: c["populacao"] for c in coleta.CONJUNTOS}
        grade_dias = np.zeros((3, 180 * 360))  # amostras, amostras em alto-mar, indivíduos
        numero = 0
        for (conjunto, _), grupo in posicoes.groupby(["conjunto", "individuo"], sort=True):
            r = processar_individuo(grupo["t_h"].to_numpy(), grupo["lat"].to_numpy(), grupo["lon"].to_numpy(), ficha["vmax_kmh"], grade, grupo_do_codigo, rng)
            if r is None:
                funil["individuos_curtos_demais"] += 1
                continue
            numero += 1
            identificador = f"{especie}_{numero:04d}"
            funil["posicoes_usadas"] += r["resumo"]["instantes"] - r["resumo"]["tirados_pelo_filtro"]
            funil["posicoes_tiradas_pelo_filtro_de_velocidade"] += r["resumo"]["tirados_pelo_filtro"]
            funil["registros_dos_individuos_usados"] += r["resumo"]["registros"]
            individuos.append({"individuo": identificador, "especie": especie, "conjunto": conjunto, "populacao": populacao[conjunto], **r["resumo"]})
            usados = np.flatnonzero(sum(r["contagens"].values()) > 0)
            for codigo in usados:
                tempos.append({"individuo": identificador, "codigo": int(codigo), **{nome: int(v[codigo]) for nome, v in r["contagens"].items()}})
            for par, vezes in r["travessias"].items():
                travessias[(especie, *par)][0] += vezes
                travessias[(especie, *par)][1] += 1
            limite = min(int(r["semana"].max()) + 1, 400)
            total_semana = np.bincount(r["semana"], minlength=limite)[:limite]
            mar_semana = np.bincount(r["semana"], weights=r["em_alto_mar"], minlength=limite)[:limite]
            for s in np.flatnonzero(total_semana):
                registro_semana = semanas[(especie, int(s))]
                registro_semana[0] += int(total_semana[s])
                registro_semana[1] += int(mar_semana[s])
                registro_semana[2] += 1
            grade_dias[0] += np.bincount(r["celula"], minlength=180 * 360)
            grade_dias[1] += np.bincount(r["celula"], weights=r["em_alto_mar"], minlength=180 * 360)
            grade_dias[2][np.unique(r["celula"])] += 1
        funil["individuos_usados"] = numero
        funis[especie] = dict(funil)
        celulas[especie] = grade_dias
        print(f"  {numero} indivíduos")

    pd.DataFrame(individuos).round(4).to_csv(destino / "individuos.csv", index=False)
    pd.DataFrame(tempos).to_csv(destino / "tempo_por_individuo.csv", index=False)
    pd.DataFrame(
        [{"especie": e, "de_grupo": a, "para_grupo": b, "travessias": v[0], "individuos": v[1]} for (e, a, b), v in sorted(travessias.items())]
    ).to_csv(destino / "travessias.csv", index=False)
    pd.DataFrame(
        [{"especie": e, "semana": s, "amostras": v[0], "amostras_em_alto_mar": v[1], "individuos": v[2]} for (e, s), v in sorted(semanas.items())]
    ).to_csv(destino / "semanas.csv", index=False)
    linhas_grade = []
    for especie, g in celulas.items():
        for c in np.flatnonzero(g[0]):
            linhas_grade.append(
                {
                    "especie": especie,
                    "lat_sul": int(c // 360) - 90,
                    "lon_oeste": int(c % 360) - 180,
                    "dias": round(g[0][c] * PASSO_H / 24.0, 2),
                    "dias_em_alto_mar": round(g[1][c] * PASSO_H / 24.0, 2),
                    "individuos": int(g[2][c]),
                }
            )
    pd.DataFrame(linhas_grade).to_csv(destino / "grade_1grau.csv", index=False)

    conjuntos = {}
    for c in coleta.CONJUNTOS:
        meta = registro_bruto["conjuntos"][c["chave"]]
        conjuntos[c["chave"]] = {"especie": c["especie"], "id_obis": c["id"], "populacao": c["populacao"], **meta}
    (destino / "coleta.json").write_text(
        json.dumps(
            {
                "data_da_coleta": max(m["data_da_coleta"] for m in registro_bruto["conjuntos"].values()),
                "conjuntos": conjuntos,
                "funil": funis,
                "parametros": {
                    "passo_h": PASSO_H,
                    "falha_maxima_dias": FALHA_MAXIMA_DIAS,
                    "cortes_dias": list(CORTES_DIAS),
                    "minimo_posicoes": MINIMO_POSICOES,
                    "minimo_dias": MINIMO_DIAS,
                    "estadia_minima_h": ESTADIA_MINIMA_AMOSTRAS * PASSO_H,
                    "caminhadas_por_individuo": N_CAMINHADAS,
                    "semente": SEMENTE,
                    "resolucao_da_grade_graus": jurisdicao.RESOLUCAO,
                    "velocidade_maxima_kmh": {e: f["vmax_kmh"] for e, f in coleta.ESPECIES.items()},
                    "intervalo_minimo_h": trajetoria.INTERVALO_MINIMO_H,
                },
                "arquivos_brutos": registro_bruto.get("arquivos", {}),
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
