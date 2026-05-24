# Análise de Mercado de Ações

Coleta notícias via **Google News RSS e alguns sites especificos como Bloomberg Línea Brasil, Infomoney,
Brazil Journal e Neofeed**   e calcula score de sentimento
para ações da B3 usando análise de linguagem natural em português.

---

## 🚀 Instalação Rápida (VSCode)

### 1. Pré-requisitos
- Python 3.10+
- pip atualizado: `python -m pip install --upgrade pip`

### 2. Clone / baixe os arquivos
Coloque os arquivos em uma pasta, ex: `market_sentiment/`

```
market_sentiment/
├── sentiment_monitor.py    ← script principal
├── requirements.txt
└── README.md
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

Ou manualmente:
```bash
pip install feedparser requests
```

### 4. Execute

```bash
cd market_sentiment
python sentiment_monitor.py
```

---

## 📊 O que o script faz

```
[01/13] Coletando notícias para BBDC4...
       ✅ 12 notícias | score: +2.40 🟢

  🟢🟢  BBDC4     +2.4  [     │███████       ]  MUITO POSITIVO
           Notícias: 12 total | 7 pos | 3 neu | 2 neg

           🟢 [+3.1] Bradesco bate expectativas no 3T24 com lucro de R$...
                    📰 Valor Econômico | 2024-11-14
```

### Saídas geradas
| Output | Descrição |
|---|---|
| Terminal | Resultados coloridos com barra visual |
| `cache_noticias.json` | Cache com TTL de 1h (evita re-fetch) |
| `relatorio_YYYYMMDD_HHMMSS.json` | Relatório completo exportável |

---

## ⚙️ Configurações principais

Dentro do `sentiment_monitor.py`, você pode ajustar:

```python
MAX_NOTICIAS = 15              # Notícias coletadas por ação
DELAY_ENTRE_REQUESTS = 2.5    # Delay em segundos (não reduza muito)
CACHE_VALIDADE_HORAS = 1      # Quanto tempo o cache é válido
```

---

## 🧠 Como funciona o sentimento

O score vai de **-10** (muito negativo) até **+10** (muito positivo):

| Score | Label | Emoji |
|---|---|---|
| ≥ 4.0 | MUITO POSITIVO | 🟢🟢 |
| ≥ 1.5 | POSITIVO | 🟢 |
| -1.5 a 1.5 | NEUTRO | ⚪ |
| ≤ -1.5 | NEGATIVO | 🔴 |
| ≤ -4.0 | MUITO NEGATIVO | 🔴🔴 |

O algoritmo:
1. Para cada ação, faz 3 buscas no Google News RSS:
   - `{TICKER} ação bolsa`
   - `{nome empresa} resultado financeiro`
   - `{nome empresa} dividendos`
2. Analisa título + resumo de cada notícia
3. Conta palavras/frases positivas e negativas com pesos
4. Aplica intensificadores (ex: "muito", "fortemente")
5. Faz média ponderada entre todas as notícias

---

## 📈 Ações monitoradas

| Ticker | Empresa |
|---|---|
| BBDC4 / BBDC3 | Bradesco |
| BEES4 | Banco Bees |
| JHSF3 | JHSF Participações |
| ITSA4 | Itaúsa |
| CXSE3 | Caixa Seguridade |
| TAEE4 | Taesa Energia |
| ABCB4 | ABC Brasil |
| CMIG4 | Cemig |
| SAUD3 | Hapvida |
| PASS3 | Ancoradouro |
| CSAN3 | Cosan |
| PMAM3 | Paraná Medicamentos |

---

## 🔁 Agendamento automático (opcional)

Para rodar a cada hora automaticamente, adicione ao `crontab` (Linux/Mac):

```bash
0 * * * * cd /caminho/market_sentiment && python sentiment_monitor.py
```

No Windows, use o **Agendador de Tarefas** ou rode em loop:

```python
# No final do sentiment_monitor.py, substitua o if __name__ por:
import time
while True:
    main(verbose=True, exportar=True)
    print("  ⏳ Próxima atualização em 60 minutos...")
    time.sleep(3600)
```

---

## ⚠️ Aviso

Este script é para fins educacionais e informativos.
Sentimento de notícias **não é recomendação de investimento**.
Sempre consulte um assessor financeiro habilitado.

---

## 🛠️ Próximos passos sugeridos

- [ ] Integrar `rich` para terminal mais bonito
- [ ] Adicionar histórico de scores em SQLite
- [ ] Dashboard com `matplotlib` ou `streamlit`
- [ ] Alertas por e-mail/Telegram quando score muda muito
- [ ] Integrar preço das ações via `yfinance` para correlação
