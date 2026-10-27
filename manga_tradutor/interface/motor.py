"""Ponte entre a interface e o núcleo do tradutor (manga_tradutor/pipeline.py).

A janela usa só o que este arquivo exporta. As listas *_TELA estão no formato
que os menus da tela usam.
"""
from ..pipeline import IDIOMAS, MOTORES, MOTORES_COM_CHAVE, Cancelado, Config, Pipeline  # noqa: F401
from ..projeto import Projeto  # noqa: F401

IDIOMAS_TELA = list(IDIOMAS.items())
# (código, nome, usa chave de API)
MOTORES_TELA = [(c, nome, c in MOTORES_COM_CHAVE) for c, nome in MOTORES.items()]
