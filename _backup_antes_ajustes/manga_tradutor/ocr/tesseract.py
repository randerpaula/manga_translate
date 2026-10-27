"""OCR com Tesseract, usado para português e inglês (e reserva do japonês).

O OCR roda em cada bloco de texto separado, com tudo que não é letra pintado
de branco (máscara do detector) e a imagem ampliada 3x. No teste com a página
de exemplo isso leu "SHINRA" e "COMEÇOU..." certo, onde a leitura do balão
inteiro errava.
"""
import os
import re
import shutil
import sys

import cv2
import numpy as np
import pytesseract


def _configurar_tesseract():
    """Acha o tesseract.exe: pasta 'tesseract' do programa, PATH ou instalação padrão."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    embutido = os.path.join(base, "tesseract", "tesseract.exe")
    if os.path.exists(embutido):
        pytesseract.pytesseract.tesseract_cmd = embutido
        os.environ.setdefault("TESSDATA_PREFIX", os.path.join(base, "tesseract", "tessdata"))
        return
    padrao = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if not shutil.which("tesseract") and os.path.exists(padrao):
        pytesseract.pytesseract.tesseract_cmd = padrao


_configurar_tesseract()


class LeitorTesseract:
    def __init__(self, idioma_tesseract="eng"):
        self.idioma = idioma_tesseract
        self.rotacao = 0      # giro (graus) do último texto lido: 0, 90 ou -90

    def ler(self, img_bgr, bbox, mascara_texto=None, vertical=False):
        """Devolve (texto, confiança média 0..100)."""
        recorte = preparar_recorte(img_bgr, bbox, mascara_texto)
        if vertical and self.idioma == "jpn":
            return _ler(recorte, "jpn_vert", 5)
        candidatos = [(0, recorte)]
        # Bloco alto e estreito em pt/en = texto girado 90° ("GAARA DA MOLE...").
        # rotacao = quanto o texto está girado (anti-horário) na página.
        if self.idioma != "jpn" and bbox[3] > bbox[2] * 2.5:
            candidatos = [(90, cv2.rotate(recorte, cv2.ROTATE_90_CLOCKWISE)),
                          (-90, cv2.rotate(recorte, cv2.ROTATE_90_COUNTERCLOCKWISE))]
        melhor = ("", 0.0, 0.0, 0)
        for rot, img in candidatos:
            img = endireitar(img)
            for psm in (6, 11):
                texto, conf = _ler(img, self.idioma, psm)
                pontos = conf * sum(c.isalnum() for c in texto)
                if pontos > melhor[2]:
                    melhor = (texto, conf, pontos, rot)
        self.rotacao = melhor[3]
        return melhor[0], melhor[1]


def preparar_recorte(img_bgr, bbox, mascara_texto=None, escala=3, margem=4):
    """Recorta o bloco, apaga o que não é letra, amplia e binariza."""
    alt, larg = img_bgr.shape[:2]
    x, y, w, h = bbox
    x0, y0 = max(x - margem, 0), max(y - margem, 0)
    x1, y1 = min(x + w + margem, larg), min(y + h + margem, alt)
    cinza = cv2.cvtColor(img_bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    if mascara_texto is not None:
        m = cv2.dilate(mascara_texto[y0:y1, x0:x1], np.ones((3, 3), np.uint8), iterations=2)
        # Letra branca em fundo preto: inverte antes de apagar o resto, senão
        # sobra só o contorno da letra.
        anel = cv2.subtract(cv2.dilate(m, np.ones((3, 3), np.uint8), iterations=3), m)
        if anel.any() and cinza[anel > 0].mean() < 100:
            cinza = 255 - cinza
        cinza = cinza.copy()
        cinza[m == 0] = 255
    cinza = cv2.resize(cinza, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)
    _, binaria = cv2.threshold(cinza, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Texto claro em fundo escuro (balão preto): inverte para letra preta.
    if (binaria == 0).mean() > 0.5:
        binaria = 255 - binaria
    return cv2.copyMakeBorder(binaria, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)


def endireitar(binaria, max_graus=35):
    """Corrige texto inclinado (letreiros tortos são comuns em mangá).

    Testa ângulos e fica com o que deixa as linhas mais "definidas": a
    projeção horizontal dos pixels pretos tem a maior variância.
    """
    tinta = (binaria < 128).astype(np.uint8)
    if tinta.sum() < 50:
        return binaria
    escala = min(1.0, 300 / max(tinta.shape))
    peq = cv2.resize(tinta, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    h, w = peq.shape
    centro = (w / 2, h / 2)

    def nitidez(graus):
        m = cv2.getRotationMatrix2D(centro, graus, 1.0)
        girada = cv2.warpAffine(peq.astype(np.float32), m, (w, h))
        return girada.sum(axis=1).var()

    angulos = range(-max_graus, max_graus + 1, 2)
    melhor = max(angulos, key=nitidez)
    if abs(melhor) < 2:
        return binaria
    H, W = binaria.shape
    m = cv2.getRotationMatrix2D((W / 2, H / 2), melhor, 1.0)
    cos, sen = abs(m[0, 0]), abs(m[0, 1])
    nW, nH = int(H * sen + W * cos), int(H * cos + W * sen)
    m[0, 2] += nW / 2 - W / 2
    m[1, 2] += nH / 2 - H / 2
    return cv2.warpAffine(binaria, m, (nW, nH), borderValue=255)


def _ler(recorte, idioma, psm):
    dados = pytesseract.image_to_data(recorte, lang=idioma, config=f"--psm {psm}",
                                      output_type=pytesseract.Output.DICT)
    palavras = []
    for i, palavra in enumerate(dados["text"]):
        palavra = palavra.strip()
        conf = float(dados["conf"][i])
        if palavra and conf >= 30:
            palavras.append((dados["top"][i], dados["left"][i], dados["height"][i], palavra, conf))
    if not palavras:
        return "", 0.0
    if idioma.startswith("jpn"):
        texto = "".join(p[3] for p in palavras)
        return texto, sum(p[4] for p in palavras) / len(palavras)

    # Agrupa as palavras em linhas pela posição vertical.
    palavras.sort()
    altura = np.median([p[2] for p in palavras])
    linhas, atual, topo = [], [], None
    for top, left, _, palavra, _ in palavras:
        if topo is not None and top - topo > altura * 0.6:
            linhas.append(atual)
            atual = []
        if not atual:
            topo = top
        atual.append((left, palavra))
    linhas.append(atual)
    texto = juntar_linhas([" ".join(p for _, p in sorted(l)) for l in linhas])
    return texto, sum(p[4] for p in palavras) / len(palavras)


def juntar_linhas(linhas):
    """Junta as linhas do balão, desfazendo hifenização ("ACON-" + "TECENDO")."""
    texto = ""
    for linha in linhas:
        if texto.endswith("-"):
            texto = texto[:-1] + linha
        elif texto:
            texto += " " + linha
        else:
            texto = linha
    return re.sub(r"\s+", " ", texto).strip()
