"""Regiões brancas fechadas (balões de fala) encontradas só com OpenCV.

Um balão é uma região branca cercada pelo contorno preto. Serve para duas
coisas: dar o formato do balão onde a tradução será escrita e, se o detector
de texto não estiver disponível, achar o texto (os "buracos" escuros dentro
da região branca).
"""
import cv2
import numpy as np


def regioes_brancas(img_bgr, limiar_branco=200, exigir_texto=True):
    """Devolve [{'bbox', 'mascara' (local, região cheia), 'buracos' (local)}]."""
    cinza = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    alt, larg = cinza.shape
    area_pagina = alt * larg

    branco = (cinza > limiar_branco).astype(np.uint8) * 255
    n, rotulos, stats, _ = cv2.connectedComponentsWithStats(branco, connectivity=4)

    regioes = []
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
        if frac_branco < 0.55 or frac_escuro >= 0.45:
            continue
        if exigir_texto and frac_escuro <= 0.01:
            continue
        # Balões são "gordos": área preenchida ocupa boa parte do retângulo.
        if area_cheia / (w * h) < 0.45:
            continue

        regioes.append({"bbox": (int(x), int(y), int(w), int(h)),
                        "mascara": cheio, "buracos": buracos})
    return regioes


def contem(regiao, px, py):
    x, y, w, h = regiao["bbox"]
    if not (x <= px < x + w and y <= py < y + h):
        return False
    return regiao["mascara"][int(py) - y, int(px) - x] > 0
