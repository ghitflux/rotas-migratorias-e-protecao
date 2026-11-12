"""Grade de jurisdição e caminhada aleatória conferidas em mundos de brinquedo."""

import numpy as np
import pytest
from shapely.geometry import box

from rotas_protecao import geodesia, jurisdicao, nulo


def _mundo_de_brinquedo() -> jurisdicao.Grade:
    """Grade de 1 grau: país 1 a oeste (lon -30 a -10, com terra de -30 a -20), país 2 a leste, alto-mar em volta."""
    zee = [box(-20, -10, -10, 10), box(10, -10, 20, 10)]
    alto_mar = [box(-180, -90, 180, 90).difference(box(-30, -10, -10, 10)).difference(box(10, -10, 20, 10))]
    terra = [box(-30, -10, -20, 10)]
    return jurisdicao.montar_grade(zee, [1, 2], alto_mar, terra, resolucao=1.0)


def test_rasterizar_pinta_pelo_centro_da_celula():
    grade = jurisdicao.rasterizar([box(0, 0, 2, 3)], [5], resolucao=1.0)
    assert (grade == 5).sum() == 6
    lat, lon = jurisdicao.centros(1.0)
    i, j = np.nonzero(grade == 5)
    assert lat[i].min() == 0.5 and lat[i].max() == 2.5 and lon[j].min() == 0.5 and lon[j].max() == 1.5


def test_classificar_devolve_pais_alto_mar_e_terra():
    grade = _mundo_de_brinquedo()
    assert grade.classificar([0.5, 0.5, 0.5, 50.0], [-15.5, 15.5, 0.5, 0.5]).tolist() == [1, 2, 0, 0]
    # a terra herda a jurisdição das águas vizinhas e fica marcada como terra
    assert grade.classificar(0.5, -25.5) == 1
    assert grade.em_terra(0.5, -25.5) and not grade.em_terra(0.5, -15.5)


def test_terra_ao_sul_de_60_graus_nao_herda_jurisdicao_de_ninguem():
    """Um continente antártico sem ZEE: fica como terra, mas fora de qualquer jurisdição nacional."""
    zee = [box(-20, -58, -10, -50)]
    antartida = box(-180, -90, 180, -70)
    alto_mar = [box(-180, -90, 180, 90).difference(zee[0]).difference(antartida)]
    grade = jurisdicao.montar_grade(zee, [1], alto_mar, [antartida], resolucao=1.0)
    assert grade.classificar(-80.5, -15.5) == jurisdicao.ALTO_MAR and grade.em_terra(-80.5, -15.5)
    assert grade.classificar(-55.5, -15.5) == 1


def test_alto_mar_na_area_do_oceano_pesa_pelo_cosseno():
    """Metade norte toda alto-mar, metade sul toda de um país, sem terra: metade da área, por simetria."""
    from rotas_protecao.analise import alto_mar_na_area_do_oceano

    grade = jurisdicao.montar_grade([box(-180, -90, 180, 0)], [1], [box(-180, 0, 180, 90)], [], resolucao=1.0)
    assert alto_mar_na_area_do_oceano(grade) == pytest.approx(0.5)
    # só a faixa polar norte (60 a 90 N) em alto-mar: (1 - sen 60°) / 2 da esfera
    polar = jurisdicao.montar_grade([box(-180, -90, 180, 60)], [1], [box(-180, 60, 180, 90)], [], resolucao=1.0)
    assert alto_mar_na_area_do_oceano(polar) == pytest.approx((1 - np.sin(np.radians(60))) / 2, rel=1e-3)


def test_longitude_e_latitude_fora_da_faixa_nao_estouram():
    grade = _mundo_de_brinquedo()
    assert grade.classificar(0.5, 360 - 15.5) == 1  # 344,5 L é o mesmo que 15,5 O
    assert grade.classificar(90.0, 180.0) == 0


def test_preencher_pelo_vizinho():
    grade = np.array([[1, 9, 9, 9, 2]], dtype=np.uint16)
    vazio = grade == 9
    assert jurisdicao.preencher_pelo_vizinho(grade, vazio, ~vazio).tolist() == [[1, 1, 1, 2, 2]] or jurisdicao.preencher_pelo_vizinho(
        grade, vazio, ~vazio
    ).tolist() == [[1, 1, 2, 2, 2]]


def test_fracao_do_tempo_de_um_animal_que_cruza_do_pais_ao_alto_mar():
    """Sai de 15,5 O (país 1) e anda para leste no equador até 4,5 L: 5,5 graus no país, 14,5 em alto-mar."""
    grade = _mundo_de_brinquedo()
    lon = np.linspace(-15.5, 4.5, 20001)
    codigos = grade.classificar(np.zeros_like(lon), lon)
    assert np.mean(codigos == 0) == pytest.approx(14.5 / 20.0, abs=1e-3)
    assert np.mean(codigos == 1) == pytest.approx(5.5 / 20.0, abs=1e-3)


def test_caminhada_sem_memoria_tem_o_deslocamento_quadratico_conhecido():
    """Passo fixo L, n passos, rumos independentes: a média do quadrado do deslocamento é n L^2."""
    rng = np.random.default_rng(7)
    lat, lon = nulo.simular_caminhadas(0.0, 0.0, np.array([10.0]), n_passos=100, n_caminhadas=6000, rng=rng)
    assert lat.shape == (101, 6000)
    deslocamento = geodesia.distancia_km(0.0, 0.0, lat[-1], lon[-1])
    assert np.mean(deslocamento**2) == pytest.approx(100 * 10.0**2, rel=0.05)


def test_caminhada_preserva_o_comprimento_dos_passos():
    rng = np.random.default_rng(3)
    passos = np.array([5.0, 20.0, 80.0])
    lat, lon = nulo.simular_caminhadas(-20.0, 60.0, passos, n_passos=50, n_caminhadas=40, rng=rng, giros=np.array([-0.2, 0.0, 0.3]))
    dados = geodesia.distancia_km(lat[:-1], lon[:-1], lat[1:], lon[1:])
    assert np.isin(np.round(dados, 6), passos).all()


def test_caminhada_persistente_vai_mais_longe_que_a_sem_memoria():
    rng = np.random.default_rng(11)
    passos = np.array([30.0])
    sem = nulo.simular_caminhadas(0.0, 0.0, passos, 60, 2000, rng)
    com = nulo.simular_caminhadas(0.0, 0.0, passos, 60, 2000, rng, giros=np.array([-0.1, 0.0, 0.1]))
    longe = lambda par: geodesia.distancia_km(0.0, 0.0, par[0][-1], par[1][-1]).mean()  # noqa: E731
    assert longe(com) > 3 * longe(sem)


def test_caminhada_com_giro_zero_e_uma_reta():
    rng = np.random.default_rng(5)
    lat, lon = nulo.simular_caminhadas(0.0, 0.0, np.array([25.0]), 40, 10, rng, giros=np.array([0.0]))
    # rumo constante não é exatamente um grande círculo; em 1.000 km a diferença fica abaixo de 0,001%
    assert np.allclose(geodesia.distancia_km(0.0, 0.0, lat[-1], lon[-1]), 40 * 25.0, rtol=1e-5)


def test_caminhada_nunca_entra_em_terra():
    grade = _mundo_de_brinquedo()
    rng = np.random.default_rng(2)
    lat, lon = nulo.simular_caminhadas(0.5, -19.5, np.array([60.0, 120.0]), n_passos=80, n_caminhadas=300, rng=rng, grade=grade)
    assert not grade.em_terra(lat, lon).any()


def test_fracao_em_alto_mar_das_caminhadas():
    grade = _mundo_de_brinquedo()
    alto_mar = np.array([True, False, False])
    # caminhada parada dentro do país 1: fração zero; parada em alto-mar: fração um
    parada_no_pais = (np.full((5, 3), 0.5), np.full((5, 3), -15.5))
    parada_fora = (np.full((5, 3), 40.5), np.full((5, 3), 0.5))
    assert nulo.fracao_em_alto_mar(*parada_no_pais, grade, alto_mar).tolist() == [0.0, 0.0, 0.0]
    assert nulo.fracao_em_alto_mar(*parada_fora, grade, alto_mar).tolist() == [1.0, 1.0, 1.0]
