"""Etapa 4: leitura do texto (OCR). Um leitor por idioma de origem."""
import re

from ..idiomas import IDIOMAS
from .correcao import proporcao_plausivel
from .tesseract import LeitorTesseract


def criar_leitor(idioma, avisar=print):
    """Japonês usa o manga-ocr; se não estiver instalado, cai no Tesseract."""
    if idioma == "ja":
        try:
            from .manga_ocr import LeitorMangaOcr
            return LeitorMangaOcr()
        except Exception as erro:
            avisar(f"manga-ocr indisponível ({erro}); usando Tesseract para japonês")
    return LeitorTesseract(IDIOMAS[idioma]["tesseract"], idioma)


_JAPONES = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def parece_texto(texto, confianca, conf_minima=55, em_balao=False, idioma=None):
    """Filtra falsos positivos (rostos, roupas, onomatopeias desenhadas).

    Dentro de um balão branco quase sempre há fala, então o filtro é mais
    brando: melhor manter uma leitura duvidosa (que aparece na revisão) do
    que perder o balão.
    """
    if em_balao:
        conf_minima = min(conf_minima, 40)
    if confianca < conf_minima:
        return False
    if _JAPONES.search(texto):
        return sum(bool(_JAPONES.match(c)) for c in texto) >= 1
    letras = sum(c.isalpha() for c in texto)
    if idioma == "en" and re.fullmatch(r"\W*[IA]\W*", texto) and confianca >= 70:
        return True       # "I..." é uma fala inteira
    if letras < 2:
        # Balões só com pontuação ("!", "?", "...") não precisam de tradução.
        return False
    # A maioria das "palavras" precisa ter 2+ letras; lixo de OCR vem picado.
    tokens = texto.split()
    boas = sum(sum(c.isalpha() for c in p) >= 2 for p in tokens)
    if not (boas >= 1 and boas / len(tokens) >= (0.34 if em_balao else 0.5)):
        return False
    # Com a lista de palavras do idioma: leitura de desenho vira "A wu UA K he",
    # com poucas palavras reais. Frases curtas (nomes, "HANAKO...") passam.
    prop = proporcao_plausivel(texto, idioma) if idioma else None
    if prop is not None and len(tokens) >= 3 and prop < 0.6:
        return False
    return True
