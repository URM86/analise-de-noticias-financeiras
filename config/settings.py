"""
============================================================
config/settings.py
Configurações centrais do sistema de monitoramento de
sentimento de mercado via Google News RSS + feeds extras + CVM.

ONDE ALTERAR CADA COISA:
  - Período de pesquisa  → IDADE_MAXIMA_HORAS (linha ~130)
  - Adicionar site RSS   → FEEDS_RSS_EXTRAS   (linha ~115)
  - Ativar/desativar CVM → CVM_ATIVO          (linha ~145)
  - Adicionar ticker CVM → CVM_CNPJ           (linha ~150)
  - Trocar modelo de IA  → MODELO_BART / MODELO_FINBERT (linha ~80)
============================================================
"""

# ── Ações monitoradas ────────────────────────────────────────────────────────
# Cada ticker pode ter múltiplos termos de busca (apelidos, nome da empresa)
# para maximizar a cobertura de notícias relevantes.
ACOES = {
    "BBDC4": {
        "nome": "Bradesco PN",
        "termos_busca": ["BBDC4", "Bradesco", "Banco Bradesco"],
    },
    "BBDC3": {
        "nome": "Bradesco ON",
        "termos_busca": ["BBDC3", "Bradesco ON", "Banco Bradesco ON"],
    },
    "BEES4": {
        "nome": "Banestes PN",
        "termos_busca": ["BEES4", "Banestes", "Banco do Estado do Espírito Santo", "Banestes SA Banco do Estado Esprt Santo Preference Shares"],
    },
    "JHSF3": {
        "nome": "JHSF Participações",
        "termos_busca": ["JHSF3", "JHSF", "JHSF Participações"],
    },
    "ITSA4": {
        "nome": "Itaúsa PN",
        "termos_busca": ["ITSA4", "Itaúsa", "Itausa"],
    },
    "CXSE3": {
        "nome": "Caixa Seguridade",
        "termos_busca": ["CXSE3", "Caixa Seguridade"],
    },
    "TAEE4": {
        "nome": "Taesa",
        "termos_busca": ["TAEE4", "Taesa", "Transmissora Aliança"],
    },
    "ABCB4": {
        "nome": "ABC Brasil",
        "termos_busca": ["ABCB4", "Banco ABC Brasil", "ABC Brasil"],
    },
    "CMIG4": {
        "nome": "Cemig",
        "termos_busca": ["CMIG4", "Cemig", "Companhia Energética Minas Gerais", "Cemig Geração e Transmissão (Cemig GT)", "Cemig Distribuição (Cemig D)",
                         "Gasmig", "Energia Livre Cemig"],
    },
    "SAUD3": {
        "nome": "Bradesco Saúde",
        "termos_busca": ["SAUD3", "Bradesco Saúde", "Bradesco Gestão de Saúde S.A.", "BRADSAÚDE ON", "BradSaúde"],
    },
    "PASS3": {
        "nome": "Compass Gas E Energia SA",
        "termos_busca": ["PASS3", "Compass Gas E Energia SA", "Compass Energia", "Comgás", "Compass Gas"],
    },
    "CSAN3": {
        "nome": "Cosan",
        "termos_busca": ["CSAN3", "Cosan", "Cosan S.A."],
    },
    "PMAM3": {
        "nome": "Paranapanema S.A.",
        "termos_busca": ["PMAM3", "Paranapanema S.A."],
    },
}

# ── Modelos de sentimento ────────────────────────────────────────────────────
# Dois modelos rodam em paralelo; o maior score vence.
MODELO_BART    = "facebook/bart-large-mnli"   # generalista (~1.6 GB)
MODELO_FINBERT = "ProsusAI/finbert"            # especialista financeiro (~400 MB)
MODELO_SENTIMENTO = MODELO_BART                # compatibilidade

LABELS_SENTIMENTO = ["positive", "negative", "neutral"]

FINBERT_LABEL_MAP = {
    "positive": "positive", "negative": "negative", "neutral": "neutral",
    "pos": "positive",      "neg": "negative",       "neu": "neutral",
}

LABEL_PT = {
    "positive": "POSITIVO",
    "negative": "NEGATIVO",
    "neutral":  "NEUTRO",
}

CONFIANCA_MINIMA = 0.50

# ── Google News RSS ──────────────────────────────────────────────────────────
GNEWS_RSS_TEMPLATE = (
    "https://news.google.com/rss/search"
    "?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
)

# ── Feeds RSS extras ─────────────────────────────────────────────────────────
# Estes feeds são varridos inteiros e filtrados por termos do ticker.
#
# COMO ADICIONAR UM NOVO SITE:
#   1. Descubra a URL do RSS (tente /feed/ ou /rss/ no final do domínio)
#   2. Copie um bloco abaixo e preencha "nome" e "url"
#   3. Deixe "ativo": True
#
# COMO DESATIVAR SEM APAGAR: mude "ativo" para False
FEEDS_RSS_EXTRAS = [
    {
        "nome":  "Bloomberg Línea Brasil",
        "url":   "https://www.bloomberglinea.com.br/arc/outboundfeeds/new-news-feed/?outputType=xml",
        "ativo": True,
    },
    {
        "nome":  "Infomoney",
        "url":   "https://www.infomoney.com.br/feed/",
        "ativo": True,
    },
    {
        "nome":  "Brazil Journal",
        "url":   "https://braziljournal.com/rss",
        "ativo": True,
    },
    {
        "nome":  "Neofeed",
        "url":   "https://neofeed.com.br/feed/",
        "ativo": True,
    },
    # ── Outros feeds disponíveis (ative mudando para True) ───────────────────
    {
        "nome":  "Valor Econômico",
        "url":   "https://valor.globo.com/rss/ultimas-noticias/",
        "ativo": False,
    },
    {
        "nome":  "Estadão Economia",
        "url":   "https://economia.estadao.com.br/rss2.xml",
        "ativo": False,
    },
    {
        "nome":  "Folha Mercado",
        "url":   "https://feeds.folha.uol.com.br/mercado/rss091.xml",
        "ativo": False,
    },
]

# ── API da CVM — Fatos Relevantes Oficiais ───────────────────────────────────
# A CVM publica fatos relevantes, comunicados e resultados via dados abertos.
# O sistema consulta por CNPJ e filtra documentos do período configurado.
#
# COMO ADICIONAR NOVO TICKER: inclua o CNPJ (só dígitos) no dict abaixo.
# COMO DESATIVAR COMPLETAMENTE: mude CVM_ATIVO para False.
CVM_ATIVO = True

# CNPJ de cada empresa (somente dígitos, sem pontos/traços/barras)
CVM_CNPJ = {
    "BBDC4": "60746948000112",   # Bradesco
    "BBDC3": "60746948000112",   # Bradesco (mesmo CNPJ, classe diferente)
    "BEES4": "28130139000145",   # Banestes
    "JHSF3": "08294224000165",   # JHSF Participações
    "ITSA4": "61532644000115",   # Itaúsa
    "CXSE3": "14388334000199",   # Caixa Seguridade
    "TAEE4": "02461786000170",   # Taesa
    "ABCB4": "28195667000106",   # ABC Brasil
    "CMIG4": "17155730000164",   # Cemig
    "SAUD3": "60460348000112",   # Hypera Pharma
    "PASS3": "09296295000160",   # Azul Linhas Aéreas
    "CSAN3": "50746577000115",   # Cosan
    "PMAM3": "60850229000146",   # Paranapanema
}

# URL da API de dados abertos da CVM
# Documentação: https://dados.cvm.gov.br/
CVM_API_FATOS = (
    "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFIN/DADOS/"
)
# Endpoint de busca de fatos relevantes (sistema ENET da CVM)
CVM_ENET_URL = (
    "https://www.rad.cvm.gov.br/ENET/frmConsultaExternaCVM.aspx"
)

MAX_FATOS_CVM = 5   # máximo de fatos relevantes por ticker por execução

# ── Limites de coleta ────────────────────────────────────────────────────────
MAX_ARTIGOS_POR_TICKER = 15   # máximo de artigos RSS por ticker por execução

# ↓ ALTERE AQUI para mudar o período de pesquisa das notícias
# Exemplos: 24 = só hoje | 48 = 2 dias | 72 = 3 dias | 168 = 1 semana
IDADE_MAXIMA_HORAS = 48

# ── Tradução ─────────────────────────────────────────────────────────────────
TRADUZIR_PARA_INGLES = True   # False = analisa em português (menos preciso)

# ── Persistência ─────────────────────────────────────────────────────────────
PASTA_DADOS   = "data"
PASTA_LOGS    = "logs"
ARQUIVO_CSV   = "data/sentimentos.csv"
ARQUIVO_EXCEL = "data/relatorio_sentimentos.xlsx"

# ── Agendamento ──────────────────────────────────────────────────────────────
INTERVALO_EXECUCAO_MIN = 60   # minutos entre execuções no modo daemon

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL   = "INFO"
LOG_ARQUIVO = "logs/market_sentiment.log"
