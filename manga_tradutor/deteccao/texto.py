"""Etapa 4: encontra o texto da página com o comic-text-detector.

O modelo (ONNX) devolve caixas de blocos de texto e uma máscara com os
pixels de letra. A máscara serve depois para a limpeza: só o que é letra é
apagado. Roda com cv2.dnn, que no teste foi ~9x mais rápido que o
onnxruntime para este modelo.
"""
import cv2
import numpy as np

TAMANHO = 1024


class DetectorTexto:
    def __init__(self, caminho_modelo, conf_minima=0.4, limiar_mascara=0.3):
        self.rede = cv2.dnn.readNetFromONNX(caminho_modelo)
        self.conf_minima = conf_minima
        self.limiar_mascara = limiar_mascara

    def detectar(self, img_bgr):
        """Devolve (blocos [(x, y, w, h, confiança)], máscara de texto da página)."""
        alt, larg = img_bgr.shape[:2]
        escala = TAMANHO / max(alt, larg)
        nl, na = int(round(larg * escala)), int(round(alt * escala))
        tela = np.zeros((TAMANHO, TAMANHO, 3), np.uint8)
        tela[:na, :nl] = cv2.resize(img_bgr, (nl, na), interpolation=cv2.INTER_AREA)
        self.rede.setInput(cv2.dnn.blobFromImage(tela, 1 / 255.0, (TAMANHO, TAMANHO), swapRB=True))
        blk, seg, _ = self.rede.forward(["blk", "seg", "det"])

        cand = blk[0]
        cand = cand[cand[:, 4] > self.conf_minima]
        caixas = [[float(c[0] - c[2] / 2), float(c[1] - c[3] / 2), float(c[2]), float(c[3])]
                  for c in cand]
        manter = cv2.dnn.NMSBoxes(caixas, cand[:, 4].tolist(), self.conf_minima, 0.35) if caixas else []
        blocos = []
        for i in np.array(manter).flatten():
            x, y, w, h = (v / escala for v in caixas[i])
            x0, y0 = max(int(x), 0), max(int(y), 0)
            x1, y1 = min(int(np.ceil(x + w)), larg), min(int(np.ceil(y + h)), alt)
            if x1 - x0 > 3 and y1 - y0 > 3:
                blocos.append((x0, y0, x1 - x0, y1 - y0, float(cand[i, 4])))

        mascara = (seg[0, 0, :na, :nl] > self.limiar_mascara).astype(np.uint8) * 255
        mascara = cv2.resize(mascara, (larg, alt), interpolation=cv2.INTER_NEAREST)
        return blocos + _blocos_da_mascara(mascara, blocos), mascara


def _blocos_da_mascara(mascara, blocos, conf=0.3):
    """Linhas de texto que a máscara achou mas o detector não encaixotou.

    Pega notas pequenas soltas sobre o desenho ("SFX: SELO"). Lixo que entrar
    aqui é descartado depois pelo OCR (confiança baixa).
    """
    alt, larg = mascara.shape
    coberto = np.zeros_like(mascara)
    for x, y, w, h, _ in blocos:
        coberto[y:y + h, x:x + w] = 255
    resto = cv2.bitwise_and(mascara, cv2.bitwise_not(coberto))
    # Medidas em pixels pensadas para uma página de ~800 px de largura.
    k = max(larg / 800, 1.0)
    nucleo = cv2.getStructuringElement(cv2.MORPH_RECT, (int(15 * k), int(5 * k)))
    unido = cv2.morphologyEx(resto, cv2.MORPH_CLOSE, nucleo)
    n, _, stats, _ = cv2.connectedComponentsWithStats(unido)
    extras = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        # Linha de texto: mais larga que alta, nem minúscula nem enorme.
        if w < 24 * k or h < 7 * k or h > alt * 0.08 or w < h * 2 or area < w * h * 0.25:
            continue
        extras.append((int(x), int(y), int(w), int(h), conf))
    return extras


def detectar_sem_modelo(img_bgr, regioes):
    """Reserva quando o modelo não está disponível: texto = buracos dos balões."""
    alt, larg = img_bgr.shape[:2]
    mascara = np.zeros((alt, larg), np.uint8)
    blocos = []
    for r in regioes:
        x, y, w, h = r["bbox"]
        # Afasta da borda para o contorno do balão não virar "letra".
        dentro = cv2.erode(r["mascara"], np.ones((3, 3), np.uint8), iterations=3)
        letras = cv2.bitwise_and(r["buracos"], dentro)
        if not letras.any():
            continue
        mascara[y:y + h, x:x + w] |= letras
        bx, by, bw, bh = cv2.boundingRect(letras)
        blocos.append((x + bx, y + by, bw, bh, 0.5))
    return blocos, mascara
