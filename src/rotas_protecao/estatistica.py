"""Estimadores e incerteza por indivíduo.

A unidade de amostra é o animal, não a posição: mil posições do mesmo indivíduo dizem onde aquele
indivíduo esteve, não onde a espécie anda. Por isso todo intervalo aqui reamostra indivíduos
inteiros (bootstrap por conglomerado).
"""

from __future__ import annotations

import numpy as np


def pesos_de_bootstrap(n_individuos: int, n_reamostras: int, rng: np.random.Generator) -> np.ndarray:
    """Matriz [n_reamostras, n_individuos]: quantas vezes cada indivíduo entra em cada reamostra."""
    return rng.multinomial(n_individuos, np.full(n_individuos, 1.0 / n_individuos), size=n_reamostras).astype(float)


def fracao_agrupada(tempo_na_categoria, tempo_total) -> float:
    """Fração do tempo somado de todos os indivíduos (quem foi rastreado por mais tempo pesa mais)."""
    total = float(np.sum(tempo_total))
    return float(np.sum(tempo_na_categoria)) / total if total > 0 else float("nan")


def fracao_media_por_individuo(tempo_na_categoria, tempo_total) -> float:
    """Média das frações individuais (cada animal pesa igual, tenha 10 dias ou 400)."""
    tempo_na_categoria, tempo_total = np.asarray(tempo_na_categoria, dtype=float), np.asarray(tempo_total, dtype=float)
    valido = tempo_total > 0
    return float(np.mean(tempo_na_categoria[valido] / tempo_total[valido])) if valido.any() else float("nan")


def intervalo(valores: np.ndarray, nivel: float = 0.95) -> tuple[float, float]:
    """Intervalo percentil das reamostras."""
    cauda = (1.0 - nivel) / 2.0
    inferior, superior = np.nanquantile(valores, [cauda, 1.0 - cauda])
    return float(inferior), float(superior)


def bootstrap_da_fracao(tempo_na_categoria, tempo_total, pesos: np.ndarray, nivel: float = 0.95) -> dict:
    """Fração agrupada com intervalo por bootstrap de indivíduos.

    `pesos` vem de `pesos_de_bootstrap`; usar a mesma matriz para várias categorias mantém as
    reamostras pareadas.
    """
    a, b = np.asarray(tempo_na_categoria, dtype=float), np.asarray(tempo_total, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        reamostras = (pesos @ a) / (pesos @ b)
    inferior, superior = intervalo(reamostras, nivel)
    return {"estimativa": fracao_agrupada(a, b), "inferior": inferior, "superior": superior}


def bootstrap_da_diferenca(num_a, den_a, num_b, den_b, pesos: np.ndarray, nivel: float = 0.95) -> dict:
    """Diferença entre duas frações agrupadas medidas nos mesmos indivíduos (reamostras pareadas)."""
    num_a, den_a = np.asarray(num_a, dtype=float), np.asarray(den_a, dtype=float)
    num_b, den_b = np.asarray(num_b, dtype=float), np.asarray(den_b, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        reamostras = (pesos @ num_a) / (pesos @ den_a) - (pesos @ num_b) / (pesos @ den_b)
    inferior, superior = intervalo(reamostras, nivel)
    estimativa = fracao_agrupada(num_a, den_a) - fracao_agrupada(num_b, den_b)
    return {"estimativa": estimativa, "inferior": inferior, "superior": superior, "prob_maior_que_zero": float(np.mean(reamostras > 0))}


def intervalo_ingenuo_por_pontos(sucessos: float, total: float, nivel: float = 0.95) -> tuple[float, float]:
    """Intervalo de Wilson tratando cada posição como independente (a conta ingênua, para comparar)."""
    from scipy import stats

    if total <= 0:
        return float("nan"), float("nan")
    z = stats.norm.ppf(1.0 - (1.0 - nivel) / 2.0)
    p = sucessos / total
    centro = (p + z**2 / (2 * total)) / (1 + z**2 / total)
    meia = z * np.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / (1 + z**2 / total)
    return float(centro - meia), float(centro + meia)
