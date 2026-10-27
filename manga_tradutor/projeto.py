"""Dados do projeto: páginas, balões e o arquivo textos.json.

O textos.json é o centro do programa: depois da leitura (OCR), tradução,
limpeza, escrita e revisão leem e gravam ali. Corrigir um balão não exige
rodar a detecção e o OCR de novo.
"""
import json
import os
from dataclasses import dataclass, field

import cv2
import numpy as np

VERSAO = 2


@dataclass
class Balao:
    id: int
    bbox: tuple                  # (x, y, largura, altura) do texto original
    area_bbox: tuple             # retângulo onde a tradução pode ser escrita
    area: np.ndarray = field(default=None, repr=False)  # máscara local (uint8) em area_bbox
    texto: str = ""
    traducao: str = ""
    confianca: float = 0.0
    vertical: bool = False       # texto vertical (japonês)
    em_balao: bool = True        # False = texto solto sobre o desenho (narração)
    rotacao: int = 0             # texto girado 90/-90 graus (ex.: na margem da página)

    def para_dict(self):
        return {"balao": self.id, "bbox": list(map(int, self.bbox)),
                "area_bbox": list(map(int, self.area_bbox)),
                "confianca_ocr": round(float(self.confianca), 1),
                "vertical": self.vertical, "em_balao": self.em_balao,
                "rotacao": self.rotacao,
                "texto": self.texto, "traducao": self.traducao}


@dataclass
class Pagina:
    numero: int
    origem: str                     # arquivo de onde veio
    original: np.ndarray = field(repr=False)
    texto_selecionavel: str = ""    # texto "digital" do PDF, se houver
    eh_manga: bool = None           # None = ainda não verificado
    pontuacao: float = 0.0
    motivos: list = field(default_factory=list)
    baloes: list = field(default_factory=list)
    limpa: np.ndarray = field(default=None, repr=False)      # texto original apagado
    traduzida: np.ndarray = field(default=None, repr=False)  # tradução escrita

    @property
    def imagem_final(self):
        """A melhor versão disponível para exportar."""
        for img in (self.traduzida, self.limpa, self.original):
            if img is not None:
                return img


@dataclass
class Projeto:
    paginas: list = field(default_factory=list)
    origem: str = ""
    destino: str = ""

    def balao(self, pagina, balao):
        for p in self.paginas:
            if p.numero == pagina:
                for b in p.baloes:
                    if b.id == balao:
                        return b

    # ---- textos.json -------------------------------------------------
    def para_dict(self):
        return {"versao": VERSAO, "origem": self.origem, "destino": self.destino,
                "paginas": [{"pagina": p.numero, "arquivo": p.origem,
                             "eh_manga": p.eh_manga, "pontuacao": p.pontuacao,
                             "motivos": p.motivos,
                             "baloes": [b.para_dict() for b in p.baloes]}
                            for p in self.paginas]}

    def salvar_textos(self, caminho):
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(self.para_dict(), f, ensure_ascii=False, indent=2)

    def aplicar_textos(self, caminho):
        """Usa os textos e traduções de um textos.json editado à mão.

        Um balão com "ignorar": true volta a ser o desenho original e sai do
        projeto (útil para leituras falsas do OCR). Aceita o formato novo e o antigo (lista de balões). Devolve quantos
        balões foram atualizados.
        """
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
        if isinstance(dados, list):   # formato da versão 1
            itens = dados
        else:
            itens = [dict(b, pagina=p["pagina"]) for p in dados["paginas"] for b in p["baloes"]]
        n = 0
        for item in itens:
            b = self.balao(item["pagina"], item["balao"])
            if not b:
                continue
            if item.get("ignorar"):
                # Leitura falsa (desenho, onomatopeia, crédito): devolve o
                # pedaço original da página e tira o balão da lista.
                self._descartar(item["pagina"], b)
            else:
                b.texto, b.traducao = item.get("texto", b.texto), item.get("traducao", b.traducao)
            n += 1
        return n

    def _descartar(self, numero, b, folga=24):
        p = next(p for p in self.paginas if p.numero == numero)
        p.baloes.remove(b)
        if p.limpa is None:
            return
        alt, larg = p.original.shape[:2]
        # A limpeza mexe no retângulo do texto (com folga) e no interior do balão.
        x, y, w, h = b.bbox
        x0, y0 = max(x - folga, 0), max(y - folga, 0)
        x1, y1 = min(x + w + folga, larg), min(y + h + folga, alt)
        p.limpa[y0:y1, x0:x1] = p.original[y0:y1, x0:x1]
        if b.area is not None:
            ax, ay, aw, ah = b.area_bbox
            m = b.area[:min(ah, alt - ay), :min(aw, larg - ax)] > 0
            p.limpa[ay:ay + m.shape[0], ax:ax + m.shape[1]][m] = \
                p.original[ay:ay + m.shape[0], ax:ax + m.shape[1]][m]

    # ---- projeto completo (para continuar depois) ----------------------
    def salvar(self, pasta):
        """Grava textos.json + imagens original, limpa e mapa das áreas."""
        os.makedirs(os.path.join(pasta, "paginas"), exist_ok=True)
        self.salvar_textos(os.path.join(pasta, "textos.json"))
        for p in self.paginas:
            base = os.path.join(pasta, "paginas", f"{p.numero:03d}")
            _gravar(base + "_original.png", p.original)
            if p.limpa is not None:
                _gravar(base + "_limpa.png", p.limpa)
            # Áreas de escrita num PNG de 16 bits: valor = id do balão.
            mapa = np.zeros(p.original.shape[:2], np.uint16)
            for b in p.baloes:
                x, y, w, h = b.area_bbox
                if b.area is not None:
                    recorte = mapa[y:y + h, x:x + w]
                    recorte[b.area[:recorte.shape[0], :recorte.shape[1]] > 0] = b.id
            _gravar(base + "_areas.png", mapa)
        return os.path.join(pasta, "textos.json")

    @classmethod
    def abrir(cls, pasta):
        with open(os.path.join(pasta, "textos.json"), encoding="utf-8") as f:
            dados = json.load(f)
        proj = cls(origem=dados.get("origem", ""), destino=dados.get("destino", ""))
        for pd in dados["paginas"]:
            base = os.path.join(pasta, "paginas", f"{pd['pagina']:03d}")
            pag = Pagina(pd["pagina"], pd.get("arquivo", ""), _ler(base + "_original.png"),
                         eh_manga=pd.get("eh_manga"), pontuacao=pd.get("pontuacao", 0.0),
                         motivos=pd.get("motivos", []))
            if os.path.exists(base + "_limpa.png"):
                pag.limpa = _ler(base + "_limpa.png")
            mapa = _ler(base + "_areas.png", cv2.IMREAD_UNCHANGED)
            for bd in pd["baloes"]:
                x, y, w, h = bd["area_bbox"]
                area = None
                if mapa is not None:
                    area = (mapa[y:y + h, x:x + w] == bd["balao"]).astype(np.uint8) * 255
                pag.baloes.append(Balao(bd["balao"], tuple(bd["bbox"]), (x, y, w, h), area,
                                        bd.get("texto", ""), bd.get("traducao", ""),
                                        bd.get("confianca_ocr", 0.0), bd.get("vertical", False),
                                        bd.get("em_balao", True), bd.get("rotacao", 0)))
            proj.paginas.append(pag)
        return proj


def _gravar(caminho, img):
    # imencode + tofile aceita caminhos com acento no Windows (imwrite não).
    cv2.imencode(".png", img)[1].tofile(caminho)


def _ler(caminho, modo=cv2.IMREAD_COLOR):
    if not os.path.exists(caminho):
        return None
    return cv2.imdecode(np.fromfile(caminho, np.uint8), modo)
