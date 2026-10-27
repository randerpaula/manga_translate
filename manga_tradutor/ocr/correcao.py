"""Correção do texto lido pelo OCR com uma lista de palavras do idioma.

As fontes de mangá enganam o Tesseract sempre do mesmo jeito: o D vira P, V
ou O ("PIP", "VIDN'T", "ANO"), o I vira "|", falta o apóstrofo ("DONT") e o
hífen dos honoríficos some ("HANAKOKUN"). Para cada palavra que não está na
lista, tentamos essas trocas e ficamos com a palavra mais comum que aparecer.
"""
import functools
import itertools
import os
import re

# Trocas típicas em letras maiúsculas (lido -> provável).
_TROCAS_MAIUSC = {"P": "D", "V": "D", "O": "D", "0": "O", "|": "I", "1": "IT", "5": "S",
                  "$": "S", "8": "B", "N": "Y", "K": "R", "J": "L", "Q": "O", "4": "A"}
_TROCAS_MINUSC = {"|": "l", "1": "l", "0": "o", "5": "s", "$": "s", "q": "g"}
_MAX_TROCAS = 2
# Palavras que existem com e sem apóstrofo: não mexemos.
_SEM_APOSTROFO = {"its", "were", "well", "ill", "id", "hell", "shell", "wed", "shed", "hes",
                  "shes", "whos"}
_HONORIFICOS = ("KUN", "CHAN", "SAN", "SENPAI", "SEMPAI", "SENSEI", "SAMA")
_PALAVRA = re.compile(r"^([^\w|$'\[]*)([\w|$'’‘\[]+?)([^\w|$]*)$")


@functools.lru_cache(maxsize=None)
def _lista(idioma):
    """{palavra: posição no ranking de frequência} ou {} se não houver lista."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"palavras_{idioma}.txt")
    if not os.path.exists(caminho):
        return {}
    with open(caminho, encoding="utf-8") as f:
        palavras = [linha.strip() for linha in f if linha.strip() and not linha.startswith("#")]
    return {p: i for i, p in enumerate(palavras)}


def conhecida(palavra, idioma):
    lista = _lista(idioma)
    return palavra.lower().replace("’", "'") in lista


def proporcao_conhecidas(texto, idioma):
    """Fração das palavras (2+ letras) que existem no idioma; None sem lista."""
    lista = _lista(idioma)
    if not lista:
        return None
    palavras = [re.sub(r"[^\w']", "", p).lower() for p in texto.split()]
    palavras = [p for p in palavras if sum(c.isalpha() for c in p) >= 2]
    if not palavras:
        return 0.0
    return sum(p in lista or p.replace("-", "") in lista for p in palavras) / len(palavras)


def proporcao_plausivel(texto, idioma):
    """Fração das letras que estão em palavras plausíveis; None sem lista.

    Plausível = palavra do idioma com 3+ letras (ou curta e muito comum, como
    OH e HI), ou palavra de 4+ letras sem números (nomes como YASHIRO,
    risadas como TEHE). Lixo de OCR vem em pedaços curtos e mistos.
    """
    lista = _lista(idioma)
    if not lista:
        return None
    total = boas = 0
    for p in texto.split():
        limpa = re.sub(r"[^\w']", "", p.replace("’", "'"))
        n = sum(c.isalnum() for c in limpa)
        total += n
        sem_hifen = limpa.lower()
        rank = lista.get(sem_hifen)
        if ((rank is not None and (n >= 3 or rank < 1500))
                or (n >= 4 and limpa.isalpha())):
            boas += n
    return boas / total if total else 0.0


def corrigir(texto, idioma):
    """Corrige o texto palavra por palavra. Sem lista para o idioma, devolve igual."""
    if not _lista(idioma):
        return texto
    tokens = texto.split()
    letras = [c for c in texto if c.isalpha()]
    maiusculo = bool(letras) and sum(c.isupper() for c in letras) >= 0.7 * len(letras)
    saida = []
    for i, t in enumerate(tokens):
        vizinhos = tokens[i - 1:i] + tokens[i + 1:i + 2]
        seguinte = tokens[i + 1] if i + 1 < len(tokens) else ""
        if (maiusculo and len(t) <= 2 and t.isdigit() and seguinte
                and any(v.isalpha() for v in vizinhos)
                and not (len(seguinte) > 3 and seguinte.upper().endswith("S"))):  # "15 POINTS"
            # "THIS 15 A..." / "WANT US 10 DO": número curto no meio de palavras
            # em maiúsculas quase sempre é palavra lida errado.
            cand = _melhor_troca(t, idioma)
            if cand and cand[1] < 300:
                saida.append(cand[0].upper())
                continue
        saida.append(_corrigir_token(t, idioma))
    return " ".join(saida)


def _corrigir_token(token, idioma):
    m = _PALAVRA.match(token)
    if not m:
        return token
    antes, nucleo, depois = m.groups()
    nucleo = nucleo.replace("’", "'").replace("‘", "'")
    if nucleo in ("|", "1", "[") and idioma == "en" and not antes.endswith("#"):
        return antes + "I" + depois
    if nucleo.isdigit() or len(nucleo) < 2:
        return antes + nucleo + depois
    return antes + _corrigir_nucleo(nucleo, idioma) + depois


def _corrigir_nucleo(nucleo, idioma):
    lista = _lista(idioma)
    minusc = nucleo.lower()
    rank = lista.get(minusc)

    com = _apostrofo(minusc, rank, idioma)
    if com:
        return _mesma_caixa(com, nucleo)
    if rank is not None and rank < 15000:
        return nucleo

    # Honorífico grudado: HANAKOKUN -> HANAKO-KUN.
    maiusc = nucleo.upper()
    for h in _HONORIFICOS:
        if maiusc.endswith(h) and len(nucleo) - len(h) >= 3 and nucleo[-len(h) - 1] != "-":
            return nucleo[:-len(h)] + "-" + nucleo[-len(h):]

    melhor = _melhor_troca(nucleo, idioma)
    if melhor is None:
        melhor = _separar(nucleo, idioma)
    if melhor is not None:
        cand, rank_cand = melhor
        # Palavra rara que vira uma bem comum (ANO -> AND) também é corrigida.
        if rank is None or (rank_cand * 10 < rank):
            return _mesma_caixa(_apostrofo(cand, rank_cand, idioma) or cand, nucleo)
    return nucleo


def _melhor_troca(nucleo, idioma):
    lista = _lista(idioma)
    trocas = _TROCAS_MAIUSC if nucleo.upper() == nucleo else dict(_TROCAS_MINUSC, N="Y", P="D")
    posicoes = [i for i, c in enumerate(nucleo) if c in trocas]
    if not posicoes or len(posicoes) > 8:
        return None
    melhor = None
    for n in range(1, min(_MAX_TROCAS, len(posicoes)) + 1):
        for escolha in itertools.combinations(posicoes, n):
            # Cada caractere pode ter mais de uma troca possível ("1" -> I ou T).
            for opcoes in itertools.product(*(trocas[nucleo[i]] for i in escolha)):
                letras = list(nucleo)
                for i, nova in zip(escolha, opcoes):
                    letras[i] = nova
                cand = "".join(letras).lower()
                r = lista.get(cand)
                if r is not None and (melhor is None or r < melhor[1]):
                    melhor = (cand, r)
        if melhor:          # prefere o menor número de trocas
            return melhor
    return None


def _apostrofo(minusc, rank, idioma):
    """Apóstrofo que sumiu: DONT -> DON'T, YOURE -> YOU'RE. None se não for o caso."""
    if "'" in minusc or minusc in _SEM_APOSTROFO:
        return None
    com = _com_apostrofo(idioma).get(minusc)
    if com and (rank is None or _lista(idioma)[com] < rank):
        return com
    return None


def _separar(nucleo, idioma):
    """Palavras grudadas: ABIT -> A BIT, IKNOW -> I KNOW."""
    lista = _lista(idioma)
    if len(nucleo) < 4 or not nucleo.isalpha():
        return None
    melhor = None
    for i in range(1, len(nucleo)):
        a, b = nucleo[:i].lower(), nucleo[i:].lower()
        if (len(a) == 1 and a not in "ai") or (len(b) == 1 and b not in "ai"):
            continue
        ra, rb = lista.get(a), lista.get(b)
        if ra is not None and rb is not None and max(ra, rb) < 3000:
            if melhor is None or max(ra, rb) < melhor[1]:
                melhor = (a + " " + b, max(ra, rb))
    return melhor


@functools.lru_cache(maxsize=None)
def _com_apostrofo(idioma):
    return {p.replace("'", ""): p for p in _lista(idioma) if "'" in p}


def _mesma_caixa(palavra, modelo):
    if modelo.upper() == modelo:
        return palavra.upper()
    if modelo[0].isupper():
        return palavra[0].upper() + palavra[1:]
    return palavra
