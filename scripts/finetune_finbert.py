#!/usr/bin/env python3
"""Fine-tune FinBERT on financial news sentiment data.

This script fine-tunes the ProsusAI/finbert model on custom financial news
data prepared by prepare_finetuning_data.py.

Requirements:
    pip install transformers datasets torch accelerate evaluate scikit-learn

Usage:
    python scripts/finetune_finbert.py --data ./data/finetuning --output ./models/finbert-finetuned
    python scripts/finetune_finbert.py --epochs 5 --batch-size 16 --learning-rate 2e-5
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Suppress warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def main():
    """Main fine-tuning entry point."""
    parser = argparse.ArgumentParser(
        description="Fine-tune FinBERT on financial news sentiment"
    )

    parser.add_argument(
        "--data",
        type=Path,
        default=Path("./data/finetuning"),
        help="Path to training data directory",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./models/finbert-finetuned"),
        help="Output directory for fine-tuned model",
    )

    parser.add_argument(
        "--base-model",
        type=str,
        default="ProsusAI/finbert",
        help="Base model to fine-tune (default: ProsusAI/finbert)",
    )

    parser.add_argument(
        "--epochs",
        type=int,
        default=3,
        help="Number of training epochs (default: 3)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Training batch size (default: 16)",
    )

    parser.add_argument(
        "--learning-rate",
        type=float,
        default=2e-5,
        help="Learning rate (default: 2e-5)",
    )

    parser.add_argument(
        "--weight-decay",
        type=float,
        default=0.01,
        help="Weight decay (default: 0.01)",
    )

    parser.add_argument(
        "--warmup-ratio",
        type=float,
        default=0.1,
        help="Warmup ratio (default: 0.1)",
    )

    parser.add_argument(
        "--max-length",
        type=int,
        default=512,
        help="Maximum sequence length (default: 512)",
    )

    parser.add_argument(
        "--fp16",
        action="store_true",
        help="Use mixed precision training",
    )

    parser.add_argument(
        "--gradient-accumulation",
        type=int,
        default=1,
        help="Gradient accumulation steps (default: 1)",
    )

    parser.add_argument(
        "--eval-steps",
        type=int,
        default=100,
        help="Evaluation frequency (default: 100 steps)",
    )

    parser.add_argument(
        "--save-steps",
        type=int,
        default=500,
        help="Checkpoint save frequency (default: 500 steps)",
    )

    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        help="Resume from checkpoint",
    )

    parser.add_argument(
        "--push-to-hub",
        action="store_true",
        help="Push model to HuggingFace Hub",
    )

    parser.add_argument(
        "--hub-model-id",
        type=str,
        default=None,
        help="Model ID for HuggingFace Hub",
    )

    args = parser.parse_args()

    # Check for required packages
    try:
        import torch
        import transformers
        import datasets
        import evaluate
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            DataCollatorWithPadding,
            Trainer,
            TrainingArguments,
            EarlyStoppingCallback,
        )
        from datasets import load_dataset, Dataset, DatasetDict
        import numpy as np
    except ImportError as e:
        print(f"Missing required package: {e}")
        print("\nInstall requirements with:")
        print("pip install transformers datasets torch accelerate evaluate scikit-learn")
        sys.exit(1)

    # Verify data exists
    if not args.data.exists():
        print(f"Data directory not found: {args.data}")
        print("Run prepare_finetuning_data.py first")
        sys.exit(1)

    # Load label mapping
    label_mapping_path = args.data / "label_mapping.json"
    if label_mapping_path.exists():
        with open(label_mapping_path) as f:
            label_mapping = json.load(f)
        id2label = {int(k): v for k, v in label_mapping["id2label"].items()}
        label2id = label_mapping["label2id"]
    else:
        # Default mapping
        id2label = {0: "positive", 1: "negative", 2: "neutral"}
        label2id = {"positive": 0, "negative": 1, "neutral": 2}

    print(f"Label mapping: {label2id}")

    # Load dataset
    print(f"\nLoading dataset from {args.data}...")

    def load_json_data(file_path):
        """Load data from JSON file."""
        with open(file_path) as f:
            data = json.load(f)
        return data.get("data", data)

    try:
        # Try HuggingFace format first
        train_data = load_json_data(args.data / "train.json")
        val_data = load_json_data(args.data / "validation.json")
        test_data = load_json_data(args.data / "test.json")

        # Convert labels to integers
        for split in [train_data, val_data, test_data]:
            for item in split:
                item["label"] = label2id.get(item["label"], item["label"])

        dataset = DatasetDict({
            "train": Dataset.from_list(train_data),
            "validation": Dataset.from_list(val_data),
            "test": Dataset.from_list(test_data),
        })

    except Exception as e:
        print(f"Error loading data: {e}")
        sys.exit(1)

    print(f"Train: {len(dataset['train'])} examples")
    print(f"Validation: {len(dataset['validation'])} examples")
    print(f"Test: {len(dataset['test'])} examples")

    # Load tokenizer and model
    print(f"\nLoading model: {args.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.base_model,
        num_labels=len(id2label),
        id2label=id2label,
        label2id=label2id,
        ignore_mismatched_sizes=True,  # In case we're changing num_labels
    )

    # Tokenize dataset
    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=args.max_length,
            padding=False,
        )

    print("\nTokenizing dataset...")
    tokenized_dataset = dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=["text"],
    )

    # Data collator
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

    # Metrics
    accuracy_metric = evaluate.load("accuracy")
    f1_metric = evaluate.load("f1")
    precision_metric = evaluate.load("precision")
    recall_metric = evaluate.load("recall")

    def compute_metrics(eval_pred):
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=1)

        accuracy = accuracy_metric.compute(predictions=predictions, references=labels)
        f1 = f1_metric.compute(predictions=predictions, references=labels, average="weighted")
        precision = precision_metric.compute(predictions=predictions, references=labels, average="weighted")
        recall = recall_metric.compute(predictions=predictions, references=labels, average="weighted")

        return {
            "accuracy": accuracy["accuracy"],
            "f1": f1["f1"],
            "precision": precision["precision"],
            "recall": recall["recall"],
        }

    # Training arguments
    training_args = TrainingArguments(
        output_dir=str(args.output),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        warmup_ratio=args.warmup_ratio,
        gradient_accumulation_steps=args.gradient_accumulation,
        fp16=args.fp16,
        eval_strategy="steps",
        eval_steps=args.eval_steps,
        save_strategy="steps",
        save_steps=args.save_steps,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        logging_dir=str(args.output / "logs"),
        logging_steps=50,
        report_to="tensorboard",
        push_to_hub=args.push_to_hub,
        hub_model_id=args.hub_model_id,
    )

    # Initialize trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset["train"],
        eval_dataset=tokenized_dataset["validation"],
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
    )

    # Resume from checkpoint if specified
    resume_from = None
    if args.resume:
        resume_from = str(args.resume)
        print(f"\nResuming from checkpoint: {resume_from}")

    # Train
    print("\nStarting fine-tuning...")
    print(f"  Epochs: {args.epochs}")
    print(f"  Batch size: {args.batch_size}")
    print(f"  Learning rate: {args.learning_rate}")
    print(f"  Output: {args.output}")

    train_result = trainer.train(resume_from_checkpoint=resume_from)

    # Save model
    print("\nSaving model...")
    trainer.save_model()
    tokenizer.save_pretrained(args.output)

    # Save training metrics
    metrics_path = args.output / "training_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(train_result.metrics, f, indent=2)

    # Evaluate on test set
    print("\nEvaluating on test set...")
    test_results = trainer.evaluate(tokenized_dataset["test"])

    print("\nTest Results:")
    for key, value in test_results.items():
        print(f"  {key}: {value:.4f}")

    # Save test metrics
    test_metrics_path = args.output / "test_metrics.json"
    with open(test_metrics_path, "w") as f:
        json.dump(test_results, f, indent=2)

    # Create model card
    model_card = f"""---
language: en
tags:
  - sentiment-analysis
  - financial
  - finbert
  - fine-tuned
license: apache-2.0
datasets:
  - custom
metrics:
  - accuracy
  - f1
  - precision
  - recall
---

# FinBERT Fine-tuned on Financial News

This model is a fine-tuned version of [{args.base_model}](https://huggingface.co/{args.base_model})
on a custom financial news sentiment dataset.

## Model Description

Fine-tuned for sentiment analysis of financial news headlines and summaries.

## Training Data

- Train: {len(dataset['train'])} examples
- Validation: {len(dataset['validation'])} examples
- Test: {len(dataset['test'])} examples

## Training Procedure

- Epochs: {args.epochs}
- Batch size: {args.batch_size}
- Learning rate: {args.learning_rate}
- Weight decay: {args.weight_decay}

## Evaluation Results

| Metric | Score |
|--------|-------|
| Accuracy | {test_results.get('eval_accuracy', 'N/A'):.4f} |
| F1 (weighted) | {test_results.get('eval_f1', 'N/A'):.4f} |
| Precision | {test_results.get('eval_precision', 'N/A'):.4f} |
| Recall | {test_results.get('eval_recall', 'N/A'):.4f} |

## Usage

```python
from transformers import AutoModelForSequenceClassification, AutoTokenizer

model = AutoModelForSequenceClassification.from_pretrained("{args.output}")
tokenizer = AutoTokenizer.from_pretrained("{args.output}")

text = "Company XYZ reports record quarterly earnings"
inputs = tokenizer(text, return_tensors="pt")
outputs = model(**inputs)
```

## Labels

- 0: positive
- 1: negative
- 2: neutral
"""

    readme_path = args.output / "README.md"
    with open(readme_path, "w") as f:
        f.write(model_card)

    print(f"\nFine-tuning complete!")
    print(f"Model saved to: {args.output}")
    print(f"\nTo use the model in the application:")
    print(f"  1. Update backend/processing/sentiment/finbert_service.py")
    print(f"  2. Set MODEL_NAME = '{args.output}'")
    print(f"  3. Or set FINBERT_MODEL_PATH environment variable")


if __name__ == "__main__":
    main()
