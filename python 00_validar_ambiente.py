"""
Validação inicial do ambiente do sistema de Análise de Sentimento de Mercado.

Este script deve ser executado antes da primeira execução de main.py e
sempre que o ambiente for reinstalado ou atualizado.

Ele valida:
1. Versão do Python
2. Ambiente virtual ativo
3. Pacotes Python essenciais instalados
4. Estrutura de diretórios e arquivos do projeto
5. Configurações em config/settings.py (tickers, feeds, campos obrigatórios)
6. Conectividade de rede com o Google News RSS
7. Conectividade com a API de Dados Abertos da CVM
8. Acesso ao Hugging Face (download dos modelos)
9. Espaço em disco suficiente para os modelos
10. Permissões de escrita em data/ e logs/

Este script não executa análise de sentimento nem coleta notícias.
"""

from __future__ import annotations

import importlib.util
import platform
import shutil
import sys
import urllib.request
import urllib.error
from pathlib import Path


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

PYTHON_MINIMO = (3, 10)

PACOTES_ESSENCIAIS = {
    "transformers": "transformers",
    "torch": "torch",
    "feedparser": "feedparser",
    "pandas": "pandas",
    "openpyxl": "openpyxl",
    "rich": "rich",
    "tqdm": "tqdm",
    "deep_translator": "deep_translator",
    "requests": "requests",
}

# Espaço mínimo em disco para baixar FinBERT (~400 MB) + BART (~1,6 GB)
# com margem de segurança de 1 GB para arquivos de cache adicionais
ESPACO_DISCO_MINIMO_GB = 3.5

# URLs para verificação de conectividade
URL_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q=BBDC4&hl=pt-BR&gl=BR&ceid=BR:pt-419"
URL_CVM_API = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/"
URL_HUGGINGFACE = "https://huggingface.co"

TIMEOUT_REDE = 10  # segundos


# ---------------------------------------------------------------------------
# Registro de mensagens
# ---------------------------------------------------------------------------

def ok(msg: str) -> None:
    print(f"  [OK]    {msg}")


def aviso(msg: str) -> None:
    print(f"  [AVISO] {msg}")


def erro(msg: str) -> None:
    print(f"  [ERRO]  {msg}")


def secao(titulo: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {titulo}")
    print(f"{'─' * 60}")


# ---------------------------------------------------------------------------
# 1. Versão do Python
# ---------------------------------------------------------------------------

def verificar_python() -> None:
    secao("1. Versão do Python")
    versao_atual = sys.version_info[:2]

    if versao_atual < PYTHON_MINIMO:
        raise RuntimeError(
            f"Python insuficiente. "
            f"Encontrado: {platform.python_version()}. "
            f"Necessário: {PYTHON_MINIMO[0]}.{PYTHON_MINIMO[1]} ou superior."
        )

    ok(f"Python {platform.python_version()}.")


# ---------------------------------------------------------------------------
# 2. Ambiente virtual
# ---------------------------------------------------------------------------

def verificar_venv() -> None:
    secao("2. Ambiente virtual")
    em_venv = sys.prefix != sys.base_prefix

    if em_venv:
        ok(f"Ambiente virtual ativo: {sys.prefix}")
    else:
        aviso(
            "Nenhum ambiente virtual detectado. "
            "Recomenda-se criar e ativar um .venv antes de rodar o projeto:\n"
            "    python -m venv .venv\n"
            "    source .venv/bin/activate  # Linux/macOS\n"
            "    .venv\\Scripts\\activate     # Windows"
        )


# ---------------------------------------------------------------------------
# 3. Pacotes Python essenciais
# ---------------------------------------------------------------------------

def verificar_pacotes() -> None:
    secao("3. Pacotes Python essenciais")
    faltantes = []

    for nome_pacote, nome_import in PACOTES_ESSENCIAIS.items():
        if importlib.util.find_spec(nome_import) is None:
            faltantes.append(nome_pacote)
            erro(f"Pacote ausente: {nome_pacote}")
        else:
            ok(f"{nome_pacote}")

    if faltantes:
        lista = " ".join(faltantes)
        raise ModuleNotFoundError(
            f"\nPacotes ausentes: {lista}.\n"
            f"Instale com:  pip install -r requirements.txt"
        )


# ---------------------------------------------------------------------------
# 4. Estrutura de arquivos e diretórios
# ---------------------------------------------------------------------------

def verificar_estrutura(raiz: Path) -> None:
    secao("4. Estrutura de arquivos e diretórios")

    # Arquivos obrigatórios
    arquivos_obrigatorios = [
        raiz / "main.py",
        raiz / "requirements.txt",
        raiz / "config" / "settings.py",
        raiz / "src" / "rss_fetcher.py",
        raiz / "src" / "sentiment_analyzer.py",
        raiz / "src" / "storage.py",
        raiz / "src" / "reporter.py",
    ]

    ausentes = []
    for arquivo in arquivos_obrigatorios:
        if arquivo.exists():
            ok(f"Encontrado: {arquivo.relative_to(raiz)}")
        else:
            erro(f"Ausente:    {arquivo.relative_to(raiz)}")
            ausentes.append(arquivo)

    if ausentes:
        raise FileNotFoundError(
            f"{len(ausentes)} arquivo(s) obrigatório(s) não encontrado(s). "
            "Verifique se o repositório foi clonado corretamente."
        )

    # Diretórios que devem existir ou serão criados
    diretorios = [
        raiz / "data",
        raiz / "logs",
    ]
    for diretorio in diretorios:
        diretorio.mkdir(parents=True, exist_ok=True)
        ok(f"Diretório disponível: {diretorio.relative_to(raiz)}/")


# ---------------------------------------------------------------------------
# 5. Configurações em config/settings.py
# ---------------------------------------------------------------------------

def verificar_configuracoes(raiz: Path) -> object:
    secao("5. Configurações (config/settings.py)")

    if str(raiz) not in sys.path:
        sys.path.insert(0, str(raiz))

    try:
        from config import settings
    except Exception as e:
        raise RuntimeError(
            f"Falha ao importar config/settings.py: {e}"
        ) from e

    ok("config/settings.py importado.")

    # Verifica existência dos atributos obrigatórios
    atributos_obrigatorios = [
        "ACOES",
        "FEEDS_RSS_EXTRAS",
        "IDADE_MAXIMA_HORAS",
        "LOG_ARQUIVO",
        "LOG_LEVEL",
        "TRADUZIR_PARA_INGLES",
        "CVM_ATIVO",
    ]

    faltantes = []
    for attr in atributos_obrigatorios:
        if hasattr(settings, attr):
            ok(f"settings.{attr} definido.")
        else:
            erro(f"settings.{attr} não encontrado.")
            faltantes.append(attr)

    if faltantes:
        raise AttributeError(
            f"Atributos ausentes em settings.py: {', '.join(faltantes)}"
        )

    # Valida ACOES: deve ser dict não-vazio com chaves str e campos mínimos
    acoes = settings.ACOES
    if not isinstance(acoes, dict) or not acoes:
        raise ValueError("settings.ACOES deve ser um dicionário não-vazio.")

    tickers_invalidos = []
    for ticker, dados in acoes.items():
        if not isinstance(ticker, str):
            tickers_invalidos.append(str(ticker))
            continue
        if "nome" not in dados or "termos_busca" not in dados:
            erro(f"Ticker {ticker} sem 'nome' ou 'termos_busca' em ACOES.")
            tickers_invalidos.append(ticker)

    if tickers_invalidos:
        raise ValueError(
            f"Entradas malformadas em ACOES: {tickers_invalidos}. "
            "Cada ticker deve ter 'nome' e 'termos_busca'."
        )

    ok(f"{len(acoes)} ticker(s) configurado(s): {', '.join(acoes.keys())}")

    # Valida FEEDS_RSS_EXTRAS: deve ser lista de dicts com 'nome', 'url', 'ativo'
    feeds = settings.FEEDS_RSS_EXTRAS
    if not isinstance(feeds, list):
        raise ValueError("settings.FEEDS_RSS_EXTRAS deve ser uma lista.")

    feeds_invalidos = []
    for feed in feeds:
        if not all(k in feed for k in ("nome", "url", "ativo")):
            feeds_invalidos.append(feed.get("nome", "<sem nome>"))

    if feeds_invalidos:
        raise ValueError(
            f"Feeds RSS malformados (faltam 'nome', 'url' ou 'ativo'): {feeds_invalidos}"
        )

    feeds_ativos = [f for f in feeds if f.get("ativo")]
    ok(
        f"{len(feeds)} feed(s) RSS configurado(s), "
        f"{len(feeds_ativos)} ativo(s)."
    )

    # Valida IDADE_MAXIMA_HORAS
    idade = settings.IDADE_MAXIMA_HORAS
    if not isinstance(idade, (int, float)) or idade <= 0:
        raise ValueError(
            f"settings.IDADE_MAXIMA_HORAS deve ser um número positivo. "
            f"Encontrado: {idade!r}"
        )
    ok(f"Período de coleta: últimas {idade} hora(s).")

    # Valida LOG_LEVEL
    niveis_validos = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    nivel = settings.LOG_LEVEL
    if nivel.upper() not in niveis_validos:
        raise ValueError(
            f"settings.LOG_LEVEL inválido: {nivel!r}. "
            f"Use um de: {', '.join(sorted(niveis_validos))}"
        )
    ok(f"Nível de log: {nivel}.")

    return settings


# ---------------------------------------------------------------------------
# 6. Conectividade — Google News RSS
# ---------------------------------------------------------------------------

def verificar_google_news() -> None:
    secao("6. Conectividade — Google News RSS")
    _checar_url(
        URL_GOOGLE_NEWS_RSS,
        descricao="Google News RSS",
        aviso_falha=(
            "O Google News RSS não respondeu. "
            "A coleta de notícias pode falhar. "
            "Verifique sua conexão com a internet ou firewall corporativo."
        ),
    )


# ---------------------------------------------------------------------------
# 7. Conectividade — API CVM
# ---------------------------------------------------------------------------

def verificar_cvm(settings) -> None:
    secao("7. Conectividade — API de Dados Abertos da CVM")

    if not getattr(settings, "CVM_ATIVO", True):
        aviso("CVM_ATIVO=False em settings.py. Verificação de conectividade ignorada.")
        return

    _checar_url(
        URL_CVM_API,
        descricao="API CVM Dados Abertos",
        aviso_falha=(
            "A API da CVM não respondeu. "
            "A coleta de fatos relevantes pode falhar. "
            "Verifique sua conexão ou desative com CVM_ATIVO=False em settings.py."
        ),
    )


# ---------------------------------------------------------------------------
# 8. Conectividade — Hugging Face
# ---------------------------------------------------------------------------

def verificar_huggingface() -> None:
    secao("8. Conectividade — Hugging Face (download de modelos)")
    _checar_url(
        URL_HUGGINGFACE,
        descricao="Hugging Face",
        aviso_falha=(
            "O Hugging Face não respondeu. "
            "O download dos modelos FinBERT e BART-large-MNLI pode falhar "
            "na primeira execução. Verifique sua conexão com a internet."
        ),
    )


def _checar_url(url: str, descricao: str, aviso_falha: str) -> None:
    """Tenta abrir uma URL com GET e registra o resultado."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=TIMEOUT_REDE) as resp:
            status = resp.status
        if status < 400:
            ok(f"{descricao} acessível (HTTP {status}).")
        else:
            aviso(f"{descricao} retornou HTTP {status}. {aviso_falha}")
    except urllib.error.URLError as e:
        aviso(f"{descricao} inacessível: {e.reason}. {aviso_falha}")
    except Exception as e:
        aviso(f"{descricao} — erro inesperado: {e}. {aviso_falha}")


# ---------------------------------------------------------------------------
# 9. Espaço em disco
# ---------------------------------------------------------------------------

def verificar_espaco_disco(raiz: Path) -> None:
    secao("9. Espaço em disco disponível")
    uso = shutil.disk_usage(raiz)
    livre_gb = uso.free / (1024 ** 3)

    if livre_gb >= ESPACO_DISCO_MINIMO_GB:
        ok(f"{livre_gb:.1f} GB livres em {raiz} (mínimo recomendado: {ESPACO_DISCO_MINIMO_GB} GB).")
    else:
        aviso(
            f"Apenas {livre_gb:.1f} GB livres em {raiz}. "
            f"Os modelos FinBERT (~400 MB) e BART-large-MNLI (~1,6 GB) "
            f"exigem ao menos {ESPACO_DISCO_MINIMO_GB} GB. "
            "Libere espaço antes de executar main.py pela primeira vez."
        )


# ---------------------------------------------------------------------------
# 10. Permissões de escrita
# ---------------------------------------------------------------------------

def verificar_permissoes(raiz: Path) -> None:
    secao("10. Permissões de escrita")
    diretorios = [raiz / "data", raiz / "logs"]

    for diretorio in diretorios:
        arquivo_teste = diretorio / ".write_test"
        try:
            arquivo_teste.write_text("ok")
            arquivo_teste.unlink()
            ok(f"Escrita permitida em {diretorio.relative_to(raiz)}/")
        except OSError as e:
            raise PermissionError(
                f"Sem permissão de escrita em {diretorio}: {e}. "
                "Ajuste as permissões do diretório antes de continuar."
            ) from e


# ---------------------------------------------------------------------------
# Resumo final
# ---------------------------------------------------------------------------

def exibir_resumo(settings) -> None:
    print(f"\n{'═' * 60}")
    print("  Resumo da configuração")
    print(f"{'═' * 60}")
    print(f"  Python             : {platform.python_version()}")
    print(f"  Tickers            : {', '.join(settings.ACOES.keys())}")
    print(f"  Período de coleta  : últimas {settings.IDADE_MAXIMA_HORAS}h")
    print(f"  Tradução PT→EN     : {settings.TRADUZIR_PARA_INGLES}")
    print(f"  Coleta CVM         : {settings.CVM_ATIVO}")
    print(f"  Nível de log       : {settings.LOG_LEVEL}")
    print(f"  Arquivo de log     : {settings.LOG_ARQUIVO}")
    feeds_ativos = [f["nome"] for f in settings.FEEDS_RSS_EXTRAS if f.get("ativo")]
    print(f"  Feeds RSS ativos   : {', '.join(feeds_ativos) if feeds_ativos else '(nenhum além do Google News)'}")
    print(f"{'═' * 60}\n")


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    raiz = Path(__file__).resolve().parent

    print(f"\n{'═' * 60}")
    print("  Validação do Ambiente — Análise de Sentimento de Mercado")
    print(f"  Projeto: {raiz}")
    print(f"{'═' * 60}")

    try:
        verificar_python()
        verificar_venv()
        verificar_pacotes()
        verificar_estrutura(raiz)
        settings = verificar_configuracoes(raiz)
        verificar_google_news()
        verificar_cvm(settings)
        verificar_huggingface()
        verificar_espaco_disco(raiz)
        verificar_permissoes(raiz)
        exibir_resumo(settings)

        print("  [OK] Validação concluída com sucesso.")
        print("       Execute  python main.py  para iniciar a análise.\n")

    except Exception as e:
        print(f"\n  [ERRO FATAL] {e}\n")
        causa = getattr(e, "__cause__", None)
        if causa is not None:
            print(f"  Causa original: {causa}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()