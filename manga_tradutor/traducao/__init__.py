"""Etapa 5: tradução dos balões, página por página, com motores de reserva.

Se o motor escolhido falhar (sem chave, sem internet, limite de uso), a página
é traduzida pelo próximo da lista: Google e depois MyMemory.
"""
from .motores import MotorClaude, MotorDeepL, MotorGoogle, MotorMyMemory, MotorNenhum

MOTORES = {
    "deepl": "DeepL (precisa de chave)",
    "google": "Google Tradutor (gratuito)",
    "claude": "Claude (precisa de chave, melhor contexto)",
    "nenhum": "Não traduzir (teste)",
}
MOTORES_COM_CHAVE = {"deepl", "claude"}

_CLASSES = {"deepl": MotorDeepL, "google": MotorGoogle, "claude": MotorClaude,
            "nenhum": MotorNenhum}


class Tradutor:
    def __init__(self, origem, destino, motor="deepl", chave=None, avisar=print):
        self.origem, self.destino = origem, destino
        self.avisar = avisar
        self.motores = []
        if motor == "nenhum":
            self.motores = [MotorNenhum()]
        else:
            try:
                self.motores.append(_CLASSES[motor](chave) if motor in MOTORES_COM_CHAVE
                                    else _CLASSES[motor]())
            except Exception as erro:
                avisar(f"{MOTORES.get(motor, motor)} indisponível ({erro}); usando o Google")
            for reserva in (MotorGoogle, MotorMyMemory):
                if not any(isinstance(m, reserva) for m in self.motores):
                    self.motores.append(reserva())
        self._cache = {}

    def traduzir_pagina(self, textos):
        """Devolve (traduções, quantos falharam). Falha = fica o texto original."""
        if not textos:
            return [], 0
        pendentes = [t for t in dict.fromkeys(textos) if t.strip() and t not in self._cache]
        if pendentes:
            entradas = [_preparar(t) for t in pendentes]
            ultimo_erro = None
            for motor in self.motores:
                try:
                    saidas = motor.traduzir(entradas, self.origem, self.destino)
                    for t, s in zip(pendentes, saidas):
                        self._cache[t] = _restaurar(t, s, self.destino)
                    break
                except Exception as erro:
                    ultimo_erro = erro
                    self.avisar(f"{motor.nome} falhou ({erro}); tentando o próximo")
            else:
                self.avisar(f"nenhum tradutor funcionou: {ultimo_erro}")
        saida = [self._cache.get(t, t) for t in textos]
        falhas = sum(1 for t in textos if t.strip() and t not in self._cache)
        return saida, falhas


def _preparar(texto):
    # Texto de mangá vem todo em maiúsculas; o tradutor entende melhor em
    # minúsculas, e no final voltamos para maiúsculas.
    return texto.capitalize() if texto.isupper() else texto


def _restaurar(original, traducao, destino):
    if original.isupper() and destino != "ja":
        return traducao.upper()
    return traducao
