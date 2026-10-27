"""Etapa 5: apaga o texto original.

Modo 'auto': se o fundo em volta das letras for liso (balão branco), pinta
com essa cor, que é instantâneo. Se houver desenho atrás, usa o LaMa; sem
LaMa, usa o inpaint do OpenCV.
"""
import cv2
import numpy as np

MODOS = ("auto", "branco", "opencv", "lama")
_K3 = np.ones((3, 3), np.uint8)


class Limpador:
    def __init__(self, modo="auto", lama=None):
        self.modo = modo
        self.lama = lama          # instância de limpeza.lama.Lama ou None

    def limpar(self, img_bgr, baloes, mascara_texto):
        """Devolve a página sem o texto dos balões detectados."""
        limpa = img_bgr.copy()
        alt, larg = img_bgr.shape[:2]
        for b in baloes:
            x, y, w, h = b.bbox
            p = 24
            x0, y0, x1, y1 = max(x - p, 0), max(y - p, 0), min(x + w + p, larg), min(y + h + p, alt)
            m = np.zeros((y1 - y0, x1 - x0), np.uint8)
            # Só as letras deste bloco (a máscara da página tem as de todos).
            m[y - y0:y - y0 + h, x - x0:x - x0 + w] = mascara_texto[y:y + h, x:x + w]
            m = cv2.dilate(m, _K3, iterations=3)   # pega a borda serrilhada das letras
            if not m.any():
                continue
            recorte = limpa[y0:y1, x0:x1]
            modo = self.modo
            if modo == "auto":
                cor = _cor_lisa(recorte, m)
                if cor is not None:
                    recorte[m > 0] = cor
                    if b.em_balao:
                        _limpar_balao(limpa, b, cor)
                    continue
                modo = "lama" if self.lama else "opencv"
            if modo == "branco":
                recorte[m > 0] = (255, 255, 255)
                if b.em_balao:
                    _limpar_balao(limpa, b, (255, 255, 255))
            elif modo == "lama" and self.lama:
                limpa[y0:y1, x0:x1] = self.lama.pintar(recorte, m)
            else:
                limpa[y0:y1, x0:x1] = cv2.inpaint(recorte, m, 3, cv2.INPAINT_TELEA)
        return limpa


def _cor_lisa(recorte, m, tolerancia=18):
    """Cor do fundo em volta das letras, se ele for liso; senão None."""
    anel = cv2.subtract(cv2.dilate(m, _K3, iterations=6), m)
    px = recorte[anel > 0]
    if len(px) < 20:
        return None
    cinza = px.mean(axis=1)
    if cinza.std() > tolerancia:
        return None
    return tuple(int(v) for v in np.median(px, axis=0))


def _limpar_balao(img, b, cor):
    """Balão de fundo liso: pinta o interior inteiro, como na versão anterior.

    Remove restos de letra que a máscara do detector não pegou.
    """
    if b.area is None:
        return
    ax, ay, aw, ah = b.area_bbox
    regiao = img[ay:ay + ah, ax:ax + aw]
    interior = cv2.erode(b.area[:regiao.shape[0], :regiao.shape[1]], _K3, iterations=1)
    # Só se o interior for quase todo da cor do fundo (não apaga desenho no balão).
    if (np.abs(regiao[interior > 0].astype(int) - cor).max(axis=1) < 60).mean() > 0.6:
        regiao[interior > 0] = cor
