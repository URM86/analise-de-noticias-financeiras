"""
============================================================
src/sentiment_analyzer.py
Análise de sentimento com DOIS modelos em paralelo:

  1. facebook/bart-large-mnli  — generalista, zero-shot
  2. ProsusAI/finbert           — especialista em finanças

Estratégia de votação:
  - Ambos os modelos analisam cada artigo independentemente
  - O modelo que retornar o MAIOR score de confiança vence
  - O resultado final mostra qual modelo venceu e os scores dos dois
  - Se apenas um modelo estiver disponível, usa-o normalmente

Fluxo por artigo:
  título + descrição
      → tradução PT-BR → EN
      → BART-MNLI (zero-shot)   → label_bart  + score_bart
      → FinBERT  (classificador) → label_finbert + score_finbert
      → maior score vence → sentimento final
============================================================
"""

import logging
import re
from typing import Optional

from config.settings import (
    MODELO_BART,
    MODELO_FINBERT,
    LABELS_SENTIMENTO,
    FINBERT_LABEL_MAP,
    LABEL_PT,
    CONFIANCA_MINIMA,
    TRADUZIR_PARA_INGLES,
)

logger = logging.getLogger(__name__)

# ── Lazy loading dos dois modelos ─────────────────────────────────────────────
# Carregados uma única vez na primeira chamada e mantidos em memória.
_pipeline_bart    = None
_pipeline_finbert = None
_translator       = None


def _get_pipeline_bart():
    """
    Carrega o pipeline do BART-MNLI (zero-shot classification).
    Download ~1.6GB na primeira vez, cacheado em ~/.cache/huggingface/.
    """
    global _pipeline_bart
    if _pipeline_bart is None:
        logger.info(f"[BART] Carregando '{MODELO_BART}'... (~1.6GB, só na primeira vez)")
        from transformers import pipeline
        _pipeline_bart = pipeline(
            task="zero-shot-classification",
            model=MODELO_BART,
            device=-1,   # -1 = CPU | 0 = GPU NVIDIA
        )
        logger.info("[BART] Modelo carregado.")
    return _pipeline_bart


def _get_pipeline_finbert():
    """
    Carrega o pipeline do FinBERT (text-classification).
    Download ~400MB na primeira vez, muito mais rápido que o BART.

    FinBERT retorna labels: 'positive', 'negative', 'neutral'
    com scores de probabilidade softmax.
    """
    global _pipeline_finbert
    if _pipeline_finbert is None:
        logger.info(f"[FinBERT] Carregando '{MODELO_FINBERT}'... (~400MB, só na primeira vez)")
        from transformers import pipeline
        _pipeline_finbert = pipeline(
            task="text-classification",
            model=MODELO_FINBERT,
            device=-1,
            # retorna scores de todos os labels, não só o top-1
            # return_all_scores=True,
            top_k=None
        )
        logger.info("[FinBERT] Modelo carregado.")
    return _pipeline_finbert


def _get_translator():
    """Tradutor PT-BR → EN usando Google Translate gratuito."""
    global _translator
    if _translator is None:
        from deep_translator import GoogleTranslator
        _translator = GoogleTranslator(source="pt", target="en")
        logger.debug("Tradutor PT→EN inicializado.")
    return _translator


def _traduzir(texto: str) -> str:
    """
    Traduz para EN. Limita a 4500 chars (limite do Google Translate free).
    Em caso de falha retorna o texto original — nunca falha silenciosamente.
    """
    if not texto or not texto.strip():
        return texto
    texto = texto[:4500]
    try:
        traduzido = _get_translator().translate(texto)
        return traduzido or texto
    except Exception as exc:
        logger.warning(f"Falha na tradução (usando original): {exc}")
        return texto


def _prepara_texto(artigo: dict) -> str:
    """
    Junta título + descrição, limpa espaços e traduz se necessário.
    Título vem primeiro porque tem mais peso semântico.
    """
    titulo    = artigo.get("titulo", "").strip()
    descricao = artigo.get("descricao", "").strip()
    texto     = f"{titulo}. {descricao}" if descricao else titulo
    texto     = re.sub(r"\s+", " ", texto).strip()

    if TRADUZIR_PARA_INGLES:
        logger.debug(f"Traduzindo: '{texto[:60]}...'")
        texto = _traduzir(texto)
        logger.debug(f"Traduzido:  '{texto[:60]}...'")

    return texto


# ── Inferência individual por modelo ─────────────────────────────────────────

def _inferir_bart(texto: str) -> tuple[str, float, dict]:
    """
    Roda o BART-MNLI no texto.

    Retorna
    -------
    label : str   – melhor label em inglês
    score : float – confiança do melhor label
    todos : dict  – scores de todos os labels
    """
    clf  = _get_pipeline_bart()
    saida = clf(texto, candidate_labels=LABELS_SENTIMENTO, multi_label=False)
    labels = saida["labels"]
    scores = saida["scores"]
    todos  = dict(zip(labels, scores))
    return labels[0], scores[0], todos


def _inferir_finbert(texto: str) -> tuple[str, float, dict]:
    """
    Roda o FinBERT no texto.

    O FinBERT usa text-classification com return_all_scores=True,
    então retorna lista de {'label': ..., 'score': ...} para cada label.

    Os labels originais do FinBERT são mapeados via FINBERT_LABEL_MAP
    para o padrão do projeto (positive/negative/neutral).
    """
    clf   = _get_pipeline_finbert()
    saida = clf(texto)[0]   # lista de dicts [{label, score}, ...]
    
    # top_k=None retorna lista de listas: [[{label, score}, ...]]
    # fallback: se vier dict ou lista de dict (versões antigas), normaliza
    if isinstance(saida, dict):
        saida = [saida]
    elif isinstance(saida[0], dict):
        pass  # lista de dicts — ok
    else:
        saida = saida[0]  # lista de listas → pega a primeira

    # Normaliza labels para o padrão do projeto
    todos = {
        FINBERT_LABEL_MAP.get(item["label"].lower(), item["label"].lower()): item["score"]
        for item in saida
    }

    melhor_label = max(todos, key=todos.get)
    melhor_score = todos[melhor_label]
    return melhor_label, melhor_score, todos


# ── Votação: maior confiança vence ────────────────────────────────────────────

def _votar(
    label_bart:    str,   score_bart:    float,
    label_finbert: str,   score_finbert: float,
) -> tuple[str, str, float]:
    """
    Compara os dois scores e elege o vencedor.

    Retorna
    -------
    vencedor  : str  – 'BART' ou 'FinBERT'
    label     : str  – label do vencedor (positive/negative/neutral)
    score     : float – confiança do vencedor
    """
    if score_bart >= score_finbert:
        return "BART", label_bart, score_bart
    else:
        return "FinBERT", label_finbert, score_finbert


# ── Função principal ──────────────────────────────────────────────────────────

def analisar_sentimento(artigo: dict) -> dict:
    """
    Analisa um artigo com BART + FinBERT e aplica votação por confiança.

    Campos adicionados ao artigo de retorno:
    ─────────────────────────────────────────
    sentimento_en       str   – label vencedor em inglês
    sentimento_pt       str   – label vencedor em português
    confianca           float – score do vencedor
    modelo_vencedor     str   – 'BART' ou 'FinBERT'

    score_bart          float – confiança do BART
    label_bart          str   – label do BART
    scores_bart         dict  – todos os scores do BART

    score_finbert       float – confiança do FinBERT
    label_finbert       str   – label do FinBERT
    scores_finbert      dict  – todos os scores do FinBERT

    concordancia        bool  – True se os dois chegaram ao mesmo label
    texto_analisado     str   – texto enviado aos modelos (para debug)
    erro                str   – mensagem de erro, se houver
    """
    resultado = artigo.copy()

    # Valores padrão (preenchidos em caso de erro)
    resultado.update({
        "sentimento_en":   "INCONCLUSIVO",
        "sentimento_pt":   "INCONCLUSIVO",
        "confianca":       0.0,
        "modelo_vencedor": "",
        "score_bart":      0.0,
        "label_bart":      "",
        "scores_bart":     {},
        "score_finbert":   0.0,
        "label_finbert":   "",
        "scores_finbert":  {},
        "concordancia":    False,
        "texto_analisado": "",
        "erro":            "",
    })

    try:
        texto = _prepara_texto(artigo)

        if not texto.strip():
            resultado["erro"] = "Texto vazio após pré-processamento."
            return resultado

        resultado["texto_analisado"] = texto

        # ── Roda os dois modelos ──────────────────────────────────────────────
        label_bart,    score_bart,    scores_bart    = _inferir_bart(texto)
        label_finbert, score_finbert, scores_finbert = _inferir_finbert(texto)

        resultado["label_bart"]     = label_bart
        resultado["score_bart"]     = round(score_bart, 4)
        resultado["scores_bart"]    = {k: round(v, 4) for k, v in scores_bart.items()}

        resultado["label_finbert"]   = label_finbert
        resultado["score_finbert"]   = round(score_finbert, 4)
        resultado["scores_finbert"]  = {k: round(v, 4) for k, v in scores_finbert.items()}

        resultado["concordancia"] = (label_bart == label_finbert)

        # ── Votação: maior confiança vence ────────────────────────────────────
        vencedor, label_final, score_final = _votar(
            label_bart,    score_bart,
            label_finbert, score_finbert,
        )

        resultado["modelo_vencedor"] = vencedor
        resultado["confianca"]       = round(score_final, 4)

        if score_final >= CONFIANCA_MINIMA:
            resultado["sentimento_en"] = label_final
            resultado["sentimento_pt"] = LABEL_PT.get(label_final, label_final.upper())
        else:
            resultado["sentimento_en"] = "inconclusive"
            resultado["sentimento_pt"] = "INCONCLUSIVO"

        # Log com resultado dos dois modelos
        concorda = "✔ concordam" if resultado["concordancia"] else "✗ divergem"
        logger.debug(
            f"[{artigo.get('ticker')}] '{artigo.get('titulo', '')[:45]}'\n"
            f"  BART:    {label_bart:<10} {score_bart:.0%}\n"
            f"  FinBERT: {label_finbert:<10} {score_finbert:.0%}\n"
            f"  → {vencedor} vence ({score_final:.0%}) | {concorda}"
        )

    except Exception as exc:
        resultado["erro"] = str(exc)
        logger.error(
            f"[{artigo.get('ticker')}] Erro na análise: {exc}",
            exc_info=True,
        )

    return resultado


def analisar_lista_artigos(artigos: list[dict], ticker: str = "") -> list[dict]:
    """
    Analisa uma lista completa de artigos com barra de progresso.
    """
    from tqdm import tqdm
    resultados = []
    prefixo = f"[{ticker}]" if ticker else "[Análise]"
    for artigo in tqdm(artigos, desc=prefixo, unit="artigo"):
        resultados.append(analisar_sentimento(artigo))
    return resultados


def resumir_sentimentos(artigos_analisados: list[dict]) -> dict:
    """
    Gera resumo estatístico dos sentimentos de um conjunto de artigos.
    Inclui métricas extras sobre concordância entre os modelos.
    """
    if not artigos_analisados:
        return {}

    ticker   = artigos_analisados[0].get("ticker", "N/A")
    contagem = {"POSITIVO": 0, "NEGATIVO": 0, "NEUTRO": 0, "INCONCLUSIVO": 0}
    soma_scores      = 0.0
    bart_vitorias    = 0
    finbert_vitorias = 0
    concordancias    = 0

    for a in artigos_analisados:
        sent = a.get("sentimento_pt", "INCONCLUSIVO")
        contagem[sent if sent in contagem else "INCONCLUSIVO"] += 1
        soma_scores += a.get("confianca", 0.0)

        if a.get("modelo_vencedor") == "BART":
            bart_vitorias += 1
        elif a.get("modelo_vencedor") == "FinBERT":
            finbert_vitorias += 1

        if a.get("concordancia"):
            concordancias += 1

    total  = len(artigos_analisados)
    validos = total - contagem["INCONCLUSIVO"]
    sentimentos_validos = {k: v for k, v in contagem.items() if k != "INCONCLUSIVO"}
    sentimento_geral = (
        max(sentimentos_validos, key=sentimentos_validos.get)
        if validos > 0 else "INCONCLUSIVO"
    )

    return {
        "ticker":            ticker,
        "total":             total,
        "positivos":         contagem["POSITIVO"],
        "negativos":         contagem["NEGATIVO"],
        "neutros":           contagem["NEUTRO"],
        "inconclusivos":     contagem["INCONCLUSIVO"],
        "score_medio":       round(soma_scores / total, 4) if total > 0 else 0.0,
        "sentimento_geral":  sentimento_geral,
        "percentual_pos":    round(contagem["POSITIVO"] / total * 100, 1) if total > 0 else 0.0,
        "percentual_neg":    round(contagem["NEGATIVO"] / total * 100, 1) if total > 0 else 0.0,
        "bart_vitorias":     bart_vitorias,
        "finbert_vitorias":  finbert_vitorias,
        "pct_concordancia":  round(concordancias / total * 100, 1) if total > 0 else 0.0,
    }
