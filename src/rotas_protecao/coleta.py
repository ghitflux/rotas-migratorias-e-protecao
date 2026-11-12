"""Coleta das bases públicas para `data/brutos/` (fora do git). Uma requisição por vez, com pausa.

Fontes (todas sem chave e sem cadastro):
- OBIS (api.obis.org/v3): posições de rastreamento por satélite, conjunto a conjunto.
- Marine Regions / Flanders Marine Institute (WFS em geo.vliz.be): Zonas Econômicas Exclusivas v12 e
  o polígono de alto-mar, ambos CC BY 4.0.
- Natural Earth (domínio público): terra 1:50m (máscara) e linha de costa 1:110m (desenho dos mapas).
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

AGENTE = "portfolio-estudos/1.0"
PAUSA_S = 0.5
BRUTOS = Path("data") / "brutos"

OBIS = "https://api.obis.org/v3"
WFS = "https://geo.vliz.be/geoserver/MarineRegions/wfs"
NATURAL_EARTH = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson"

RAATD = "48cb8624-a221-47ed-9a6d-b99b0bb394e0"

# Espécies do estudo: nome científico aceito no WoRMS, nome comum e teto de velocidade sustentada (km/h)
# usado no filtro de posições impossíveis. Os tetos são escolhas deste estudo, folgadas de propósito.
ESPECIES = {
    "couro": {"cientifico": "Dermochelys coriacea", "comum": "tartaruga-de-couro", "vmax_kmh": 6.0},
    "cabecuda": {"cientifico": "Caretta caretta", "comum": "tartaruga-cabeçuda", "vmax_kmh": 6.0},
    "baleia": {"cientifico": "Rhincodon typus", "comum": "tubarão-baleia", "vmax_kmh": 10.0},
    "elefante": {"cientifico": "Mirounga leonina", "comum": "elefante-marinho-do-sul", "vmax_kmh": 12.0},
    "albatroz": {"cientifico": "Diomedea exulans", "comum": "albatroz-errante", "vmax_kmh": 110.0},
}

# Conjuntos de rastreamento por satélite usados. `individuo` diz de que campo sai o identificador do
# animal: "organismID" (padrão do OBIS-SEAMAP), "eventID_nome" (prefixo do eventID até a data) ou
# "occurrenceID_prefixo" (RAATD: o que vem antes de ":deployment:").
CONJUNTOS = [
    {"chave": "couro_africa_sul_1", "especie": "couro", "id": "30bc7528-925f-4df4-b89b-d204ab024294", "individuo": "organismID", "populacao": "África do Sul (Índico sudoeste)"},
    {"chave": "couro_africa_sul_2", "especie": "couro", "id": "021165f1-0a42-4ae6-a651-c8dda089475a", "individuo": "organismID", "populacao": "África do Sul (Índico sudoeste)"},
    {"chave": "cabecuda_pacifico_norte", "especie": "cabecuda", "id": "3b71a712-ca34-4368-a029-52b5db32b140", "individuo": "organismID", "populacao": "Pacífico Norte"},
    {"chave": "cabecuda_pacifico_juvenis", "especie": "cabecuda", "id": "f0134b03-3f28-4a87-b596-f08c896fe9d5", "individuo": "organismID", "populacao": "Pacífico Norte"},
    {"chave": "cabecuda_taiwan", "especie": "cabecuda", "id": "269609a8-58e6-4b58-86af-7d3b5cd44e71", "individuo": "organismID", "populacao": "Pacífico Norte"},
    {"chave": "cabecuda_japao", "especie": "cabecuda", "id": "08e9a21c-7acf-4b63-96dc-34e7a3611fcd", "individuo": "organismID", "populacao": "Pacífico Norte"},
    {"chave": "cabecuda_mediterraneo_oeste", "especie": "cabecuda", "id": "e69a5cc7-2c7d-4ef7-8662-a68a326bddad", "individuo": "eventID_nome", "populacao": "Mediterrâneo"},
    {"chave": "cabecuda_creta", "especie": "cabecuda", "id": "0801a5a2-66e3-441c-83a3-25f0ef0fc0f5", "individuo": "organismID", "populacao": "Mediterrâneo"},
    {"chave": "cabecuda_reuniao", "especie": "cabecuda", "id": "7687b242-05b7-48d7-a316-ba6dc34e72b5", "individuo": "organismID", "populacao": "Índico sudoeste"},
    {"chave": "cabecuda_mocambique", "especie": "cabecuda", "id": "b606c4a0-d693-4a03-9086-0be6e501c0fc", "individuo": "organismID", "populacao": "Índico sudoeste"},
    {"chave": "cabecuda_bonaire", "especie": "cabecuda", "id": "5ab87d96-5ef6-4886-b295-4e08d01ab65a", "individuo": "organismID", "populacao": "Caribe"},
    {"chave": "baleia_galapagos", "especie": "baleia", "id": "7a9532d6-bfd2-49e9-b595-c4e7daebfc72", "individuo": "organismID", "populacao": "Galápagos (Pacífico leste)"},
    {"chave": "baleia_mar_de_coral", "especie": "baleia", "id": "538763eb-b436-414b-b353-df94b40187a1", "individuo": "organismID", "populacao": "Mar de Coral (Pacífico oeste)"},
    {"chave": "elefante_raatd", "especie": "elefante", "id": RAATD, "individuo": "occurrenceID_prefixo", "populacao": "Oceano Austral"},
    {"chave": "albatroz_raatd", "especie": "albatroz", "id": RAATD, "individuo": "occurrenceID_prefixo", "populacao": "Oceano Austral"},
]  # fmt: skip

CAMPOS_OBIS = ("id", "decimalLatitude", "decimalLongitude", "eventDate", "organismID", "occurrenceID", "eventID", "basisOfRecord")
CAMPOS_ZEE = ("mrgid", "geoname", "pol_type", "sovereign1", "sovereign2", "territory1", "iso_sov1", "iso_sov2", "iso_ter1")


def _abrir(url: str, tentativas: int = 6, espera: int = 300) -> bytes:
    """Uma requisição, com repetição e espera crescente."""
    requisicao = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept-Encoding": "gzip"})
    for tentativa in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(requisicao, timeout=espera) as resposta:
                corpo = resposta.read()
                if resposta.headers.get("Content-Encoding") == "gzip":
                    corpo = gzip.decompress(corpo)
            time.sleep(PAUSA_S)
            return corpo
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as erro:
            if tentativa == tentativas:
                raise RuntimeError(f"falha ao baixar {url[:140]}: {erro}") from erro
            time.sleep(10 * tentativa)
    raise RuntimeError("inalcançável")


def _json(url: str) -> dict:
    return json.loads(_abrir(url))


def baixar_conjunto_obis(conjunto: dict, destino: Path) -> int:
    """Baixa as posições de uma espécie num conjunto do OBIS, paginando pelo identificador.

    Grava um CSV compactado só com os campos necessários. Devolve o número de registros.
    """
    cientifico = ESPECIES[conjunto["especie"]]["cientifico"]
    base = {"datasetid": conjunto["id"], "scientificname": cientifico, "size": 5000, "fields": ",".join(CAMPOS_OBIS)}
    parcial = destino.with_suffix(".parcial")
    total, baixados, depois = None, 0, None
    with gzip.open(parcial, "wt", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(CAMPOS_OBIS)
        while True:
            parametros = dict(base) if depois is None else {**base, "after": depois}
            pagina = _json(f"{OBIS}/occurrence?{urllib.parse.urlencode(parametros)}")
            lote = pagina["results"]
            total = pagina["total"] if total is None else total
            escritor.writerows([[r.get(c, "") for c in CAMPOS_OBIS] for r in lote])
            baixados += len(lote)
            if len(lote) < 5000:
                break
            depois = lote[-1]["id"]
    if baixados < total:
        parcial.unlink()
        raise RuntimeError(f"OBIS {conjunto['chave']}: {baixados} de {total} registros")
    parcial.replace(destino)
    return baixados


def metadados_do_conjunto(identificador: str) -> dict:
    """Título, citação e licença de um conjunto, como o OBIS os publica."""
    d = _json(f"{OBIS}/dataset/{identificador}")["results"][0]
    direitos = d.get("intellectualrights") or ""
    if "Non" in direitos:
        licenca = "CC BY-NC 4.0"
    elif "waived" in direitos or "CC0" in direitos:
        licenca = "CC0"
    elif "Attribution" in direitos:
        licenca = "CC BY 4.0"
    else:
        licenca = direitos[:60]
    return {"titulo": d.get("title"), "citacao": d.get("citation"), "doi": d.get("citation_id"), "licenca": licenca, "publicado": (d.get("published") or "")[:10]}


def baixar_camada_wfs(camada: str, destino: Path, campos: tuple[str, ...], por_pagina: int = 4, ordenar: str = "mrgid") -> int:
    """Baixa uma camada de polígonos do Marine Regions, em páginas pequenas, simplificando na chegada.

    Os polígonos originais têm detalhe de metros e somam centenas de megabytes; a análise usa uma grade
    de 0,1 grau, então cada polígono é simplificado com tolerância de 0,01 grau antes de ser guardado.
    """
    import shapely

    base = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": f"MarineRegions:{camada}", "outputFormat": "application/json"}
    if ordenar:
        base["sortBy"] = ordenar
    # Atributos primeiro, numa requisição leve (sem geometria), na mesma ordem das páginas de geometria.
    atributos = _json(f"{WFS}?{urllib.parse.urlencode({**base, 'propertyName': ','.join(campos)})}")
    propriedades = [{c: f["properties"].get(c) for c in campos} for f in atributos["features"]]
    total = len(propriedades)
    geometrias = []
    for inicio in range(0, total, por_pagina):
        corpo = _abrir(f"{WFS}?{urllib.parse.urlencode({**base, 'count': por_pagina, 'startIndex': inicio, 'propertyName': 'the_geom'})}")
        # O leitor de GeoJSON do GEOS (em C) devolve uma coleção com a geometria de cada feição, na ordem.
        for geometria in shapely.get_parts(shapely.from_geojson(corpo)):
            simples = shapely.simplify(geometria, 0.01, preserve_topology=False)
            geometrias.append(simples if shapely.is_valid(simples) else shapely.make_valid(simples))
        print(f"    {camada}: {len(geometrias)} de {total}", flush=True)
    if len(geometrias) != total:
        raise RuntimeError(f"WFS {camada}: {len(geometrias)} geometrias para {total} feições")
    feicoes = [
        {"type": "Feature", "properties": p, "geometry": json.loads(shapely.to_geojson(g))} for p, g in zip(propriedades, geometrias)
    ]
    destino.write_text(json.dumps({"type": "FeatureCollection", "features": feicoes}), encoding="utf-8")
    return total


def baixar_natural_earth(nome: str, destino: Path) -> None:
    corpo = _abrir(f"{NATURAL_EARTH}/{nome}.geojson")
    if json.loads(corpo)["type"] != "FeatureCollection":
        raise RuntimeError(f"Natural Earth {nome}: arquivo inesperado")
    destino.write_bytes(corpo)


def resumo_dos_arquivos(pasta: Path = BRUTOS) -> dict:
    """Tamanho e SHA-256 de cada arquivo bruto, para registrar o que foi coletado."""
    return {
        arquivo.name: {"bytes": arquivo.stat().st_size, "sha256": hashlib.sha256(arquivo.read_bytes()).hexdigest()[:16]}
        for arquivo in sorted(pasta.iterdir())
        if arquivo.is_file()
    }
