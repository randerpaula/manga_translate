# Receita do PyInstaller para o executável do Windows (modo pasta).
# Use pelo gerar_exe.bat, ou rode da pasta tradutor-manga:
#   python -m PyInstaller --noconfirm build\tradutor_manga.spec
#
# Variáveis de ambiente opcionais:
#   TESSERACT_DIR   pasta do Tesseract (padrão C:\Program Files\Tesseract-OCR)
#   INCLUIR_TORCH=1 inclui PyTorch, LaMa e manga-ocr (programa bem maior)
import os
import shutil

RAIZ = os.path.abspath(os.path.join(SPECPATH, ".."))
TESSERACT = os.environ.get("TESSERACT_DIR", r"C:\Program Files\Tesseract-OCR")
IDIOMAS_TESSERACT = {"por", "eng", "jpn", "jpn_vert", "osd"}
INCLUIR_TORCH = os.environ.get("INCLUIR_TORCH") == "1"

# Coisas que as bibliotecas puxam mas o tradutor não usa e que deixam o
# programa centenas de MB maior. O detector roda com cv2.dnn (sem onnxruntime)
# e o deep-translator usa o html.parser (sem lxml).
excludes = ["tkinter", "matplotlib", "IPython", "pytest", "pandas", "onnxruntime",
            "pymupdf.layout", "pymupdf4llm", "lxml"]
hiddenimports = []
if INCLUIR_TORCH:
    hiddenimports += ["manga_ocr", "torch"]
else:
    # Sem PyTorch o programa avisa e usa Tesseract + OpenCV.
    excludes += ["torch", "torchvision", "manga_ocr", "transformers"]

# Listas de palavras usadas para corrigir o OCR (ficam junto do módulo ocr).
datas = [(os.path.join(RAIZ, "manga_tradutor", "ocr", f"palavras_{idioma}.txt"),
          os.path.join("manga_tradutor", "ocr")) for idioma in ("en", "pt")]

a = Analysis(
    [os.path.join(RAIZ, "tradutor_gui.py")],
    pathex=[RAIZ],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TradutorManga",
    console=False,          # sem janela preta de terminal
    icon=os.path.join(SPECPATH, "icone.ico") if os.path.exists(os.path.join(SPECPATH, "icone.ico")) else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="TradutorManga")

# O núcleo procura o Tesseract e os modelos ao lado do .exe (não em _internal),
# então essas pastas são copiadas depois de montar o programa.
PASTA_FINAL = os.path.join(DISTPATH, "TradutorManga")


def _sem_idiomas_extras(pasta, nomes):
    if os.path.basename(pasta) != "tessdata":
        return []
    return [n for n in nomes if n.endswith(".traineddata") and n.split(".")[0] not in IDIOMAS_TESSERACT]


if os.path.isdir(TESSERACT):
    shutil.copytree(TESSERACT, os.path.join(PASTA_FINAL, "tesseract"),
                    ignore=_sem_idiomas_extras, dirs_exist_ok=True)
    print(f"Tesseract incluído de {TESSERACT}")
else:
    print(f"AVISO: Tesseract não encontrado em {TESSERACT}; o executável vai "
          "depender do Tesseract instalado no computador do usuário.")

# Modelos já baixados vão junto, para o programa não baixar na primeira vez.
if os.path.isdir(os.path.join(RAIZ, "modelos")):
    shutil.copytree(os.path.join(RAIZ, "modelos"), os.path.join(PASTA_FINAL, "modelos"),
                    dirs_exist_ok=True)
