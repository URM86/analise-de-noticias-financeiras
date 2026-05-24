"""
============================================================
src/reporter.py
Exibição de resultados no terminal usando Rich.

Mostra os scores dos dois modelos (BART e FinBERT) lado a lado
e destaca qual venceu em cada artigo.
============================================================
"""

import logging
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

logger = logging.getLogger(__name__)

console = Console()

COR_SENTIMENTO = {
    "POSITIVO":     "bold green",
    "NEGATIVO":     "bold red",
    "NEUTRO":       "dim white",
    "INCONCLUSIVO": "yellow",
}

EMOJI_SENTIMENTO = {
    "POSITIVO":     "📈",
    "NEGATIVO":     "📉",
    "NEUTRO":       "➡️",
    "INCONCLUSIVO": "❓",
}

LABEL_PT = {
    "positive": "POSITIVO",
    "negative": "NEGATIVO",
    "neutral":  "NEUTRO",
}


def exibir_cabecalho() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]Market Sentiment Monitor[/bold cyan]\n"
            "[dim]Google News RSS · BART-MNLI + FinBERT · Votação por confiança[/dim]\n"
            f"[dim]{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}[/dim]",
            border_style="cyan",
        )
    )


def exibir_artigos_ticker(ticker: str, artigos: list[dict]) -> None:
    """
    Tabela com os dois modelos lado a lado e o vencedor destacado.
    Colunas: Data | Título | BART | FinBERT | Vencedor | Sentimento | Conf.
    """
    if not artigos:
        console.print(f"[yellow][{ticker}] Nenhum artigo encontrado.[/yellow]")
        return

    tabela = Table(
        title=f"[bold]{ticker}[/bold] – {len(artigos)} notícia(s)",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold blue",
        expand=True,
    )

    tabela.add_column("Data",       style="dim",      width=10)
    tabela.add_column("Título",                       width=36)
    tabela.add_column("BART",       justify="center", width=12)
    tabela.add_column("FinBERT",    justify="center", width=12)
    tabela.add_column("Vencedor",   justify="center", width=10)
    tabela.add_column("Sentimento", justify="center", width=14)
    tabela.add_column("Conf.",      justify="right",  width=6)

    for artigo in artigos:
        sentimento = artigo.get("sentimento_pt", "INCONCLUSIVO")
        cor        = COR_SENTIMENTO.get(sentimento, "white")
        emoji      = EMOJI_SENTIMENTO.get(sentimento, "")
        confianca  = artigo.get("confianca", 0.0)
        vencedor   = artigo.get("modelo_vencedor", "")
        concordou  = artigo.get("concordancia", False)

        # Célula BART
        lb      = artigo.get("label_bart", "")
        sb      = artigo.get("score_bart", 0.0)
        cor_b   = COR_SENTIMENTO.get(LABEL_PT.get(lb, ""), "dim")
        cell_b  = Text(f"{lb[:3].upper()} {sb:.0%}", style=cor_b)

        # Célula FinBERT
        lf      = artigo.get("label_finbert", "")
        sf      = artigo.get("score_finbert", 0.0)
        cor_f   = COR_SENTIMENTO.get(LABEL_PT.get(lf, ""), "dim")
        cell_f  = Text(f"{lf[:3].upper()} {sf:.0%}", style=cor_f)

        # Vencedor + ícone de concordância
        icon_v  = f"{'✔ ' if concordou else ''}{vencedor}"

        data_pub = artigo.get("data_pub", "")
        if "T" in data_pub:
            data_pub = data_pub.split("T")[0]

        tabela.add_row(
            data_pub[:10],
            artigo.get("titulo", "")[:36],
            cell_b,
            cell_f,
            icon_v,
            Text(f"{emoji} {sentimento}", style=cor),
            f"{confianca:.0%}",
        )

    console.print(tabela)


def exibir_resumo_geral(resumos: list[dict]) -> None:
    """
    Tabela de resumo geral com vitórias por modelo e % de concordância.
    """
    if not resumos:
        console.print("[red]Nenhum resumo disponível.[/red]")
        return

    tabela = Table(
        title="[bold]RESUMO GERAL – Sentimento de Mercado[/bold]",
        box=box.DOUBLE_EDGE,
        header_style="bold magenta",
    )

    tabela.add_column("Ticker",      style="bold",     width=8)
    tabela.add_column("Notícias",    justify="center", width=9)
    tabela.add_column("📈 Pos",      justify="center", width=7)
    tabela.add_column("📉 Neg",      justify="center", width=7)
    tabela.add_column("➡ Neu",       justify="center", width=7)
    tabela.add_column("Sentimento",  justify="center", width=14)
    tabela.add_column("Conf. Méd",   justify="right",  width=9)
    tabela.add_column("BART wins",   justify="center", width=9)
    tabela.add_column("FIN wins",    justify="center", width=8)
    tabela.add_column("Concorda %",  justify="right",  width=10)

    for r in resumos:
        sent  = r.get("sentimento_geral", "INCONCLUSIVO")
        cor   = COR_SENTIMENTO.get(sent, "white")
        emoji = EMOJI_SENTIMENTO.get(sent, "")

        tabela.add_row(
            r.get("ticker", ""),
            str(r.get("total", 0)),
            f"[green]{r.get('positivos', 0)}[/green]",
            f"[red]{r.get('negativos', 0)}[/red]",
            str(r.get("neutros", 0)),
            Text(f"{emoji} {sent}", style=cor),
            f"{r.get('score_medio', 0.0):.0%}",
            str(r.get("bart_vitorias", 0)),
            str(r.get("finbert_vitorias", 0)),
            f"{r.get('pct_concordancia', 0.0):.0f}%",
        )

    console.print()
    console.print(tabela)
    console.print()


def exibir_erro(mensagem: str) -> None:
    console.print(f"[bold red]❌ ERRO:[/bold red] {mensagem}")

def exibir_sucesso(mensagem: str) -> None:
    console.print(f"[bold green]✔[/bold green] {mensagem}")

def exibir_info(mensagem: str) -> None:
    console.print(f"[cyan]ℹ[/cyan] {mensagem}")
