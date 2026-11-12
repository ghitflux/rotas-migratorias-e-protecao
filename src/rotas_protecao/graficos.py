"""Figuras do README e do notebook, no estilo do portfólio."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection
from matplotlib.colors import ListedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from rotas_protecao.estilo import (
    APAGADO,
    AQUA,
    AZUL,
    EIXO,
    ESTILO,
    GRADE,
    LARANJA,
    SERIES,
    SUPERFICIE,
    TINTA,
    TINTA_SECUNDARIA,
    percentual,
)

# A cor segue a espécie, sempre a mesma em todas as figuras.
COR_DA_ESPECIE = {"albatroz": SERIES[0], "elefante": SERIES[1], "couro": SERIES[2], "cabecuda": SERIES[3], "baleia": SERIES[4]}


def _titulos(fig: Figure, titulo: str, subtitulo: str) -> None:
    fig.text(0.02, 0.965, titulo, fontsize=13, fontweight="bold", color=TINTA, va="top")
    fig.text(0.02, 0.905, subtitulo, fontsize=9.5, color=TINTA_SECUNDARIA, va="top")


def _eixo_percentual(ax: plt.Axes, eixo: str = "y", teto: float = 1.0) -> None:
    marcas = np.arange(0, teto + 0.001, 0.2)
    if eixo == "y":
        ax.set_ylim(0, teto)
        ax.set_yticks(marcas)
        ax.set_yticklabels([percentual(m) for m in marcas])
    else:
        ax.set_xlim(0, teto)
        ax.set_xticks(marcas)
        ax.set_xticklabels([percentual(m) for m in marcas])


def tempo_x_pontos(tabela: pd.DataFrame, titulo: str, subtitulo: str) -> Figure:
    """Barras lado a lado: fração em alto-mar pelo tempo (azul, com IC) e pela contagem de registros (laranja)."""
    with plt.rc_context(ESTILO):
        fig, ax = plt.subplots(figsize=(8.2, 4.6), dpi=160)
        fig.subplots_adjust(top=0.76, left=0.08, right=0.98, bottom=0.17)
        _titulos(fig, titulo, subtitulo)
        x = np.arange(len(tabela))
        largura = 0.36
        ax.bar(x - largura / 2 - 0.01, tabela["tempo"], largura, color=AZUL, label="pelo tempo rastreado (IC 95% por indivíduo)")
        ax.bar(x + largura / 2 + 0.01, tabela["pontos"], largura, color=LARANJA, label="pela contagem de registros")
        ax.errorbar(x - largura / 2 - 0.01, tabela["tempo"], yerr=[tabela["tempo"] - tabela["tempo_inf"], tabela["tempo_sup"] - tabela["tempo"]], fmt="none", ecolor=TINTA, elinewidth=1.1, capsize=3)
        for xi, (_, linha) in zip(x, tabela.iterrows()):
            ax.annotate(percentual(linha["tempo"]), (xi - largura / 2 - 0.01, linha["tempo_sup"]), xytext=(0, 4), textcoords="offset points", ha="center", fontsize=9, color=TINTA)
            ax.annotate(percentual(linha["pontos"]), (xi + largura / 2 + 0.01, linha["pontos"]), xytext=(0, 4), textcoords="offset points", ha="center", fontsize=9, color=TINTA_SECUNDARIA)
        ax.set_xticks(x)
        ax.set_xticklabels([f"{linha['nome']}\n{linha['individuos']} animais" for _, linha in tabela.iterrows()], fontsize=9)
        _eixo_percentual(ax)
        ax.set_ylabel("fração em alto-mar")
        ax.legend(loc="upper right", fontsize=8.5)
    return fig


def mapa_do_tempo(grade: pd.DataFrame, costa: list, titulo: str, subtitulo: str) -> Figure:
    """Células de 1 grau com tempo rastreado: azul onde a maior parte é alto-mar, laranja onde é água de algum país."""
    with plt.rc_context(ESTILO):
        fig = plt.figure(figsize=(8.2, 5.0), dpi=160)
        _titulos(fig, titulo, subtitulo)
        ax = fig.add_axes([0.02, 0.09, 0.96, 0.74])
        soma = grade.groupby(["lat_sul", "lon_oeste"], as_index=False)[["dias", "dias_em_alto_mar"]].sum()
        imagem = np.full((180, 360), np.nan)
        maioria_mar = soma["dias_em_alto_mar"] > 0.5 * soma["dias"]
        # três tons por regime, pela quantidade de dias de animal na célula
        nivel = np.digitize(soma["dias"], [3, 30])
        imagem[soma["lat_sul"].to_numpy() + 90, soma["lon_oeste"].to_numpy() + 180] = np.where(maioria_mar, nivel, nivel + 3)
        cores = ["#a9cbf3", "#5598e7", "#1c5cab", "#f6c3ad", "#eb6834", "#a8431a"]
        ax.imshow(imagem, origin="lower", extent=(-180, 180, -90, 90), cmap=ListedColormap(cores), vmin=-0.5, vmax=5.5, interpolation="nearest", aspect="auto", zorder=1)
        ax.add_collection(LineCollection(costa, colors=APAGADO, linewidths=0.5, zorder=2))
        ax.set_xlim(-180, 180)
        ax.set_ylim(-80, 62)
        ax.set_aspect(1.15)
        ax.grid(False)
        ax.set_xticks([])
        ax.set_yticks([])
        for lado in ax.spines.values():
            lado.set_visible(True)
            lado.set_color(EIXO)
        legenda = [
            Patch(facecolor=cores[0], label="alto-mar: menos de 3 dias de animal"),
            Patch(facecolor=cores[1], label="alto-mar: 3 a 30 dias"),
            Patch(facecolor=cores[2], label="alto-mar: mais de 30 dias"),
            Patch(facecolor=cores[3], label="águas de algum país: menos de 3 dias"),
            Patch(facecolor=cores[4], label="águas de algum país: 3 a 30 dias"),
            Patch(facecolor=cores[5], label="águas de algum país: mais de 30 dias"),
        ]
        fig.legend(handles=legenda, loc="lower center", ncols=3, fontsize=8, bbox_to_anchor=(0.5, 0.0), columnspacing=1.2, handlelength=1.2)
    return fig


def curva_desde_a_marcacao(curva: pd.DataFrame, nomes: dict, titulo: str, subtitulo: str, semanas: int = 40) -> Figure:
    """Fração em alto-mar a cada semana depois da marcação, uma linha por espécie."""
    with plt.rc_context(ESTILO):
        fig, ax = plt.subplots(figsize=(8.2, 4.6), dpi=160)
        fig.subplots_adjust(top=0.76, left=0.08, right=0.80, bottom=0.13)
        _titulos(fig, titulo, subtitulo)
        finais = []
        for especie, cor in COR_DA_ESPECIE.items():
            parte = curva[(curva["especie"] == especie) & (curva["semana"] < semanas)]
            if parte.empty:
                continue
            ax.plot(parte["semana"], parte["fracao_em_alto_mar"], color=cor)
            finais.append((float(parte["fracao_em_alto_mar"].iloc[-1]), int(parte["semana"].iloc[-1]), nomes[especie], cor))
        # rótulos diretos à direita, afastados uns dos outros
        finais.sort()
        ultimo_y = -1.0
        for y, x, nome, cor in finais:
            if x < semanas - 3:  # a série acaba antes (poucos animais rastreados por tanto tempo): rótulo no fim da linha
                ax.annotate(nome, (x, y), xytext=(6, 7), textcoords="offset points", fontsize=8.5, color=TINTA_SECUNDARIA, va="center")
                continue
            y_rotulo = max(y, ultimo_y + 0.055)
            ax.annotate(nome, (x, y), xytext=(semanas + 0.6, y_rotulo), textcoords="data", fontsize=8.5, color=TINTA_SECUNDARIA, va="center", annotation_clip=False)
            ax.plot([x, semanas + 0.4], [y, y_rotulo], color=cor, linewidth=0.8, clip_on=False)
            ultimo_y = y_rotulo
        ax.axvspan(0, 4, color=GRADE, alpha=0.6, linewidth=0)
        ax.annotate("primeiras 4 semanas", (0.2, 0.97), fontsize=8.5, color=TINTA_SECUNDARIA, va="top")
        ax.set_xlim(0, semanas)
        _eixo_percentual(ax)
        ax.set_xlabel("semanas desde a marcação")
        ax.set_ylabel("fração das amostras em alto-mar")
    return fig


def jurisdicoes(tabela: pd.DataFrame, ordem: list[str], titulo: str, subtitulo: str, quantas: int = 5) -> Figure:
    """Painel por espécie: as jurisdições com mais tempo, com intervalo. Alto-mar em azul, países em laranja."""
    with plt.rc_context(ESTILO):
        fig, eixos = plt.subplots(1, len(ordem), figsize=(8.2, 4.4), dpi=160)
        fig.subplots_adjust(top=0.74, left=0.015, right=0.985, bottom=0.11, wspace=0.08)
        _titulos(fig, titulo, subtitulo)
        for ax, especie in zip(eixos, ordem):
            parte = tabela[tabela["chave_especie"] == especie].head(quantas).iloc[::-1]
            y = np.arange(len(parte))
            cores = [AZUL if t == "alto-mar" else (APAGADO if t != "ZEE" else LARANJA) for t in parte["tipo"]]
            ax.barh(y, parte["fracao_do_tempo"], color=cores, height=0.62)
            ax.errorbar(parte["fracao_do_tempo"], y, xerr=[parte["fracao_do_tempo"] - parte["ic95_inferior"], parte["ic95_superior"] - parte["fracao_do_tempo"]], fmt="none", ecolor=TINTA, elinewidth=1, capsize=2)
            for yi, (_, linha) in zip(y, parte.iterrows()):
                nome = linha["jurisdicao"].replace("Área em disputa: ", "Disputa: ").replace("Regime conjunto: ", "Conjunto: ").replace("Reino Unido", "R. Unido").replace(" / ", "/")
                nome = nome if len(nome) <= 30 else nome[:29] + "…"
                ax.annotate(f"{nome}  {percentual(linha['fracao_do_tempo'])}", (0, yi + 0.33), xytext=(0, 2), textcoords="offset points", fontsize=7.6, color=TINTA, va="bottom")
            ax.set_ylim(-0.6, quantas - 0.1)
            ax.set_xlim(0, 1)
            ax.set_xticks([0, 0.5])
            ax.set_xticklabels(["0", "50%"], fontsize=8)
            ax.set_yticks([])
            ax.grid(axis="y", visible=False)
            ax.grid(axis="x", visible=True)
            ax.set_title(parte["nome_comum"].iloc[0], fontsize=9.5, color=TINTA_SECUNDARIA, loc="left")
        fig.legend(
            handles=[Patch(facecolor=AZUL, label="alto-mar"), Patch(facecolor=LARANJA, label="ZEE de um país"), Patch(facecolor=APAGADO, label="área em disputa ou regime conjunto")],
            loc="lower center", ncols=3, fontsize=8.5, bbox_to_anchor=(0.5, 0.0),
        )  # fmt: skip
    return fig


def observado_x_acaso(tabela: pd.DataFrame, nomes: dict, ordem: list[str], titulo: str, subtitulo: str) -> Figure:
    """Alto-mar observado (azul) contra as duas caminhadas aleatórias (laranja e verde-água), por espécie."""
    with plt.rc_context(ESTILO):
        fig, ax = plt.subplots(figsize=(8.2, 4.4), dpi=160)
        fig.subplots_adjust(top=0.76, left=0.24, right=0.97, bottom=0.20)
        _titulos(fig, titulo, subtitulo)
        for k, especie in enumerate(ordem):
            parte = tabela[tabela["especie"] == especie].set_index("caminhada")
            sem, com = parte.loc["sem memória"], parte.loc["com persistência"]
            ax.plot([min(sem["acaso"], com["acaso"], sem["observado"]), max(sem["acaso"], com["acaso"], sem["observado"])], [k, k], color=GRADE, linewidth=2.5, zorder=1)
            ax.plot(sem["acaso"], k, "o", color=LARANJA, zorder=3, label="caminhada sem memória" if k == 0 else None)
            ax.plot(com["acaso"], k, "o", color=AQUA, zorder=3, label="caminhada com persistência" if k == 0 else None)
            ax.plot(sem["observado"], k, "o", color=AZUL, zorder=4, markersize=10, label="animais reais" if k == 0 else None)
            ax.annotate(percentual(sem["observado"]), (sem["observado"], k), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=9, color=TINTA)
        ax.set_yticks(range(len(ordem)))
        ax.set_yticklabels([nomes[e] for e in ordem])
        ax.invert_yaxis()
        ax.set_ylim(len(ordem) - 0.5, -0.6)
        _eixo_percentual(ax, "x")
        ax.grid(axis="x", visible=True)
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("fração dos dias em alto-mar")
        fig.legend(*ax.get_legend_handles_labels(), loc="lower center", ncols=3, fontsize=8.5, bbox_to_anchor=(0.5, 0.0))
    return fig


def jurisdicoes_por_animal(tabela: pd.DataFrame, nomes: dict, ordem: list[str], titulo: str, subtitulo: str, teto: int = 5) -> Figure:
    """Barras empilhadas na horizontal: parte dos animais de cada espécie que usou 0, 1, 2, 3, 4 ou mais jurisdições nacionais."""
    tons = ["#e6e4dc", "#a9cbf3", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]
    with plt.rc_context(ESTILO):
        fig, ax = plt.subplots(figsize=(8.2, 4.2), dpi=160)
        fig.subplots_adjust(top=0.74, left=0.24, right=0.97, bottom=0.22)
        _titulos(fig, titulo, subtitulo)
        for k, especie in enumerate(ordem):
            linha = tabela[tabela["especie"] == especie].iloc[0]
            contagem = np.zeros(teto + 1)
            for n, vezes in linha["distribuicao"].items():
                contagem[min(int(n), teto)] += vezes
            partes = contagem / contagem.sum()
            esquerda = 0.0
            for n, parte in enumerate(partes):
                if parte > 0:
                    ax.barh(k, parte, left=esquerda, color=tons[n], height=0.6, edgecolor=SUPERFICIE, linewidth=1.5)
                    if parte >= 0.06:
                        ax.annotate(percentual(parte), (esquerda + parte / 2, k), ha="center", va="center", fontsize=8.5, color=TINTA if n < 3 else SUPERFICIE)
                esquerda += parte
        ax.set_yticks(range(len(ordem)))
        ax.set_yticklabels([nomes[e] for e in ordem])
        ax.invert_yaxis()
        _eixo_percentual(ax, "x")
        ax.grid(False)
        ax.set_xlabel("parte dos animais rastreados")
        rotulos = ["nenhuma", "1", "2", "3", "4", f"{teto} ou mais"]
        fig.legend(handles=[Patch(facecolor=t, label=r) for t, r in zip(tons, rotulos)], loc="lower center", ncols=6, fontsize=8.5, bbox_to_anchor=(0.55, 0.0), title="jurisdições nacionais usadas por pelo menos 24 h", title_fontsize=8.5)
    return fig
