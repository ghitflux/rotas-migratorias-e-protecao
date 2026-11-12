"""Geometria na esfera: distância por grande círculo, rumo, ponto de destino e interpolação.

Tudo vetorizado em NumPy, com latitude e longitude em graus e distância em quilômetros. A Terra é
tratada como esfera de raio médio 6.371,0088 km; o erro em relação ao elipsoide fica abaixo de 0,5%,
muito menor que o erro de posição de um transmissor por satélite.
"""

from __future__ import annotations

import numpy as np

RAIO_KM = 6371.0088
MILHA_NAUTICA_KM = 1.852


def distancia_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Distância por grande círculo (fórmula do haversine)."""
    f1, f2 = np.radians(lat1), np.radians(lat2)
    df = f2 - f1
    dl = np.radians(np.asarray(lon2, dtype=float) - np.asarray(lon1, dtype=float))
    a = np.sin(df / 2) ** 2 + np.cos(f1) * np.cos(f2) * np.sin(dl / 2) ** 2
    return 2 * RAIO_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def rumo_inicial(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Rumo de partida de 1 para 2, em radianos (0 = norte, pi/2 = leste), no intervalo [0, 2 pi)."""
    f1, f2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(np.asarray(lon2, dtype=float) - np.asarray(lon1, dtype=float))
    y = np.sin(dl) * np.cos(f2)
    x = np.cos(f1) * np.sin(f2) - np.sin(f1) * np.cos(f2) * np.cos(dl)
    return np.mod(np.arctan2(y, x), 2 * np.pi)


def destino(lat, lon, rumo, distancia) -> tuple[np.ndarray, np.ndarray]:
    """Ponto a `distancia` km de (lat, lon) seguindo o `rumo` (radianos) por um grande círculo."""
    f1, l1 = np.radians(lat), np.radians(lon)
    d = np.asarray(distancia, dtype=float) / RAIO_KM
    seno = np.sin(f1) * np.cos(d) + np.cos(f1) * np.sin(d) * np.cos(rumo)
    f2 = np.arcsin(np.clip(seno, -1.0, 1.0))
    l2 = l1 + np.arctan2(np.sin(rumo) * np.sin(d) * np.cos(f1), np.cos(d) - np.sin(f1) * np.sin(f2))
    return np.degrees(f2), normalizar_longitude(np.degrees(l2))


def normalizar_longitude(lon) -> np.ndarray:
    """Leva a longitude para o intervalo [-180, 180)."""
    return np.mod(np.asarray(lon, dtype=float) + 180.0, 360.0) - 180.0


def para_vetor(lat, lon) -> np.ndarray:
    """Vetor unitário (x, y, z) de cada ponto; a última dimensão tem tamanho 3."""
    f, l = np.radians(lat), np.radians(lon)
    return np.stack([np.cos(f) * np.cos(l), np.cos(f) * np.sin(l), np.sin(f)], axis=-1)


def de_vetor(v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Latitude e longitude de vetores (não precisam estar normalizados)."""
    norma = np.linalg.norm(v, axis=-1)
    lat = np.degrees(np.arcsin(np.clip(v[..., 2] / norma, -1.0, 1.0)))
    lon = np.degrees(np.arctan2(v[..., 1], v[..., 0]))
    return lat, lon


def interpolar(lat1, lon1, lat2, lon2, fracao) -> tuple[np.ndarray, np.ndarray]:
    """Ponto na fração `fracao` (0 a 1) do grande círculo entre 1 e 2 (interpolação esférica).

    É o que impede o erro clássico de interpolar latitude e longitude como se fossem um plano: perto
    da linha de data (180 graus) a média das longitudes cai do outro lado do planeta.
    """
    a, b = para_vetor(lat1, lon1), para_vetor(lat2, lon2)
    fracao = np.asarray(fracao, dtype=float)
    angulo = np.arccos(np.clip(np.sum(a * b, axis=-1), -1.0, 1.0))
    seno = np.sin(angulo)
    proximo = seno < 1e-12  # pontos coincidentes: qualquer combinação serve
    seno_seguro = np.where(proximo, 1.0, seno)
    pa = np.where(proximo, 1.0 - fracao, np.sin((1.0 - fracao) * angulo) / seno_seguro)
    pb = np.where(proximo, fracao, np.sin(fracao * angulo) / seno_seguro)
    return de_vetor(pa[..., None] * a + pb[..., None] * b)


def ponto_medio(lat, lon) -> tuple[float, float]:
    """Centro de um grupo de pontos (média dos vetores unitários), seguro na linha de data."""
    lat_m, lon_m = de_vetor(para_vetor(lat, lon).mean(axis=0))
    return float(lat_m), float(lon_m)
