"""Etapa 5: escreve a tradução no lugar do texto original."""
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONTES_CANDIDATAS = [
    r"C:\Windows\Fonts\comicbd.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
# Fontes com os caracteres japoneses (as de cima não têm).
FONTES_JAPONES = [
    r"C:\Windows\Fonts\YuGothB.ttc",
    r"C:\Windows\Fonts\meiryob.ttc",
    r"C:\Windows\Fonts\msgothic.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
]


def achar_fonte(caminho=None, idioma="pt"):
    if caminho:
        return caminho
    lista = FONTES_JAPONES if idioma == "ja" else FONTES_CANDIDATAS
    pasta_fontes = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fontes")
    if os.path.isdir(pasta_fontes):   # fonte própria do programa, se houver
        lista = sorted(os.path.join(pasta_fontes, f) for f in os.listdir(pasta_fontes)
                       if f.lower().endswith((".ttf", ".otf", ".ttc"))) + lista
    for f in lista:
        if os.path.exists(f):
            return f
    return None  # cai na fonte padrão do Pillow


def escrever_balao(img_bgr, balao, fonte=None, idioma="pt", tamanho_max=40, tamanho_min=8):
    """Escreve balao.traducao dentro da área do balão (altera img_bgr)."""
    texto = (balao.traducao or "").strip()
    if not texto or balao.area is None:
        return img_bgr
    ax, ay, aw, ah = balao.area_bbox
    interior = np.zeros(img_bgr.shape[:2], np.uint8)
    regiao = interior[ay:ay + ah, ax:ax + aw]
    regiao[:] = balao.area[:regiao.shape[0], :regiao.shape[1]]
    # Texto solto sobre o desenho ganha contorno branco para continuar legível.
    contorno = 0 if balao.em_balao else 2
    args = (texto, achar_fonte(fonte, idioma), tamanho_max, tamanho_min, contorno, idioma == "ja")
    if balao.rotacao in (90, -90):
        # Escreve na horizontal sobre o recorte "desgirado" e gira de volta.
        ida, volta = ((cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE)
                      if balao.rotacao == 90 else
                      (cv2.ROTATE_90_COUNTERCLOCKWISE, cv2.ROTATE_90_CLOCKWISE))
        recorte = img_bgr[ay:ay + ah, ax:ax + aw]
        mascara = regiao.copy()
        girado = np.ascontiguousarray(cv2.rotate(recorte, ida))
        escrever_texto(girado, cv2.rotate(mascara, ida), *args)
        recorte[:] = cv2.rotate(girado, volta)
        return img_bgr
    return escrever_texto(img_bgr, interior, *args)


def escrever_texto(img_bgr, interior, texto, caminho_fonte=None, tamanho_max=40,
                   tamanho_min=8, contorno=0, separar_letras=False):
    """Escreve o texto centralizado na máscara, com a maior fonte que couber.

    A largura disponível é medida linha a linha na máscara, então o texto
    acompanha o formato oval do balão em vez de usar só o retângulo.
    """
    ys, xs = np.nonzero(interior)
    if not len(ys) or not texto.strip():
        return img_bgr
    topo, base = ys.min(), ys.max()
    cx = int(xs.mean())
    # Japonês não tem espaço entre palavras: quebra entre letras.
    palavras = list(texto.replace(" ", "")) if separar_letras else texto.split()
    sep = "" if separar_letras else " "

    for tamanho in range(tamanho_max, tamanho_min - 1, -1):
        f = _fonte(caminho_fonte, tamanho)
        layout = _quebrar(palavras, sep, f, interior, topo, base, cx, tamanho)
        if layout:
            break
    else:
        f = _fonte(caminho_fonte, tamanho_min)
        layout = _quebrar(palavras, sep, f, interior, topo, base, cx, tamanho_min, forcar=True)

    pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    desenho = ImageDraw.Draw(pil)
    for linha, y in layout:
        largura = desenho.textlength(linha, font=f)
        desenho.text((cx - largura / 2, y), linha, font=f, fill=(0, 0, 0),
                     stroke_width=contorno, stroke_fill=(255, 255, 255))
    img_bgr[:] = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    return img_bgr


def _fonte(caminho, tamanho):
    if caminho:
        return ImageFont.truetype(caminho, tamanho)
    return ImageFont.load_default(size=tamanho)


def _largura_livre(interior, y0, y1, cx, margem=0.85):
    """Largura simétrica em torno de cx que cabe na máscara entre y0 e y1."""
    faixa = interior[max(y0, 0):y1]
    if not faixa.size:
        return 0
    linha = faixa.min(axis=0) > 0   # coluna livre em todas as linhas da faixa
    if not linha[cx]:
        return 0
    esq = cx
    while esq > 0 and linha[esq - 1]:
        esq -= 1
    dir_ = cx
    while dir_ < len(linha) - 1 and linha[dir_ + 1]:
        dir_ += 1
    return 2 * min(cx - esq, dir_ - cx) * margem


def _quebrar(palavras, sep, fonte, interior, topo, base, cx, tamanho, forcar=False):
    """Tenta distribuir as palavras em linhas que caibam no balão.

    Devolve [(linha, y), ...] ou None se não couber com esse tamanho.
    """
    alt_linha = int(tamanho * 1.15)
    # Testa várias alturas de bloco (número de linhas) e centraliza na vertical.
    for n_linhas in range(1, len(palavras) + 1):
        altura_total = n_linhas * alt_linha
        y = (topo + base) // 2 - altura_total // 2
        if y < topo and not forcar:
            return None
        layout, resto = [], list(palavras)
        for _ in range(n_linhas):
            livre = _largura_livre(interior, y, y + alt_linha, cx)
            linha = []
            while resto and fonte.getlength(sep.join(linha + [resto[0]])) <= livre:
                linha.append(resto.pop(0))
            if not linha and resto and forcar:
                linha.append(resto.pop(0))
            layout.append((sep.join(linha), y))
            y += alt_linha
        if not resto:
            return [(l, yy) for l, yy in layout if l]
    return None
