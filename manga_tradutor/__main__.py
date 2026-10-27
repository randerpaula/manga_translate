"""Tradutor de mangá: python -m manga_tradutor <arquivo.pdf | .cbz | pasta | imagens...>

Fluxo:
 1. lê o PDF, CBZ ou o grupo de imagens
 2. verifica se as páginas são de mangá e pergunta os idiomas
 3. organiza as páginas em ordem
 4. encontra o texto, lê (OCR) e apaga o original
 5. guarda os textos (textos.json), traduz e escreve a tradução
 6. exporta o PDF/CBZ e as imagens traduzidas
"""
import argparse
import os
import sys

from .pipeline import (FORMATOS, IDIOMAS, MODOS_LIMPEZA, MOTORES, Config, Pipeline,
                       Projeto)


def perguntar(texto, padrao=None):
    resp = input(f"{texto}{f' [{padrao}]' if padrao else ''}: ").strip()
    return resp or padrao


def escolher_idioma(rotulo, padrao):
    print(f"\n{rotulo}:")
    for cod, nome in IDIOMAS.items():
        print(f"  {cod:4} {nome}")
    while True:
        cod = perguntar("Código do idioma", padrao)
        if cod in IDIOMAS:
            return cod
        print(f"  use um destes: {', '.join(IDIOMAS)}")


def mostrar(etapa, atual, total, msg):
    if etapa == "modelos":
        print(f"\r    {msg}   ", end="", flush=True)
    elif msg and atual < total:
        print(f"    {etapa}: {msg} ({atual + 1}/{total})")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Traduz os balões de fala de mangás.")
    ap.add_argument("entradas", nargs="*", help="arquivo PDF/CBZ, pasta ou imagens")
    ap.add_argument("-o", "--origem", choices=IDIOMAS, help="idioma original do mangá")
    ap.add_argument("-d", "--destino", choices=IDIOMAS, help="idioma de destino")
    ap.add_argument("-s", "--saida", default="saida_traduzida", help="pasta de saída")
    ap.add_argument("-f", "--formato", default="pdf", choices=FORMATOS, help="formato final")
    ap.add_argument("--motor", default="deepl", choices=MOTORES,
                    help="tradutor (se falhar, usa Google e depois MyMemory)")
    ap.add_argument("--chave", help="chave da API do DeepL ou do Claude "
                                    "(ou variáveis DEEPL_API_KEY / ANTHROPIC_API_KEY)")
    ap.add_argument("--limpeza", default="auto", choices=MODOS_LIMPEZA,
                    help="como apagar o texto original")
    ap.add_argument("--rtl", action=argparse.BooleanOptionalAction, default=None,
                    help="ordem de leitura da direita para a esquerda (padrão: sim, como em mangá; "
                         "use --no-rtl para quadrinhos ocidentais)")
    ap.add_argument("--fonte", help="arquivo .ttf para o texto traduzido")
    ap.add_argument("--sem-detector", action="store_true",
                    help="não usa o modelo de detecção (só balões brancos)")
    ap.add_argument("--usar-json", help="textos.json editado: usa esses textos e traduções")
    ap.add_argument("--projeto", help="pasta de um projeto salvo: só reescreve e exporta")
    ap.add_argument("--salvar-projeto", action="store_true",
                    help="salva o projeto em <saida>/projeto para corrigir depois")
    ap.add_argument("-y", "--sim", action="store_true", help="não faz perguntas")
    ap.add_argument("--dpi", type=int, default=200, help="resolução para PDFs")
    args = ap.parse_args(argv)

    cfg = Config(origem=args.origem, destino=args.destino, motor=args.motor,
                 chave_api=args.chave, rtl=args.rtl, fonte=args.fonte, dpi=args.dpi,
                 limpeza=args.limpeza, usar_detector=not args.sem_detector)
    pipe = Pipeline(cfg, progresso=mostrar)

    # Projeto salvo: aplica correções do textos.json e só reescreve.
    if args.projeto:
        projeto = Projeto.abrir(args.projeto)
        cfg.origem = cfg.origem or projeto.origem
        cfg.destino = cfg.destino or projeto.destino
        if args.usar_json:
            print(f"{projeto.aplicar_textos(args.usar_json)} balão(ões) atualizados do JSON")
        pipe.renderizar(projeto)
        arquivos = pipe.exportar(projeto, args.saida, args.formato)
        print(f"Pronto! Arquivo final: {arquivos[0]}")
        return

    if not args.entradas:
        ap.error("informe um arquivo PDF/CBZ, uma pasta ou imagens (ou --projeto)")

    print("1/6 Lendo arquivos...")
    projeto = pipe.carregar(args.entradas)
    if not projeto.paginas:
        sys.exit("Nenhuma página encontrada. Envie um PDF, CBZ ou imagens.")

    print("2/6 Verificando se é mangá...")
    pipe.verificar_manga(projeto)
    for p in projeto.paginas:
        print(f"    pág. {p.numero}: {'mangá' if p.eh_manga else 'não parece mangá'} "
              f"({p.pontuacao:.2f}) - {'; '.join(p.motivos)}")
    if not any(p.eh_manga for p in projeto.paginas):
        if args.sim or perguntar("Nenhuma página parece mangá. Processar mesmo assim? (s/n)", "n") != "s":
            sys.exit("Encerrado: o arquivo não parece ser um mangá.")
        for p in projeto.paginas:
            p.eh_manga = True
    cfg.origem = cfg.origem or ("en" if args.sim else escolher_idioma("Idioma ORIGINAL do mangá", "en"))
    cfg.destino = cfg.destino or ("pt" if args.sim else escolher_idioma("Traduzir PARA qual idioma", "pt"))

    nomes = [os.path.basename(p.origem) for p in projeto.paginas]
    print(f"3/6 Páginas em ordem: {nomes[:10]}{' ...' if len(nomes) > 10 else ''}")

    print("4/6 Procurando o texto, lendo e apagando o original...")
    pipe.analisar(projeto)
    for p in projeto.paginas:
        if p.eh_manga:
            print(f"    pág. {p.numero}: {len(p.baloes)} balão(ões)")

    print("5/6 Traduzindo e escrevendo...")
    falhas = 0
    if args.usar_json:
        print(f"    {projeto.aplicar_textos(args.usar_json)} balão(ões) vindos de {args.usar_json}")
    falhas = pipe.traduzir(projeto)
    pipe.renderizar(projeto)

    print("6/6 Exportando...")
    arquivos = pipe.exportar(projeto, args.saida, args.formato)
    if args.salvar_projeto:
        print(f"    projeto salvo em {os.path.dirname(projeto.salvar(os.path.join(args.saida, 'projeto')))}")
    print(f"Pronto! Arquivo final: {arquivos[0]}")
    caminho_json = os.path.join(args.saida, "textos.json")
    print(f"    textos em {caminho_json} (edite e rode com --usar-json para corrigir)")
    if falhas:
        print(f"ATENÇÃO: {falhas} balão(ões) ficaram no idioma original porque a tradução "
              f"falhou (sem internet?). Corrija em {caminho_json} e rode com --usar-json.")


if __name__ == "__main__":
    main()
