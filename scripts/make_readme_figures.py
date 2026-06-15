"""Generate the README figures from real FinBERT inference.

Runs ProsusAI/finbert (the same model and score formula the pipeline uses) over a
set of example financial headlines and writes two figures to figures/.

    score = P(positive) - P(negative)        # -1 .. +1, matches finbert_service.py

Run: python scripts/make_readme_figures.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL = "ProsusAI/finbert"
LABELS = ["positive", "negative", "neutral"]
OUT = Path(__file__).resolve().parent.parent / "figures"

# A small picked set of headlines, the kind of micro-cap event the scraper watches.
EXAMPLES = [
    "Company reports record quarterly revenue, beats estimates",
    "FDA grants priority review for lead drug candidate",
    "Board approves $50 million share buyback program",
    "Firm secures $200M defense contract from the Pentagon",
    "Net loss widens as gross margin collapses year over year",
    "SEC opens fraud investigation into accounting practices",
    "Company announces dilutive offering of 12 million shares",
    "Auditor flags substantial doubt about going concern",
    "Quarterly earnings report scheduled for next Tuesday",
    "Company to present at industry conference in March",
    "CEO to step down at end of fiscal year",
    "Phase 2 trial misses primary endpoint, shares halted",
]

# A larger pool used only to measure how often the model hedges to neutral.
POOL = EXAMPLES + [
    "Insider buys 500,000 shares at market price",
    "Short seller publishes report alleging undisclosed liabilities",
    "Company signs distribution deal expanding into Europe",
    "Patent granted for core manufacturing process",
    "Guidance cut on weak demand and rising input costs",
    "Dividend suspended to preserve cash",
    "Acquisition completed ahead of schedule",
    "Class action lawsuit filed over delayed filings",
    "Backlog grows to a record on strong bookings",
    "Reverse split announced to maintain listing compliance",
    "Company files for bankruptcy protection",
    "Strategic review launched to explore a sale",
    "Preliminary results show in-line revenue",
    "New CFO appointed from a larger competitor",
    "Plant fire disrupts production for an unknown period",
    "Contract renewed with largest customer for three years",
    "Delisting notice received from the exchange",
    "Upsized offering prices below the prior close",
    "Milestone payment triggered under licensing agreement",
    "Routine 8-K filed disclosing officer compensation",
    "Annual meeting of shareholders set for June",
    "Company repays term loan in full ahead of maturity",
    "Recall issued for a single product lot",
    "Settlement reached, charge taken this quarter",
    "Order book softens after a strong prior quarter",
    "Joint venture formed to develop a new market",
    "Convertible notes restructured with existing holders",
    "Trading volume spikes on no company-specific news",
]


def score_texts(texts, tok, model):
    enc = tok(texts, return_tensors="pt", truncation=True, max_length=512, padding=True)
    with torch.no_grad():
        probs = torch.softmax(model(**enc).logits, dim=1)
    out = []
    for row in probs:
        p = {lab: float(row[i]) for i, lab in enumerate(LABELS)}
        out.append((p["positive"] - p["negative"], max(p, key=p.get), p))
    return out


def fig_examples(scored):
    pairs = sorted(zip(EXAMPLES, scored), key=lambda x: x[1][0])
    texts = [t for t, _ in pairs]
    scores = [s[0] for _, s in pairs]
    colors = ["#2e7d32" if v > 0.3 else "#c62828" if v < -0.3 else "#9e9e9e" for v in scores]

    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.barh(range(len(texts)), scores, color=colors)
    ax.set_yticks(range(len(texts)))
    ax.set_yticklabels(texts, fontsize=8.5)
    ax.axvline(0, color="#444", linewidth=0.8)
    ax.axvline(0.3, color="#bbb", linewidth=0.8, linestyle="--")
    ax.axvline(-0.3, color="#bbb", linewidth=0.8, linestyle="--")
    ax.set_xlim(-1, 1)
    ax.set_xlabel("FinBERT score  (P(positive) - P(negative))")
    fig.tight_layout()
    fig.savefig(OUT / "finbert_scores.png", dpi=140)
    plt.close(fig)


def fig_neutral(scored_pool):
    scores = [s[0] for s in scored_pool]
    argmax_neutral = sum(1 for s in scored_pool if s[1] == "neutral")
    band_neutral = sum(1 for v in scores if -0.3 <= v <= 0.3)
    n = len(scores)

    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.hist(scores, bins=20, range=(-1, 1), color="#5c6bc0", edgecolor="white")
    ax.axvspan(-0.3, 0.3, color="#9e9e9e", alpha=0.18)
    ax.axvline(0, color="#444", linewidth=0.8)
    ax.set_xlim(-1, 1)
    ax.set_xlabel("FinBERT score")
    ax.set_ylabel("headlines")
    ax.text(
        0, ax.get_ylim()[1] * 0.92,
        f"{band_neutral}/{n} land in the neutral band",
        ha="center", fontsize=9, color="#555",
    )
    fig.tight_layout()
    fig.savefig(OUT / "neutral_band.png", dpi=140)
    plt.close(fig)

    print(f"pool size: {n}")
    print(f"argmax neutral: {argmax_neutral}/{n} ({argmax_neutral / n:.0%})")
    print(f"score in [-0.3, 0.3]: {band_neutral}/{n} ({band_neutral / n:.0%})")


def main():
    OUT.mkdir(exist_ok=True)
    print("loading", MODEL)
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL)
    model.eval()

    fig_examples(score_texts(EXAMPLES, tok, model))
    fig_neutral(score_texts(POOL, tok, model))
    print("wrote figures to", OUT)


if __name__ == "__main__":
    main()
