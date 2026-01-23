# FinBERT Fine-Tuning Guide

This document describes how to fine-tune the FinBERT sentiment analysis model on custom financial news data.

## Overview

The system uses [ProsusAI/finbert](https://huggingface.co/ProsusAI/finbert) for financial sentiment analysis. Fine-tuning on domain-specific data can improve accuracy for:

- Penny stock / micro-cap news
- SEC filings
- Press releases
- Social media sentiment

## Prerequisites

### System Requirements

- Python 3.10+
- 8GB+ RAM (16GB recommended)
- GPU recommended for faster training (NVIDIA with CUDA)
- 10GB+ disk space for model checkpoints

### Python Dependencies

```bash
pip install transformers datasets torch accelerate evaluate scikit-learn tensorboard
```

## Data Preparation

### Step 1: Export Labeled Data

Use the data preparation script to export events with sentiment labels:

```bash
# Export all labeled data in HuggingFace format
python scripts/prepare_finetuning_data.py --output ./data/finetuning --format huggingface

# Export with filtering
python scripts/prepare_finetuning_data.py \
    --output ./data/finetuning \
    --min-alpha 0.3 \
    --min-confidence 0.7 \
    --balance undersample
```

### Step 2: Export Unlabeled Data for Annotation

If you need more training data, export unlabeled events:

```bash
python scripts/prepare_finetuning_data.py --export-unlabeled --limit 1000
```

This creates a CSV file for manual annotation.

### Data Format

The script outputs data in HuggingFace datasets format:

```
data/finetuning/
  train.json          # Training split (80%)
  validation.json     # Validation split (10%)
  test.json           # Test split (10%)
  label_mapping.json  # Label ID mapping
  dataset_info.json   # Dataset metadata
```

Each JSON file contains:

```json
{
  "data": [
    {"text": "Company XYZ reports record earnings", "label": "positive"},
    {"text": "Stock plunges on fraud investigation", "label": "negative"},
    {"text": "Company to report earnings next week", "label": "neutral"}
  ]
}
```

### Data Requirements

| Metric | Minimum | Recommended |
|--------|---------|-------------|
| Total examples | 1,000 | 10,000+ |
| Per class | 200 | 2,000+ |
| Text length | 20 chars | 50-200 chars |

## Fine-Tuning Process

### Step 1: Run Fine-Tuning

```bash
python scripts/finetune_finbert.py \
    --data ./data/finetuning \
    --output ./models/finbert-finetuned \
    --epochs 3 \
    --batch-size 16 \
    --learning-rate 2e-5
```

### Hyperparameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--epochs` | 3 | Number of training epochs |
| `--batch-size` | 16 | Training batch size |
| `--learning-rate` | 2e-5 | Learning rate |
| `--weight-decay` | 0.01 | Weight decay for regularization |
| `--warmup-ratio` | 0.1 | Warmup steps ratio |
| `--max-length` | 512 | Maximum sequence length |
| `--fp16` | False | Enable mixed precision training |
| `--gradient-accumulation` | 1 | Gradient accumulation steps |

### GPU Training

For faster training with GPU:

```bash
# Check CUDA availability
python -c "import torch; print(torch.cuda.is_available())"

# Run with mixed precision
python scripts/finetune_finbert.py \
    --data ./data/finetuning \
    --output ./models/finbert-finetuned \
    --fp16 \
    --batch-size 32
```

### CPU Training

For systems without GPU:

```bash
python scripts/finetune_finbert.py \
    --data ./data/finetuning \
    --output ./models/finbert-finetuned \
    --batch-size 8 \
    --gradient-accumulation 4
```

## Monitoring Training

### TensorBoard

Training logs are saved to the output directory:

```bash
tensorboard --logdir ./models/finbert-finetuned/logs
```

Access at http://localhost:6006

### Metrics

The training script tracks:
- **Loss**: Training and validation loss
- **Accuracy**: Classification accuracy
- **F1 Score**: Weighted F1 score (primary metric)
- **Precision/Recall**: Per-class metrics

## Using the Fine-Tuned Model

### Option 1: Update Service Configuration

Edit `backend/processing/sentiment/finbert_service.py`:

```python
class FinBERTService:
    # Change from default model
    MODEL_NAME = "./models/finbert-finetuned"  # Or absolute path
```

### Option 2: Environment Variable

```bash
export FINBERT_MODEL_PATH="./models/finbert-finetuned"
```

Then update the service to use it:

```python
import os

class FinBERTService:
    MODEL_NAME = os.environ.get("FINBERT_MODEL_PATH", "ProsusAI/finbert")
```

### Option 3: Runtime Configuration

```python
from backend.processing.sentiment.finbert_service import FinBERTService

# Use fine-tuned model
service = FinBERTService(model_name="./models/finbert-finetuned")
result = service.analyze("Company reports record earnings")
```

## Evaluation

### Automated Evaluation

The fine-tuning script automatically evaluates on the test set and saves metrics:

```bash
cat models/finbert-finetuned/test_metrics.json
```

### Manual Evaluation

```python
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch

# Load model
model_path = "./models/finbert-finetuned"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSequenceClassification.from_pretrained(model_path)

# Test examples
test_texts = [
    "Company beats earnings expectations",
    "Stock crashes on bankruptcy fears",
    "Quarterly report scheduled for next week",
]

for text in test_texts:
    inputs = tokenizer(text, return_tensors="pt", truncation=True)
    with torch.no_grad():
        outputs = model(**inputs)

    probs = torch.softmax(outputs.logits, dim=1)
    pred = torch.argmax(probs).item()

    labels = {0: "positive", 1: "negative", 2: "neutral"}
    print(f"{text}")
    print(f"  Prediction: {labels[pred]} ({probs[0][pred]:.2%})")
    print()
```

## Best Practices

### Data Quality

1. **Balanced Classes**: Use `--balance undersample` to balance classes
2. **High Confidence**: Filter with `--min-confidence 0.7` for cleaner labels
3. **Diverse Sources**: Include data from multiple news sources
4. **Recent Data**: Prioritize recent articles for current market language

### Training Tips

1. **Start Small**: Test with a small dataset first
2. **Monitor Overfitting**: Watch validation loss vs training loss
3. **Early Stopping**: The script includes early stopping (patience=3)
4. **Checkpoints**: Model saves checkpoints every 500 steps

### Common Issues

#### Out of Memory (OOM)

```bash
# Reduce batch size and use gradient accumulation
python scripts/finetune_finbert.py \
    --batch-size 8 \
    --gradient-accumulation 4
```

#### Slow Training

```bash
# Enable mixed precision (requires GPU)
python scripts/finetune_finbert.py --fp16
```

#### Poor Performance

1. Check data quality and label accuracy
2. Try different hyperparameters
3. Increase training data
4. Ensure balanced classes

## Advanced Topics

### Resuming Training

```bash
python scripts/finetune_finbert.py \
    --resume ./models/finbert-finetuned/checkpoint-1000
```

### Push to HuggingFace Hub

```bash
# Login first
huggingface-cli login

# Train and push
python scripts/finetune_finbert.py \
    --push-to-hub \
    --hub-model-id your-username/finbert-financial-news
```

### Multi-GPU Training

```bash
# Using accelerate
accelerate launch scripts/finetune_finbert.py \
    --data ./data/finetuning \
    --output ./models/finbert-finetuned
```

### Hyperparameter Search

For optimal hyperparameters, consider using Optuna or Ray Tune:

```python
# Example with Optuna
import optuna
from transformers import Trainer, TrainingArguments

def objective(trial):
    learning_rate = trial.suggest_loguniform("learning_rate", 1e-6, 1e-4)
    batch_size = trial.suggest_categorical("batch_size", [8, 16, 32])

    training_args = TrainingArguments(
        learning_rate=learning_rate,
        per_device_train_batch_size=batch_size,
        ...
    )

    trainer = Trainer(...)
    trainer.train()

    return trainer.evaluate()["eval_f1"]

study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=20)
```

## File Structure

```
scripts/
  prepare_finetuning_data.py  # Data export script
  finetune_finbert.py         # Fine-tuning script

data/
  finetuning/
    train.json
    validation.json
    test.json
    label_mapping.json
    dataset_info.json
    unlabeled_for_annotation.csv  # If exported

models/
  finbert-finetuned/
    config.json
    model.safetensors
    tokenizer.json
    vocab.txt
    training_metrics.json
    test_metrics.json
    README.md
    logs/                     # TensorBoard logs
```

## Related Documentation

- [Data Labeling Guidelines](./DATA_LABELING_GUIDELINES.md)
- [Paywall Strategy](./PAYWALL_STRATEGY.md)
- [Sentiment Analysis Architecture](./ARCHITECTURE.md)
