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


POPULACOES = {
    "Pacífico Norte": {"en": "North Pacific", "es": "Pacífico Norte"},
    "Índico sudoeste": {"en": "SW Indian Ocean", "es": "Índico suroccidental"},
    "Mediterrâneo": {"en": "Mediterranean", "es": "Mediterráneo"},
    "Caribe": {"en": "Caribbean", "es": "Caribe"},
    "Galápagos (Pacífico leste)": {"pt": "Galápagos", "en": "Galápagos", "es": "Galápagos"},
    "Mar de Coral (Pacífico oeste)": {"pt": "Mar de Coral", "en": "Coral Sea", "es": "Mar del Coral"},
}
CURTO = {  # nome curto da espécie para rótulos compostos
    "cabecuda": {"pt": "Cabeçuda", "en": "Loggerhead", "es": "Boba"},
    "baleia": {"pt": "Tubarão-baleia", "en": "Whale shark", "es": "Tiburón ballena"},
}


def _tres(pt: str, en: str, es: str) -> dict:
    return {"pt": pt, "en": en, "es": es}


def _serie_de_barras(nome: dict, papel: str, ordem: list[str], valores: list[float]) -> dict:
    return {
        "nome": nome,
        "papel": papel,
        "pontos": [[NOMES[e]["pt"], round(float(v), 4)] for e, v in zip(ordem, valores)],
        "rotulos": {i: [NOMES[e][i] for e in ordem] for i in IDIOMAS},
    }


def graficos_extras(r: dict) -> list[dict]:
    """Os outros achados do README como dados, do mais importante para o menos. Mapas não entram."""
    am = {linha["especie"]: linha for linha in r["alto_mar_por_especie"]}
    ordem = [linha["especie"] for linha in r["alto_mar_por_especie"]]
    eixo_especie = _tres("Espécie", "Species", "Especie")
    y_alto_mar = _tres("Fração do tempo em alto-mar", "Share of time on the high seas", "Fracción del tiempo en alta mar")

    # 1. A mesma espécie, população a população (só espécies com mais de uma população marcada)
    pops = [p for p in r["por_populacao"] if p["especie"] in CURTO]
    pops.sort(key=lambda p: (ordem.index(p["especie"]), -p["estimativa"]))
    cab = [p["estimativa"] for p in pops if p["especie"] == "cabecuda"]
    menor, maior = _pct(min(cab)), _pct(max(cab))
    rotulos_pop = {
        i: [f"{CURTO[p['especie']][i]} · {POPULACOES.get(p['populacao'], {}).get(i, p['populacao'])}" for p in pops]
        for i in IDIOMAS
    }
    populacoes = {
        "tipo": "barras",
        "titulo": _tres(
            f"Mesma espécie, outro número: a tartaruga-cabeçuda vai de {menor} a {maior} conforme a população",
            f"Same species, different answer: loggerheads range from {menor} to {maior} by population",
            f"Misma especie, otro número: la tortuga boba va del {menor} al {maior} según la población",
        ),
        "eixo_x": _tres("Espécie e local de marcação", "Species and tagging region", "Especie y lugar de marcado"),
        "eixo_y": y_alto_mar,
        "formato_x": "numero",
        "formato_y": "percentual",
        "series": [
            {
                "nome": _tres("Tempo em alto-mar", "Time on the high seas", "Tiempo en alta mar"),
                "papel": "principal",
                "pontos": [[rotulos_pop["pt"][k], round(p["estimativa"], 4)] for k, p in enumerate(pops)],
                "rotulos": rotulos_pop,
            }
        ],
        "leitura": _tres(
            "Fração do tempo em alto-mar por local de marcação. O número de uma espécie depende de quais populações foram marcadas; o 0% do Mediterrâneo também reflete o mapa, que divide aquele mar inteiro em zonas nacionais.",
            "Share of time on the high seas by tagging region. A species-level figure depends on which populations were tagged; the Mediterranean 0% also reflects the source map, which splits that whole sea into national zones.",
            "Fracción del tiempo en alta mar según el lugar de marcado. La cifra de una especie depende de qué poblaciones se marcaron; el 0% del Mediterráneo refleja también el mapa, que reparte todo ese mar en zonas nacionales.",
        ),
    }

    # 2. Semana a semana desde a marcação (quatro séries: o tubarão-baleia só tem animais suficientes até a 13ª semana)
    papeis = {"cabecuda": "principal", "couro": "alternativa", "elefante": "base", "albatroz": "neutro"}
    series_curva = []
    for especie, papel in papeis.items():
        pontos = sorted((int(c["semana"]), round(c["fracao_em_alto_mar"], 4)) for c in r["curva_semanal"] if c["especie"] == especie and c["fracao_em_alto_mar"] is not None)
        series_curva.append({"nome": NOMES[especie], "papel": papel, "pontos": [list(p) for p in pontos][:80]})
    curva = {
        "tipo": "linhas",
        "titulo": _tres(
            "As tartarugas levam meses para chegar ao alto-mar; albatrozes e elefantes-marinhos, dias",
            "Turtles take months to reach the high seas; albatrosses and elephant seals take days",
            "Las tortugas tardan meses en llegar a alta mar; albatros y elefantes marinos, días",
        ),
        "eixo_x": _tres("Semanas desde a marcação", "Weeks since tagging", "Semanas desde el marcado"),
        "eixo_y": _tres("Fração das amostras em alto-mar", "Share of samples on the high seas", "Fracción de las muestras en alta mar"),
        "formato_x": "numero",
        "formato_y": "percentual",
        "series": series_curva,
        "leitura": _tres(
            "Animais são marcados na praia ou na colônia, então o começo de toda trajetória é costeiro. Nas tartarugas isso puxa o alto-mar para baixo; o tubarão-baleia ficou fora porque só tem animais suficientes até a 13ª semana.",
            "Animals are tagged on the beach or at the colony, so every track starts near the coast. For turtles this drags the high-seas share down; whale sharks are left out because too few were tracked beyond week 13.",
            "Los animales se marcan en la playa o en la colonia, así que toda trayectoria empieza cerca de la costa. En las tortugas eso reduce la alta mar; el tiburón ballena queda fuera porque pocos se rastrearon más allá de la semana 13.",
        ),
    }

    # 3. Contra o acaso
    acaso = {(linha["especie"], linha["caminhada"]): linha for linha in r["contra_o_acaso"]}
    acima, abaixo = acima_e_abaixo_do_acaso(r["contra_o_acaso"], ordem)
    n = len(ordem)
    contra = {
        "tipo": "barras",
        "titulo": _tres(
            f"Mais alto-mar do que o acaso em {len(acima)} das {n} espécies, menos em {len(abaixo)}",
            f"More high-seas time than chance in {len(acima)} of {n} species, less in {len(abaixo)}",
            f"Más alta mar que el azar en {len(acima)} de {n} especies, menos en {len(abaixo)}",
        ),
        "eixo_x": eixo_especie,
        "eixo_y": _tres("Fração dos dias em alto-mar", "Share of days on the high seas", "Fracción de los días en alta mar"),
        "formato_x": "numero",
        "formato_y": "percentual",
        "series": [
            _serie_de_barras(_tres("Animais reais", "Real animals", "Animales reales"), "principal", ordem, [acaso[(e, "sem memória")]["observado"] for e in ordem]),
            _serie_de_barras(_tres("Caminhada sem memória", "Memoryless random walk", "Caminata sin memoria"), "base", ordem, [acaso[(e, "sem memória")]["acaso"] for e in ordem]),
            _serie_de_barras(_tres("Caminhada com persistência", "Persistent random walk", "Caminata con persistencia"), "alternativa", ordem, [acaso[(e, "com persistência")]["acaso"] for e in ordem]),
        ],
        "leitura": _tres(
            "As caminhadas partem do ponto de marcação e usam os passos diários do próprio animal. Animais reais acima das duas caminhadas: o alto-mar é destino, não acaso. O albatroz fica abaixo porque sempre volta à colônia, o que a caminhada não faz.",
            "The walks start at the tagging site and reuse the animal's own daily steps. Real animals above both walks means the high seas are a destination, not chance. Albatrosses fall below because they keep returning to the colony, which a random walk never does.",
            "Las caminatas parten del punto de marcado y usan los pasos diarios del propio animal. Animales reales por encima de las dos caminatas: la alta mar es destino, no azar. El albatros queda por debajo porque siempre vuelve a la colonia, algo que la caminata no hace.",
        ),
    }

    # 4. No lugar do mapa: onde fica o tempo de cada espécie, por regime
    sul = {linha["especie"]: linha for linha in r["alto_mar_ao_sul_de_60"]}
    regimes = {
        "tipo": "barras",
        "titulo": _tres(
            f"No elefante-marinho, {_pct(sul['elefante']['parte_do_tempo_em_alto_mar'])} do alto-mar fica ao sul de 60°S; no albatroz, {_pct(sul['albatroz']['parte_do_tempo_em_alto_mar'])}",
            f"For elephant seals, {_pct(sul['elefante']['parte_do_tempo_em_alto_mar'])} of high-seas time lies south of 60°S; for albatrosses, {_pct(sul['albatroz']['parte_do_tempo_em_alto_mar'])}",
            f"En el elefante marino, el {_pct(sul['elefante']['parte_do_tempo_em_alto_mar'])} de la alta mar queda al sur de 60°S; en el albatros, el {_pct(sul['albatroz']['parte_do_tempo_em_alto_mar'])}",
        ),
        "eixo_x": eixo_especie,
        "eixo_y": _tres("Fração do tempo rastreado", "Share of tracked time", "Fracción del tiempo rastreado"),
        "formato_x": "numero",
        "formato_y": "percentual",
        "series": [
            _serie_de_barras(_tres("Alto-mar ao norte de 60°S", "High seas north of 60°S", "Alta mar al norte de 60°S"), "principal", ordem, [sul[e]["alto_mar_ao_norte_de_60_no_tempo_total"] for e in ordem]),
            _serie_de_barras(_tres("Alto-mar ao sul de 60°S (Tratado da Antártida)", "High seas south of 60°S (Antarctic Treaty area)", "Alta mar al sur de 60°S (Tratado Antártico)"), "alternativa", ordem, [sul[e]["parte_do_tempo_total"] for e in ordem]),
            _serie_de_barras(_tres("Águas de algum país", "Some country's waters", "Aguas de algún país"), "base", ordem, [1.0 - am[e]["tempo"] for e in ordem]),
        ],
        "leitura": _tres(
            "As três barras de cada espécie somam 100% do tempo rastreado. Ao sul de 60°S nenhuma zona nacional é reconhecida, mas já existe um regime de gestão próprio: para o elefante-marinho, é ali que está a maior parte do alto-mar.",
            "The three bars for each species add up to 100% of tracked time. South of 60°S no national zone is recognised, but a dedicated management regime already exists: for elephant seals, most of their high-seas time is there.",
            "Las tres barras de cada especie suman el 100% del tiempo rastreado. Al sur de 60°S no se reconoce ninguna zona nacional, pero ya existe un régimen de gestión propio: para el elefante marino, ahí está la mayor parte de su alta mar.",
        ),
    }

    # 5. Quantos países um mesmo animal usa
    pa = {linha["especie"]: linha for linha in r["jurisdicoes_por_individuo"]}
    a2, c2 = _pct(pa["albatroz"]["duas_ou_mais"]), _pct(pa["couro"]["duas_ou_mais"])
    paises = {
        "tipo": "barras",
        "titulo": _tres(
            f"{a2} dos albatrozes e {c2} das tartarugas-de-couro usaram águas de dois ou mais países",
            f"{a2} of albatrosses and {c2} of leatherbacks used the waters of two or more countries",
            f"El {a2} de los albatros y el {c2} de las tortugas laúd usaron aguas de dos o más países",
        ),
        "eixo_x": eixo_especie,
        "eixo_y": _tres("Parte dos animais rastreados", "Share of tracked animals", "Parte de los animales rastreados"),
        "formato_x": "numero",
        "formato_y": "percentual",
        "series": [
            _serie_de_barras(_tres("Duas ou mais jurisdições nacionais", "Two or more national jurisdictions", "Dos o más jurisdicciones nacionales"), "principal", ordem, [pa[e]["duas_ou_mais"] for e in ordem]),
            _serie_de_barras(_tres("Três ou mais", "Three or more", "Tres o más"), "alternativa", ordem, [pa[e]["tres_ou_mais"] for e in ordem]),
            _serie_de_barras(_tres("Nenhuma (só alto-mar)", "None (high seas only)", "Ninguna (solo alta mar)"), "neutro", ordem, [pa[e]["nenhuma"] for e in ordem]),
        ],
        "leitura": _tres(
            "Parte dos animais de cada espécie que ficou 24 horas ou mais em duas, em três ou em nenhuma jurisdição nacional (zona de um país ou área em disputa). Proteger a rota de um único animal já pede acordo entre países.",
            "Share of each species' animals that spent 24 hours or more in two, in three, or in no national jurisdiction (a country's zone or a disputed area). Protecting a single animal's route already takes agreement between countries.",
            "Parte de los animales de cada especie que pasó 24 horas o más en dos, en tres o en ninguna jurisdicción nacional (zona de un país o área en disputa). Proteger la ruta de un solo animal ya exige acuerdo entre países.",
        ),
    }
    return [populacoes, curva, contra, regimes, paises]


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
    return {
        **textos,
        "etiquetas": ["telemetria", "análise espacial", "bootstrap por indivíduo", "modelo nulo", "OBIS"],
        "grafico": grafico,
        "graficos_extras": graficos_extras(r),
    }
