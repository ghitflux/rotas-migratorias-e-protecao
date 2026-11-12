"""Estimadores e bootstrap por indivíduo conferidos em casos de resposta conhecida."""

import numpy as np
import pytest

from rotas_protecao import estatistica


def test_fracao_agrupada_e_media_por_individuo_diferem_quando_as_duracoes_sao_desiguais():
    # um animal de 10 dias todo na costa e um de 390 dias todo em alto-mar
    em_alto_mar, total = np.array([0.0, 390.0]), np.array([10.0, 390.0])
    assert estatistica.fracao_agrupada(em_alto_mar, total) == pytest.approx(0.975)
    assert estatistica.fracao_media_por_individuo(em_alto_mar, total) == pytest.approx(0.5)


def test_pesos_de_bootstrap_somam_o_numero_de_individuos():
    pesos = estatistica.pesos_de_bootstrap(17, 500, np.random.default_rng(0))
    assert pesos.shape == (500, 17)
    assert (pesos.sum(axis=1) == 17).all()
    assert pesos.mean() == pytest.approx(1.0)


def test_individuos_identicos_dao_intervalo_de_largura_zero():
    pesos = estatistica.pesos_de_bootstrap(30, 400, np.random.default_rng(1))
    r = estatistica.bootstrap_da_fracao(np.full(30, 25.0), np.full(30, 100.0), pesos)
    assert r["estimativa"] == pytest.approx(0.25)
    assert r["inferior"] == pytest.approx(0.25) and r["superior"] == pytest.approx(0.25)


def test_bootstrap_reproduz_o_erro_padrao_da_media():
    """Com tempos iguais, a fração agrupada é a média das frações: o intervalo deve ter ~1,96 erros padrão."""
    rng = np.random.default_rng(4)
    fracoes = rng.beta(2, 5, 400)
    pesos = estatistica.pesos_de_bootstrap(400, 4000, rng)
    r = estatistica.bootstrap_da_fracao(fracoes * 100, np.full(400, 100.0), pesos)
    erro_padrao = fracoes.std(ddof=1) / np.sqrt(400)
    assert r["estimativa"] == pytest.approx(fracoes.mean())
    assert (r["superior"] - r["inferior"]) / 2 == pytest.approx(1.96 * erro_padrao, rel=0.08)


def test_intervalo_por_individuo_e_mais_largo_que_o_ingenuo_por_pontos():
    """20 animais, 1.000 posições cada, cada animal quase todo num lado: os pontos fingem uma certeza que não há."""
    rng = np.random.default_rng(9)
    fracoes = rng.choice([0.05, 0.95], 20)
    posicoes_em_alto_mar = rng.binomial(1000, fracoes).astype(float)
    total = np.full(20, 1000.0)
    pesos = estatistica.pesos_de_bootstrap(20, 3000, rng)
    por_individuo = estatistica.bootstrap_da_fracao(posicoes_em_alto_mar, total, pesos)
    ingenuo = estatistica.intervalo_ingenuo_por_pontos(posicoes_em_alto_mar.sum(), total.sum())
    largura_individuo = por_individuo["superior"] - por_individuo["inferior"]
    largura_ingenua = ingenuo[1] - ingenuo[0]
    assert largura_individuo > 10 * largura_ingenua


def test_cobertura_do_bootstrap_por_individuo():
    """Em 300 mundos simulados com fração verdadeira 0,4, o intervalo de 90% deve conter a verdade perto de 90% das vezes."""
    rng = np.random.default_rng(21)
    acertos = 0
    for _ in range(300):
        fracoes = rng.beta(2, 3, 60)  # média 0,4
        tempo = np.full(60, 50.0)
        pesos = estatistica.pesos_de_bootstrap(60, 400, rng)
        r = estatistica.bootstrap_da_fracao(fracoes * tempo, tempo, pesos, nivel=0.90)
        acertos += r["inferior"] <= 0.4 <= r["superior"]
    assert 0.83 <= acertos / 300 <= 0.95


def test_diferenca_pareada_zero_quando_as_duas_medidas_sao_iguais():
    rng = np.random.default_rng(6)
    a, total = rng.uniform(0, 50, 25), np.full(25, 50.0)
    pesos = estatistica.pesos_de_bootstrap(25, 500, rng)
    r = estatistica.bootstrap_da_diferenca(a, total, a, total, pesos)
    assert r["estimativa"] == 0.0 and r["inferior"] == 0.0 and r["superior"] == 0.0


def test_diferenca_pareada_detecta_deslocamento_constante():
    rng = np.random.default_rng(8)
    total = np.full(40, 100.0)
    b = rng.uniform(10, 60, 40)
    pesos = estatistica.pesos_de_bootstrap(40, 800, rng)
    r = estatistica.bootstrap_da_diferenca(b + 15.0, total, b, total, pesos)
    assert r["estimativa"] == pytest.approx(0.15)
    assert r["inferior"] == pytest.approx(0.15) and r["superior"] == pytest.approx(0.15)
    assert r["prob_maior_que_zero"] == 1.0


def test_intervalo_de_wilson_valor_conhecido():
    # 50 em 100, 95%: (0,404, 0,596)
    inferior, superior = estatistica.intervalo_ingenuo_por_pontos(50, 100)
    assert inferior == pytest.approx(0.4038, abs=1e-3) and superior == pytest.approx(0.5962, abs=1e-3)
