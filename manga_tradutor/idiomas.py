"""Idiomas suportados e os códigos que cada serviço usa para eles."""

IDIOMAS = {
    "pt": {"nome": "Português (Brasil)", "deepl_origem": "PT", "deepl_destino": "PT-BR",
           "google": "pt", "mymemory": "pt-BR", "tesseract": "por"},
    "en": {"nome": "Inglês (EUA)", "deepl_origem": "EN", "deepl_destino": "EN-US",
           "google": "en", "mymemory": "en-US", "tesseract": "eng"},
    "ja": {"nome": "Japonês", "deepl_origem": "JA", "deepl_destino": "JA",
           "google": "ja", "mymemory": "ja-JP", "tesseract": "jpn"},
}


def nome(codigo):
    return IDIOMAS[codigo]["nome"]


def validar(codigo):
    if codigo not in IDIOMAS:
        raise ValueError(f"Idioma '{codigo}' não suportado. Use: {', '.join(IDIOMAS)}")
    return codigo
