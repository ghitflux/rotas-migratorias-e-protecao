"""Reconstrução da trajetória de um indivíduo a partir de posições de satélite.

Quatro passos, cada um numa função:
1. `juntar_simultaneas`: ordena no tempo e funde posições com o mesmo carimbo de tempo;
2. `filtro_de_velocidade`: tira posições que exigiriam uma velocidade impossível para a espécie;
3. `interpolar_regular`: amostra a trajetória a intervalos iguais de tempo, sem atravessar falhas longas;
4. `passos_e_giros`: comprimento dos passos e ângulos de giro, usados na caminhada aleatória.

O tempo é sempre um vetor de horas (float) a partir de uma origem qualquer.
"""

from __future__ import annotations

import numpy as np

from rotas_protecao import geodesia

INTERVALO_MINIMO_H = 1.0


def juntar_simultaneas(t_h, lat, lon) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Ordena no tempo e substitui posições com o mesmo instante pelo centro delas.

    Vários conjuntos só publicam a data (sem hora): as posições do mesmo dia não têm ordem conhecida,
    então viram um ponto só.
    """
    t_h, lat, lon = np.asarray(t_h, dtype=float), np.asarray(lat, dtype=float), np.asarray(lon, dtype=float)
    ordem = np.argsort(t_h, kind="stable")
    t_h, lat, lon = t_h[ordem], lat[ordem], lon[ordem]
    unicos, inverso, contagem = np.unique(t_h, return_inverse=True, return_counts=True)
    if len(unicos) == len(t_h):
        return t_h, lat, lon
    vetores = np.zeros((len(unicos), 3))
    np.add.at(vetores, inverso, geodesia.para_vetor(lat, lon))
    lat_u, lon_u = geodesia.de_vetor(vetores / contagem[:, None])
    return unicos, lat_u, lon_u


def velocidades_kmh(t_h, lat, lon, intervalo_minimo_h: float = INTERVALO_MINIMO_H) -> np.ndarray:
    """Velocidade entre posições consecutivas (tamanho n - 1).

    O intervalo de tempo tem um piso: duas posições a minutos uma da outra, cada uma com erro de
    alguns quilômetros, dariam uma velocidade enorme sem que nenhuma das duas esteja errada.
    """
    d = geodesia.distancia_km(lat[:-1], lon[:-1], lat[1:], lon[1:])
    return d / np.maximum(np.diff(t_h), intervalo_minimo_h)


def filtro_de_velocidade(t_h, lat, lon, vmax_kmh: float, intervalo_minimo_h: float = INTERVALO_MINIMO_H) -> np.ndarray:
    """Máscara booleana das posições que ficam. Espera o tempo já ordenado.

    Primeiro tira os "espinhos": posições que exigiriam mais que `vmax_kmh` tanto para chegar da
    anterior quanto para ir à seguinte (nas pontas, em relação às duas vizinhas do mesmo lado). Repete
    até não sobrar nenhum. Depois faz uma passada para a frente que tira o que ainda for inalcançável
    a partir da última posição aceita (pega dois erros seguidos no mesmo lugar errado).
    """
    t_h, lat, lon = np.asarray(t_h, dtype=float), np.asarray(lat, dtype=float), np.asarray(lon, dtype=float)
    fica = np.ones(len(t_h), dtype=bool)

    def veloz(i: np.ndarray, j: np.ndarray) -> np.ndarray:
        d = geodesia.distancia_km(lat[i], lon[i], lat[j], lon[j])
        return d / np.maximum(np.abs(t_h[j] - t_h[i]), intervalo_minimo_h) > vmax_kmh

    for _ in range(50):
        indices = np.flatnonzero(fica)
        if len(indices) < 3:
            break
        rapido = veloz(indices[:-1], indices[1:])
        espinho = np.zeros(len(indices), dtype=bool)
        espinho[1:-1] = rapido[:-1] & rapido[1:]
        espinho[0] = rapido[0] and bool(veloz(indices[:1], indices[2:3])[0])
        espinho[-1] = rapido[-1] and bool(veloz(indices[-3:-2], indices[-1:])[0])
        if not espinho.any():
            break
        fica[indices[espinho]] = False

    indices = np.flatnonzero(fica)
    if len(indices) >= 2 and veloz(indices[:-1], indices[1:]).any():
        ultimo = indices[0]
        for i in indices[1:]:
            d = geodesia.distancia_km(lat[ultimo], lon[ultimo], lat[i], lon[i])
            if d / max(t_h[i] - t_h[ultimo], intervalo_minimo_h) > vmax_kmh:
                fica[i] = False
            else:
                ultimo = i
    return fica


def interpolar_regular(t_h, lat, lon, passo_h: float, falha_maxima_h: float = np.inf) -> dict[str, np.ndarray]:
    """Amostras da trajetória a cada `passo_h` horas, pelo grande círculo entre posições consecutivas.

    Cada amostra fica no meio de um intervalo de `passo_h` horas e representa exatamente esse tempo.
    Trechos entre duas posições separadas por mais que `falha_maxima_h` não são interpolados: o
    animal não foi visto ali, e o tempo da falha não entra na conta. Devolve `t_h`, `lat`, `lon` e
    `segmento` (número do trecho contínuo de cada amostra).
    """
    t_h, lat, lon = np.asarray(t_h, dtype=float), np.asarray(lat, dtype=float), np.asarray(lon, dtype=float)
    vazio = {"t_h": np.array([]), "lat": np.array([]), "lon": np.array([]), "segmento": np.array([], dtype=int)}
    if len(t_h) < 2:
        return vazio
    cortes = np.flatnonzero(np.diff(t_h) > falha_maxima_h) + 1
    inicios = np.concatenate([[0], cortes])
    fins = np.concatenate([cortes, [len(t_h)]])
    partes_t, partes_seg = [], []
    for numero, (i, f) in enumerate(zip(inicios, fins)):
        duracao = t_h[f - 1] - t_h[i]
        n = int(np.floor(duracao / passo_h + 1e-9))
        if n >= 1:
            partes_t.append(t_h[i] + (np.arange(n) + 0.5) * passo_h)
            partes_seg.append(np.full(n, numero))
    if not partes_t:
        return vazio
    t_reg, segmento = np.concatenate(partes_t), np.concatenate(partes_seg)
    antes = np.clip(np.searchsorted(t_h, t_reg, side="right") - 1, 0, len(t_h) - 2)
    fracao = (t_reg - t_h[antes]) / (t_h[antes + 1] - t_h[antes])
    lat_reg, lon_reg = geodesia.interpolar(lat[antes], lon[antes], lat[antes + 1], lon[antes + 1], fracao)
    return {"t_h": t_reg, "lat": lat_reg, "lon": lon_reg, "segmento": segmento}


def tempo_em_falhas_h(t_h, falha_maxima_h: float) -> float:
    """Soma das falhas de transmissão maiores que o limite (tempo em que o animal não foi visto)."""
    dt = np.diff(np.asarray(t_h, dtype=float))
    return float(dt[dt > falha_maxima_h].sum())


def passos_e_giros(lat, lon, segmento) -> tuple[np.ndarray, np.ndarray]:
    """Comprimento dos passos (km) entre amostras consecutivas do mesmo trecho e ângulos de giro (rad).

    O giro é a diferença entre o rumo de um passo e o do passo anterior, em (-pi, pi]. Um animal que
    segue reto tem giros perto de zero; um que vaga sem direção tem giros espalhados.
    """
    lat, lon, segmento = np.asarray(lat, dtype=float), np.asarray(lon, dtype=float), np.asarray(segmento)
    if len(lat) < 2:
        return np.array([]), np.array([])
    mesmo = segmento[1:] == segmento[:-1]
    passos = geodesia.distancia_km(lat[:-1], lon[:-1], lat[1:], lon[1:])
    rumos = geodesia.rumo_inicial(lat[:-1], lon[:-1], lat[1:], lon[1:])
    giro = np.mod(np.diff(rumos) + np.pi, 2 * np.pi) - np.pi
    giro_valido = mesmo[1:] & mesmo[:-1] & (passos[1:] > 0) & (passos[:-1] > 0)
    return passos[mesmo], giro[giro_valido]


def corridas(codigos, segmento, minimo: int = 1) -> list[tuple[int, int, int]]:
    """Sequência de estadias: (código, segmento, número de amostras), na ordem em que acontecem.

    Estadias com menos que `minimo` amostras são descartadas e as vizinhas iguais, fundidas: evita
    contar como travessia um animal que oscila em cima de uma fronteira.
    """
    codigos, segmento = np.asarray(codigos), np.asarray(segmento)
    if len(codigos) == 0:
        return []
    muda = np.flatnonzero((codigos[1:] != codigos[:-1]) | (segmento[1:] != segmento[:-1])) + 1
    inicios = np.concatenate([[0], muda])
    tamanhos = np.diff(np.concatenate([inicios, [len(codigos)]]))
    resultado: list[tuple[int, int, int]] = []
    for i, n in zip(inicios, tamanhos):
        if n < minimo:
            continue
        codigo, seg = int(codigos[i]), int(segmento[i])
        if resultado and resultado[-1][0] == codigo and resultado[-1][1] == seg:
            resultado[-1] = (codigo, seg, resultado[-1][2] + int(n))
        else:
            resultado.append((codigo, seg, int(n)))
    return resultado
