"""Orquestra as etapas. Usado pela linha de comando e pela interface.

    pipe = Pipeline(Config(origem="ja", destino="pt"), progresso=fn)
    projeto = pipe.carregar(["capitulo.pdf"])
    pipe.verificar_manga(projeto)      # não depende do idioma
    pipe.analisar(projeto)             # detecção + OCR + limpeza
    falhas = pipe.traduzir(projeto)
    pipe.renderizar(projeto)           # ou renderizar(projeto, [3]) após editar a pág. 3
    pipe.exportar(projeto, "saida", "pdf")

progresso(etapa, atual, total, mensagem), com etapa em
'carregar', 'verificar', 'analisar', 'traduzir', 'renderizar', 'exportar'.
"""
import os
import threading
from dataclasses import dataclass

from . import modelos, paginas
from .deteccao import (DetectorTexto, detectar_sem_modelo, eh_pagina_de_manga,
                       montar_baloes, ordenar_baloes, regioes_brancas)
from .idiomas import IDIOMAS as _IDIOMAS
from .idiomas import validar
from .limpeza import MODOS as MODOS_LIMPEZA
from .limpeza import Limpador
from .ocr import criar_leitor, parece_texto
from .projeto import Projeto
from .render import escrever_balao
from .traducao import MOTORES, MOTORES_COM_CHAVE, Tradutor

IDIOMAS = {codigo: info["nome"] for codigo, info in _IDIOMAS.items()}
FORMATOS = ("pdf", "cbz", "png")

__all__ = ["Pipeline", "Config", "Cancelado", "Projeto", "IDIOMAS", "MOTORES",
           "MOTORES_COM_CHAVE", "MODOS_LIMPEZA", "FORMATOS"]


class Cancelado(Exception):
    """A etapa em andamento foi interrompida por pipe.cancelar()."""


@dataclass
class Config:
    origem: str = None             # 'pt', 'en' ou 'ja'
    destino: str = None
    motor: str = "deepl"           # ver MOTORES
    chave_api: str = None          # DeepL ou Claude; senão usa DEEPL_API_KEY / ANTHROPIC_API_KEY
    rtl: bool = None               # None = automático (direita→esquerda se origem for japonês)
    fonte: str = None              # .ttf para o texto traduzido
    dpi: int = 200                 # resolução ao ler PDF
    limpeza: str = "auto"          # ver MODOS_LIMPEZA
    usar_detector: bool = True     # False = só o método antigo (balões brancos)
    baixar_modelos: bool = True    # baixa modelos que faltarem na primeira execução


class Pipeline:
    def __init__(self, config=None, progresso=None, avisar=None):
        self.config = config or Config()
        self._progresso = progresso
        self._avisar = avisar or (lambda msg: print(f"    aviso: {msg}"))
        self._cancelar = threading.Event()
        self._detector = self._lama = None
        self._leitores = {}

    # ---- controle ------------------------------------------------------
    def cancelar(self):
        self._cancelar.set()

    def _passo(self, etapa, atual, total, msg=""):
        if self._cancelar.is_set():
            self._cancelar.clear()
            raise Cancelado(etapa)
        if self._progresso:
            self._progresso(etapa, atual, total, msg)

    # ---- etapas --------------------------------------------------------
    def carregar(self, entradas):
        """Etapas 1 e 3: lê os arquivos e põe as páginas em ordem natural."""
        self._passo("carregar", 0, 1, "lendo arquivos")
        projeto = Projeto(paginas.carregar(entradas, self.config.dpi, self._avisar))
        self._passo("carregar", 1, 1, f"{len(projeto.paginas)} página(s)")
        return projeto

    def verificar_manga(self, projeto):
        """Etapa 2: marca cada página como mangá ou não."""
        total = len(projeto.paginas)
        for i, p in enumerate(projeto.paginas):
            self._passo("verificar", i, total, f"página {p.numero}")
            p.eh_manga, p.pontuacao, p.motivos = eh_pagina_de_manga(p.original, p.texto_selecionavel)
        self._passo("verificar", total, total, "")
        return projeto

    def analisar(self, projeto):
        """Etapa 4 e limpeza: acha o texto, lê (OCR) e apaga o original."""
        cfg = self.config
        validar(cfg.origem)
        projeto.origem = cfg.origem
        if any(p.eh_manga is None for p in projeto.paginas):
            self.verificar_manga(projeto)
        detector = self._obter_detector()
        leitor = self._obter_leitor(cfg.origem)
        limpador = Limpador(cfg.limpeza, self._obter_lama())
        rtl = cfg.rtl if cfg.rtl is not None else cfg.origem == "ja"
        total = len(projeto.paginas)
        for i, p in enumerate(projeto.paginas):
            self._passo("analisar", i, total, f"página {p.numero}")
            if not p.eh_manga:
                p.baloes, p.limpa = [], p.original.copy()
                continue
            regioes = regioes_brancas(p.original, exigir_texto=False)
            if detector:
                blocos, mascara = detector.detectar(p.original)
            else:
                blocos, mascara = detectar_sem_modelo(p.original, regioes_brancas(p.original))
            baloes = []
            for b in montar_baloes(p.original, blocos, regioes):
                x, y, w, h = b.bbox
                b.vertical = cfg.origem == "ja" and h > w * 1.2
                b.texto, b.confianca = leitor.ler(p.original, b.bbox, mascara, b.vertical)
                b.rotacao = getattr(leitor, "rotacao", 0)
                if parece_texto(b.texto, b.confianca) and not _parece_onomatopeia(b, p.original):
                    baloes.append(b)
            p.baloes = ordenar_baloes(baloes, rtl)
            p.limpa = limpador.limpar(p.original, p.baloes, mascara)
            p.traduzida = None
        self._passo("analisar", total, total, "")
        return projeto

    def traduzir(self, projeto, sobrescrever=False):
        """Traduz página por página. Devolve quantos balões ficaram sem tradução."""
        cfg = self.config
        validar(cfg.origem)
        validar(cfg.destino)
        projeto.destino = cfg.destino
        tradutor = Tradutor(cfg.origem, cfg.destino, cfg.motor, cfg.chave_api, self._avisar)
        falhas = 0
        total = len(projeto.paginas)
        for i, p in enumerate(projeto.paginas):
            self._passo("traduzir", i, total, f"página {p.numero}")
            alvo = [b for b in p.baloes if sobrescrever or not b.traducao]
            if not alvo:
                continue
            traducoes, f = tradutor.traduzir_pagina([b.texto for b in alvo])
            for b, t in zip(alvo, traducoes):
                b.traducao = t
            falhas += f
        self._passo("traduzir", total, total, "")
        return falhas

    def renderizar(self, projeto, paginas=None):
        """Escreve as traduções sobre a imagem limpa. paginas = lista de números."""
        alvo = [p for p in projeto.paginas if paginas is None or p.numero in paginas]
        destino = projeto.destino or self.config.destino or "pt"
        for i, p in enumerate(alvo):
            self._passo("renderizar", i, len(alvo), f"página {p.numero}")
            img = (p.limpa if p.limpa is not None else p.original).copy()
            for b in p.baloes:
                escrever_balao(img, b, self.config.fonte, destino)
            p.traduzida = img
        self._passo("renderizar", len(alvo), len(alvo), "")
        return projeto

    def exportar(self, projeto, pasta, formato="pdf", nome=None):
        """Grava o resultado e o textos.json. Devolve [arquivo principal, ...]."""
        if formato not in FORMATOS:
            raise ValueError(f"formato deve ser um de {FORMATOS}")
        self._passo("exportar", 0, 1, "gravando")
        if nome is None:
            base = os.path.splitext(os.path.basename(projeto.paginas[0].origem.split("#")[0]))[0]
            nome = f"{base}_{projeto.destino or 'traduzido'}"
        arquivos = paginas.exportar(projeto.paginas, pasta, nome, formato)
        projeto.salvar_textos(os.path.join(pasta, "textos.json"))
        self._passo("exportar", 1, 1, arquivos[0])
        return arquivos

    # ---- modelos (carregados uma vez só) -------------------------------
    def _obter_detector(self):
        if not self.config.usar_detector:
            return None
        if self._detector is None:
            caminho = modelos.caminho("detector", self.config.baixar_modelos,
                                      self._progresso_download("detector"))
            if caminho:
                self._detector = DetectorTexto(caminho)
            else:
                self._avisar("detector de texto indisponível; usando só balões brancos")
                self._detector = False
        return self._detector or None

    def _obter_lama(self):
        if self.config.limpeza not in ("auto", "lama"):
            return None
        if self._lama is None:
            self._lama = False
            try:
                import torch  # noqa: F401  (só para saber se está instalado)
                caminho = modelos.caminho("lama", self.config.baixar_modelos,
                                          self._progresso_download("lama"))
                if caminho:
                    from .limpeza.lama import Lama
                    self._lama = Lama(caminho)
            except ImportError:
                self._avisar("PyTorch não instalado: texto sobre desenho será apagado com OpenCV")
            except Exception as erro:
                self._avisar(f"LaMa indisponível ({erro}); usando OpenCV")
        return self._lama or None

    def _obter_leitor(self, idioma):
        if idioma not in self._leitores:
            self._leitores[idioma] = criar_leitor(idioma, self._avisar)
        return self._leitores[idioma]

    def _progresso_download(self, nome):
        def fn(lido, total):
            mb = lido / 1e6
            msg = f"baixando modelo {nome}: {mb:.0f} MB" + (f" de {total / 1e6:.0f} MB" if total else "")
            if self._progresso:
                self._progresso("modelos", lido, total or 0, msg)
        return fn


def _parece_onomatopeia(balao, img):
    """Onomatopeias ficam no original: texto fora de balão com letras enormes."""
    if balao.em_balao:
        return False
    return balao.bbox[3] > img.shape[0] * 0.12 and balao.bbox[2] > img.shape[1] * 0.12
