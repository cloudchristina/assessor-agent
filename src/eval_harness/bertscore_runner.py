"""Wrap BERTScore for narrative-vs-reference similarity."""
from __future__ import annotations

from bert_score import score

_DEFAULT_MODEL = "microsoft/deberta-xlarge-mnli"


def bertscore_vs_reference(
    narrative_text: str,
    reference_text: str,
    *,
    model_type: str = _DEFAULT_MODEL,
) -> float:
    """Return F1 BERTScore in [0, 1] (clamped).

    Parameters
    ----------
    narrative_text:
        The agent's narrative output to score.
    reference_text:
        The reference/ground-truth text to compare against.
    model_type:
        HuggingFace model identifier for BERTScore.
        Default: "microsoft/deberta-xlarge-mnli".

    Returns
    -------
    float in [0, 1], the F1-score similarity clamped to unit range.
    """
    _, _, f1 = score(
        cands=[narrative_text],
        refs=[reference_text],
        model_type=model_type,
        rescale_with_baseline=True,
        verbose=False,
    )
    val = float(f1[0])
    return max(0.0, min(1.0, val))
