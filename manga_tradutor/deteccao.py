"""Etapas 2 e 4: decide se a página é de mangá e encontra os balões de fala.

A detecção de balões usa só OpenCV: um balão é uma região branca fechada
(cercada pelo contorno preto) que tem letras escuras dentro. Cada candidato
depois é confirmado pelo OCR (ver ocr.py), o que descarta rostos, roupas e
outras áreas brancas que não têm texto.
"""
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class Balao:
    id: int
    bbox: tuple                 # (x, y, largura, altura) na página
    mascara: np.ndarray = field(repr=False)  # máscara do balão inteiro (uint8 0/255)
    texto: str = ""
    traducao: str = ""
    confianca: float = 0.0


def eh_pagina_de_manga(img_bgr, texto_selecionavel=""):
    """Heurística simples. Devolve (é_manga, pontuação 0..1, motivos)."""
    motivos = []
    pontos = 0.0

    # 1) Página com muito texto selecionável é documento, não mangá.
    if len(texto_selecionavel.strip()) > 150:
        motivos.append("página tem muito texto selecionável (parece documento)")
        return False, 0.0, motivos
    pontos += 0.25
    motivos.append("pouco ou nenhum texto selecionável")

    # 2) Mangá costuma ser preto e branco (saturação baixa).
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    saturacao = float(hsv[..., 1].mean()) / 255
    if saturacao < 0.15:
        pontos += 0.25
        motivos.append(f"imagem quase sem cor (saturação {saturacao:.2f})")

    # 3) Muitos traços (desenho), não uma foto lisa ou página em branco.
    cinza = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    bordas = cv2.Canny(cinza, 80, 200)
    densidade = float((bordas > 0).mean())
    if 0.02 < densidade < 0.35:
        pontos += 0.2
        motivos.append(f"densidade de traços típica de desenho ({densidade:.2f})")

    # 4) Tem regiões brancas fechadas com texto (candidatas a balão).
    n = len(candidatos_a_balao(img_bgr))
    if n:
        pontos += 0.3
        motivos.append(f"{n} região(ões) parecida(s) com balão")

    # Precisa de pelo menos 0.7: sem balões, uma página em P&B não basta.
    return pontos >= 0.7, round(pontos, 2), motivos


def candidatos_a_balao(img_bgr, limiar_branco=200):
    """Encontra regiões brancas fechadas que contêm traços escuros (letras)."""
    cinza = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    alt, larg = cinza.shape
    area_pagina = alt * larg

    branco = (cinza > limiar_branco).astype(np.uint8) * 255
    n, rotulos, stats, _ = cv2.connectedComponentsWithStats(branco, connectivity=4)

    candidatos = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < area_pagina * 0.002 or area > area_pagina * 0.3:
            continue
        if w < 20 or h < 15:
            continue
        # Encosta na borda da imagem em 3+ lados -> é fundo, não balão.
        lados = (x <= 1) + (y <= 1) + (x + w >= larg - 1) + (y + h >= alt - 1)
        if lados >= 3:
            continue

        comp = (rotulos[y:y + h, x:x + w] == i).astype(np.uint8) * 255
        contornos, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cheio = np.zeros_like(comp)
        cv2.drawContours(cheio, contornos, -1, 255, cv2.FILLED)
        area_cheia = int((cheio > 0).sum())
        if area_cheia == 0:
            continue

        # Pixels escuros dentro do balão = letras (os "buracos" do componente).
        buracos = cv2.subtract(cheio, comp)
        frac_escuro = (buracos > 0).sum() / area_cheia
        frac_branco = area / area_cheia
        if not (0.01 < frac_escuro < 0.45) or frac_branco < 0.55:
            continue

        # Balões são "gordos": área preenchida ocupa boa parte do retângulo.
        if area_cheia / (w * h) < 0.45:
            continue

        mascara = np.zeros((alt, larg), np.uint8)
        mascara[y:y + h, x:x + w] = cheio
        candidatos.append({"bbox": (int(x), int(y), int(w), int(h)),
                           "mascara": mascara,
                           "texto_mascara": _mascara_global(buracos, x, y, alt, larg)})
    return candidatos


def _mascara_global(local, x, y, alt, larg):
    m = np.zeros((alt, larg), np.uint8)
    m[y:y + local.shape[0], x:x + local.shape[1]] = local
    return m


def ordenar_baloes(baloes, direita_para_esquerda=False):
    """Ordem de leitura: de cima para baixo, e na mesma faixa por x."""
    if not baloes:
        return baloes
    altura_media = np.mean([b.bbox[3] for b in baloes])

    def chave(b):
        x, y, w, h = b.bbox
        faixa = int((y + h / 2) // (altura_media * 0.8))
        cx = x + w / 2
        return (faixa, -cx if direita_para_esquerda else cx)

    baloes = sorted(baloes, key=chave)
    for i, b in enumerate(baloes, 1):
        b.id = i
    return baloes
