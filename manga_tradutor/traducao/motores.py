"""Motores de tradução. Cada um traduz a lista de balões de uma página."""
import json
import os

from ..idiomas import IDIOMAS


class Motor:
    nome = ""

    def traduzir(self, textos, origem, destino):
        raise NotImplementedError


class MotorDeepL(Motor):
    """DeepL API (padrão). A chave grátis termina em ':fx'."""
    nome = "DeepL"

    def __init__(self, chave=None):
        import deepl
        chave = chave or os.environ.get("DEEPL_API_KEY")
        if not chave:
            raise ValueError("falta a chave da API do DeepL")
        self._t = deepl.Translator(chave)

    def traduzir(self, textos, origem, destino):
        # O resto da página vai como contexto (não é traduzido nem cobrado).
        contexto = " ".join(textos)
        res = self._t.translate_text(textos, source_lang=IDIOMAS[origem]["deepl_origem"],
                                     target_lang=IDIOMAS[destino]["deepl_destino"],
                                     context=contexto)
        return [r.text for r in res]


class MotorGoogle(Motor):
    """Google Tradutor gratuito (não oficial, pode bloquear sem aviso)."""
    nome = "Google"

    def traduzir(self, textos, origem, destino):
        sl, tl = IDIOMAS[origem]["google"], IDIOMAS[destino]["google"]
        try:
            from deep_translator import GoogleTranslator
            t = GoogleTranslator(source=sl, target=tl)
            return [t.translate(x) or x for x in textos]
        except Exception:
            # Algumas redes bloqueiam translate.google.com; o endpoint da API
            # (translate.googleapis.com) costuma continuar acessível.
            return [_google_api(x, sl, tl) or x for x in textos]


def _google_api(texto, sl, tl):
    import urllib.parse
    import urllib.request
    url = ("https://translate.googleapis.com/translate_a/single?client=gtx&dt=t&"
           + urllib.parse.urlencode({"sl": sl, "tl": tl, "q": texto}))
    with urllib.request.urlopen(url, timeout=20) as resp:
        dados = json.loads(resp.read().decode("utf-8"))
    return "".join(p[0] for p in dados[0] if p[0])


class MotorMyMemory(Motor):
    """MyMemory gratuito, reserva quando os outros falham."""
    nome = "MyMemory"

    def traduzir(self, textos, origem, destino):
        from deep_translator import MyMemoryTranslator
        t = MyMemoryTranslator(source=IDIOMAS[origem]["mymemory"],
                               target=IDIOMAS[destino]["mymemory"])
        return [t.translate(x) or x for x in textos]


class MotorClaude(Motor):
    """Claude: traduz a página inteira de uma vez, mantendo tom, gênero e nomes."""
    nome = "Claude"
    MODELO = "claude-opus-5-5"

    def __init__(self, chave=None):
        import anthropic
        self._cliente = anthropic.Anthropic(api_key=chave) if chave else anthropic.Anthropic()

    def traduzir(self, textos, origem, destino):
        numerados = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(textos))
        pedido = (
            f"Estes são os balões de fala de uma página de mangá, em ordem de leitura, "
            f"em {IDIOMAS[origem]['nome']}. Traduza cada um para {IDIOMAS[destino]['nome']}, "
            f"de forma natural para diálogo de mangá, usando o contexto da página. "
            f"Mantenha nomes próprios. O OCR pode ter erros de letra; corrija pelo contexto. "
            f"Devolva exatamente {len(textos)} traduções, na mesma ordem.\n\n{numerados}"
        )
        esquema = {
            "type": "object",
            "properties": {"traducoes": {"type": "array", "items": {"type": "string"}}},
            "required": ["traducoes"],
            "additionalProperties": False,
        }
        resp = self._cliente.beta.messages.create(
            model=self.MODELO,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": esquema}},
            messages=[{"role": "user", "content": pedido}],
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError("o Claude recusou traduzir esta página")
        texto = next(b.text for b in resp.content if b.type == "text")
        traducoes = json.loads(texto)["traducoes"]
        if len(traducoes) != len(textos):
            raise RuntimeError(f"o Claude devolveu {len(traducoes)} traduções para {len(textos)} balões")
        return traducoes


class MotorNenhum(Motor):
    """Não traduz: útil para testar OCR e layout sem internet."""
    nome = "nenhum"

    def traduzir(self, textos, origem, destino):
        return list(textos)
