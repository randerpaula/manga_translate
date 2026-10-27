"""Inpainting com LaMa treinado em mangá/anime (IOPaint), via PyTorch.

Reconstrói o desenho que estava atrás do texto (retícula, cabelo, cenário).
Roda só no recorte em volta de cada texto, não na página inteira.
"""
import cv2
import numpy as np


class Lama:
    def __init__(self, caminho_modelo):
        import torch                      # importação pesada
        self.torch = torch
        self.modelo = torch.jit.load(caminho_modelo, map_location="cpu")
        self.modelo.eval()

    def pintar(self, img_bgr, mascara, lado_max=1024):
        """img_bgr e mascara do mesmo tamanho; devolve a imagem pintada."""
        alt, larg = img_bgr.shape[:2]
        escala = min(1.0, lado_max / max(alt, larg))
        img, m = img_bgr, mascara
        if escala < 1:
            tam = (int(larg * escala), int(alt * escala))
            img = cv2.resize(img, tam, interpolation=cv2.INTER_AREA)
            m = cv2.resize(m, tam, interpolation=cv2.INTER_NEAREST)
        h, w = img.shape[:2]
        H, W = (h + 7) // 8 * 8, (w + 7) // 8 * 8   # o modelo pede múltiplos de 8
        img = np.pad(img, ((0, H - h), (0, W - w), (0, 0)), mode="symmetric")
        m = np.pad(m, ((0, H - h), (0, W - w)))
        torch = self.torch
        x = torch.from_numpy(np.ascontiguousarray(img[:, :, ::-1])).permute(2, 0, 1)[None].float() / 255
        mk = torch.from_numpy((m > 0).astype(np.float32))[None, None]
        with torch.no_grad():
            saida = self.modelo(x, mk)[0].permute(1, 2, 0).numpy()
        saida = np.clip(saida * 255, 0, 255).astype(np.uint8)[:h, :w, ::-1]
        if escala < 1:
            saida = cv2.resize(saida, (larg, alt), interpolation=cv2.INTER_CUBIC)
        # Fora da máscara mantém o original, pixel a pixel.
        resultado = img_bgr.copy()
        resultado[mascara > 0] = saida[mascara > 0]
        return resultado
