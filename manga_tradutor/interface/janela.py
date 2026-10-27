"""Janela principal do tradutor de mangá (PySide6).

Só cuida da tela: toda a lógica está no Pipeline (manga_tradutor/pipeline.py),
que esta janela chama por meio de interface/motor.py. Uma versão mobile no
futuro pode reaproveitar o mesmo núcleo com outra camada de tela.

Fluxo:
  1. Abrir: arrastar ou escolher PDF, imagens ou pasta (ou um projeto salvo)
  2. Verificar: mostra quais páginas parecem mangá
  3. Idioma: pergunta de qual idioma para qual
  4. Traduzir: lê os balões, traduz e escreve, em segundo plano
  5. Revisar: original x traduzida, edição de cada balão com redesenho automático
  6. Exportar: PDF, CBZ ou PNG (+ textos.json)
"""
import os
import sys
import traceback

from PySide6.QtCore import QObject, QSettings, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar,
    QScrollArea, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from . import tema
from .componentes import (AreaSoltar, CartaoBalao, Etapas, Visor, botao, caminhos_validos,
                          para_pixmap, rotulo)
from .motor import IDIOMAS_TELA, MOTORES_TELA, Cancelado, Config, Pipeline, Projeto

FILTRO_ENTRADA = "PDF ou imagens (*.pdf *.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)"
NOMES_ETAPA = {"modelos": "Baixando modelos (só na primeira vez)",
               "carregar": "Lendo as páginas", "verificar": "Verificando se é mangá",
               "analisar": "Lendo os balões", "traduzir": "Traduzindo",
               "renderizar": "Escrevendo as traduções", "exportar": "Exportando"}
ABRIR, VERIFICAR, IDIOMA, TRADUZIR, REVISAR, EXPORTAR = range(6)


class Trabalho(QObject):
    """Roda uma função fora da thread da tela e avisa quando termina."""
    terminou = Signal(object)
    falhou = Signal(str)

    def __init__(self, funcao):
        super().__init__()
        self.funcao = funcao

    def rodar(self):
        try:
            self.terminou.emit(self.funcao())
        except Cancelado:
            self.falhou.emit("Cancelado.")
        except Exception:
            self.falhou.emit(traceback.format_exc())


class Sinais(QObject):
    progresso = Signal(str, int, int, str)
    aviso = Signal(str)


def combo(itens, selecionado):
    caixa = QComboBox()
    for cod, nome, *_ in itens:
        caixa.addItem(nome, cod)
    caixa.setCurrentIndex(max(caixa.findData(selecionado), 0))
    return caixa


def painel(margem=14):
    quadro = QFrame()
    quadro.setObjectName("painel")
    v = QVBoxLayout(quadro)
    v.setContentsMargins(margem, margem, margem, margem)
    v.setSpacing(10)
    return quadro, v


class DialogoIdioma(QDialog):
    """Etapa 2: depois de verificar as páginas, pergunta para qual idioma traduzir."""

    def __init__(self, pai, n_manga, n_total, origem, destino):
        super().__init__(pai)
        self.setWindowTitle("Idioma da tradução")
        self.setMinimumWidth(420)
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 18)
        v.setSpacing(12)
        v.addWidget(rotulo("Para qual idioma traduzir?", "grande"))
        v.addWidget(rotulo(f"{n_manga} de {n_total} página(s) parecem ser de mangá.", "fraco"))
        form = QFormLayout()
        form.setSpacing(10)
        self.origem = combo(IDIOMAS_TELA, origem)
        self.destino = combo(IDIOMAS_TELA, destino)
        form.addRow("Idioma do mangá", self.origem)
        form.addRow("Traduzir para", self.destino)
        v.addLayout(form)
        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok = botoes.button(QDialogButtonBox.Ok)
        ok.setText("Traduzir")
        ok.setObjectName("primario")
        botoes.button(QDialogButtonBox.Cancel).setText("Agora não")
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        v.addWidget(botoes)


class DialogoConfig(QDialog):
    """Chaves de API e aparência."""

    def __init__(self, pai, config):
        super().__init__(pai)
        self.setWindowTitle("Configurações")
        self.setMinimumWidth(460)
        self.config = config
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 18)
        v.setSpacing(12)
        v.addWidget(rotulo("Configurações", "grande"))
        form = QFormLayout()
        form.setSpacing(10)
        self.chaves = {}
        for cod, nome, usa_chave in MOTORES_TELA:
            if usa_chave:
                campo = QLineEdit(config.value(f"chave_{cod}", ""))
                campo.setEchoMode(QLineEdit.Password)
                campo.setPlaceholderText("cole a chave aqui")
                self.chaves[cod] = campo
                form.addRow(f"Chave {nome.split(' (')[0]}", campo)
        self.tema = QComboBox()
        self.tema.addItem("Escuro", "escuro")
        self.tema.addItem("Claro", "claro")
        self.tema.setCurrentIndex(self.tema.findData(tema.nome_atual()))
        form.addRow("Aparência", self.tema)
        v.addLayout(form)
        v.addWidget(rotulo("Sem chave, o DeepL e o Claude usam o Google Tradutor no lugar. "
                           "As chaves ficam guardadas só neste computador.", "fraco", quebra=True))
        botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Save).setText("Salvar")
        botoes.button(QDialogButtonBox.Save).setObjectName("primario")
        botoes.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        v.addWidget(botoes)

    def salvar(self):
        for cod, campo in self.chaves.items():
            self.config.setValue(f"chave_{cod}", campo.text().strip())
        self.config.setValue("tema", self.tema.currentData())


class Janela(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tradutor de Mangá")
        self.setWindowIcon(tema.icone())
        self.resize(1380, 860)
        self.setAcceptDrops(True)
        self.config = QSettings("TradutorManga", "TradutorManga")
        self.pipe = None
        self.projeto = None
        self.thread = self.trabalho = None
        self._em_andamento = set()
        self.numero_atual = None
        self.balao_atual = None
        self.cartoes = {}
        self.avisos = 0
        self.ultima_pasta = self.config.value("ultima_pasta", os.path.expanduser("~"))
        self.sinais = Sinais()
        self.sinais.progresso.connect(self._progresso)
        self.sinais.aviso.connect(self._aviso)

        central = QWidget()
        central.setObjectName("fundo")
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self._montar_cabecalho())
        v.addWidget(self._montar_barra_ocupado())
        self.pilha = QStackedWidget()
        self.pilha.addWidget(self._montar_inicio())
        self.pilha.addWidget(self._montar_trabalho())
        v.addWidget(self.pilha, 1)
        self.setCentralWidget(central)
        self._montar_rodape()
        self._atalhos()
        self._etapa(ABRIR)
        self._atualizar_botoes()

    # ================= montagem =================
    def _montar_cabecalho(self):
        cab = QFrame()
        cab.setObjectName("cabecalho")
        h = QHBoxLayout(cab)
        h.setContentsMargins(16, 10, 12, 10)
        h.setSpacing(12)
        logo = rotulo("")
        logo.setPixmap(tema.icone_app(30))
        h.addWidget(logo)
        h.addWidget(rotulo("Tradutor de Mangá", "titulo_app"))
        h.addSpacing(24)
        self.etapas = Etapas()
        h.addWidget(self.etapas, 1)
        h.addSpacing(12)
        self.botao_novo = botao("Novo", "plano", self.novo, "Começar com outro arquivo")
        h.addWidget(self.botao_novo)
        self.botao_tema = botao("", "plano", self.alternar_tema, "Alternar tema claro/escuro")
        h.addWidget(self.botao_tema)
        h.addWidget(botao("⚙  Configurações", "plano", self.abrir_config))
        return cab

    def _montar_barra_ocupado(self):
        self.barra_ocupado = QFrame()
        self.barra_ocupado.setObjectName("cabecalho")
        h = QHBoxLayout(self.barra_ocupado)
        h.setContentsMargins(16, 6, 12, 6)
        self.texto_ocupado = rotulo("", "fraco")
        self.texto_ocupado.setMinimumWidth(260)
        h.addWidget(self.texto_ocupado)
        self.progresso = QProgressBar()
        self.progresso.setTextVisible(False)
        h.addWidget(self.progresso, 1)
        h.addWidget(botao("Cancelar", "plano", self.cancelar))
        self.barra_ocupado.hide()
        return self.barra_ocupado

    def _montar_inicio(self):
        tela = QWidget()
        g = QVBoxLayout(tela)
        g.setContentsMargins(40, 30, 40, 30)
        g.addStretch()
        linha = QHBoxLayout()
        linha.addStretch()
        self.area_soltar = AreaSoltar(self.abrir_arquivos, self.abrir_pasta, self.abrir_projeto)
        self.area_soltar.soltou.connect(self._carregar)
        self.area_soltar.setMaximumWidth(760)
        linha.addWidget(self.area_soltar, 1)
        linha.addStretch()
        g.addLayout(linha)
        dica = rotulo("Dica: depois de traduzir, clique num balão da página para corrigir o texto.", "fraco")
        dica.setAlignment(Qt.AlignCenter)
        g.addSpacing(14)
        g.addWidget(dica)
        g.addStretch()
        return tela

    def _montar_trabalho(self):
        tela = QWidget()
        h = QHBoxLayout(tela)
        h.setContentsMargins(12, 12, 12, 12)
        divisao = QSplitter(Qt.Horizontal)
        divisao.setHandleWidth(10)
        divisao.addWidget(self._montar_miniaturas())
        divisao.addWidget(self._montar_centro())
        divisao.addWidget(self._montar_lateral())
        divisao.setStretchFactor(1, 1)
        divisao.setSizes([190, 820, 360])
        h.addWidget(divisao)
        return tela

    def _montar_miniaturas(self):
        quadro, v = painel(8)
        quadro.setMinimumWidth(150)
        quadro.setMaximumWidth(260)
        self.titulo_paginas = rotulo("Páginas", "titulo_secao")
        v.addWidget(self.titulo_paginas)
        self.lista = QListWidget()
        # Miniatura em cima, legenda embaixo, uma página por linha.
        self.lista.setViewMode(QListWidget.IconMode)
        self.lista.setFlow(QListWidget.TopToBottom)
        self.lista.setWrapping(False)
        self.lista.setMovement(QListWidget.Static)
        self.lista.setResizeMode(QListWidget.Adjust)
        self.lista.setIconSize(QSize(130, 180))
        self.lista.setGridSize(QSize(160, 230))
        self.lista.setWordWrap(True)
        self.lista.currentRowChanged.connect(self._selecionar_linha)
        v.addWidget(self.lista)
        return quadro

    def _montar_centro(self):
        quadro, v = painel(8)
        barra = QHBoxLayout()
        self.grupo_modo = QButtonGroup(self)
        for i, nome in enumerate(("Original", "Traduzida", "Comparar")):
            b = botao(nome, "segmento")
            b.setCheckable(True)
            self.grupo_modo.addButton(b, i)
            barra.addWidget(b)
        barra.setSpacing(0)
        self.grupo_modo.button(2).setChecked(True)
        self.grupo_modo.idClicked.connect(lambda _: self._mostrar_pagina())
        barra.addSpacing(14)
        self.check_caixas = QCheckBox("Mostrar balões")
        self.check_caixas.setChecked(True)
        self.check_caixas.toggled.connect(self._alternar_caixas)
        barra.addWidget(self.check_caixas)
        barra.addStretch()
        self.botao_anterior = botao("‹", "plano", lambda: self._passar(-1), "Página anterior (PgUp)")
        self.texto_pagina = rotulo("", "fraco")
        self.botao_proxima = botao("›", "plano", lambda: self._passar(1), "Próxima página (PgDn)")
        for w in (self.botao_anterior, self.texto_pagina, self.botao_proxima):
            barra.addWidget(w)
        barra.addSpacing(10)
        barra.addWidget(botao("−", "plano", lambda: self._zoom(1 / 1.25), "Diminuir (Ctrl −)"))
        barra.addWidget(botao("Ajustar", "plano", self._ajustar, "Página inteira (Ctrl 0)"))
        barra.addWidget(botao("+", "plano", lambda: self._zoom(1.25), "Aumentar (Ctrl +)"))
        v.addLayout(barra)

        self.visor_a, self.visor_b = Visor(), Visor()
        for visor in (self.visor_a, self.visor_b):
            visor.clicou_balao.connect(self._focar_balao)
        # Com zoom manual, rolar uma página rola a outra junto.
        for de, para in ((self.visor_a, self.visor_b), (self.visor_b, self.visor_a)):
            for barra_de, barra_para in ((de.horizontalScrollBar(), para.horizontalScrollBar()),
                                         (de.verticalScrollBar(), para.verticalScrollBar())):
                barra_de.valueChanged.connect(
                    lambda valor, de=de, b=barra_para: None if de.ajustar_auto else b.setValue(valor))
            de.zoom_mudou.connect(lambda de=de, para=para: self._copiar_zoom(de, para))
        self.rotulo_a, self.rotulo_b = rotulo("Original", "chip"), rotulo("Traduzida", "chip")
        lados = QSplitter(Qt.Horizontal)
        lados.setHandleWidth(8)
        for r, visor in ((self.rotulo_a, self.visor_a), (self.rotulo_b, self.visor_b)):
            caixa = QWidget()
            cv = QVBoxLayout(caixa)
            cv.setContentsMargins(0, 0, 0, 0)
            cv.setSpacing(4)
            cv.addWidget(r, 0, Qt.AlignLeft)
            cv.addWidget(visor)
            lados.addWidget(caixa)
        self.caixa_b = lados.widget(1)
        lados.setStretchFactor(0, 1)
        lados.setStretchFactor(1, 1)
        v.addWidget(lados, 1)
        return quadro

    def _montar_lateral(self):
        lado = QWidget()
        lado.setMinimumWidth(320)
        lado.setMaximumWidth(460)
        v = QVBoxLayout(lado)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        quadro, q = painel()
        q.addWidget(rotulo("Tradução", "titulo_secao"))
        idiomas = QHBoxLayout()
        self.combo_origem = combo(IDIOMAS_TELA, self.config.value("origem", "en"))
        self.combo_destino = combo(IDIOMAS_TELA, self.config.value("destino", "pt"))
        idiomas.addWidget(self.combo_origem, 1)
        idiomas.addWidget(rotulo("→", "fraco"))
        idiomas.addWidget(self.combo_destino, 1)
        q.addLayout(idiomas)
        self.combo_motor = combo(MOTORES_TELA, self.config.value("motor", MOTORES_TELA[0][0]))
        self.combo_motor.setToolTip("Serviço de tradução. Chaves de API em Configurações.")
        q.addWidget(self.combo_motor)
        self.botao_traduzir = botao("Traduzir", "primario", self.traduzir, "Lê os balões e traduz de novo")
        q.addWidget(self.botao_traduzir)
        v.addWidget(quadro)

        quadro, q = painel()
        topo = QHBoxLayout()
        self.titulo_baloes = rotulo("Balões", "titulo_secao")
        topo.addWidget(self.titulo_baloes)
        topo.addStretch()
        q.addLayout(topo)
        self.vazio_baloes = rotulo("Traduza para ver e corrigir os balões desta página.", "fraco", quebra=True)
        q.addWidget(self.vazio_baloes)
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.area_cartoes = QWidget()
        self.lista_cartoes = QVBoxLayout(self.area_cartoes)
        self.lista_cartoes.setContentsMargins(0, 0, 4, 0)
        self.lista_cartoes.setSpacing(8)
        self.lista_cartoes.addStretch()
        rolagem.setWidget(self.area_cartoes)
        self.rolagem_cartoes = rolagem
        q.addWidget(rolagem, 1)
        v.addWidget(quadro, 1)

        quadro, q = painel()
        self.botao_exportar = botao("Exportar", "primario")
        menu = QMenu(self)
        menu.addAction("PDF", lambda: self.exportar("pdf"))
        menu.addAction("CBZ (leitores de quadrinhos)", lambda: self.exportar("cbz"))
        menu.addAction("Imagens PNG", lambda: self.exportar("png"))
        self.botao_exportar.setMenu(menu)
        q.addWidget(self.botao_exportar)
        self.botao_salvar = botao("Salvar projeto", None, self.salvar_projeto,
                                  "Guarda tudo para continuar depois (Ctrl+S)")
        q.addWidget(self.botao_salvar)
        v.addWidget(quadro)
        return lado

    def _montar_rodape(self):
        self.registro = QPlainTextEdit(self)
        self.registro.setWindowFlag(Qt.Window)
        self.registro.setReadOnly(True)
        self.registro.setWindowTitle("Registro")
        self.registro.resize(720, 320)
        self.botao_registro = botao("Registro", "plano", self._mostrar_registro,
                                    "Detalhes de cada etapa e avisos")
        self.statusBar().addPermanentWidget(self.botao_registro)
        self.statusBar().showMessage("Arraste um mangá para começar.")

    def _atalhos(self):
        for tecla, acao in ((QKeySequence.Open, self.abrir_arquivos), ("Ctrl+S", self.salvar_projeto),
                            ("Ctrl+E", lambda: self.exportar("pdf")), ("PgDown", lambda: self._passar(1)),
                            ("PgUp", lambda: self._passar(-1)), ("Ctrl+0", self._ajustar),
                            ("Ctrl++", lambda: self._zoom(1.25)), ("Ctrl+=", lambda: self._zoom(1.25)),
                            ("Ctrl+-", lambda: self._zoom(1 / 1.25))):
            QShortcut(QKeySequence(tecla), self, acao)

    # ================= estado =================
    def _etapa(self, n):
        self.etapas.definir(n)
        self.pilha.setCurrentIndex(0 if n == ABRIR else 1)

    def _atualizar_botoes(self):
        ocupado = self.thread is not None
        tem = bool(self.projeto and self.projeto.paginas)
        traduzida = tem and any(p.traduzida is not None for p in self.projeto.paginas)
        self.barra_ocupado.setVisible(ocupado)
        for w in (self.combo_origem, self.combo_destino, self.combo_motor, self.botao_novo,
                  self.area_soltar):
            w.setEnabled(not ocupado)
        self.botao_traduzir.setEnabled(tem and not ocupado)
        self.botao_exportar.setEnabled(traduzida and not ocupado)
        self.botao_salvar.setEnabled(tem and not ocupado)
        self.area_cartoes.setEnabled(not ocupado)
        self.botao_tema.setText("☀  Claro" if tema.nome_atual() == "escuro" else "☾  Escuro")

    # ================= segundo plano =================
    def _novo_pipeline(self):
        motor = self.combo_motor.currentData()
        chave = self.config.value(f"chave_{motor}", "") or None
        cfg = Config(origem=self.combo_origem.currentData(),
                     destino=self.combo_destino.currentData(), motor=motor, chave_api=chave)
        for nome in ("origem", "destino", "motor"):
            self.config.setValue(nome, getattr(cfg, nome))
        # O pipeline chama progresso/avisar de dentro da thread de trabalho;
        # os sinais levam a chamada de volta para a thread da tela.
        self.pipe = Pipeline(cfg, progresso=self.sinais.progresso.emit, avisar=self.sinais.aviso.emit)
        return self.pipe

    def _rodar(self, funcao, ao_terminar):
        thread = QThread(self)
        trabalho = Trabalho(funcao)
        trabalho.moveToThread(thread)
        thread.started.connect(trabalho.rodar)
        trabalho.terminou.connect(self._concluido)
        trabalho.falhou.connect(self._falhou)
        for sinal in (trabalho.terminou, trabalho.falhou):
            sinal.connect(thread.quit)
        self._em_andamento.add((thread, trabalho))
        thread.finished.connect(lambda: self._em_andamento.discard((thread, trabalho)))
        thread.finished.connect(thread.deleteLater)
        self.thread, self.trabalho, self._ao_terminar = thread, trabalho, ao_terminar
        self.progresso.setRange(0, 0)
        self._atualizar_botoes()
        thread.start()

    def _livre(self):
        self.thread = self.trabalho = None
        self._atualizar_botoes()

    def _concluido(self, resultado):
        self._livre()
        self._ao_terminar(resultado)

    def _falhou(self, erro):
        self._livre()
        self.registro.appendPlainText(erro)
        if erro.startswith("Cancelado"):
            self.statusBar().showMessage("Cancelado.", 5000)
        else:
            QMessageBox.warning(self, "Algo deu errado", erro.strip().splitlines()[-1]
                                + "\n\nDetalhes no Registro (canto inferior direito).")
        if not (self.projeto and self.projeto.paginas):
            self._etapa(ABRIR)

    def _progresso(self, etapa, atual, total, mensagem):
        nome = NOMES_ETAPA.get(etapa, etapa)
        self.progresso.setRange(0, max(total, 1))
        self.progresso.setValue(atual)
        self.texto_ocupado.setText(f"{nome}… {mensagem if etapa == 'modelos' else ''}".strip())
        if mensagem and etapa != "modelos":
            self.registro.appendPlainText(f"{nome}: {mensagem}")

    def _aviso(self, msg):
        self.avisos += 1
        self.registro.appendPlainText(f"aviso: {msg}")
        self.botao_registro.setText(f"Registro  ⚠ {self.avisos}")

    def cancelar(self):
        if self.pipe:
            self.pipe.cancelar()
            self.texto_ocupado.setText("Cancelando…")

    # ================= 1. abrir =================
    def abrir_arquivos(self):
        if self.thread:
            return
        arquivos, _ = QFileDialog.getOpenFileNames(self, "Escolha o PDF ou as imagens",
                                                   self.ultima_pasta, FILTRO_ENTRADA)
        if arquivos:
            self._carregar(arquivos)

    def abrir_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, "Pasta com as páginas", self.ultima_pasta)
        if pasta:
            self._carregar([pasta])

    def dragEnterEvent(self, e):
        if not self.thread and caminhos_validos(e.mimeData().urls()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        caminhos = caminhos_validos(e.mimeData().urls())
        if caminhos and not self.thread:
            self._carregar(caminhos)

    def novo(self):
        self.projeto = None
        self._limpar_trabalho()
        self._etapa(ABRIR)
        self._atualizar_botoes()

    def _limpar_trabalho(self):
        self.lista.clear()
        self._preencher_cartoes(None)
        self.visor_a.mostrar(None)
        self.visor_b.mostrar(None)
        self.registro.clear()
        self.avisos = 0
        self.botao_registro.setText("Registro")

    def _carregar(self, entradas):
        self.ultima_pasta = os.path.dirname(os.path.abspath(entradas[0]))
        self.config.setValue("ultima_pasta", self.ultima_pasta)
        self.projeto = None
        self._limpar_trabalho()
        self._etapa(VERIFICAR)
        pipe = self._novo_pipeline()

        def carregar_e_verificar():
            projeto = pipe.carregar(entradas)
            pipe.verificar_manga(projeto)
            return projeto

        self._rodar(carregar_e_verificar, self._carregado)

    # ================= 2 e 3. é mangá? qual idioma? =================
    def _carregado(self, projeto):
        self.projeto = projeto
        paginas = projeto.paginas
        if not paginas:
            QMessageBox.information(self, "Nada encontrado",
                                    "Nenhuma página encontrada. Escolha um PDF ou imagens.")
            self._etapa(ABRIR)
            return
        self._preencher_lista()
        n_manga = sum(bool(p.eh_manga) for p in paginas)
        if n_manga == 0:
            resp = QMessageBox.question(
                self, "Não parece mangá",
                "Nenhuma página parece ser de mangá.\nQuer traduzir mesmo assim?")
            if resp != QMessageBox.Yes:
                self.statusBar().showMessage("O arquivo não parece ser um mangá.")
                return
            for p in paginas:
                p.eh_manga = True
            self._preencher_lista()
            n_manga = len(paginas)

        self._etapa(IDIOMA)
        dialogo = DialogoIdioma(self, n_manga, len(paginas), self.combo_origem.currentData(),
                                self.combo_destino.currentData())
        if dialogo.exec() == QDialog.Accepted:
            self.combo_origem.setCurrentIndex(dialogo.origem.currentIndex())
            self.combo_destino.setCurrentIndex(dialogo.destino.currentIndex())
            self.traduzir()
        else:
            self.statusBar().showMessage("Escolha os idiomas à direita e clique em Traduzir.")

    def _preencher_lista(self):
        linha = max(self.lista.currentRow(), 0)
        self.lista.blockSignals(True)
        self.lista.clear()
        for p in self.projeto.paginas:
            if p.eh_manga is False:
                situacao = "ignorada"
            elif p.baloes:
                situacao = f"{len(p.baloes)} balões" if len(p.baloes) > 1 else "1 balão"
            else:
                situacao = "mangá"
            imagem = p.traduzida if p.traduzida is not None else p.original
            item = QListWidgetItem(QIcon(para_pixmap(imagem)), f"Pág. {p.numero} · {situacao}")
            item.setData(Qt.UserRole, p.numero)
            item.setToolTip("\n".join(p.motivos or []))
            if p.eh_manga is False:
                item.setForeground(tema.qcor("texto_fraco"))
            self.lista.addItem(item)
        self.lista.blockSignals(False)
        self.titulo_paginas.setText(f"Páginas ({len(self.projeto.paginas)})")
        self.lista.setCurrentRow(min(linha, self.lista.count() - 1))
        self._selecionar_linha(self.lista.currentRow())
        self._atualizar_botoes()

    # ================= 4. traduzir =================
    def traduzir(self):
        if not self.projeto:
            return
        if self.combo_origem.currentData() == self.combo_destino.currentData():
            QMessageBox.information(self, "Idiomas iguais", "Escolha idiomas diferentes.")
            return
        self._etapa(TRADUZIR)
        self.registro.appendPlainText(f"Traduzindo de {self.combo_origem.currentText()} para "
                                      f"{self.combo_destino.currentText()} "
                                      f"({self.combo_motor.currentText()})…")
        pipe, projeto = self._novo_pipeline(), self.projeto

        def tudo():
            pipe.analisar(projeto)
            falhas = pipe.traduzir(projeto)
            pipe.renderizar(projeto)
            return falhas

        self._rodar(tudo, self._traduzido)

    def _traduzido(self, falhas):
        self._etapa(REVISAR)
        self._preencher_lista()
        total = sum(len(p.baloes) for p in self.projeto.paginas)
        self.registro.appendPlainText(f"Pronto: {total} balão(ões) em {len(self.projeto.paginas)} página(s).")
        if falhas:
            QMessageBox.warning(self, "Alguns balões ficaram sem tradução",
                                f"{falhas} balão(ões) ficaram com o texto original (sem internet "
                                "ou limite do serviço?). Corrija nos cartões à direita ou "
                                "clique em Traduzir de novo.")
        self.statusBar().showMessage(f"Tradução pronta: {total} balão(ões). Clique num balão "
                                     "para corrigir.", 8000)

    # ================= 5. revisar =================
    def _pagina(self, numero):
        return next(p for p in self.projeto.paginas if p.numero == numero)

    def _selecionar_linha(self, linha):
        if linha < 0 or not self.projeto:
            return
        self.numero_atual = self.lista.item(linha).data(Qt.UserRole)
        self.balao_atual = None
        self.texto_pagina.setText(f"{linha + 1} / {self.lista.count()}")
        self._mostrar_pagina(nova=True)
        self._preencher_cartoes(self._pagina(self.numero_atual))

    def _passar(self, delta):
        if self.lista.count():
            self.lista.setCurrentRow(max(0, min(self.lista.count() - 1, self.lista.currentRow() + delta)))

    def _mostrar_pagina(self, nova=False):
        if self.numero_atual is None or not self.projeto:
            return
        p = self._pagina(self.numero_atual)
        modo = self.grupo_modo.checkedId()
        original = para_pixmap(p.original)
        traduzida = para_pixmap(p.traduzida) if p.traduzida is not None else None
        aviso = ("Ainda não traduzida" if p.eh_manga is not False
                 else "Página ignorada (não parece mangá)")
        if nova:
            for visor in (self.visor_a, self.visor_b):
                visor.ajustar_auto = True
        self.caixa_b.setVisible(modo == 2)
        if modo == 1:
            self.rotulo_a.setText("Traduzida")
            self.visor_a.mostrar(traduzida, p.baloes, aviso)
        else:
            self.rotulo_a.setText("Original")
            self.visor_a.mostrar(original, p.baloes)
            if modo == 2:
                self.visor_b.mostrar(traduzida, p.baloes, aviso)
        self._marcar_balao(self.balao_atual)

    def _preencher_cartoes(self, pagina):
        while self.lista_cartoes.count() > 1:
            w = self.lista_cartoes.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.cartoes = {}
        baloes = pagina.baloes if pagina else []
        for b in baloes:
            cartao = CartaoBalao(b)
            cartao.editado.connect(self._editar_balao)
            cartao.focado.connect(self._focar_balao)
            self.cartoes[b.id] = cartao
            self.lista_cartoes.insertWidget(self.lista_cartoes.count() - 1, cartao)
        self.titulo_baloes.setText(f"Balões ({len(baloes)})" if baloes else "Balões")
        self.vazio_baloes.setVisible(not baloes)
        if pagina and pagina.eh_manga is False and not baloes:
            self.vazio_baloes.setText("Esta página não parece mangá e foi ignorada.")
        else:
            self.vazio_baloes.setText("Traduza para ver e corrigir os balões desta página.")

    def _focar_balao(self, id_balao):
        if id_balao == self.balao_atual:
            return
        self.balao_atual = id_balao
        self._marcar_balao(id_balao)
        cartao = self.cartoes.get(id_balao)
        if cartao:
            self.rolagem_cartoes.ensureWidgetVisible(cartao, 0, 20)
            if not cartao.campo.hasFocus():
                cartao.campo.setFocus()

    def _marcar_balao(self, id_balao):
        for visor in (self.visor_a, self.visor_b):
            visor.selecionar(id_balao)
        for i, cartao in self.cartoes.items():
            cartao.selecionar(i == id_balao)

    def _alternar_caixas(self, sim):
        for visor in (self.visor_a, self.visor_b):
            visor.mostrar_caixas = sim
        self._marcar_balao(self.balao_atual)

    def _editar_balao(self, id_balao, texto):
        p = self._pagina(self.numero_atual)
        b = next((b for b in p.baloes if b.id == id_balao), None)
        if b is None or b.traducao == texto or self.thread:
            return
        b.traducao = texto
        if self.pipe is None:
            self._novo_pipeline()
        self.pipe.renderizar(self.projeto, [p.numero])
        self._mostrar_pagina()
        item = self.lista.currentItem()
        if item:
            item.setIcon(QIcon(para_pixmap(p.traduzida)))
        self.statusBar().showMessage(f"Balão {id_balao} atualizado.", 3000)

    def _zoom(self, fator):
        self.visor_a.ampliar(fator)

    def _ajustar(self):
        self.visor_a.ajustar()

    def _copiar_zoom(self, de, para):
        if not para.isVisible() or para.item_imagem is None:
            return
        if de.ajustar_auto:
            if not para.ajustar_auto:
                para.ajustar()
        else:
            para.ajustar_auto = False
            para.setTransform(de.transform())

    # ================= 6. exportar / projeto =================
    def exportar(self, formato):
        if not self.botao_exportar.isEnabled():
            return
        pasta = QFileDialog.getExistingDirectory(self, "Onde salvar o mangá traduzido", self.ultima_pasta)
        if not pasta:
            return
        if self.pipe is None:
            self._novo_pipeline()
        pipe, projeto = self.pipe, self.projeto
        self._rodar(lambda: pipe.exportar(projeto, pasta, formato=formato),
                    lambda arquivos: self._exportado(arquivos, pasta))

    def _exportado(self, arquivos, pasta):
        self._etapa(EXPORTAR)
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Exportado")
        caixa.setText(f"Pronto! Arquivo salvo em:\n{arquivos[0]}")
        abrir = caixa.addButton("Abrir pasta", QMessageBox.AcceptRole)
        caixa.addButton("Fechar", QMessageBox.RejectRole)
        caixa.exec()
        if caixa.clickedButton() is abrir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(pasta))

    def salvar_projeto(self):
        if not self.botao_salvar.isEnabled():
            return
        pasta = QFileDialog.getExistingDirectory(self, "Pasta para salvar o projeto", self.ultima_pasta)
        if not pasta:
            return
        self.projeto.origem = self.combo_origem.currentData()
        self.projeto.destino = self.combo_destino.currentData()
        projeto = self.projeto
        self._rodar(lambda: projeto.salvar(pasta),
                    lambda _: self.statusBar().showMessage(f"Projeto salvo em {pasta}", 6000))

    def abrir_projeto(self):
        pasta = QFileDialog.getExistingDirectory(self, "Pasta de um projeto salvo", self.ultima_pasta)
        if not pasta:
            return
        if not os.path.exists(os.path.join(pasta, "textos.json")):
            QMessageBox.information(self, "Projeto não encontrado",
                                    "Essa pasta não tem um textos.json de projeto salvo.")
            return
        self._limpar_trabalho()
        self._etapa(REVISAR)

        def renderizar(projeto):
            self.projeto = projeto
            for caixa, codigo in ((self.combo_origem, projeto.origem), (self.combo_destino, projeto.destino)):
                if caixa.findData(codigo) >= 0:
                    caixa.setCurrentIndex(caixa.findData(codigo))
            pipe = self._novo_pipeline()
            self._rodar(lambda: pipe.renderizar(projeto), lambda _: self._preencher_lista())

        self._rodar(lambda: Projeto.abrir(pasta), renderizar)

    # ================= aparência =================
    def alternar_tema(self):
        self.aplicar_tema("claro" if tema.nome_atual() == "escuro" else "escuro")

    def aplicar_tema(self, nome):
        tema.usar(nome)
        self.config.setValue("tema", nome)
        QApplication.instance().setStyleSheet(tema.folha_de_estilo())
        self.etapas.update()
        self._atualizar_botoes()
        self._mostrar_pagina()

    def abrir_config(self):
        dialogo = DialogoConfig(self, self.config)
        if dialogo.exec() == QDialog.Accepted:
            dialogo.salvar()
            self.aplicar_tema(dialogo.tema.currentData())

    def _mostrar_registro(self):
        self.registro.show()
        self.registro.raise_()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Tradutor de Mangá")
    app.setStyle("Fusion")
    app.setWindowIcon(tema.icone())
    tema.usar(QSettings("TradutorManga", "TradutorManga").value("tema", "escuro"))
    app.setStyleSheet(tema.folha_de_estilo())
    janela = Janela()
    janela.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
