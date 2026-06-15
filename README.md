# news-scraper

I scrape micro-cap news as it lands and score how much each headline should move the stock.

Most of the real moves in small names come from one SEC filing or press release, minutes before anyone writes it up. So the whole thing is built around reading that single line of text fast and deciding whether it matters. The question I started with: is a pre-trained financial sentiment model enough to do that on its own? I used FinBERT ([Araci, 2019](https://arxiv.org/abs/1908.10063)), BERT fine-tuned on financial text and the usual off-the-shelf pick. It isn't enough, and the two figures below are why.

## What FinBERT does with a headline

FinBERT returns probabilities for positive, negative, and neutral. I take the score as P(positive) minus P(negative), so it runs from -1 to +1. On obvious headlines it behaves:

![FinBERT score on a sample of headlines](figures/finbert_scores.png)

A record-revenue beat and a $200M contract sit near +1, a CEO stepping down goes negative. The middle is the problem. "Phase 2 trial misses primary endpoint, shares halted" comes out slightly positive, and so does a dilutive offering. FinBERT scores the tone of the words, not what the event does to the stock.

## It hedges to neutral

Over a wider set of headlines, most come back flat:

![Distribution of FinBERT scores over 40 headlines](figures/neutral_band.png)

24 of 40 land inside the [-0.3, 0.3] band, 25 of 40 are neutral by argmax. Wire copy is terse and deliberately hedged, which is the exact case FinBERT has the least to grab. Sentiment alone leaves most of the feed unscored.

## So sentiment is one input

The alpha score for an event is a weighted sum, and sentiment is a quarter of it:

| signal | weight |
| --- | --- |
| event type (offering, SEC filing, going concern, ...) | 0.35 |
| FinBERT sentiment | 0.25 |
| source reliability | 0.15 |
| recency | 0.15 |
| float and liquidity | 0.10 |

Event type carries the most because what happened beats how it was phrased. The classifier reads a dilutive offering as bearish at -0.4 no matter the wording, then sentiment only nudges the tie. Around that sits the rest of the repo: the ingestion workers, ticker linking, a FastAPI backend, and a Next.js dashboard.

## Reproducing the figures

```
pip install torch transformers matplotlib
python scripts/make_readme_figures.py
```

The full pipeline runs under `docker-compose up -d`; the backend installs with `cd backend && pip install -e .`.
