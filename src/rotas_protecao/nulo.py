"""Hipótese nula: o que um animal sem destino faria a partir do mesmo ponto de marcação.

Duas caminhadas aleatórias, as duas com os passos sorteados (com reposição) dos passos do próprio
animal, e as duas impedidas de entrar em terra:
- sem memória: cada passo sai num rumo qualquer;
- com persistência: o rumo de cada passo é o do anterior mais um giro sorteado dos giros do próprio
  animal. Preserva o quanto ele anda reto, mas não para onde.

Se o animal real passa mais tempo em alto-mar do que as caminhadas, o alto-mar não é acaso de quem
anda muito: é para lá que ele vai.
"""

from __future__ import annotations

import numpy as np

from rotas_protecao import geodesia
from rotas_protecao.jurisdicao import Grade

TENTATIVAS_FORA_DA_TERRA = 8


def simular_caminhadas(
    lat0: float,
    lon0: float,
    passos_km: np.ndarray,
    n_passos: int,
    n_caminhadas: int,
    rng: np.random.Generator,
    giros: np.ndarray | None = None,
    grade: Grade | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Simula `n_caminhadas` caminhadas de `n_passos` passos a partir de (lat0, lon0).

    Devolve latitude e longitude com formato [n_passos + 1, n_caminhadas]; a linha 0 é a partida.
    Com `giros`, a caminhada é a persistente; sem, a sem memória. Com `grade`, um passo que cairia em
    terra é sorteado de novo (até 8 vezes; se não der, a caminhada fica parada naquele passo).
    """
    lat = np.empty((n_passos + 1, n_caminhadas))
    lon = np.empty((n_passos + 1, n_caminhadas))
    lat[0], lon[0] = lat0, lon0
    rumo = rng.uniform(0.0, 2 * np.pi, n_caminhadas)
    for k in range(n_passos):
        comprimento = rng.choice(passos_km, n_caminhadas)
        if giros is None or len(giros) == 0:
            rumo = rng.uniform(0.0, 2 * np.pi, n_caminhadas)
        else:
            rumo = rumo + rng.choice(giros, n_caminhadas)
        nova_lat, nova_lon = geodesia.destino(lat[k], lon[k], rumo, comprimento)
        if grade is not None:
            barrado = grade.em_terra(nova_lat, nova_lon)
            for _ in range(TENTATIVAS_FORA_DA_TERRA):
                if not barrado.any():
                    break
                rumo[barrado] = rng.uniform(0.0, 2 * np.pi, int(barrado.sum()))
                lat_b, lon_b = geodesia.destino(lat[k][barrado], lon[k][barrado], rumo[barrado], comprimento[barrado])
                nova_lat[barrado], nova_lon[barrado] = lat_b, lon_b
                barrado = grade.em_terra(nova_lat, nova_lon)
            nova_lat[barrado], nova_lon[barrado] = lat[k][barrado], lon[k][barrado]
        lat[k + 1], lon[k + 1] = nova_lat, nova_lon
    return lat, lon


def fracao_em_alto_mar(lat: np.ndarray, lon: np.ndarray, grade: Grade, alto_mar: np.ndarray) -> np.ndarray:
    """Fração dos passos de cada caminhada (colunas) em células cujo código está marcado em `alto_mar`.

    `alto_mar` é um vetor booleano indexado pelo código de jurisdição. A linha 0 (a partida) não conta.
    """
    codigos = grade.classificar(lat[1:], lon[1:])
    return alto_mar[codigos].mean(axis=0)
