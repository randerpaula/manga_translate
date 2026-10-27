"""Etapa 4: lê o texto de cada balão com Tesseract.

O OCR roda em cada balão separado (e não na página inteira), com a área fora
do balão pintada de branco e a imagem ampliada 3x, o que melhora muito a
leitura das letras pequenas de mangá.
"""
import os
import re
import shutil

import cv2
import numpy as np
import pytesseract

# Caminho padrão no Windows, usado só se o tesseract não estiver no PATH.
_TESSERACT_WINDOWS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if not shutil.which("tesseract") and os.path.exists(_TESSERACT_WINDOWS):
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_WINDOWS


def preparar_recorte(img_bgr, mascara, bbox, escala=3):
    """Tratamento da imagem: recorta o balão, limpa o fundo, amplia e binariza."""
    x, y, w, h = bbox
    cinza = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)[y:y + h, x:x + w].copy()
    m = mascara[y:y + h, x:x + w]
    # Afasta um pouco da borda para o contorno do balão não virar "letra".
    m = cv2.erode(m, np.ones((3, 3), np.uint8), iterations=2)
    cinza[m == 0] = 255
    cinza = cv2.resize(cinza, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)
    _, binaria = cv2.threshold(cinza, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.copyMakeBorder(binaria, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)


def ler_balao(img_bgr, mascara, bbox, idioma="eng"):
    """Devolve (texto, confiança média 0..100).

    Testa dois modos do Tesseract (bloco único e texto esparso) e fica com o
    que leu mais letras com mais confiança.
    """
    recorte = preparar_recorte(img_bgr, mascara, bbox)
    melhor = ("", 0.0, 0.0)
    for psm in (6, 11):
        texto, conf = _ler(recorte, idioma, psm)
        pontos = conf * sum(c.isalpha() for c in texto)
        if pontos > melhor[2]:
            melhor = (texto, conf, pontos)
    return melhor[0], melhor[1]


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


def parece_texto(texto, confianca, conf_minima=55):
    """Filtra falsos positivos (rostos, roupas) que o OCR lê como lixo."""
    letras = sum(c.isalpha() for c in texto)
    if letras < 2 or confianca < conf_minima:
        return False
    # A maioria das "palavras" precisa ter 2+ letras; lixo de OCR vem picado.
    tokens = texto.split()
    boas = sum(sum(c.isalpha() for c in p) >= 2 for p in tokens)
    return boas >= 1 and boas / len(tokens) >= 0.5
