"""Grade global de jurisdição: a que águas pertence cada célula de 0,1 grau do oceano.

A grade é montada uma vez a partir dos polígonos das Zonas Econômicas Exclusivas (Marine Regions,
v12), do polígono de alto-mar da mesma fonte e da máscara de terra do Natural Earth. Depois disso,
classificar uma posição é só consultar a célula: não há ponto em polígono durante a análise.

Códigos: 0 = alto-mar; 1 em diante = linha da tabela de jurisdições (uma por polígono da fonte).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

ALTO_MAR = 0
INDEFINIDO = 65535
RESOLUCAO = 0.1
LIMITE_DO_TRATADO_DA_ANTARTIDA = -60.0


@dataclass
class Grade:
    """Códigos de jurisdição e máscara de terra numa grade regular de latitude e longitude."""

    codigos: np.ndarray  # [n_lat, n_lon], uint16; linha 0 = latitude mais ao sul
    terra: np.ndarray  # [n_lat, n_lon], bool
    resolucao: float = RESOLUCAO

    def indices(self, lat, lon) -> tuple[np.ndarray, np.ndarray]:
        n_lat, n_lon = self.codigos.shape
        i = np.clip(np.floor((np.asarray(lat, dtype=float) + 90.0) / self.resolucao).astype(int), 0, n_lat - 1)
        j = np.mod(np.floor((np.asarray(lon, dtype=float) + 180.0) / self.resolucao).astype(int), n_lon)
        return i, j

    def classificar(self, lat, lon) -> np.ndarray:
        """Código de jurisdição de cada posição."""
        i, j = self.indices(lat, lon)
        return self.codigos[i, j]

    def em_terra(self, lat, lon) -> np.ndarray:
        i, j = self.indices(lat, lon)
        return self.terra[i, j]


def centros(resolucao: float = RESOLUCAO) -> tuple[np.ndarray, np.ndarray]:
    """Latitudes e longitudes dos centros das células."""
    lat = -90.0 + (np.arange(round(180 / resolucao)) + 0.5) * resolucao
    lon = -180.0 + (np.arange(round(360 / resolucao)) + 0.5) * resolucao
    return lat, lon


def rasterizar(poligonos: list, valores: list[int], resolucao: float = RESOLUCAO, fundo: int = INDEFINIDO) -> np.ndarray:
    """Pinta cada polígono (shapely) na grade com o seu valor: a célula recebe o valor se o centro cai dentro.

    Polígonos posteriores na lista sobrescrevem os anteriores. Só as células da caixa envolvente de
    cada polígono são testadas.
    """
    import shapely

    lat, lon = centros(resolucao)
    grade = np.full((len(lat), len(lon)), fundo, dtype=np.uint16)
    for poligono, valor in zip(poligonos, valores):
        oeste, sul, leste, norte = poligono.bounds
        i0, i1 = np.searchsorted(lat, sul), np.searchsorted(lat, norte)
        j0, j1 = np.searchsorted(lon, oeste), np.searchsorted(lon, leste)
        if i1 <= i0 or j1 <= j0:
            continue
        shapely.prepare(poligono)
        x, y = np.meshgrid(lon[j0:j1], lat[i0:i1])
        dentro = shapely.contains_xy(poligono, x, y)
        grade[i0:i1, j0:j1][dentro] = valor
    return grade


def preencher_pelo_vizinho(grade: np.ndarray, vazio: np.ndarray, doadores: np.ndarray) -> np.ndarray:
    """Dá a cada célula de `vazio` o valor da célula de `doadores` mais próxima (em células da grade).

    Serve para as águas interiores e arquipelágicas e para a terra: não estão nos polígonos de ZEE nem
    no de alto-mar, e pertencem ao país cujas águas estão ao lado.
    """
    if not doadores.any():
        return grade.copy()
    _, (i, j) = ndimage.distance_transform_edt(~doadores, return_indices=True)
    resultado = grade.copy()
    resultado[vazio] = grade[i[vazio], j[vazio]]
    return resultado


def montar_grade(zee: list, codigos_zee: list[int], alto_mar: list, terra: list, resolucao: float = RESOLUCAO) -> Grade:
    """Junta as três camadas numa `Grade`.

    Ordem: o alto-mar entra primeiro, as ZEE por cima (a camada de ZEE é a mais recente das duas); o
    que não está em nenhuma (terra, águas interiores e arquipelágicas, e as pequenas diferenças entre
    as versões das duas camadas) recebe a jurisdição da célula de ZEE mais próxima.
    """
    grade = rasterizar(alto_mar, [ALTO_MAR] * len(alto_mar), resolucao)
    pintura = rasterizar(zee, codigos_zee, resolucao)
    grade[pintura != INDEFINIDO] = pintura[pintura != INDEFINIDO]
    mascara_terra = rasterizar(terra, [1] * len(terra), resolucao, fundo=0).astype(bool)
    vazio = grade == INDEFINIDO
    # Ao sul de 60°S vale o Tratado da Antártida: nenhuma ZEE é reconhecida ali. O continente e as
    # plataformas de gelo (onde focas descansam) contam como fora de qualquer jurisdição nacional.
    lat, _ = centros(resolucao)
    grade[vazio & (lat < LIMITE_DO_TRATADO_DA_ANTARTIDA)[:, None]] = ALTO_MAR
    grade = preencher_pelo_vizinho(grade, grade == INDEFINIDO, (grade != INDEFINIDO) & (grade != ALTO_MAR))
    return Grade(codigos=grade, terra=mascara_terra & vazio, resolucao=resolucao)


def salvar(grade: Grade, caminho) -> None:
    np.savez_compressed(caminho, codigos=grade.codigos, terra=np.packbits(grade.terra), resolucao=grade.resolucao)


def carregar(caminho) -> Grade:
    with np.load(caminho) as arquivo:
        codigos = arquivo["codigos"]
        terra = np.unpackbits(arquivo["terra"])[: codigos.size].reshape(codigos.shape).astype(bool)
        return Grade(codigos=codigos, terra=terra, resolucao=float(arquivo["resolucao"]))
