"""Funções geodésicas conferidas contra valores conhecidos."""

import numpy as np
import pytest

from rotas_protecao import geodesia


def test_um_grau_no_equador():
    # 1 grau de arco = 2 pi R / 360
    esperado = 2 * np.pi * geodesia.RAIO_KM / 360
    assert geodesia.distancia_km(0, 0, 0, 1) == pytest.approx(esperado, rel=1e-12)
    assert esperado == pytest.approx(111.195, abs=0.001)


def test_do_polo_ao_equador_e_antipodas():
    quarto = np.pi * geodesia.RAIO_KM / 2
    assert geodesia.distancia_km(90, 0, 0, 77) == pytest.approx(quarto, rel=1e-12)
    assert geodesia.distancia_km(0, 0, 0, 180) == pytest.approx(2 * quarto, rel=1e-12)
    assert geodesia.distancia_km(10, 20, -10, -160) == pytest.approx(2 * quarto, rel=1e-7)  # o haversine perde precisão nos antípodas


def test_distancia_entre_cidades():
    # Paris (48,8566 N, 2,3522 L) a Nova York (40,7128 N, 74,0060 O): cerca de 5.837 km na esfera
    assert geodesia.distancia_km(48.8566, 2.3522, 40.7128, -74.0060) == pytest.approx(5837, abs=5)


def test_um_grau_de_longitude_encolhe_com_o_cosseno_da_latitude():
    no_equador = geodesia.distancia_km(0, 0, 0, 1)
    a_60_graus = geodesia.distancia_km(60, 0, 60, 1)
    assert a_60_graus == pytest.approx(no_equador * np.cos(np.radians(60)), rel=1e-4)


def test_distancia_atravessa_a_linha_de_data():
    assert geodesia.distancia_km(0, 179.5, 0, -179.5) == pytest.approx(geodesia.distancia_km(0, 0, 0, 1), rel=1e-9)


def test_rumos_cardeais():
    assert geodesia.rumo_inicial(0, 0, 10, 0) == pytest.approx(0.0, abs=1e-12)
    assert geodesia.rumo_inicial(0, 0, 0, 10) == pytest.approx(np.pi / 2)
    assert geodesia.rumo_inicial(0, 0, -10, 0) == pytest.approx(np.pi)
    assert geodesia.rumo_inicial(0, 0, 0, -10) == pytest.approx(3 * np.pi / 2)


def test_destino_desfaz_distancia_e_rumo():
    rng = np.random.default_rng(1)
    lat, lon = rng.uniform(-70, 70, 200), rng.uniform(-180, 180, 200)
    rumo, d = rng.uniform(0, 2 * np.pi, 200), rng.uniform(1, 3000, 200)
    lat2, lon2 = geodesia.destino(lat, lon, rumo, d)
    assert np.allclose(geodesia.distancia_km(lat, lon, lat2, lon2), d, rtol=1e-9)
    assert np.allclose(np.cos(geodesia.rumo_inicial(lat, lon, lat2, lon2) - rumo), 1.0, atol=1e-9)


def test_destino_para_o_norte_e_pela_linha_de_data():
    lat, lon = geodesia.destino(0.0, 0.0, 0.0, 2 * np.pi * geodesia.RAIO_KM / 360 * 10)
    assert (lat, lon) == (pytest.approx(10.0), pytest.approx(0.0, abs=1e-9))
    lat, lon = geodesia.destino(0.0, 179.0, np.pi / 2, 2 * np.pi * geodesia.RAIO_KM / 360 * 2)
    assert (lat, lon) == (pytest.approx(0.0, abs=1e-9), pytest.approx(-179.0))


def test_interpolacao_no_equador_e_nas_pontas():
    lat, lon = geodesia.interpolar(0, 0, 0, 90, np.array([0.0, 0.25, 0.5, 1.0]))
    assert np.allclose(lat, 0.0, atol=1e-9)
    assert np.allclose(lon, [0.0, 22.5, 45.0, 90.0])


def test_interpolacao_nao_da_a_volta_no_mundo_na_linha_de_data():
    lat, lon = geodesia.interpolar(10.0, 170.0, 10.0, -170.0, 0.5)
    assert abs(abs(float(lon)) - 180.0) < 1e-9  # e não 0, que é o que a média das longitudes daria
    assert float(lat) > 10.0  # o grande círculo passa ao norte do paralelo


def test_ponto_medio_do_grande_circulo_fica_a_meia_distancia():
    lat, lon = geodesia.interpolar(48.8566, 2.3522, 40.7128, -74.0060, 0.5)
    total = geodesia.distancia_km(48.8566, 2.3522, 40.7128, -74.0060)
    assert geodesia.distancia_km(48.8566, 2.3522, lat, lon) == pytest.approx(total / 2, rel=1e-9)
    assert geodesia.distancia_km(lat, lon, 40.7128, -74.0060) == pytest.approx(total / 2, rel=1e-9)


def test_interpolar_pontos_coincidentes():
    lat, lon = geodesia.interpolar(-33.0, 151.0, -33.0, 151.0, 0.3)
    assert (float(lat), float(lon)) == (pytest.approx(-33.0), pytest.approx(151.0))


def test_ponto_medio_na_linha_de_data():
    lat, lon = geodesia.ponto_medio(np.array([0.0, 0.0]), np.array([179.0, -179.0]))
    assert lat == pytest.approx(0.0, abs=1e-9)
    assert abs(lon) == pytest.approx(180.0)
