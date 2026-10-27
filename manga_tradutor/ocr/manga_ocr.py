"""OCR de japonês com o manga-ocr (lê texto vertical, furigana e letra estilizada).

Na primeira vez, o pacote baixa o modelo (~450 MB) do Hugging Face.
"""
import cv2
from PIL import Image


class LeitorMangaOcr:
    def __init__(self):
        from manga_ocr import MangaOcr   # importação pesada (PyTorch)
        self._mocr = MangaOcr()

    def ler(self, img_bgr, bbox, mascara_texto=None, vertical=False):
        alt, larg = img_bgr.shape[:2]
        x, y, w, h = bbox
        m = 4
        recorte = img_bgr[max(y - m, 0):min(y + h + m, alt), max(x - m, 0):min(x + w + m, larg)]
        texto = self._mocr(Image.fromarray(cv2.cvtColor(recorte, cv2.COLOR_BGR2RGB)))
        # O manga-ocr não dá confiança; texto vazio ou só pontuação conta como 0.
        conf = 90.0 if any(c.isalnum() for c in texto) else 0.0
        return texto.strip(), conf
