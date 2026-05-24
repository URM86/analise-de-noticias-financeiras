
Coleta notícias via Google News RSS e fontes especializadas como Bloomberg Línea Brasil, InfoMoney, Brazil Journal e NeoFeed, além de fatos relevantes oficiais publicados na CVM, para calcular _scores_ de sentimento aplicados à análise de ações da B3 utilizando os modelos **FinBERT** e **BART-large-MNLI** disponibilizados pela plataforma Hugging Face.

A proposta do projeto é inspirada no [B3Analysis](https://github.com/guhcostan/b3analysis), enquanto a estrutura inicial do código foi desenvolvida com auxílio do Claude (Anthropic).

> **Atenção**
> Este projeto possui finalidade educacional e de estudo pessoal. Os relatórios são gerados por modelos de linguagem e não constituem recomendação de investimento, consultoria financeira ou análise profissional. Investimentos em renda variável envolvem risco de perda parcial ou total do capital investido. Antes de investir, consulte um profissional autorizado e registrado na Comissão de Valores Mobiliários (CVM).
---

## O que este sistema faz

Para cada ação monitorada, o sistema executa automaticamente três etapas:

**1. Coleta de notícias** — busca artigos publicados no período configurado (padrão: últimas 48 horas) em múltiplas fontes:

- **Google News RSS** — pesquisa por termo (ex: "Bradesco", "BBDC4") e retorna artigos de qualquer veículo indexado pelo Google
- **Bloomberg Línea Brasil** — feed RSS oficial do portal de notícias financeiras
- **InfoMoney** — feed RSS do maior portal de finanças pessoais do Brasil
- **Brazil Journal** — feed RSS do portal especializado em negócios e mercado de capitais
- **NeoFeed** — feed RSS do portal focado em empreendedorismo, inovação e finanças
- **CVM — Dados Abertos** — fatos relevantes, comunicados ao mercado e documentos regulatórios consultados diretamente via API pública da Comissão de Valores Mobiliários, filtrados pelo CNPJ de cada empresa

Cada artigo é deduplicado por hash MD5 da URL. Artigos já processados em execuções anteriores são ignorados automaticamente para evitar retrabalho.

**2. Análise de sentimento** — dois modelos de linguagem analisam cada artigo de forma independente, e o que retornar maior score de confiança define o resultado final:

- **BART-large-MNLI** (`facebook/bart-large-mnli`) — modelo generalista da Meta treinado em _Natural Language Inference_. Usa _zero-shot classification_: recebe o texto e os rótulos `positive`, `negative`, `neutral` e decide qual melhor se aplica, sem nenhum treinamento específico para finanças. Tamanho: ~1,6 GB.
- **FinBERT** (`ProsusAI/finbert`) — modelo especialista, treinado diretamente em textos financeiros como notícias de mercado, relatórios de analistas e o dataset _Financial PhraseBank_. Reconhece expressões como "lucro acima do esperado", "guidance conservador" e "redução de dividendos" com muito mais precisão. Tamanho: ~400 MB.

Antes da análise, o título e o resumo de cada artigo são traduzidos automaticamente do português para o inglês via Google Translate gratuito, pois ambos os modelos performam melhor em inglês. Essa etapa pode ser desativada com a flag `--sem-traducao`.

Se o score de confiança do modelo vencedor for inferior a 50%, o resultado é marcado como **INCONCLUSIVO** em vez de forçar uma classificação pouco confiável.

**3. Persistência e relatório** — os resultados são salvos em dois formatos:

- `data/sentimentos.csv` — histórico completo de todos os artigos analisados, em modo _append_ (nunca apaga dados anteriores)
- `data/relatorio_sentimentos.xlsx` — arquivo Excel com três abas: **Resumo** (uma linha por ticker com cores por sentimento), **Histórico** (todos os artigos) e **Pivot** (tabela cruzada sentimento × ticker)

---

## Ações monitoradas

| Ticker | Empresa |
|--------|---------|
| BBDC4 | Bradesco PN |
| BBDC3 | Bradesco ON |
| BEES4 | Banestes PN |
| JHSF3 | JHSF Participações |
| ITSA4 | Itaúsa PN |
| CXSE3 | Caixa Seguridade |
| TAEE4 | Taesa PN |
| ABCB4 | ABC Brasil PN |
| CMIG4 | Cemig PN |
| SAUD3 | Hypera Pharma |
| PASS3 | Azul Linhas Aéreas |
| CSAN3 | Cosan |
| PMAM3 | Paranapanema |

---

## Estrutura de arquivos

```
market_sentiment/
├── main.py                        # Ponto de entrada — execute este arquivo
├── requirements.txt               # Dependências Python
│
├── config/
│   └── settings.py                # Todas as configurações do sistema
│                                  # ← aqui você personaliza tudo
│
├── src/
│   ├── rss_fetcher.py             # Coleta de notícias (Google News, feeds extras, CVM)
│   ├── sentiment_analyzer.py      # Análise com BART + FinBERT e votação por confiança
│   ├── storage.py                 # Salva CSV e exporta Excel
│   └── reporter.py                # Exibe tabelas coloridas no terminal (Rich)
│
├── data/
│   ├── sentimentos.csv            # Gerado automaticamente na primeira execução
│   └── relatorio_sentimentos.xlsx # Gerado automaticamente na primeira execução
│
├── logs/
│   └── market_sentiment.log       # Log detalhado de cada execução
│
└── .vscode/
    ├── launch.json                # Configurações de debug (F5 no VSCode)
    └── settings.json              # Configurações do projeto para o VSCode
```

---

## Pré-requisitos

- **Python 3.10 ou superior** — verifique com `python --version`
- **Conexão com a internet** — necessária para coletar notícias e baixar os modelos na primeira execução
- **Espaço em disco** — ~2 GB para os modelos (baixados uma única vez e armazenados em `~/.cache/huggingface/`)
- **VSCode** (opcional, mas recomendado) com a extensão [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)

---

## Instalação

### Opção 1 — Clonar o repositório via Git

```bash
git clone https://github.com/seu-usuario/market-sentiment.git
cd market-sentiment
```

### Opção 2 — Baixar o ZIP

Baixe o arquivo `.zip`, extraia em uma pasta de sua escolha e abra o terminal dentro dessa pasta.

### Instalar as dependências

Sem ambiente virtual (mais simples):

```bash
pip install -r requirements.txt
```

Com ambiente virtual (recomendado para não interferir em outros projetos):

```bash
# Criar o ambiente
python -m venv .venv

# Ativar — Windows
.venv\Scripts\activate

# Ativar — Linux / macOS
source .venv/bin/activate

# Instalar
pip install -r requirements.txt
```

> A instalação do PyTorch + Transformers pode levar alguns minutos dependendo da velocidade da internet.

---

## Como executar

Todos os comandos abaixo devem ser rodados dentro da pasta do projeto.

### Análise completa — todos os 13 tickers

```bash
python main.py
```

### Analisar apenas tickers específicos

```bash
python main.py --tickers BBDC4 ITSA4 CSAN3
```

### Modo daemon — execução automática em loop

Repete a análise automaticamente no intervalo configurado (padrão: 60 minutos). Útil para monitoramento contínuo durante o pregão.

```bash
# Loop a cada 60 minutos (padrão)
python main.py --daemon

# Loop com intervalo personalizado (ex: a cada 30 minutos)
python main.py --daemon --intervalo 30
```

Pressione `Ctrl + C` para parar.

### Desativar a tradução automática

Por padrão, o sistema traduz os textos para inglês antes da análise, pois os modelos são mais precisos em inglês. Para desativar (análise direto em português, mais rápido porém menos preciso):

```bash
python main.py --sem-traducao
```

### Controlar o nível de detalhe dos logs

```bash
python main.py --log-nivel DEBUG    # mostra tudo, incluindo cada requisição HTTP
python main.py --log-nivel WARNING  # mostra apenas alertas e erros
```

### No VSCode — pressione F5

O arquivo `.vscode/launch.json` já contém cinco configurações prontas:

| Nome | O que faz |
|------|-----------|
| ▶ Executar (todos os tickers) | Roda `python main.py` normalmente |
| 🔍 Debug – BBDC4 apenas | Roda só o BBDC4 com log DEBUG, permite breakpoints |
| 🔄 Daemon Mode (60 min) | Loop automático a cada hora |
| ⚡ Sem tradução (rápido) | Todos os tickers sem traduzir |
| 🧪 Teste – ITSA4 CSAN3 CMIG4 | Subset de 3 tickers para testes rápidos |

---

## Primeira execução — o que esperar

Na primeira vez que rodar, o sistema vai baixar automaticamente os dois modelos do Hugging Face:

- `facebook/bart-large-mnli` → ~1,6 GB (pode levar 5–15 minutos)
- `ProsusAI/finbert` → ~400 MB (mais rápido)

Os modelos são salvos em `~/.cache/huggingface/` e **não são baixados novamente** nas execuções seguintes.

Durante a análise, o terminal exibirá uma tabela como esta para cada ticker:

```
──────────────────────── BBDC4 ────────────────────────
╭──────────┬──────────────────────────┬────────┬─────────┬──────────┬──────────────┬──────╮
│ Data     │ Título                   │  BART  │ FinBERT │ Vencedor │ Sentimento   │ Conf │
├──────────┼──────────────────────────┼────────┼─────────┼──────────┼──────────────┼──────┤
│ 2026-05  │ Bradesco bate expectat.. │POS 87% │ POS 74% │ ✔ BART   │ 📈 POSITIVO  │  87% │
│ 2026-05  │ Analistas cortam preço.. │NEU 55% │ NEG 91% │  FinBERT │ 📉 NEGATIVO  │  91% │
╰──────────┴──────────────────────────┴────────┴─────────┴──────────┴──────────────┴──────╯
```

E ao final, um resumo geral de todos os tickers com sentimento predominante e estatísticas de concordância entre os modelos.

---

## Personalização — tudo em `config/settings.py`

Você não precisa alterar nenhum outro arquivo para personalizar o sistema. Todas as configurações ficam em um único lugar: **`config/settings.py`**.

### Mudar o período de pesquisa das notícias

```python
# Linha IDADE_MAXIMA_HORAS
IDADE_MAXIMA_HORAS = 48   # 24 = só hoje | 72 = 3 dias | 168 = 1 semana
```

### Ativar sites que estão desativados

```python
# Em FEEDS_RSS_EXTRAS, mude "ativo" de False para True
{
    "nome":  "Valor Econômico",
    "url":   "https://valor.globo.com/rss/ultimas-noticias/",
    "ativo": True,   # ← era False
},
```

### Adicionar um site novo

Qualquer site que ofereça RSS pode ser adicionado. A URL do RSS normalmente termina em `/feed/` ou `/rss/`. Adicione um bloco novo na lista `FEEDS_RSS_EXTRAS`:

```python
{
    "nome":  "Nome do Site",
    "url":   "https://www.seusite.com.br/feed/",
    "ativo": True,
},
```

### Adicionar uma nova ação

Em `ACOES`, adicione um novo bloco com o ticker, o nome da empresa e os termos de busca (nome popular, nome completo, variações):

```python
"VALE3": {
    "nome": "Vale S.A.",
    "termos_busca": ["VALE3", "Vale", "Vale S.A.", "minério de ferro"],
},
```

Em seguida, adicione o CNPJ da empresa em `CVM_CNPJ` para receber também os fatos relevantes da CVM:

```python
"VALE3": "33592510000154",   # Vale S.A.
```

### Desativar a coleta de fatos relevantes da CVM

```python
CVM_ATIVO = False
```

### Desativar a tradução automática

```python
TRADUZIR_PARA_INGLES = False
```

---

## Onde ficam os resultados

| Arquivo | Conteúdo |
|---------|----------|
| `data/sentimentos.csv` | Histórico completo de todos os artigos analisados. Cada linha é um artigo com ticker, título, fonte, data, sentimento dos dois modelos, qual venceu e score de confiança. Nunca é apagado entre execuções. |
| `data/relatorio_sentimentos.xlsx` | Arquivo Excel com aba **Resumo** (visão rápida por ticker com cores), aba **Histórico** (todos os artigos) e aba **Pivot** (tabela cruzada). Atualizado ao final de cada execução. |
| `logs/market_sentiment.log` | Log técnico detalhado de cada execução: requisições HTTP, artigos filtrados, scores dos modelos, erros. Útil para diagnosticar problemas. |

---

## Dependências principais

| Biblioteca | Versão | Função |
|------------|--------|--------|
| `transformers` | 4.40+ | Carrega e executa os modelos BART e FinBERT via Hugging Face |
| `torch` | 2.2+ | Backend de computação para os modelos (CPU por padrão) |
| `feedparser` | 6.0+ | Parseia feeds RSS de qualquer fonte |
| `deep-translator` | 1.11+ | Tradução PT→EN via Google Translate gratuito |
| `pandas` | 2.2+ | Manipulação dos dados e geração do CSV |
| `openpyxl` | 3.1+ | Exportação do relatório Excel |
| `rich` | 13.7+ | Tabelas coloridas e formatadas no terminal |
| `tqdm` | 4.66+ | Barras de progresso durante a análise |

---

## Limitações conhecidas

**Rate limiting do Google News** — O Google News pode bloquear requisições muito frequentes. No modo daemon, use intervalos de no mínimo 30 minutos. O sistema já inclui pausas entre requisições para reduzir esse risco.

**Precisão dos modelos** — BART e FinBERT são modelos de propósito geral (ainda que o FinBERT seja especializado em finanças). Notícias ambíguas, irônicas ou com contexto muito técnico podem ser classificadas incorretamente. Resultados com confiança abaixo de 60% devem ser interpretados com cautela.

**Cobertura de ações menos líquidas** — Tickers como BEES4 e PMAM3 têm cobertura menor na mídia. É normal que algumas execuções retornem poucos ou nenhum artigo para essas ações.

**Velocidade em CPU** — Sem GPU, cada artigo leva entre 3 e 10 segundos para ser analisado pelos dois modelos. Para 13 tickers com 15 artigos cada, isso pode representar até 30–40 minutos de processamento em hardware mais lento.

**Feeds RSS externos** — Bloomberg Línea, Infomoney, Brazil Journal e NeoFeed podem alterar suas URLs de RSS sem aviso. Se um feed parar de funcionar, desative-o em `FEEDS_RSS_EXTRAS` (`"ativo": False`) e consulte o site para a nova URL.

---

## Referências

- [B3Analysis](https://github.com/guhcostan/b3analysis) — inspiração para o projeto
- [ProsusAI/finbert](https://huggingface.co/ProsusAI/finbert) — modelo FinBERT no Hugging Face
- [facebook/bart-large-mnli](https://huggingface.co/facebook/bart-large-mnli) — modelo BART no Hugging Face
- [API de Dados Abertos da CVM](https://dados.cvm.gov.br/) — fatos relevantes e documentos regulatórios
- [Google News RSS](https://news.google.com/rss/search) — feed de busca de notícias
