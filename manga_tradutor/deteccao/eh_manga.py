"""Etapa 2: decide se a página é de mangá. Não depende do idioma."""
import cv2

from .regioes import regioes_brancas


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
    n = len(regioes_brancas(img_bgr))
    if n:
        pontos += 0.3
        motivos.append(f"{n} região(ões) parecida(s) com balão")

    # Precisa de pelo menos 0.7: sem balões, uma página em P&B não basta.
    return pontos >= 0.7, round(pontos, 2), motivos
