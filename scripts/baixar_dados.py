"""Baixa as bases públicas para data/brutos/ e monta o extrato agregado em data/.

    uv run python scripts/baixar_dados.py               # baixa o que falta e monta o extrato
    uv run python scripts/baixar_dados.py --so-extrato  # só remonta o extrato a partir de data/brutos/

O download completo leva de 20 a 40 minutos (quase tudo é o conjunto RAATD, com mais de um milhão de
posições). Arquivo já baixado não é baixado de novo. O extrato em data/ é o que `rodar_analise.py`
usa: ele não contém nenhuma posição de animal, só agregados por indivíduo, por espécie e por célula.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from rotas_protecao import coleta, preparo  # noqa: E402

BRUTOS = RAIZ / "data" / "brutos"


def baixar() -> None:
    BRUTOS.mkdir(parents=True, exist_ok=True)
    registro_caminho = BRUTOS / "coleta_bruta.json"
    registro = json.loads(registro_caminho.read_text(encoding="utf-8")) if registro_caminho.exists() else {"conjuntos": {}}

    for nome in ("ne_110m_coastline", "ne_50m_land"):
        destino = BRUTOS / f"{nome}.geojson"
        if not destino.exists():
            print(f"Natural Earth: {nome}")
            coleta.baixar_natural_earth(nome, destino)

    camadas = {"eez": (coleta.CAMPOS_ZEE, 4, "mrgid"), "high_seas": (("mrgid", "name"), 1, "")}
    for camada, (campos, por_pagina, ordenar) in camadas.items():
        destino = BRUTOS / f"marineregions_{camada}.geojson"
        if not destino.exists():
            print(f"Marine Regions: camada {camada}")
            n = coleta.baixar_camada_wfs(camada, destino, campos, por_pagina, ordenar)
            print(f"  {n} polígonos")

    for conjunto in coleta.CONJUNTOS:
        destino = BRUTOS / f"obis_{conjunto['chave']}.csv.gz"
        if not destino.exists():
            inicio = time.time()
            print(f"OBIS: {conjunto['chave']}")
            n = coleta.baixar_conjunto_obis(conjunto, destino)
            registro["conjuntos"][conjunto["chave"]] = {
                "registros": n,
                "data_da_coleta": date.today().isoformat(),
                **coleta.metadados_do_conjunto(conjunto["id"]),
            }
            registro_caminho.write_text(json.dumps(registro, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  {n} registros em {time.time() - inicio:.0f} s")
    registro["arquivos"] = coleta.resumo_dos_arquivos(BRUTOS)
    registro.setdefault("data_da_coleta", date.today().isoformat())
    registro_caminho.write_text(json.dumps(registro, ensure_ascii=False, indent=1), encoding="utf-8")

    # Verificação de tamanho: o RAATD tem de vir inteiro (mais de 900 mil posições de elefante-marinho).
    minimos = {"elefante_raatd": 900_000, "albatroz_raatd": 100_000, "cabecuda_pacifico_norte": 40_000}
    for chave, minimo in minimos.items():
        if registro["conjuntos"][chave]["registros"] < minimo:
            raise RuntimeError(f"{chave}: {registro['conjuntos'][chave]['registros']} registros, esperava pelo menos {minimo}")


def main() -> None:
    if "--so-extrato" not in sys.argv:
        baixar()
    inicio = time.time()
    preparo.montar_extrato(BRUTOS, RAIZ / "data")
    print(f"Extrato montado em {time.time() - inicio:.0f} s")


if __name__ == "__main__":
    main()
