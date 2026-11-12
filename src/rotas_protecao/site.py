"""Bloco `para_o_site` de reports/resultados.json: textos nos três idiomas e o gráfico do achado principal."""

from __future__ import annotations

IDIOMAS = ("pt", "en", "es")
NOMES = {
    "albatroz": {"pt": "Albatroz-errante", "en": "Wandering albatross", "es": "Albatros errante"},
    "elefante": {"pt": "Elefante-marinho-do-sul", "en": "Southern elephant seal", "es": "Elefante marino del sur"},
    "couro": {"pt": "Tartaruga-de-couro", "en": "Leatherback turtle", "es": "Tortuga laúd"},
    "cabecuda": {"pt": "Tartaruga-cabeçuda", "en": "Loggerhead turtle", "es": "Tortuga boba"},
    "baleia": {"pt": "Tubarão-baleia", "en": "Whale shark", "es": "Tiburón ballena"},
}
# Nome no plural, sem artigo, para entrar no meio de uma frase.
PLURAL = {
    "albatroz": {"pt": "albatrozes-errantes", "en": "wandering albatrosses", "es": "albatros errantes"},
    "elefante": {"pt": "elefantes-marinhos-do-sul", "en": "southern elephant seals", "es": "elefantes marinos del sur"},
    "couro": {"pt": "tartarugas-de-couro", "en": "leatherback turtles", "es": "tortugas laúd"},
    "cabecuda": {"pt": "tartarugas-cabeçudas", "en": "loggerhead turtles", "es": "tortugas bobas"},
    "baleia": {"pt": "tubarões-baleia", "en": "whale sharks", "es": "tiburones ballena"},
}


def _pct(valor: float) -> str:
    """Percentual inteiro (igual nos três idiomas)."""
    return f"{int(valor * 100 + 0.5 + 1e-9)}%"  # metade para cima, como no texto do README


def _milhar(valor: float, idioma: str) -> str:
    texto = f"{valor:,.0f}"
    return texto if idioma == "en" else texto.replace(",", ".")


def _lista(especies: list[str], idioma: str) -> str:
    nomes = [PLURAL[e][idioma] for e in especies]
    if not nomes:
        return {"pt": "nenhuma espécie", "en": "no species", "es": "ninguna especie"}[idioma]
    if len(nomes) == 1:
        return nomes[0]
    return ", ".join(nomes[:-1]) + {"pt": " e ", "en": " and ", "es": " y "}[idioma] + nomes[-1]


def acima_e_abaixo_do_acaso(contra_o_acaso: list[dict], ordem: list[str]) -> tuple[list[str], list[str]]:
    """Espécies cujo intervalo da diferença exclui zero nas duas caminhadas aleatórias."""
    acima, abaixo = [], []
    for e in ordem:
        linhas = [linha for linha in contra_o_acaso if linha["especie"] == e]
        if all(linha["diferenca_inf"] > 0 for linha in linhas):
            acima.append(e)
        elif all(linha["diferenca_sup"] < 0 for linha in linhas):
            abaixo.append(e)
    return acima, abaixo


def bloco(r: dict) -> dict:
    am = {linha["especie"]: linha for linha in r["alto_mar_por_especie"]}
    ordem = [linha["especie"] for linha in r["alto_mar_por_especie"]]
    g = r["geral"]
    maior = max(ordem, key=lambda e: am[e]["tempo"])
    menor = min(ordem, key=lambda e: am[e]["tempo"])
    pior = max(ordem, key=lambda e: abs(am[e]["diferenca"]))  # onde contar registros mais erra
    empatam = sum(1 for e in ordem if am[e]["diferenca_inf"] <= 0 <= am[e]["diferenca_sup"] or abs(am[e]["diferenca"]) < 0.005)
    acima, abaixo = acima_e_abaixo_do_acaso(r["contra_o_acaso"], ordem)
    data = r["coleta"]["data_da_coleta"]
    dia, mes, ano = int(data[8:10]), int(data[5:7]), data[:4]
    meses_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    def p(e: str, campo: str) -> str:
        return _pct(am[e][campo])

    textos = {
        "numero_chave": {
            "pt": f"{p(menor, 'tempo')} a {p(maior, 'tempo')}",
            "en": f"{p(menor, 'tempo')} to {p(maior, 'tempo')}",
            "es": f"{p(menor, 'tempo')} a {p(maior, 'tempo')}",
        },
        "pergunta": {
            "pt": "Quanto do caminho de um animal marinho migratório passa por águas de algum país, e quanto por alto-mar?",
            "en": "How much of a migratory marine animal's path lies in some country's waters, and how much on the high seas?",
            "es": "¿Cuánto del camino de un animal marino migratorio pasa por aguas de algún país y cuánto por alta mar?",
        },
        "resultado": {
            "pt": (
                f"Depende muito da espécie e de onde ela foi marcada: os {PLURAL[maior]['pt']} rastreados passaram {p(maior, 'tempo')} do tempo em alto-mar "
                f"(IC 95%: {p(maior, 'tempo_inf')} a {p(maior, 'tempo_sup')}) e os {PLURAL[menor]['pt']}, {p(menor, 'tempo')} ({p(menor, 'tempo_inf')} a {p(menor, 'tempo_sup')}). "
                f"Contar registros em vez de tempo empata em {empatam} das {len(ordem)} espécies; onde erra, erra mais nas {PLURAL[pior]['pt']}: {p(pior, 'pontos')} em vez de {p(pior, 'tempo')}."
            ),
            "en": (
                f"It depends heavily on the species and on where it was tagged: tracked {PLURAL[maior]['en']} spent {p(maior, 'tempo')} of their time on the high seas "
                f"(95% CI {p(maior, 'tempo_inf')} to {p(maior, 'tempo_sup')}), {PLURAL[menor]['en']} {p(menor, 'tempo')} ({p(menor, 'tempo_inf')} to {p(menor, 'tempo_sup')}). "
                f"Counting records instead of time ties in {empatam} of the {len(ordem)} species; where it is off, it is furthest off for {PLURAL[pior]['en']}: {p(pior, 'pontos')} instead of {p(pior, 'tempo')}."
            ),
            "es": (
                f"Depende mucho de la especie y de dónde se marcó: los {PLURAL[maior]['es']} rastreados pasaron el {p(maior, 'tempo')} del tiempo en alta mar "
                f"(IC 95 %: {p(maior, 'tempo_inf')} a {p(maior, 'tempo_sup')}) y los {PLURAL[menor]['es']}, el {p(menor, 'tempo')} ({p(menor, 'tempo_inf')} a {p(menor, 'tempo_sup')}). "
                f"Contar registros en lugar de tiempo empata en {empatam} de las {len(ordem)} especies; donde falla, falla más en las {PLURAL[pior]['es']}: {p(pior, 'pontos')} en vez de {p(pior, 'tempo')}."
            ),
        },
        "detalhe": {
            "pt": (
                "No gráfico, a barra azul é a fração do tempo em alto-mar e a laranja, a fração dos registros; a faixa é o intervalo de 95% reamostrando animais inteiros. "
                f"Contra caminhadas aleatórias que partem do mesmo ponto com os mesmos passos, o alto-mar fica acima do acaso para {_lista(acima, 'pt')} e abaixo para {_lista(abaixo, 'pt')}."
            ),
            "en": (
                "In the chart, the blue bar is the share of time on the high seas and the orange bar the share of records; the band is the 95% interval from resampling whole animals. "
                f"Against random walks that start at the same tagging site with the same step lengths, high-seas use is above chance for {_lista(acima, 'en')} and below it for {_lista(abaixo, 'en')}."
            ),
            "es": (
                "En el gráfico, la barra azul es la fracción del tiempo en alta mar y la naranja, la de los registros; la banda es el intervalo del 95 % remuestreando animales enteros. "
                f"Frente a caminatas aleatorias que parten del mismo punto con los mismos pasos, el uso de alta mar queda por encima del azar en {_lista(acima, 'es')} y por debajo en {_lista(abaixo, 'es')}."
            ),
        },
        "dados": {
            "pt": f"{_milhar(g['individuos'], 'pt')} animais de {g['especies']} espécies rastreados por satélite ({g['ano_inicial']} a {g['ano_final']}), de {g['conjuntos']} conjuntos públicos do OBIS coletados em {dia:02d}/{mes:02d}/{ano}, sobre as ZEE do Marine Regions (v12).",
            "en": f"{_milhar(g['individuos'], 'en')} satellite-tracked animals of {g['especies']} species ({g['ano_inicial']}–{g['ano_final']}) from {g['conjuntos']} public OBIS datasets collected on {dia} {meses_en[mes - 1]} {ano}, overlaid on Marine Regions EEZs (v12).",
            "es": f"{_milhar(g['individuos'], 'es')} animales de {g['especies']} especies rastreados por satélite ({g['ano_inicial']} a {g['ano_final']}), de {g['conjuntos']} conjuntos públicos de OBIS recogidos el {dia:02d}/{mes:02d}/{ano}, sobre las ZEE de Marine Regions (v12).",
        },
    }
    rotulos = {i: [NOMES[e][i] for e in ordem] for i in IDIOMAS}
    grafico = {
        "tipo": "barras",
        "titulo": {
            "pt": "Tempo em alto-mar por espécie: pelo tempo rastreado e pela contagem de registros",
            "en": "Time on the high seas by species: by tracked time and by record count",
            "es": "Tiempo en alta mar por especie: por tiempo rastreado y por recuento de registros",
        },
        "eixo_x": {"pt": "Espécie", "en": "Species", "es": "Especie"},
        "eixo_y": {"pt": "Fração em alto-mar", "en": "Share on the high seas", "es": "Fracción en alta mar"},
        "formato_x": "numero",
        "formato_y": "percentual",
        "series": [
            {
                "nome": {"pt": "Pelo tempo rastreado", "en": "By tracked time", "es": "Por tiempo rastreado"},
                "papel": "principal",
                "pontos": [[NOMES[e]["pt"], round(am[e]["tempo"], 4)] for e in ordem],
                "rotulos": rotulos,
            },
            {
                "nome": {"pt": "Pela contagem de registros", "en": "By record count", "es": "Por recuento de registros"},
                "papel": "base",
                "pontos": [[NOMES[e]["pt"], round(am[e]["pontos"], 4)] for e in ordem],
                "rotulos": rotulos,
            },
        ],
        "faixa": {
            "serie": 0,
            "inferior": [[NOMES[e]["pt"], round(am[e]["tempo_inf"], 4)] for e in ordem],
            "superior": [[NOMES[e]["pt"], round(am[e]["tempo_sup"], 4)] for e in ordem],
        },
    }
    return {**textos, "etiquetas": ["telemetria", "análise espacial", "bootstrap por indivíduo", "modelo nulo", "OBIS"], "grafico": grafico}
