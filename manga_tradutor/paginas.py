"""Etapas 1, 3 e 6: lê PDF, imagens ou CBZ, organiza as páginas e exporta."""
import io
import os
import re
import zipfile

import cv2
try:
    import pymupdf as fitz
except ImportError:  # versões antigas do PyMuPDF
    import fitz
import numpy as np

from .projeto import Pagina

EXTENSOES_IMAGEM = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
EXTENSOES_ARQUIVO = (".zip", ".cbz")
EXTENSOES_ACEITAS = EXTENSOES_IMAGEM + EXTENSOES_ARQUIVO + (".pdf",)


def _ordem_natural(nome):
    """Ordena "pag2" antes de "pag10"."""
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", nome)]


def listar_arquivos(entradas):
    """Expande pastas e ordena os arquivos em ordem natural."""
    arquivos = []
    for e in entradas:
        if os.path.isdir(e):
            arquivos += [os.path.join(e, f) for f in os.listdir(e)
                         if f.lower().endswith(EXTENSOES_ACEITAS)]
        else:
            arquivos.append(e)
    arquivos.sort(key=lambda f: _ordem_natural(os.path.basename(f)))
    return arquivos


def carregar(entradas, dpi=200, avisar=print):
    """Aceita PDF, CBZ/ZIP, pasta de imagens ou lista de arquivos."""
    paginas = []

    def nova(origem, img, texto=""):
        paginas.append(Pagina(len(paginas) + 1, origem, img, texto))

    for arq in listar_arquivos(entradas):
        nome = arq.lower()
        if nome.endswith(".pdf"):
            with fitz.open(arq) as doc:
                for pag in doc:
                    img, texto = _pagina_pdf(doc, pag, dpi)
                    nova(f"{arq}#{pag.number + 1}", img, texto)
        elif nome.endswith(EXTENSOES_ARQUIVO):
            with zipfile.ZipFile(arq) as z:
                internos = sorted((n for n in z.namelist() if n.lower().endswith(EXTENSOES_IMAGEM)),
                                  key=_ordem_natural)
                for n in internos:
                    img = cv2.imdecode(np.frombuffer(z.read(n), np.uint8), cv2.IMREAD_COLOR)
                    if img is not None:
                        nova(f"{arq}#{n}", img)
        elif nome.endswith(EXTENSOES_IMAGEM):
            # imdecode aceita caminhos com acento no Windows (imread não).
            img = cv2.imdecode(np.fromfile(arq, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                avisar(f"não consegui abrir {arq}, pulando")
                continue
            nova(arq, img)
    return paginas


def _pagina_pdf(doc, pag, dpi):
    """Imagem e texto digital de uma página de PDF.

    Mangá impresso de um leitor web vem com cabeçalho, botões e URL em volta
    da imagem. Se uma imagem ocupa boa parte da página, usa só ela (na
    resolução original) e só o texto digital que está em cima dela.
    """
    area_pag = pag.rect.width * pag.rect.height
    melhor = None
    for info in pag.get_images(full=True):
        for r in pag.get_image_rects(info[0]):
            if r.width * r.height > 0.35 * area_pag and (melhor is None or
                                                         r.width * r.height > melhor[1].width * melhor[1].height):
                melhor = (info[0], r)
    if melhor:
        xref, ret = melhor
        try:
            pix = fitz.Pixmap(doc, xref)
            if pix.n - pix.alpha >= 4:      # CMYK
                pix = fitz.Pixmap(fitz.csRGB, pix)
            if pix.alpha:
                pix = fitz.Pixmap(pix, 0)
            # Imagem pequena demais: renderiza só a área dela na resolução pedida.
            if pix.width < 600:
                pix = pag.get_pixmap(dpi=dpi, clip=ret)
            texto = " ".join(w[4] for w in pag.get_text("words") if fitz.Rect(w[:4]).intersects(ret))
            return _pixmap_bgr(pix), texto
        except Exception:
            pass  # formato de imagem incomum: cai na página inteira
    return _pixmap_bgr(pag.get_pixmap(dpi=dpi)), pag.get_text()


def _pixmap_bgr(pix):
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)
    if pix.n == 1:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return cv2.cvtColor(img, cv2.COLOR_RGBA2BGR if pix.n == 4 else cv2.COLOR_RGB2BGR)


def exportar(paginas, pasta_saida, nome="traduzido", formato="pdf"):
    """formato: 'pdf' (PDF + PNGs), 'cbz' ou 'png'. Devolve [arquivo principal, ...]."""
    os.makedirs(pasta_saida, exist_ok=True)
    pngs = []
    if formato in ("pdf", "png"):
        for p in paginas:
            caminho = os.path.join(pasta_saida, f"{nome}_pag{p.numero:03d}.png")
            cv2.imencode(".png", p.imagem_final)[1].tofile(caminho)
            pngs.append(caminho)
    if formato == "png":
        return pngs
    if formato == "cbz":
        caminho = os.path.join(pasta_saida, f"{nome}.cbz")
        with zipfile.ZipFile(caminho, "w", zipfile.ZIP_STORED) as z:
            for p in paginas:
                z.writestr(f"{p.numero:03d}.png", cv2.imencode(".png", p.imagem_final)[1].tobytes())
        return [caminho]
    caminho = os.path.join(pasta_saida, f"{nome}.pdf")
    with fitz.open() as doc:
        for p in paginas:
            dados = cv2.imencode(".png", p.imagem_final)[1].tobytes()
            with fitz.open(stream=io.BytesIO(dados), filetype="png") as img:
                doc.insert_pdf(fitz.open("pdf", img.convert_to_pdf()))
        # Abre o arquivo e grava os bytes: funciona com acentos no caminho.
        with open(caminho, "wb") as f:
            f.write(doc.tobytes())
    return [caminho] + pngs
