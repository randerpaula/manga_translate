"""Tradução dos textos dos balões.

Usa o deep-translator (Google Tradutor gratuito, até 5000 caracteres por
pedido), que substitui a biblioteca `translate` antiga e seu limite de 500
caracteres. Cada balão é traduzido separado, então o limite nunca é atingido.
"""
from deep_translator import GoogleTranslator

# Idiomas mais comuns: código do tradutor -> código do Tesseract (OCR).
IDIOMAS = {
    "pt": ("Português", "por"),
    "en": ("Inglês", "eng"),
    "es": ("Espanhol", "spa"),
    "fr": ("Francês", "fra"),
    "it": ("Italiano", "ita"),
    "de": ("Alemão", "deu"),
    "ja": ("Japonês", "jpn"),
    "ko": ("Coreano", "kor"),
    "zh-CN": ("Chinês", "chi_sim"),
}


class Tradutor:
    def __init__(self, destino, origem="auto", motor="google"):
        self.motor = motor
        if motor == "google":
            self._t = GoogleTranslator(source=origem, target=destino)

    def traduzir(self, texto):
        if not texto.strip():
            return texto
        if self.motor == "nenhum":       # modo de teste, sem internet
            return texto
        # Texto de mangá vem todo em maiúsculas; o tradutor entende melhor
        # em minúsculas, e no final voltamos para maiúsculas.
        maiusculo = texto.isupper()
        entrada = texto.capitalize() if maiusculo else texto
        saida = self._t.translate(entrada) or texto
        return saida.upper() if maiusculo else saida
