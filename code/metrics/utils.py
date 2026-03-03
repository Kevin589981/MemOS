"""
Borrowed from https://github.com/WujiangXu/AgenticMemory/blob/main/utils.py

@article{xu2025mem,
    title={A-mem: Agentic memory for llm agents},
    author={Xu, Wujiang and Liang, Zujie and Mei, Kai and Gao, Hang and Tan, Juntao
           and Zhang, Yongfeng},
    journal={arXiv preprint arXiv:2502.12110},
    year={2025}
}
"""

import statistics
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Union

import nltk
from bert_score import score as bert_score
from nltk.translate.bleu_score import SmoothingFunction, sentence_bleu
from nltk.translate.meteor_score import meteor_score
from rouge_score import rouge_scorer
from sentence_transformers import SentenceTransformer

# from load_dataset import load_locomo_dataset, QA, Turn, Session, Conversation
from sentence_transformers.util import pytorch_cos_sim

# Download required NLTK data
try:
    nltk.download("punkt", quiet=True)
    nltk.download("wordnet", quiet=True)
except Exception as e:
    print(f"Error downloading NLTK data: {e}")

# Initialize SentenceTransformer model (this will be reused)
try:
    sentence_model = SentenceTransformer("all-MiniLM-L6-v2")
except Exception as e:
    print(f"Warning: Could not load SentenceTransformer model: {e}")
    sentence_model = None


def simple_tokenize(text):
    """Simple tokenization function."""
    # Convert to string if not already
    text = str(text)
    return text.lower().replace(".", " ").replace(",", " ").replace("!", " ").replace("?", " ").split()


_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _format_day_month_year(dt: datetime) -> str:
    return f"{dt.day} {dt.strftime('%B %Y')}"


def _parse_date_any(text: str) -> datetime | None:
    text = str(text).strip()

    m = re.fullmatch(
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s*,?\s*(\d{4})\b",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        day = int(m.group(1))
        month = _MONTHS[m.group(2).lower()]
        year = int(m.group(3))
        return datetime(year, month, day)

    m = re.fullmatch(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(\d{4})\b",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        month = _MONTHS[m.group(1).lower()]
        day = int(m.group(2))
        year = int(m.group(3))
        return datetime(year, month, day)

    return None


def normalize_time_answer(text: str) -> str:
    """Normalize equivalent date/time expressions to a canonical form.

    This is used to make string-matching metrics more robust for category-2 (time) questions.
    """

    s = str(text).strip()
    if not s:
        return s

    dt = _parse_date_any(s)
    if dt:
        return _format_day_month_year(dt)

    m = re.fullmatch(r"Last\s+week\s*\(([^)]+)\)", s, flags=re.IGNORECASE)
    if m:
        dt = _parse_date_any(m.group(1))
        if dt:
            return _format_day_month_year(dt)

    m = re.search(
        r"\bThe\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+before\s+(.+)$",
        s,
        flags=re.IGNORECASE,
    )
    if m:
        target_weekday = _WEEKDAYS[m.group(1).lower()]
        anchor_dt = _parse_date_any(m.group(2))
        if anchor_dt:
            days_back = (anchor_dt.weekday() - target_weekday) % 7
            if days_back == 0:
                days_back = 7
            return _format_day_month_year(anchor_dt - timedelta(days=days_back))

    m = re.search(r"\bThe\s+week\s+before\s+(.+)$", s, flags=re.IGNORECASE)
    if m:
        anchor_dt = _parse_date_any(m.group(1))
        if anchor_dt:
            return _format_day_month_year(anchor_dt - timedelta(days=7))

    m = re.search(r"\bThe\s+weekend\s+before\s+(.+)$", s, flags=re.IGNORECASE)
    if m:
        anchor_dt = _parse_date_any(m.group(1))
        if anchor_dt:
            target_weekday = _WEEKDAYS["saturday"]
            days_back = (anchor_dt.weekday() - target_weekday) % 7
            if days_back == 0:
                days_back = 7
            return _format_day_month_year(anchor_dt - timedelta(days=days_back))

    m = re.search(r"\btwo\s+weekends\s+before\s+(.+)$", s, flags=re.IGNORECASE)
    if m:
        anchor_dt = _parse_date_any(m.group(1))
        if anchor_dt:
            target_weekday = _WEEKDAYS["saturday"]
            days_back = (anchor_dt.weekday() - target_weekday) % 7
            if days_back == 0:
                days_back = 7
            first_weekend = anchor_dt - timedelta(days=days_back)
            return _format_day_month_year(first_weekend - timedelta(days=14))

    m = re.fullmatch(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s*,?\s*(\d{4})",
        s,
        flags=re.IGNORECASE,
    )
    if m:
        month_name = m.group(1).capitalize()
        year = int(m.group(2))
        return f"{month_name} {year}"

    m = re.fullmatch(r"(19\d{2}|20\d{2})", s)
    if m:
        return m.group(1)

    return s


def calculate_rouge_scores(prediction: str, reference: str) -> Dict[str, float]:
    """Calculate ROUGE scores for prediction against reference."""
    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
    scores = scorer.score(reference, prediction)
    return {
        "rouge1_f": scores["rouge1"].fmeasure,
        "rouge2_f": scores["rouge2"].fmeasure,
        "rougeL_f": scores["rougeL"].fmeasure,
    }


def calculate_bleu_scores(prediction: str, reference: str) -> Dict[str, float]:
    """Calculate BLEU scores with different n-gram settings."""
    try:
        pred_tokens = nltk.word_tokenize(prediction.lower())
        ref_tokens = [nltk.word_tokenize(reference.lower())]
    except LookupError:
        pred_tokens = simple_tokenize(prediction)
        ref_tokens = [simple_tokenize(reference)]

    weights_list = [(1, 0, 0, 0), (0.5, 0.5, 0, 0), (0.33, 0.33, 0.33, 0), (0.25, 0.25, 0.25, 0.25)]
    smooth = SmoothingFunction().method1

    scores = {}
    for n, weights in enumerate(weights_list, start=1):
        try:
            score = sentence_bleu(ref_tokens, pred_tokens, weights=weights, smoothing_function=smooth)
        except Exception as e:
            print(f"Error calculating BLEU score: {e}")
            score = 0.0
        scores[f"bleu{n}"] = score

    return scores


def calculate_bert_scores(prediction: str, reference: str) -> Dict[str, float]:
    """Calculate BERTScore for semantic similarity."""
    try:
        P, R, F1 = bert_score([prediction], [reference], lang="en", verbose=False)
        return {"bert_precision": P.item(), "bert_recall": R.item(), "bert_f1": F1.item()}
    except Exception as e:
        print(f"Error calculating BERTScore: {e}")
        return {"bert_precision": 0.0, "bert_recall": 0.0, "bert_f1": 0.0}


def calculate_meteor_score(prediction: str, reference: str) -> float:
    """Calculate METEOR score for the prediction."""
    try:
        return meteor_score([reference.split()], prediction.split())
    except Exception as e:
        print(f"Error calculating METEOR score: {e}")
        return 0.0


def calculate_sentence_similarity(prediction: str, reference: str) -> float:
    """Calculate sentence embedding similarity using SentenceBERT."""
    if sentence_model is None:
        return 0.0
    try:
        # Encode sentences
        embedding1 = sentence_model.encode([prediction], convert_to_tensor=True)
        embedding2 = sentence_model.encode([reference], convert_to_tensor=True)

        # Calculate cosine similarity
        similarity = pytorch_cos_sim(embedding1, embedding2).item()
        return float(similarity)
    except Exception as e:
        print(f"Error calculating sentence similarity: {e}")
        return 0.0


def calculate_metrics(prediction: str, reference: str, category: int | str | None = None) -> Dict[str, float]:
    """Calculate comprehensive evaluation metrics for a prediction."""
    # Handle empty or None values
    if not prediction or not reference:
        return {
            "exact_match": 0,
            "f1": 0.0,
            "rouge1_f": 0.0,
            "rouge2_f": 0.0,
            "rougeL_f": 0.0,
            "bleu1": 0.0,
            "bleu2": 0.0,
            "bleu3": 0.0,
            "bleu4": 0.0,
            "bert_f1": 0.0,
            "meteor": 0.0,
            "sbert_similarity": 0.0,
        }

    # Convert to strings if they're not already
    prediction = str(prediction).strip()
    reference = str(reference).strip()

    if str(category).strip() == "2":
        prediction = normalize_time_answer(prediction)
        reference = normalize_time_answer(reference)

    # Calculate exact match
    exact_match = int(prediction.lower() == reference.lower())

    # Calculate token-based F1 score
    pred_tokens = set(simple_tokenize(prediction))
    ref_tokens = set(simple_tokenize(reference))
    common_tokens = pred_tokens & ref_tokens

    if not pred_tokens or not ref_tokens:
        f1 = 0.0
    else:
        precision = len(common_tokens) / len(pred_tokens)
        recall = len(common_tokens) / len(ref_tokens)
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Calculate all scores
    bleu_scores = calculate_bleu_scores(prediction, reference)

    # Combine all metrics
    metrics = {
        "exact_match": exact_match,
        "f1": f1,
        **bleu_scores,
    }

    return metrics


def aggregate_metrics(
    all_metrics: List[Dict[str, float]], all_categories: List[int]
) -> Dict[str, Dict[str, Union[float, Dict[str, float]]]]:
    """Calculate aggregate statistics for all metrics, split by category."""
    if not all_metrics:
        return {}

    # Initialize aggregates for overall and per-category metrics
    aggregates = defaultdict(list)
    category_aggregates = defaultdict(lambda: defaultdict(list))

    # Collect all values for each metric, both overall and per category
    for metrics, category in zip(all_metrics, all_categories):
        for metric_name, value in metrics.items():
            aggregates[metric_name].append(value)
            category_aggregates[category][metric_name].append(value)

    # Calculate statistics for overall metrics
    results = {"overall": {}}

    for metric_name, values in aggregates.items():
        results["overall"][metric_name] = {
            "mean": statistics.mean(values),
            "std": statistics.stdev(values) if len(values) > 1 else 0.0,
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "count": len(values),
        }

    # Calculate statistics for each category
    for category in sorted(category_aggregates.keys()):
        results[f"category_{category}"] = {}
        for metric_name, values in category_aggregates[category].items():
            if values:  # Only calculate if we have values for this category
                results[f"category_{category}"][metric_name] = {
                    "mean": statistics.mean(values),
                    "std": statistics.stdev(values) if len(values) > 1 else 0.0,
                    "median": statistics.median(values),
                    "min": min(values),
                    "max": max(values),
                    "count": len(values),
                }

    return results
