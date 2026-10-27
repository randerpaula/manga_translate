"""Arquivos de modelos de IA: onde ficam e como baixar na primeira execução."""
import hashlib
import os
import sys
import urllib.request

MODELOS = {
    # Detector de texto de mangá (comic-text-detector), roda com o OpenCV.
    "detector": {
        "arquivo": "comictextdetector.pt.onnx",
        "url": "https://github.com/zyddnys/manga-image-translator/releases/download/beta-0.3/comictextdetector.pt.onnx",
        "sha256": "1a86ace74961413cbd650002e7bb4dcec4980ffa21b2f19b86933372071d718f",
        "tamanho_mb": 95,
    },
    # LaMa treinado em mangá/anime (IOPaint), precisa do PyTorch.
    "lama": {
        "arquivo": "anime-manga-big-lama.pt",
        "url": "https://github.com/Sanster/models/releases/download/AnimeMangaInpainting/anime-manga-big-lama.pt",
        "sha256": "479d3afdcb7ed2fd944ed4ebcc39ca45b33491f0f2e43eb1000bd623cfb41823",
        "tamanho_mb": 206,
    },
}


def pasta_modelos():
    """Pasta 'modelos' ao lado do programa; se não der para gravar, usa a do usuário."""
    if os.environ.get("MANGA_TRADUTOR_MODELOS"):
        return os.environ["MANGA_TRADUTOR_MODELOS"]
    if getattr(sys, "frozen", False):          # executável do PyInstaller
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pasta = os.path.join(base, "modelos")
    try:
        os.makedirs(pasta, exist_ok=True)
        teste = os.path.join(pasta, ".escrita")
        open(teste, "w").close()
        os.remove(teste)
        return pasta
    except OSError:  # ex.: instalado em Arquivos de Programas sem permissão
        raiz = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache")
        pasta = os.path.join(raiz, "TradutorManga", "modelos")
        os.makedirs(pasta, exist_ok=True)
        return pasta


def caminho(nome, baixar=True, progresso=None):
    """Caminho do modelo; baixa se faltar. Devolve None se não conseguir."""
    info = MODELOS[nome]
    destino = os.path.join(pasta_modelos(), info["arquivo"])
    if os.path.exists(destino):
        return destino
    if not baixar:
        return None
    try:
        _baixar(info, destino, progresso)
        return destino
    except Exception as erro:
        print(f"  aviso: não consegui baixar o modelo '{nome}': {erro}")
        return None


def _baixar(info, destino, progresso=None):
    temp = destino + ".parcial"
    h = hashlib.sha256()
    with urllib.request.urlopen(info["url"], timeout=60) as resp, open(temp, "wb") as f:
        total = int(resp.headers.get("Content-Length") or 0)
        lido = 0
        while True:
            bloco = resp.read(1 << 20)
            if not bloco:
                break
            f.write(bloco)
            h.update(bloco)
            lido += len(bloco)
            if progresso:
                progresso(lido, total)
    if h.hexdigest() != info["sha256"]:
        os.remove(temp)
        raise ValueError("arquivo baixado está corrompido (sha256 diferente)")
    os.replace(temp, destino)
