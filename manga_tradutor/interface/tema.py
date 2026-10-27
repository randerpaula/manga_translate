"""Cores e estilo (QSS) da interface, nos modos escuro e claro.

Todas as cores ficam em TEMAS; o resto da interface usa só os nomes
(cor("destaque"), cor("texto_fraco")...), então trocar a paleta é mexer aqui.
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap

TEMAS = {
    "escuro": {
        "fundo": "#15161c", "superficie": "#1e1f28", "superficie2": "#272834",
        "borda": "#343546", "texto": "#ecedf3", "texto_fraco": "#9a9cb0",
        "destaque": "#ff4d5e", "destaque_hover": "#ff6b79", "sobre_destaque": "#ffffff",
        "sucesso": "#3ecf8e", "alerta": "#f5b94a", "selecao": "rgba(255, 77, 94, 0.18)",
    },
    "claro": {
        "fundo": "#f3f4f8", "superficie": "#ffffff", "superficie2": "#eceef4",
        "borda": "#d9dbe5", "texto": "#1b1c24", "texto_fraco": "#6a6c80",
        "destaque": "#e8364a", "destaque_hover": "#f04a5d", "sobre_destaque": "#ffffff",
        "sucesso": "#1f9d63", "alerta": "#c98a12", "selecao": "rgba(232, 54, 74, 0.12)",
    },
}

_atual = "escuro"


def usar(nome):
    global _atual
    _atual = nome if nome in TEMAS else "escuro"


def nome_atual():
    return _atual


def cor(nome):
    return TEMAS[_atual][nome]


def qcor(nome, alfa=None):
    c = QColor(cor(nome))
    if alfa is not None:
        c.setAlpha(alfa)
    return c


def folha_de_estilo():
    c = TEMAS[_atual]
    return f"""
    * {{ font-size: 10pt; }}
    QMainWindow, QDialog, #fundo {{ background: {c['fundo']}; color: {c['texto']}; }}
    QWidget {{ color: {c['texto']}; }}
    QLabel {{ background: transparent; }}
    QToolTip {{ background: {c['superficie2']}; color: {c['texto']}; border: 1px solid {c['borda']}; padding: 4px; }}

    #cabecalho {{ background: {c['superficie']}; border-bottom: 1px solid {c['borda']}; }}
    #titulo_app {{ font-size: 13pt; font-weight: 700; }}
    #painel, #cartao {{ background: {c['superficie']}; border: 1px solid {c['borda']}; border-radius: 12px; }}
    #cartao[selecionado="true"] {{ border: 2px solid {c['destaque']}; }}
    #titulo_secao {{ font-weight: 700; font-size: 10.5pt; }}
    #fraco {{ color: {c['texto_fraco']}; }}
    #chip {{ background: {c['superficie2']}; color: {c['texto_fraco']}; border-radius: 8px; padding: 1px 8px; font-size: 8.5pt; }}
    #chip_ok {{ background: {c['sucesso']}; color: #ffffff; border-radius: 8px; padding: 1px 8px; font-size: 8.5pt; }}
    #chip_alerta {{ background: {c['alerta']}; color: #1b1c24; border-radius: 8px; padding: 1px 8px; font-size: 8.5pt; }}

    #area_soltar {{ background: {c['superficie']}; border: 2px dashed {c['borda']}; border-radius: 20px; }}
    #area_soltar[ativa="true"] {{ border-color: {c['destaque']}; background: {c['selecao']}; }}
    #grande {{ font-size: 18pt; font-weight: 700; }}

    QPushButton {{ background: {c['superficie2']}; border: 1px solid {c['borda']}; border-radius: 8px;
                   padding: 7px 14px; }}
    QPushButton:hover {{ border-color: {c['texto_fraco']}; }}
    QPushButton:disabled {{ color: {c['texto_fraco']}; background: {c['superficie']}; }}
    QPushButton#primario {{ background: {c['destaque']}; color: {c['sobre_destaque']}; border: none; font-weight: 600; }}
    QPushButton#primario:hover {{ background: {c['destaque_hover']}; }}
    QPushButton#primario:disabled {{ background: {c['borda']}; color: {c['texto_fraco']}; }}
    QPushButton#plano {{ background: transparent; border: none; padding: 6px 10px; }}
    QPushButton#plano:hover {{ background: {c['superficie2']}; }}
    QPushButton#segmento {{ border-radius: 0; padding: 6px 14px; }}
    QPushButton#segmento:checked {{ background: {c['destaque']}; color: {c['sobre_destaque']}; border-color: {c['destaque']}; }}
    QPushButton::menu-indicator {{ subcontrol-position: right center; right: 8px; }}

    QComboBox, QLineEdit, QPlainTextEdit {{ background: {c['superficie2']}; border: 1px solid {c['borda']};
                   border-radius: 8px; padding: 6px 8px; selection-background-color: {c['destaque']}; }}
    QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus {{ border-color: {c['destaque']}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{ background: {c['superficie']}; border: 1px solid {c['borda']};
                   selection-background-color: {c['destaque']}; outline: none; }}

    QListWidget {{ background: transparent; border: none; outline: none; }}
    QListWidget::item {{ border-radius: 10px; padding: 6px; margin: 2px 4px; }}
    QListWidget::item:selected {{ background: {c['selecao']}; color: {c['texto']}; border: 1px solid {c['destaque']}; }}
    QListWidget::item:hover:!selected {{ background: {c['superficie2']}; }}

    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle {{ background: {c['borda']}; border-radius: 4px; min-height: 30px; min-width: 30px; }}
    QScrollBar::handle:hover {{ background: {c['texto_fraco']}; }}
    QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; border: none; }}

    QProgressBar {{ background: {c['superficie2']}; border: none; border-radius: 3px; max-height: 6px; }}
    QProgressBar::chunk {{ background: {c['destaque']}; border-radius: 3px; }}
    QGraphicsView {{ background: {c['fundo']}; border: none; }}
    QSplitter::handle {{ background: transparent; }}
    QStatusBar {{ background: {c['superficie']}; color: {c['texto_fraco']}; border-top: 1px solid {c['borda']}; }}
    QMenu {{ background: {c['superficie']}; border: 1px solid {c['borda']}; padding: 4px; border-radius: 8px; }}
    QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {c['destaque']}; color: {c['sobre_destaque']}; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; }}
    """


def icone_app(tamanho=256):
    """Ícone desenhado em código: balão de fala branco sobre quadrado vermelho."""
    pix = QPixmap(tamanho, tamanho)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    s = tamanho / 256
    p.setBrush(QColor("#e8364a"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(8 * s, 8 * s, 240 * s, 240 * s), 56 * s, 56 * s)
    balao = QPainterPath()
    balao.addEllipse(QRectF(38 * s, 50 * s, 180 * s, 130 * s))
    rabo = QPainterPath()
    rabo.moveTo(QPointF(80 * s, 160 * s))
    rabo.lineTo(QPointF(60 * s, 212 * s))
    rabo.lineTo(QPointF(120 * s, 172 * s))
    rabo.closeSubpath()
    p.setBrush(QColor("#ffffff"))
    p.drawPath(balao.united(rabo))
    fonte = QFont("Arial")
    fonte.setPixelSize(max(6, int(58 * s)))
    fonte.setWeight(QFont.Black)
    p.setFont(fonte)
    p.setPen(QColor("#e8364a"))
    p.drawText(QRectF(38 * s, 50 * s, 180 * s, 130 * s), Qt.AlignCenter, "A→あ" if tamanho >= 64 else "A")
    p.end()
    return pix


def icone():
    ic = QIcon()
    for t in (16, 32, 48, 64, 128, 256):
        ic.addPixmap(icone_app(t))
    return ic
