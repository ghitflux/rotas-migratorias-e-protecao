"""Carrega o extrato agregado de `data/` e dá nome às jurisdições."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from rotas_protecao import jurisdicao
from rotas_protecao.coleta import ESPECIES

RAIZ = Path(__file__).resolve().parents[2]
ALTO_MAR = "Alto-mar"

# Nome em português dos países que aparecem nas trajetórias (os demais ficam como vêm da fonte).
PAISES = {
    "Argentina": "Argentina",
    "Australia": "Austrália",
    "Brazil": "Brasil",
    "Chile": "Chile",
    "Comores": "Comores",
    "Costa Rica": "Costa Rica",
    "Colombia": "Colômbia",
    "Ecuador": "Equador",
    "France": "França",
    "Greece": "Grécia",
    "Indonesia": "Indonésia",
    "Italy": "Itália",
    "Japan": "Japão",
    "Libya": "Líbia",
    "Madagascar": "Madagascar",
    "Mauritius": "Maurício",
    "Mexico": "México",
    "Mozambique": "Moçambique",
    "Namibia": "Namíbia",
    "New Zealand": "Nova Zelândia",
    "Norway": "Noruega",
    "Papua New Guinea": "Papua-Nova Guiné",
    "Peru": "Peru",
    "Russia": "Rússia",
    "Seychelles": "Seicheles",
    "Solomon Islands": "Ilhas Salomão",
    "Somalia": "Somália",
    "South Africa": "África do Sul",
    "Spain": "Espanha",
    "Tunisia": "Tunísia",
    "Turkey": "Turquia",
    "United Kingdom": "Reino Unido",
    "United States": "Estados Unidos",
    "Uruguay": "Uruguai",
    "Algeria": "Argélia",
    "Morocco": "Marrocos",
    "Egypt": "Egito",
    "Tanzania": "Tanzânia",
    "Kenya": "Quênia",
    "Portugal": "Portugal",
    "China": "China",
    "Taiwan": "Taiwan",
    "Philippines": "Filipinas",
    "South Korea": "Coreia do Sul",
    "North Korea": "Coreia do Norte",
    "Venezuela": "Venezuela",
    "Netherlands": "Países Baixos",
    "Panama": "Panamá",
    "Nicaragua": "Nicarágua",
    "Honduras": "Honduras",
    "Cuba": "Cuba",
    "Vanuatu": "Vanuatu",
    "Fiji": "Fiji",
    "Angola": "Angola",
    "Malta": "Malta",
    "Albania": "Albânia",
    "Croatia": "Croácia",
    "Cyprus": "Chipre",
    "Kiribati": "Kiribati",
    "Micronesia": "Micronésia",
    "Palau": "Palau",
    "Canada": "Canadá",
    "Dominican Republic": "República Dominicana",
    "Colombia ": "Colômbia",
    "India": "Índia",
    "Oman": "Omã",
    "Yemen": "Iêmen",
    "Vietnam": "Vietnã",
    "Malaysia": "Malásia",
    "Western Sahara": "Saara Ocidental",
    "Mauritania": "Mauritânia",
    "Republic of Mauritius": "Maurício",
    "Federal Republic of Somalia": "Somália",
    "East Timor": "Timor-Leste",
    "Nauru": "Nauru",
    "Tuvalu": "Tuvalu",
    "Marshall Islands": "Ilhas Marshall",
}
TIPOS = {"Joint regime": "Regime conjunto", "Overlapping claim": "Área em disputa"}


def nome_do_grupo(rotulo_fonte: str) -> str:
    """Nome em português de uma categoria de jurisdição."""
    if rotulo_fonte == "High seas":
        return ALTO_MAR
    if ": " in rotulo_fonte:
        tipo, paises = rotulo_fonte.split(": ", 1)
        return f"{TIPOS.get(tipo, tipo)}: {' / '.join(PAISES.get(p, p) for p in paises.split(' / '))}"
    return PAISES.get(rotulo_fonte, rotulo_fonte)


def carregar(pasta: Path | None = None) -> dict:
    """Lê o extrato. Não precisa de rede nem de `data/brutos/`."""
    pasta = Path(pasta) if pasta else RAIZ / "data"
    jurisdicoes = pd.read_csv(pasta / "jurisdicoes.csv")
    grupos = jurisdicoes.drop_duplicates("grupo").set_index("grupo")["rotulo_fonte"].map(nome_do_grupo)
    tempo = pd.read_csv(pasta / "tempo_por_individuo.csv")
    tempo["grupo"] = tempo["codigo"].map(jurisdicoes.set_index("codigo")["grupo"])
    individuos = pd.read_csv(pasta / "individuos.csv")
    costa = json.loads((pasta / "costa_110m.geojson").read_text(encoding="utf-8"))
    linhas = []
    for feicao in costa["features"]:
        geometria = feicao["geometry"]
        partes = [geometria["coordinates"]] if geometria["type"] == "LineString" else geometria["coordinates"]
        linhas += [np.asarray(p)[:, :2] for p in partes]
    return {
        "especies": ESPECIES,
        "jurisdicoes": jurisdicoes,
        "nome_do_grupo": grupos,  # índice: grupo (0 = alto-mar)
        "individuos": individuos,
        "tempo": tempo,
        "travessias": pd.read_csv(pasta / "travessias.csv"),
        "semanas": pd.read_csv(pasta / "semanas.csv"),
        "grade_1grau": pd.read_csv(pasta / "grade_1grau.csv"),
        "coleta": json.loads((pasta / "coleta.json").read_text(encoding="utf-8")),
        "costa": linhas,
        "grade": jurisdicao.carregar(pasta / "grade_jurisdicao.npz"),
    }


def matriz_por_grupo(base: dict, especie: str, coluna: str = "amostras") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Matriz [indivíduo x grupo de jurisdição] com a contagem de `coluna`, e a ficha dos indivíduos na mesma ordem."""
    ficha = base["individuos"][base["individuos"]["especie"] == especie].set_index("individuo")
    tempo = base["tempo"][base["tempo"]["individuo"].isin(ficha.index)]
    matriz = tempo.pivot_table(index="individuo", columns="grupo", values=coluna, aggfunc="sum", fill_value=0)
    matriz = matriz.reindex(ficha.index, fill_value=0)
    if 0 not in matriz.columns:
        matriz[0] = 0
    return matriz.sort_index(axis=1), ficha
