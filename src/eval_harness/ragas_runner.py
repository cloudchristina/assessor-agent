"""Wrap Ragas with our schemas. We feed it:
  question     = a constant prompt describing the task
  answer       = narrative text (executive summary + theme summaries + finding narratives)
  contexts     = list of finding evidence strings (one per finding)
  ground_truth = the case's must_mention items joined
"""
from __future__ import annotations

from datasets import Dataset
from ragas.evaluation import evaluate
from ragas.metrics import answer_relevancy, context_precision, faithfulness


def compute_ragas_metrics(
    narrative_text: str,
    findings: list[dict],
    must_mention: list[str],
) -> dict[str, float]:
    """Compute Ragas faithfulness, answer_relevance, and context_precision.

    Parameters
    ----------
    narrative_text:
        The agent's narrative output (executive summary + finding details).
    findings:
        List of finding dicts (each has rule_id, severity, principal, etc.).
    must_mention:
        List of strings that must appear in the narrative for the case to pass.

    Returns
    -------
    dict with keys ``faithfulness``, ``answer_relevance``, ``context_precision``.
    All values are floats in [0, 1].
    """
    contexts = [_finding_to_context(f) for f in findings]
    dataset = Dataset.from_dict(
        {
            "question": ["Summarise the access-review findings for this cycle"],
            "answer": [narrative_text],
            "contexts": [contexts],
            "ground_truth": [" ".join(must_mention)],
        }
    )
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision],
    )
    return {
        "faithfulness": float(result["faithfulness"]),
        "answer_relevance": float(result["answer_relevancy"]),
        "context_precision": float(result["context_precision"]),
    }


def _finding_to_context(f: dict) -> str:
    """Serialise a single finding dict to a plain-text context string for Ragas."""
    parts = [
        f"finding_id={f.get('finding_id', '?')}",
        f"rule_id={f.get('rule_id', '?')}",
        f"severity={f.get('severity', '?')}",
        f"principal={f.get('principal', '?')}",
        f"databases={f.get('databases', [])}",
        f"ism_controls={f.get('ism_controls', [])}",
        f"evidence={f.get('evidence', {})}",
    ]
    return " | ".join(parts)
