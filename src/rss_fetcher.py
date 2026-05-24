"""
============================================================
src/rss_fetcher.py
Coleta de notícias de MÚLTIPLAS fontes:

  FONTE 1 — Google News RSS (busca por termos do ticker)
  FONTE 2 — Feeds RSS extras (Bloomberg Línea, Infomoney,
             Brazil Journal, Neofeed, etc.) — varridos
             inteiros e filtrados por termos do ticker
  FONTE 3 — API da CVM (fatos relevantes oficiais,
             filtrados por CNPJ da empresa)

Fluxo por ticker:
  1. Busca no Google News RSS (por cada termo de busca)
  2. Varre cada feed RSS extra ativo e filtra por termos
  3. Consulta fatos relevantes na CVM via API pública
  4. Unifica tudo, deduplica por hash MD5 da URL
  5. Filtra por idade máxima (IDADE_MAXIMA_HORAS)
  6. Retorna lista com no máximo MAX_ARTIGOS_POR_TICKER itens

COMO ADICIONAR NOVO SITE RSS:
  → Edite config/settings.py → FEEDS_RSS_EXTRAS
  → Não precisa alterar este arquivo

COMO AJUSTAR O PERÍODO:
  → Edite config/settings.py → IDADE_MAXIMA_HORAS
============================================================
"""

import logging
import re
import time
import hashlib
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
from typing import Optional

import feedparser

from config.settings import (
    GNEWS_RSS_TEMPLATE,
    FEEDS_RSS_EXTRAS,
    MAX_ARTIGOS_POR_TICKER,
    IDADE_MAXIMA_HORAS,
    ACOES,
    CVM_ATIVO,
    CVM_CNPJ,
    MAX_FATOS_CVM,
)

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


# ── Utilitários comuns ────────────────────────────────────────────────────────

def _gera_id(url: str) -> str:
    """Hash MD5 truncado da URL — usado como ID único para deduplicação."""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _parse_data(entry) -> Optional[datetime]:
    """Extrai a data de publicação de um entry feedparser como datetime UTC."""
    for campo in ("published_parsed", "updated_parsed"):
        val = getattr(entry, campo, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _eh_recente(data_pub: Optional[datetime]) -> bool:
    """Retorna True se o artigo está dentro do período configurado."""
    if data_pub is None:
        return True   # sem data → aceita (melhor false positive que false negative)
    limite = datetime.now(tz=timezone.utc) - timedelta(hours=IDADE_MAXIMA_HORAS)
    return data_pub >= limite


def _limpa_html(texto: str) -> str:
    """Remove tags HTML simples do texto."""
    return re.sub(r"<[^>]+>", "", texto).strip()


def _monta_artigo(ticker: str, entry, fonte: str, termo: str) -> dict:
    """
    Constrói o dicionário padrão de artigo a partir de um entry feedparser.
    Separa o nome da fonte do título quando o Google News injeta "Título - Fonte".
    """
    titulo = getattr(entry, "title", "").strip()
    fonte_suffix = ""
    if " - " in titulo:
        partes = titulo.rsplit(" - ", 1)
        titulo = partes[0].strip()
        fonte_suffix = partes[1].strip()

    descricao = _limpa_html(getattr(entry, "summary", "") or "")
    url       = getattr(entry, "link", "") or ""
    data_pub  = _parse_data(entry)

    return {
        "ticker":      ticker,
        "id":          _gera_id(url),
        "titulo":      titulo,
        "descricao":   descricao,
        "url":         url,
        "fonte":       fonte or fonte_suffix or "Desconhecida",
        "data_pub":    data_pub.isoformat() if data_pub else "desconhecida",
        "termo_busca": termo,
        "origem":      "rss",
    }


# ── FONTE 1: Google News RSS ──────────────────────────────────────────────────

def _buscar_gnews(ticker: str, termos: list[str],
                  vistos: set, limite: int, delay: float) -> list[dict]:
    """
    Busca artigos no Google News RSS para cada termo de busca do ticker.
    Retorna lista de artigos novos (não presentes em 'vistos').
    """
    coletados = []

    for termo in termos:
        if len(coletados) >= limite:
            break

        url_rss = GNEWS_RSS_TEMPLATE.format(query=quote_plus(termo))
        logger.debug(f"[{ticker}][GNews] {url_rss}")

        try:
            feed = feedparser.parse(
                url_rss,
                agent=HEADERS["User-Agent"],
                request_headers=HEADERS,
            )
        except Exception as e:
            logger.warning(f"[{ticker}][GNews] Erro ao parsear '{termo}': {e}")
            time.sleep(delay)
            continue

        if not feed.entries:
            logger.debug(f"[{ticker}][GNews] Nenhuma entrada para '{termo}'.")
            time.sleep(delay)
            continue

        logger.info(f"[{ticker}][GNews] '{termo}' → {len(feed.entries)} entradas")

        for entry in feed.entries:
            if len(coletados) >= limite:
                break

            url = getattr(entry, "link", "") or ""
            if not url:
                continue

            art_id = _gera_id(url)
            if art_id in vistos:
                continue

            data_pub = _parse_data(entry)
            if not _eh_recente(data_pub):
                continue

            fonte = (
                getattr(entry, "source", {}).get("title", "")
                or feed.feed.get("title", "Google News")
            )

            artigo = _monta_artigo(ticker, entry, fonte, termo)
            vistos.add(art_id)
            coletados.append(artigo)

        time.sleep(delay)

    return coletados


# ── FONTE 2: Feeds RSS extras ─────────────────────────────────────────────────

def _termo_presente(texto: str, termos: list[str]) -> bool:
    """
    Verifica se algum termo de busca do ticker aparece no texto.
    Comparação case-insensitive.
    """
    texto_lower = texto.lower()
    return any(t.lower() in texto_lower for t in termos)


def _buscar_feed_extra(ticker: str, termos: list[str], feed_cfg: dict,
                       vistos: set, limite: int) -> list[dict]:
    """
    Varre um feed RSS extra inteiro e filtra artigos que mencionam
    algum dos termos de busca do ticker no título ou descrição.

    Esta é a diferença em relação ao Google News:
    - Google News → já filtra por termo na busca
    - Feeds extras → baixamos o feed completo e filtramos localmente
    """
    nome_feed = feed_cfg["nome"]
    url_feed  = feed_cfg["url"]
    coletados = []

    logger.debug(f"[{ticker}][{nome_feed}] Varrendo {url_feed}")

    try:
        feed = feedparser.parse(
            url_feed,
            agent=HEADERS["User-Agent"],
            request_headers=HEADERS,
        )
    except Exception as e:
        logger.warning(f"[{ticker}][{nome_feed}] Erro ao parsear: {e}")
        return []

    if not feed.entries:
        logger.debug(f"[{ticker}][{nome_feed}] Feed vazio ou inacessível.")
        return []

    logger.debug(
        f"[{ticker}][{nome_feed}] {len(feed.entries)} entradas no feed — filtrando..."
    )

    for entry in feed.entries:
        if len(coletados) >= limite:
            break

        url = getattr(entry, "link", "") or ""
        if not url:
            continue

        art_id = _gera_id(url)
        if art_id in vistos:
            continue

        data_pub = _parse_data(entry)
        if not _eh_recente(data_pub):
            continue

        # ── Filtro por relevância ─────────────────────────────────────────────
        # Só aceita se o ticker ou nome da empresa aparecer no título/descrição
        titulo    = getattr(entry, "title", "") or ""
        descricao = _limpa_html(getattr(entry, "summary", "") or "")
        texto_completo = f"{titulo} {descricao}"

        if not _termo_presente(texto_completo, termos):
            continue   # artigo não fala sobre este ticker → ignora

        artigo = _monta_artigo(ticker, entry, nome_feed, nome_feed)
        vistos.add(art_id)
        coletados.append(artigo)
        logger.debug(f"[{ticker}][{nome_feed}] ✔ '{titulo[:50]}'")

    if coletados:
        logger.info(
            f"[{ticker}][{nome_feed}] {len(coletados)} artigo(s) relevantes encontrados."
        )

    return coletados


def _buscar_todos_feeds_extras(ticker: str, termos: list[str],
                                vistos: set, limite: int,
                                delay: float) -> list[dict]:
    """Itera sobre todos os feeds extras ativos e coleta artigos relevantes."""
    feeds_ativos = [f for f in FEEDS_RSS_EXTRAS if f.get("ativo", False)]
    todos = []

    for feed_cfg in feeds_ativos:
        if len(todos) >= limite:
            break
        artigos = _buscar_feed_extra(ticker, termos, feed_cfg, vistos, limite - len(todos))
        todos.extend(artigos)
        time.sleep(delay)

    return todos


# ── FONTE 3: API CVM — Fatos Relevantes ──────────────────────────────────────

def _buscar_fatos_cvm(ticker: str, vistos: set) -> list[dict]:
    """
    Busca fatos relevantes na API pública da CVM usando o CNPJ da empresa.

    A CVM disponibiliza um CSV de documentos por empresa no endpoint:
    https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFIN/DADOS/

    Usamos o endpoint de fatos relevantes do sistema ENET (ITR/FR),
    filtrando por CNPJ e data.

    Retorna artigos no mesmo formato padrão do projeto, com
    origem="cvm" para identificação nos relatórios.
    """
    if not CVM_ATIVO:
        return []

    cnpj = CVM_CNPJ.get(ticker)
    if not cnpj:
        logger.debug(f"[{ticker}][CVM] CNPJ não configurado — pulando.")
        return []

    import urllib.request
    import json
    from urllib.parse import urlencode

    coletados = []

    # ── Endpoint da API de dados abertos da CVM ───────────────────────────────
    # A CVM disponibiliza arquivos CSV com metadados de documentos por ano.
    # Usamos o endpoint de busca de documentos recentes via parâmetros de URL.
    #
    # URL de fatos relevantes do ENET (sistema público da CVM):
    # https://www.rad.cvm.gov.br/ENET/frmConsultaExternaCVM.aspx
    # mas para API programática usamos o endpoint de dados abertos:
    base_url = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FR/DADOS/"

    ano_atual = datetime.now().year
    anos = [ano_atual, ano_atual - 1]   # ano atual + anterior (caso seja início do ano)

    limite = MAX_FATOS_CVM
    data_corte = datetime.now(tz=timezone.utc) - timedelta(hours=IDADE_MAXIMA_HORAS)

    for ano in anos:
        if len(coletados) >= limite:
            break

        url_csv = f"{base_url}fr_cia_aberta_{ano}.csv"
        logger.debug(f"[{ticker}][CVM] Consultando {url_csv}")

        try:
            req = urllib.request.Request(
                url_csv,
                headers={"User-Agent": HEADERS["User-Agent"]},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                conteudo = resp.read().decode("latin-1")
        except Exception as e:
            logger.warning(f"[{ticker}][CVM] Erro ao baixar CSV {ano}: {e}")
            continue

        # Processa o CSV linha por linha (sem pandas para evitar dependência extra)
        linhas = conteudo.splitlines()
        if not linhas:
            continue

        # Cabeçalho do CSV da CVM:
        # CNPJ_CIA;DENOM_CIA;DT_REFER;DT_RECEB;ID_DOC;LINK_DOC;...
        cabecalho = [c.strip() for c in linhas[0].split(";")]

        try:
            idx_cnpj   = cabecalho.index("CNPJ_CIA")
            idx_dt     = cabecalho.index("DT_RECEB")
            idx_link   = cabecalho.index("LINK_DOC") if "LINK_DOC" in cabecalho else -1
            idx_assunto = cabecalho.index("ASSUNTO") if "ASSUNTO" in cabecalho else -1
            idx_denom  = cabecalho.index("DENOM_CIA")
        except ValueError as e:
            logger.warning(f"[{ticker}][CVM] Coluna não encontrada no CSV: {e}")
            continue

        # Normaliza CNPJ: remove pontuação para comparação
        cnpj_limpo = re.sub(r"\D", "", cnpj)

        for linha in linhas[1:]:
            if len(coletados) >= limite:
                break

            campos = [c.strip() for c in linha.split(";")]
            if len(campos) <= max(idx_cnpj, idx_dt):
                continue

            # Filtra pelo CNPJ da empresa
            cnpj_linha = re.sub(r"\D", "", campos[idx_cnpj])
            if cnpj_linha != cnpj_limpo:
                continue

            # Filtra pela data
            try:
                dt_str = campos[idx_dt][:10]   # "YYYY-MM-DD"
                dt_pub = datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if dt_pub < data_corte:
                    continue
            except Exception:
                pass   # sem data → aceita

            # Monta URL do documento
            link = campos[idx_link].strip() if idx_link >= 0 and idx_link < len(campos) else ""
            if not link:
                link = f"https://www.rad.cvm.gov.br/ENET/frmConsultaExternaCVM.aspx?CNPJ={cnpj}"

            art_id = _gera_id(link)
            if art_id in vistos:
                continue

            assunto = campos[idx_assunto].strip() if idx_assunto >= 0 and idx_assunto < len(campos) else "Fato Relevante"
            empresa = campos[idx_denom].strip() if idx_denom < len(campos) else ticker

            coletados.append({
                "ticker":      ticker,
                "id":          art_id,
                "titulo":      f"[CVM] {empresa} — {assunto}",
                "descricao":   f"Fato relevante publicado na CVM em {campos[idx_dt][:10]}. Empresa: {empresa}.",
                "url":         link,
                "fonte":       "CVM — Dados Abertos",
                "data_pub":    campos[idx_dt][:10],
                "termo_busca": cnpj,
                "origem":      "cvm",
            })
            vistos.add(art_id)

    if coletados:
        logger.info(f"[{ticker}][CVM] {len(coletados)} fato(s) relevante(s) encontrado(s).")
    else:
        logger.debug(f"[{ticker}][CVM] Nenhum fato relevante no período.")

    return coletados


# ── Orquestrador principal ────────────────────────────────────────────────────

def buscar_artigos_ticker(ticker: str, delay_segundos: float = 1.5) -> list[dict]:
    """
    Coleta artigos de TODAS as fontes para um ticker:
      1. Google News RSS
      2. Feeds RSS extras (Bloomberg Línea, Infomoney, Brazil Journal, Neofeed...)
      3. Fatos relevantes da CVM

    Todos os artigos passam pelo mesmo filtro de idade e deduplicação.

    Parâmetros
    ----------
    ticker : str
        Código do ticker (ex: "BBDC4")
    delay_segundos : float
        Pausa entre requisições para não sobrecarregar os servidores.

    Retorna
    -------
    list[dict]
        Lista unificada de artigos com os campos padrão do projeto.
    """
    config = ACOES.get(ticker)
    if not config:
        logger.error(f"Ticker '{ticker}' não encontrado em ACOES.")
        return []

    termos  = config["termos_busca"]
    vistos: set[str] = set()
    todos:  list[dict] = []

    logger.info(f"[{ticker}] ── Iniciando coleta multi-fonte ──")

    # ── 1. Google News ────────────────────────────────────────────────────────
    limite_gnews = MAX_ARTIGOS_POR_TICKER // 2   # divide o limite entre fontes
    artigos_gnews = _buscar_gnews(ticker, termos, vistos, limite_gnews, delay_segundos)
    todos.extend(artigos_gnews)
    logger.info(f"[{ticker}] Google News: {len(artigos_gnews)} artigo(s)")

    # ── 2. Feeds extras ───────────────────────────────────────────────────────
    limite_extras = MAX_ARTIGOS_POR_TICKER - len(todos)
    if limite_extras > 0:
        artigos_extras = _buscar_todos_feeds_extras(
            ticker, termos, vistos, limite_extras, delay_segundos
        )
        todos.extend(artigos_extras)
        logger.info(f"[{ticker}] Feeds extras: {len(artigos_extras)} artigo(s)")

    # ── 3. CVM ────────────────────────────────────────────────────────────────
    fatos_cvm = _buscar_fatos_cvm(ticker, vistos)
    todos.extend(fatos_cvm)   # fatos CVM não contam no limite de artigos RSS

    logger.info(
        f"[{ticker}] Total coletado: {len(todos)} item(ns) "
        f"(GNews: {len(artigos_gnews)} | "
        f"Extras: {len(artigos_extras) if limite_extras > 0 else 0} | "
        f"CVM: {len(fatos_cvm)})"
    )
    return todos


def buscar_todos_tickers(tickers: list[str] | None = None) -> dict[str, list[dict]]:
    """Itera sobre todos os tickers e retorna mapa ticker → artigos."""
    tickers = tickers or list(ACOES.keys())
    return {ticker: buscar_artigos_ticker(ticker) for ticker in tickers}
