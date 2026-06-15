# news-scraper

scrapes micro-cap news as it lands and scores how much each headline should move the stock. most real moves in small names come from one SEC filing or press release, minutes before anyone writes it up, so it's built around reading that single line of text fast.

the question i started with: is a pre-trained sentiment model enough to do that alone? i used FinBERT ([Araci, 2019](https://arxiv.org/abs/1908.10063)), BERT fine-tuned on financial text and the usual off-the-shelf pick. it isn't, and these two figures are why.

score is P(positive) minus P(negative), so -1 to +1. on obvious headlines it behaves:

![FinBERT score on a sample of headlines](figures/finbert_scores.png)

but the middle is the problem. "Phase 2 trial misses primary endpoint, shares halted" comes out slightly positive, and so does a dilutive offering. it scores the tone of the words, not what the event does to the stock. over a wider set, most headlines just come back flat:

![Distribution of FinBERT scores over 40 headlines](figures/neutral_band.png)

24 of 40 land in the [-0.3, 0.3] band. wire copy is terse and hedged, exactly where FinBERT has the least to grab.

so sentiment ends up as one input, not the answer. the alpha score is a weighted sum:

- event type (offering, SEC filing, going concern, ...) 0.35
- FinBERT sentiment 0.25
- source reliability 0.15
- recency 0.15
- float and liquidity 0.10

event type wins because what happened beats how it was phrased. a dilutive offering reads bearish at -0.4 no matter the wording, then sentiment nudges the tie. the rest of the repo is the ingestion workers, ticker linking, a FastAPI backend, and a Next.js dashboard around that.

figures come straight from the model:

```
pip install torch transformers matplotlib
python scripts/make_readme_figures.py
```
