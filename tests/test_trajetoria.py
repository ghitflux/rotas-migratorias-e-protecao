"""Reconstrução de trajetória conferida em trajetórias sintéticas de resposta conhecida."""

import numpy as np
import pytest

from rotas_protecao import geodesia, trajetoria

GRAU_KM = 2 * np.pi * geodesia.RAIO_KM / 360


def _reta_no_equador(horas, kmh=4.0):
    """Animal andando para leste no equador a velocidade constante."""
    horas = np.asarray(horas, dtype=float)
    return horas, np.zeros(len(horas)), horas * kmh / GRAU_KM


def test_juntar_simultaneas_ordena_e_funde():
    t, lat, lon = trajetoria.juntar_simultaneas([5.0, 0.0, 5.0, 2.0], [0.0, 0.0, 0.0, 0.0], [10.0, 0.0, 12.0, 4.0])
    assert t.tolist() == [0.0, 2.0, 5.0]
    assert np.allclose(lon, [0.0, 4.0, 11.0])
    assert np.allclose(lat, 0.0, atol=1e-9)


def test_filtro_nao_tira_nada_de_uma_trajetoria_limpa():
    t, lat, lon = _reta_no_equador(np.arange(0, 240, 6))
    assert trajetoria.filtro_de_velocidade(t, lat, lon, vmax_kmh=6.0).all()


def test_filtro_tira_espinhos_isolados_no_meio_e_nas_pontas():
    t, lat, lon = _reta_no_equador(np.arange(0, 240, 6))
    lat = lat.copy()
    ruins = [0, 7, 20, len(t) - 1]
    lat[ruins] = 5.0  # 556 km fora da rota, impossível a 6 km/h em 6 horas
    fica = trajetoria.filtro_de_velocidade(t, lat, lon, vmax_kmh=6.0)
    assert np.flatnonzero(~fica).tolist() == ruins


def test_filtro_tira_dois_erros_seguidos_no_mesmo_lugar():
    t, lat, lon = _reta_no_equador(np.arange(0, 240, 6))
    lat = lat.copy()
    lat[[10, 11]] = 5.0
    fica = trajetoria.filtro_de_velocidade(t, lat, lon, vmax_kmh=6.0)
    assert np.flatnonzero(~fica).tolist() == [10, 11]


def test_filtro_aceita_posicoes_quase_simultaneas_com_erro_pequeno():
    # duas posições a 6 minutos, a 3 km uma da outra: 30 km/h na conta crua, mas é só erro de posição
    t = np.array([0.0, 6.0, 6.1, 12.0])
    lon = np.array([0.0, 24.0, 27.0, 48.0]) / GRAU_KM
    assert trajetoria.filtro_de_velocidade(t, np.zeros(4), lon, vmax_kmh=6.0).all()


def test_interpolacao_regular_devolve_o_tempo_exato():
    t, lat, lon = _reta_no_equador([0, 5, 7, 30, 31, 100])
    r = trajetoria.interpolar_regular(t, lat, lon, passo_h=10.0)
    assert r["t_h"].tolist() == [5.0, 15.0, 25.0, 35.0, 45.0, 55.0, 65.0, 75.0, 85.0, 95.0]
    assert np.allclose(r["lon"], r["t_h"] * 4.0 / GRAU_KM)  # movimento uniforme: posição proporcional ao tempo
    assert (r["segmento"] == 0).all()


def test_interpolacao_nao_atravessa_falha_longa():
    t, lat, lon = _reta_no_equador([0, 10, 20, 500, 510, 520])
    r = trajetoria.interpolar_regular(t, lat, lon, passo_h=10.0, falha_maxima_h=240.0)
    assert r["t_h"].tolist() == [5.0, 15.0, 505.0, 515.0]
    assert r["segmento"].tolist() == [0, 0, 1, 1]
    assert trajetoria.tempo_em_falhas_h(t, 240.0) == 480.0
    sem_limite = trajetoria.interpolar_regular(t, lat, lon, passo_h=10.0)
    assert len(sem_limite["t_h"]) == 52


def test_tempo_e_pontos_dao_respostas_diferentes_quando_a_transmissao_e_desigual():
    """Animal passa 100 h a oeste de uma fronteira e 100 h a leste, mas transmite 10 vezes mais a oeste."""
    kmh = 4.0
    fronteira_lon = 100 * kmh / GRAU_KM
    horas = np.concatenate([np.arange(0, 100, 1.0), np.arange(100, 201, 10.0)])
    t, lat, lon = _reta_no_equador(horas, kmh)
    fracao_por_pontos = np.mean(lon >= fronteira_lon)
    r = trajetoria.interpolar_regular(t, lat, lon, passo_h=1.0)
    fracao_por_tempo = np.mean(r["lon"] >= fronteira_lon)
    assert fracao_por_tempo == pytest.approx(0.5)
    assert fracao_por_pontos == pytest.approx(11 / 111)


def test_interpolacao_atravessa_a_linha_de_data():
    t = np.array([0.0, 10.0])
    r = trajetoria.interpolar_regular(t, np.zeros(2), np.array([179.0, -179.0]), passo_h=5.0)
    assert np.allclose(np.abs(r["lon"]), [179.5, 179.5])
    assert r["lon"][0] > 0 > r["lon"][1]


def test_trajetoria_curta_demais_nao_gera_amostra():
    r = trajetoria.interpolar_regular([0.0, 3.0], [0.0, 0.0], [0.0, 0.1], passo_h=6.0)
    assert len(r["t_h"]) == 0
    assert len(trajetoria.interpolar_regular([0.0], [0.0], [0.0], passo_h=6.0)["t_h"]) == 0


def test_passos_e_giros_de_um_quadrado():
    # leste, norte, oeste: dois giros de 90 graus para a esquerda (negativos, pois o rumo cai)
    lat = np.array([0.0, 0.0, 0.1, 0.1])
    lon = np.array([0.0, 0.1, 0.1, 0.0])
    passos, giros = trajetoria.passos_e_giros(lat, lon, np.zeros(4, dtype=int))
    assert np.allclose(passos, 0.1 * GRAU_KM, rtol=1e-3)
    assert np.allclose(giros, -np.pi / 2, atol=1e-3)


def test_passos_nao_ligam_trechos_diferentes():
    lat = np.zeros(4)
    lon = np.array([0.0, 0.1, 50.0, 50.1])
    passos, giros = trajetoria.passos_e_giros(lat, lon, np.array([0, 0, 1, 1]))
    assert len(passos) == 2 and passos.max() < 12
    assert len(giros) == 0


def test_corridas_descarta_oscilacao_curta_e_funde_vizinhas():
    codigos = [3, 3, 3, 3, 0, 3, 3, 3, 3, 0, 0, 0, 0, 7, 7, 7, 7]
    resultado = trajetoria.corridas(codigos, np.zeros(len(codigos), dtype=int), minimo=4)
    assert resultado == [(3, 0, 8), (0, 0, 4), (7, 0, 4)]
    assert trajetoria.corridas([], [], minimo=4) == []
