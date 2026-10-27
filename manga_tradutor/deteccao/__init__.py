"""Etapas 2 e 4: é mangá? onde está o texto? qual é o balão de cada texto?"""
import cv2
import numpy as np

from ..projeto import Balao
from .eh_manga import eh_pagina_de_manga
from .regioes import contem, regioes_brancas
from .texto import DetectorTexto, detectar_sem_modelo

__all__ = ["eh_pagina_de_manga", "regioes_brancas", "DetectorTexto",
           "detectar_sem_modelo", "montar_baloes", "ordenar_baloes"]


def montar_baloes(img_bgr, blocos, regioes):
    """Junta os blocos de texto que caem no mesmo balão.

    Texto dentro de uma região branca fechada usa o formato do balão para
    escrever a tradução. Texto solto (narração sobre o desenho) usa a caixa do
    próprio texto, um pouco ampliada.
    """
    alt, larg = img_bgr.shape[:2]
    grupos = {}   # índice da região (ou -n para texto solto) -> blocos
    for n, (x, y, w, h, conf) in enumerate(blocos):
        cx, cy = x + w / 2, y + h / 2
        dono = next((i for i, r in enumerate(regioes) if contem(r, cx, cy)), None)
        grupos.setdefault(dono if dono is not None else -(n + 1), []).append((x, y, w, h, conf))

    baloes = []
    for chave, bs in grupos.items():
        x0 = min(b[0] for b in bs)
        y0 = min(b[1] for b in bs)
        x1 = max(b[0] + b[2] for b in bs)
        y1 = max(b[1] + b[3] for b in bs)
        bbox = (x0, y0, x1 - x0, y1 - y0)
        if chave >= 0:
            r = regioes[chave]
            area = cv2.erode(r["mascara"], np.ones((3, 3), np.uint8), iterations=3)
            baloes.append(Balao(0, bbox, r["bbox"], area, em_balao=True))
        else:
            mx, my = int((x1 - x0) * 0.1) + 2, int((y1 - y0) * 0.1) + 2
            ax0, ay0 = max(x0 - mx, 0), max(y0 - my, 0)
            ax1, ay1 = min(x1 + mx, larg), min(y1 + my, alt)
            area = np.full((ay1 - ay0, ax1 - ax0), 255, np.uint8)
            baloes.append(Balao(0, bbox, (ax0, ay0, ax1 - ax0, ay1 - ay0), area, em_balao=False))
    return baloes


def ordenar_baloes(baloes, direita_para_esquerda=False):
    """Ordem de leitura: faixas de cima para baixo; na faixa, por x.

    Usa o retângulo do balão (não só o do texto). Um balão entra na faixa
    atual se o seu centro vertical cai dentro dela, então balões lado a lado
    com alturas diferentes continuam na mesma faixa.
    """
    if not baloes:
        return baloes
    faixas = []   # [topo, base, [balões]]
    for b in sorted(baloes, key=lambda b: b.area_bbox[1]):
        x, y, w, h = b.area_bbox
        cy = y + h / 2
        if faixas and faixas[-1][0] <= cy <= faixas[-1][1]:
            faixas[-1][1] = max(faixas[-1][1], y + h)
            faixas[-1][2].append(b)
        else:
            faixas.append([y, y + h, [b]])
    ordem = []
    for _, _, grupo in faixas:
        grupo.sort(key=lambda b: b.area_bbox[0] + b.area_bbox[2] / 2,
                   reverse=direita_para_esquerda)
        ordem += grupo
    for i, b in enumerate(ordem, 1):
        b.id = i
    return ordem
