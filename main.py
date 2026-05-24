"""
============================================================
main.py
Orquestrador principal do sistema de monitoramento de
sentimento de mercado via Google News RSS + BART-MNLI.

Uso:
    python main.py                    # Execução única (todos os tickers)
    python main.py --tickers BBDC4 ITSA4   # Tickers específicos
    python main.py --daemon           # Modo contínuo (repete a cada N min)
    python main.py --sem-traducao     # Desativa tradução PT→EN
    python main.py --ajuda            # Ajuda

Fluxo principal:
    1. Logging configurado
    2. Para cada ticker:
        a. Busca artigos no Google News RSS (rss_fetcher)
        b. Filtra artigos já processados (storage)
        c. Analisa sentimento com BART-MNLI (sentiment_analyzer)
        d. Salva resultados em CSV (storage)
        e. Exibe tabela no terminal (reporter)
    3. Exporta relatório Excel com resumo geral
    4. Exibe tabela de resumo no terminal
============================================================
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# ── Garante que src/ e config/ estejam no PYTHONPATH ─────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import (
    ACOES,
    INTERVALO_EXECUCAO_MIN,
    LOG_ARQUIVO,
    LOG_LEVEL,
)
from src.rss_fetcher       import buscar_artigos_ticker
from src.sentiment_analyzer import (
    analisar_lista_artigos,
    resumir_sentimentos,
)
from src.storage           import (
    salvar_artigos_csv,
    carregar_ids_processados,
    exportar_excel,
)
from src.reporter          import (
    console,
    exibir_cabecalho,
    exibir_artigos_ticker,
    exibir_resumo_geral,
    exibir_info,
    exibir_sucesso,
    exibir_erro,
)


# ── Configuração de Logging ───────────────────────────────────────────────────

def configurar_logging(nivel: str = LOG_LEVEL, arquivo: str = LOG_ARQUIVO) -> None:
    """
    Configura logging em dois handlers:
      1. FileHandler  → grava TUDO em arquivo (debug incluso)
      2. StreamHandler → exibe apenas WARNING+ no terminal
         (Rich já cuida da saída visual principal)

    O arquivo de log usa rotação manual por data no nome
    para não crescer indefinidamente.
    """
    from datetime import datetime
    Path(arquivo).parent.mkdir(parents=True, exist_ok=True)

    nivel_num = getattr(logging, nivel.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler de arquivo (nível DEBUG para diagnóstico)
    fh = logging.FileHandler(arquivo, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    # Handler de console (apenas WARNING+ para não poluir saída Rich)
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(formatter)

    logging.basicConfig(level=logging.DEBUG, handlers=[fh, ch])


# ── Lógica Principal ──────────────────────────────────────────────────────────

def executar_ciclo(tickers: list[str]) -> list[dict]:
    """
    Executa um ciclo completo de coleta → análise → persistência
    para a lista de tickers fornecida.

    Retorna lista de resumos por ticker (para o relatório final).
    """
    logger = logging.getLogger(__name__)

    # Carrega IDs já processados para evitar re-análise
    ids_processados = carregar_ids_processados()
    exibir_info(f"{len(ids_processados)} artigos já no histórico (serão ignorados).")

    todos_resumos: list[dict] = []

    for ticker in tickers:
        console.rule(f"[bold cyan]{ticker}[/bold cyan]")

        # ── 1. Coleta RSS ─────────────────────────────────────────────────────
        exibir_info(f"[{ticker}] Buscando notícias no Google News RSS...")
        artigos = buscar_artigos_ticker(ticker)

        if not artigos:
            exibir_info(f"[{ticker}] Nenhuma notícia encontrada.")
            todos_resumos.append(
                {
                    "ticker": ticker,
                    "total": 0,
                    "positivos": 0,
                    "negativos": 0,
                    "neutros": 0,
                    "inconclusivos": 0,
                    "score_medio": 0.0,
                    "sentimento_geral": "SEM DADOS",
                    "percentual_pos": 0.0,
                    "percentual_neg": 0.0,
                }
            )
            continue

        # ── 2. Filtra artigos já processados ──────────────────────────────────
        novos = [a for a in artigos if a.get("id") not in ids_processados]
        ja_vistos = len(artigos) - len(novos)

        if ja_vistos:
            exibir_info(f"[{ticker}] {ja_vistos} artigo(s) já analisados → ignorados.")

        if not novos:
            exibir_info(f"[{ticker}] Nenhum artigo novo para analisar.")
            continue

        exibir_info(f"[{ticker}] {len(novos)} artigo(s) novos para análise de sentimento.")

        # ── 3. Análise de Sentimento (BART-MNLI) ──────────────────────────────
        artigos_analisados = analisar_lista_artigos(novos, ticker=ticker)

        # ── 4. Exibe resultados no terminal ───────────────────────────────────
        exibir_artigos_ticker(ticker, artigos_analisados)

        # ── 5. Salva em CSV ───────────────────────────────────────────────────
        salvos = salvar_artigos_csv(artigos_analisados)
        exibir_sucesso(f"[{ticker}] {salvos} artigo(s) salvos em CSV.")

        # ── 6. Resumo do ticker ───────────────────────────────────────────────
        resumo = resumir_sentimentos(artigos_analisados)
        todos_resumos.append(resumo)

        # Atualiza IDs processados para próximas iterações no mesmo ciclo
        ids_processados.update(a.get("id", "") for a in artigos_analisados)

    return todos_resumos


def main() -> None:
    """Ponto de entrada principal."""

    # ── Parser de argumentos ──────────────────────────────────────────────────
    parser = argparse.ArgumentParser(
        description="Market Sentiment Monitor – Google News RSS + BART-MNLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        metavar="TICKER",
        help="Tickers específicos para analisar (padrão: todos)",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help=f"Executa em loop, repetindo a cada {INTERVALO_EXECUCAO_MIN} minutos.",
    )
    parser.add_argument(
        "--intervalo",
        type=int,
        default=INTERVALO_EXECUCAO_MIN,
        metavar="MIN",
        help=f"Intervalo em minutos para o modo daemon (padrão: {INTERVALO_EXECUCAO_MIN})",
    )
    parser.add_argument(
        "--sem-traducao",
        action="store_true",
        help="Desativa tradução PT→EN (análise em português, menos precisa)",
    )
    parser.add_argument(
        "--log-nivel",
        default=LOG_LEVEL,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help=f"Nível de log (padrão: {LOG_LEVEL})",
    )

    args = parser.parse_args()

    # ── Aplica configurações de runtime ──────────────────────────────────────
    configurar_logging(nivel=args.log_nivel)

    if args.sem_traducao:
        import config.settings as s
        s.TRADUZIR_PARA_INGLES = False
        exibir_info("Tradução PT→EN desativada.")

    # Valida tickers informados
    tickers_validos = list(ACOES.keys())
    if args.tickers:
        invalidos = [t for t in args.tickers if t not in tickers_validos]
        if invalidos:
            exibir_erro(
                f"Tickers inválidos: {invalidos}. "
                f"Disponíveis: {tickers_validos}"
            )
            sys.exit(1)
        tickers = args.tickers
    else:
        tickers = tickers_validos

    # ── Execução ──────────────────────────────────────────────────────────────
    if args.daemon:
        exibir_info(
            f"Modo daemon ativado. Executando a cada {args.intervalo} minuto(s). "
            "Pressione Ctrl+C para parar."
        )
        while True:
            exibir_cabecalho()
            resumos = executar_ciclo(tickers)

            if resumos:
                exibir_resumo_geral(resumos)
                exportar_excel(resumos)
                exibir_sucesso(f"Relatório Excel atualizado.")

            exibir_info(
                f"Próxima execução em {args.intervalo} minuto(s)... "
                "(Ctrl+C para parar)"
            )
            time.sleep(args.intervalo * 60)

    else:
        # Execução única
        exibir_cabecalho()
        resumos = executar_ciclo(tickers)

        if resumos:
            exibir_resumo_geral(resumos)
            exportar_excel(resumos)
            exibir_sucesso("Análise concluída. Relatório Excel gerado.")
        else:
            exibir_info("Nenhum dado novo coletado nesta execução.")


if __name__ == "__main__":
    main()
