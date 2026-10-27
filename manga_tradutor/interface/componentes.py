"""Peças visuais reutilizadas pela janela principal."""
import os

import cv2
from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGraphicsRectItem, QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView,
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from . import tema

EXTENSOES = (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")


def para_pixmap(img_bgr):
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    return QPixmap.fromImage(QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy())


def rotulo(texto, nome=None, quebra=False):
    r = QLabel(texto)
    if nome:
        r.setObjectName(nome)
    r.setWordWrap(quebra)
    return r


def botao(texto, nome=None, ao_clicar=None, dica=None):
    b = QPushButton(texto)
    if nome:
        b.setObjectName(nome)
    if ao_clicar:
        b.clicked.connect(ao_clicar)
    if dica:
        b.setToolTip(dica)
    b.setCursor(Qt.PointingHandCursor)
    return b


def caminhos_validos(urls):
    caminhos = [u.toLocalFile() for u in urls if u.isLocalFile()]
    return [c for c in caminhos if os.path.isdir(c) or c.lower().endswith(EXTENSOES)]


class AreaSoltar(QFrame):
    """Tela inicial: arraste arquivos aqui ou use os botões."""
    soltou = Signal(list)

    def __init__(self, ao_arquivos, ao_pasta, ao_projeto):
        super().__init__()
        self.setObjectName("area_soltar")
        self.setAcceptDrops(True)
        self.setMinimumSize(560, 360)
        v = QVBoxLayout(self)
        v.setSpacing(14)
        v.addStretch()
        icone = QLabel()
        icone.setPixmap(tema.icone_app(96))
        icone.setAlignment(Qt.AlignCenter)
        v.addWidget(icone)
        for texto, nome in (("Arraste aqui o seu mangá", "grande"),
                            ("PDF, imagens (PNG, JPG, WEBP…) ou uma pasta com as páginas", "fraco")):
            r = rotulo(texto, nome)
            r.setAlignment(Qt.AlignCenter)
            v.addWidget(r)
        linha = QHBoxLayout()
        linha.addStretch()
        linha.addWidget(botao("Escolher arquivos", "primario", ao_arquivos))
        linha.addWidget(botao("Escolher pasta", None, ao_pasta))
        linha.addWidget(botao("Abrir projeto salvo", "plano", ao_projeto,
                              "Continua um trabalho salvo antes, sem refazer a leitura"))
        linha.addStretch()
        v.addSpacing(8)
        v.addLayout(linha)
        v.addStretch()

    def _ativa(self, sim):
        self.setProperty("ativa", "true" if sim else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e):
        if caminhos_validos(e.mimeData().urls()):
            e.acceptProposedAction()
            self._ativa(True)

    def dragLeaveEvent(self, e):
        self._ativa(False)

    def dropEvent(self, e):
        self._ativa(False)
        caminhos = caminhos_validos(e.mimeData().urls())
        if caminhos:
            self.soltou.emit(caminhos)


class Etapas(QWidget):
    """Indicador das etapas do processo no cabeçalho."""
    NOMES = ["Abrir", "Verificar", "Idioma", "Traduzir", "Revisar", "Exportar"]

    def __init__(self):
        super().__init__()
        self.atual = 0
        self.setMinimumHeight(30)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def definir(self, indice):
        self.atual = indice
        self.update()

    def sizeHint(self):
        return QSize(620, 30)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        n = len(self.NOMES)
        largura = self.width() / n
        fonte = QFont(self.font())
        fonte.setPointSizeF(9)
        for i, nome in enumerate(self.NOMES):
            x = i * largura
            cy = self.height() / 2
            feito, atual = i < self.atual, i == self.atual
            if i:
                p.setPen(QPen(tema.qcor("destaque" if feito or atual else "borda"), 2))
                p.drawLine(int(x - 8), int(cy), int(x + 4), int(cy))
            cor_circulo = tema.qcor("destaque") if (feito or atual) else tema.qcor("superficie2")
            p.setPen(QPen(tema.qcor("destaque" if atual else "borda"), 1.5))
            p.setBrush(cor_circulo)
            p.drawEllipse(QRectF(x + 8, cy - 10, 20, 20))
            p.setPen(tema.qcor("sobre_destaque" if (feito or atual) else "texto_fraco"))
            fonte.setBold(True)
            p.setFont(fonte)
            p.drawText(QRectF(x + 8, cy - 10, 20, 20), Qt.AlignCenter, "✓" if feito else str(i + 1))
            fonte.setBold(atual)
            p.setFont(fonte)
            p.setPen(tema.qcor("texto" if (feito or atual) else "texto_fraco"))
            p.drawText(QRectF(x + 34, 0, largura - 40, self.height()), Qt.AlignVCenter | Qt.AlignLeft, nome)
        p.end()


class Visor(QGraphicsView):
    """Mostra uma página com zoom (Ctrl+roda), arrastar e as caixas dos balões."""
    clicou_balao = Signal(int)
    zoom_mudou = Signal()

    def __init__(self):
        super().__init__()
        self.cena = QGraphicsScene(self)
        self.setScene(self.cena)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setAlignment(Qt.AlignCenter)
        self.item_imagem = None
        self.caixas = {}
        self.mostrar_caixas = True
        self.ajustar_auto = True
        self.aviso = rotulo("", "fraco")

    def mostrar(self, pixmap, baloes=(), aviso=""):
        self.cena.clear()
        self.caixas = {}
        self.item_imagem = None
        if pixmap is None:
            t = self.cena.addText(aviso)
            t.setDefaultTextColor(tema.qcor("texto_fraco"))
            self.setSceneRect(t.boundingRect())
            return
        self.item_imagem = self.cena.addPixmap(pixmap)
        self.item_imagem.setTransformationMode(Qt.SmoothTransformation)
        self.setSceneRect(QRectF(pixmap.rect()))
        for b in baloes:
            x, y, w, h = b.bbox
            caixa = QGraphicsRectItem(x - 3, y - 3, w + 6, h + 6)
            caixa.setData(0, b.id)
            numero = QGraphicsSimpleTextItem(str(b.id), caixa)
            fonte = QFont()
            fonte.setBold(True)
            fonte.setPixelSize(max(12, int(pixmap.height() / 70)))
            numero.setFont(fonte)
            numero.setPos(x - 3, y - 6 - numero.boundingRect().height())
            self.caixas[b.id] = caixa
            self.cena.addItem(caixa)
        self.selecionar(None)
        if self.ajustar_auto:
            self.ajustar()

    def selecionar(self, id_balao):
        for i, caixa in self.caixas.items():
            sel = i == id_balao
            caixa.setVisible(self.mostrar_caixas or sel)
            caixa.setPen(QPen(tema.qcor("destaque"), 4 if sel else 2, Qt.SolidLine if sel else Qt.DashLine))
            caixa.setBrush(QBrush(tema.qcor("destaque", 50 if sel else 18)))
            for filho in caixa.childItems():
                filho.setBrush(tema.qcor("destaque"))
        if id_balao in self.caixas:
            self.ensureVisible(self.caixas[id_balao], 40, 40)

    def ajustar(self):
        if self.item_imagem:
            self.ajustar_auto = True
            self.fitInView(self.item_imagem, Qt.KeepAspectRatio)
            self.zoom_mudou.emit()

    def ampliar(self, fator):
        self.ajustar_auto = False
        self.scale(fator, fator)
        self.zoom_mudou.emit()

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self.ampliar(1.15 if e.angleDelta().y() > 0 else 1 / 1.15)
        else:
            super().wheelEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.ajustar_auto:
            QTimer.singleShot(0, self.ajustar)

    def mousePressEvent(self, e):
        for item in self.items(e.position().toPoint()):
            alvo = item if isinstance(item, QGraphicsRectItem) else item.parentItem()
            if isinstance(alvo, QGraphicsRectItem) and alvo.data(0) is not None:
                self.clicou_balao.emit(alvo.data(0))
                break
        super().mousePressEvent(e)


class CartaoBalao(QFrame):
    """Um balão no painel lateral: texto lido e tradução editável."""
    editado = Signal(int, str)
    focado = Signal(int)

    def __init__(self, balao):
        super().__init__()
        self.setObjectName("cartao")
        self.id = balao.id
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(6)
        topo = QHBoxLayout()
        topo.addWidget(rotulo(f"Balão {balao.id}", "titulo_secao"))
        topo.addStretch()
        conf = float(balao.confianca or 0)
        chip = rotulo(f"leitura {conf:.0f}%", "chip_ok" if conf >= 80 else "chip_alerta" if conf < 60 else "chip")
        chip.setToolTip("Confiança do OCR. Abaixo de 60%, confira o texto lido.")
        topo.addWidget(chip)
        if getattr(balao, "rotacao", 0):
            topo.addWidget(rotulo("girado", "chip"))
        if getattr(balao, "em_balao", True) is False:
            topo.addWidget(rotulo("solto", "chip"))
        v.addLayout(topo)
        lido = rotulo(balao.texto, "fraco", quebra=True)
        lido.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(lido)
        self.campo = QPlainTextEdit(balao.traducao)
        self.campo.setPlaceholderText("Tradução")
        self.campo.setFixedHeight(68)
        self.campo.installEventFilter(self)
        v.addWidget(self.campo)
        # Redesenha a página pouco depois de parar de digitar.
        self._espera = QTimer(self, singleShot=True, interval=700)
        self._espera.timeout.connect(lambda: self.editado.emit(self.id, self.campo.toPlainText()))
        self.campo.textChanged.connect(self._espera.start)

    def selecionar(self, sim):
        self.setProperty("selecionado", "true" if sim else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def eventFilter(self, obj, e):
        if e.type() == e.Type.FocusIn:
            self.focado.emit(self.id)
        return False

    def mousePressEvent(self, e):
        self.focado.emit(self.id)
        super().mousePressEvent(e)
