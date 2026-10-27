"""Etapa 4: leitura do texto (OCR). Um leitor por idioma de origem."""
import re

from ..idiomas import IDIOMAS
from .tesseract import LeitorTesseract


def criar_leitor(idioma, avisar=print):
    """Japonês usa o manga-ocr; se não estiver instalado, cai no Tesseract."""
    if idioma == "ja":
        try:
            from .manga_ocr import LeitorMangaOcr
            return LeitorMangaOcr()
        except Exception as erro:
            avisar(f"manga-ocr indisponível ({erro}); usando Tesseract para japonês")
    return LeitorTesseract(IDIOMAS[idioma]["tesseract"])


_JAPONES = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def parece_texto(texto, confianca, conf_minima=55):
    """Filtra falsos positivos (rostos, roupas, onomatopeias desenhadas)."""
    if confianca < conf_minima:
        return False
    if _JAPONES.search(texto):
        return sum(bool(_JAPONES.match(c)) for c in texto) >= 1
    letras = sum(c.isalpha() for c in texto)
    if letras < 2:
        # Balões só com pontuação ("!", "?", "...") não precisam de tradução.
        return False
    # A maioria das "palavras" precisa ter 2+ letras; lixo de OCR vem picado.
    tokens = texto.split()
    boas = sum(sum(c.isalpha() for c in p) >= 2 for p in tokens)
    return boas >= 1 and boas / len(tokens) >= 0.5
