#!/usr/bin/env python3
"""Prepare training data for fine-tuning sentiment models on financial news.

This script exports labeled events from the database and prepares them
for fine-tuning FinBERT or similar sentiment analysis models.

Usage:
    python scripts/prepare_finetuning_data.py --output ./data/training
    python scripts/prepare_finetuning_data.py --format huggingface --split 0.8
    python scripts/prepare_finetuning_data.py --export-unlabeled --limit 1000
"""

import argparse
import csv
import json
import os
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class OutputFormat(str, Enum):
    """Output format options."""

    JSONL = "jsonl"
    CSV = "csv"
    HUGGINGFACE = "huggingface"  # HuggingFace datasets format


class SentimentLabel(str, Enum):
    """Sentiment labels for training."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass
class TrainingExample:
    """A single training example."""

    id: str
    text: str
    label: SentimentLabel
    confidence: float = 1.0
    source: str = ""
    ticker: str = ""
    event_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "label": self.label.value,
            "confidence": self.confidence,
            "source": self.source,
            "ticker": self.ticker,
            "event_type": self.event_type,
            "metadata": self.metadata,
        }


class FineTuningDataPreparer:
    """Prepares data for fine-tuning sentiment models."""

    # Minimum text length for training examples
    MIN_TEXT_LENGTH = 20

    # Maximum text length (will truncate)
    MAX_TEXT_LENGTH = 512

    # Minimum confidence threshold for including examples
    MIN_CONFIDENCE = 0.6

    def __init__(self, database_url: str):
        """Initialize data preparer.

        Args:
            database_url: PostgreSQL connection URL.
        """
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)

    def export_labeled_data(
        self,
        min_alpha: float | None = None,
        event_types: list[str] | None = None,
        limit: int | None = None,
        min_confidence: float | None = None,
    ) -> list[TrainingExample]:
        """Export labeled events as training examples.

        Args:
            min_alpha: Minimum alpha score filter.
            event_types: Filter by event types.
            limit: Maximum number of examples.
            min_confidence: Minimum sentiment confidence.

        Returns:
            List of TrainingExample objects.
        """
        min_confidence = min_confidence or self.MIN_CONFIDENCE

        query = """
            SELECT
                id,
                ticker,
                event_type,
                headline,
                summary,
                content,
                source_name,
                sentiment_score,
                sentiment_label,
                sentiment_confidence,
                alpha_score,
                direction
            FROM events
            WHERE sentiment_label IS NOT NULL
              AND sentiment_confidence >= :min_confidence
        """

        params: dict[str, Any] = {"min_confidence": min_confidence}

        if min_alpha is not None:
            query += " AND alpha_score >= :min_alpha"
            params["min_alpha"] = min_alpha

        if event_types:
            query += " AND event_type = ANY(:event_types)"
            params["event_types"] = event_types

        query += " ORDER BY event_time DESC"

        if limit:
            query += " LIMIT :limit"
            params["limit"] = limit

        examples = []

        with self.Session() as session:
            result = session.execute(text(query), params)

            for row in result:
                # Combine headline and summary for training text
                text_parts = []
                if row.headline:
                    text_parts.append(row.headline)
                if row.summary and row.summary != row.headline:
                    text_parts.append(row.summary)

                text = " ".join(text_parts)

                # Skip if text too short
                if len(text) < self.MIN_TEXT_LENGTH:
                    continue

                # Truncate if too long
                if len(text) > self.MAX_TEXT_LENGTH:
                    text = text[: self.MAX_TEXT_LENGTH]

                # Map sentiment label
                try:
                    label = SentimentLabel(row.sentiment_label.lower())
                except (ValueError, AttributeError):
                    continue

                example = TrainingExample(
                    id=str(row.id),
                    text=text,
                    label=label,
                    confidence=row.sentiment_confidence or 1.0,
                    source=row.source_name or "",
                    ticker=row.ticker or "",
                    event_type=row.event_type or "",
                    metadata={
                        "alpha_score": row.alpha_score,
                        "direction": row.direction,
                        "sentiment_score": row.sentiment_score,
                    },
                )
                examples.append(example)

        print(f"Exported {len(examples)} labeled examples")
        return examples

    def export_unlabeled_data(
        self,
        limit: int = 1000,
        exclude_sources: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Export unlabeled events for manual labeling.

        Args:
            limit: Maximum number of examples.
            exclude_sources: Sources to exclude.

        Returns:
            List of unlabeled examples for annotation.
        """
        query = """
            SELECT
                id,
                ticker,
                event_type,
                headline,
                summary,
                source_name,
                source_url,
                event_time
            FROM events
            WHERE sentiment_label IS NULL
               OR sentiment_confidence < :min_confidence
        """

        params: dict[str, Any] = {"min_confidence": self.MIN_CONFIDENCE}

        if exclude_sources:
            query += " AND source_name != ALL(:exclude_sources)"
            params["exclude_sources"] = exclude_sources

        query += " ORDER BY event_time DESC LIMIT :limit"
        params["limit"] = limit

        examples = []

        with self.Session() as session:
            result = session.execute(text(query), params)

            for row in result:
                text_parts = []
                if row.headline:
                    text_parts.append(row.headline)
                if row.summary and row.summary != row.headline:
                    text_parts.append(row.summary)

                text = " ".join(text_parts)

                if len(text) < self.MIN_TEXT_LENGTH:
                    continue

                examples.append(
                    {
                        "id": str(row.id),
                        "text": text[:self.MAX_TEXT_LENGTH],
                        "ticker": row.ticker or "",
                        "event_type": row.event_type or "",
                        "source": row.source_name or "",
                        "source_url": row.source_url or "",
                        "event_time": row.event_time.isoformat() if row.event_time else "",
                        "label": "",  # To be filled by annotator
                        "confidence": "",  # To be filled by annotator
                        "notes": "",  # Optional annotator notes
                    }
                )

        print(f"Exported {len(examples)} unlabeled examples for annotation")
        return examples

    def balance_dataset(
        self,
        examples: list[TrainingExample],
        strategy: str = "undersample",
    ) -> list[TrainingExample]:
        """Balance dataset by label distribution.

        Args:
            examples: List of training examples.
            strategy: Balancing strategy ('undersample', 'oversample').

        Returns:
            Balanced list of examples.
        """
        # Group by label
        by_label: dict[SentimentLabel, list[TrainingExample]] = {}
        for ex in examples:
            if ex.label not in by_label:
                by_label[ex.label] = []
            by_label[ex.label].append(ex)

        # Print distribution
        print("\nOriginal distribution:")
        for label, exs in sorted(by_label.items(), key=lambda x: x[0].value):
            print(f"  {label.value}: {len(exs)}")

        if strategy == "undersample":
            # Undersample to smallest class
            min_count = min(len(exs) for exs in by_label.values())
            balanced = []
            for exs in by_label.values():
                balanced.extend(random.sample(exs, min_count))

        elif strategy == "oversample":
            # Oversample to largest class
            max_count = max(len(exs) for exs in by_label.values())
            balanced = []
            for exs in by_label.values():
                balanced.extend(exs)
                # Add duplicates to reach max_count
                while len([e for e in balanced if e.label == exs[0].label]) < max_count:
                    balanced.append(random.choice(exs))

        else:
            balanced = examples

        # Shuffle
        random.shuffle(balanced)

        print(f"\nBalanced dataset size: {len(balanced)}")
        return balanced

    def split_dataset(
        self,
        examples: list[TrainingExample],
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
    ) -> tuple[list[TrainingExample], list[TrainingExample], list[TrainingExample]]:
        """Split dataset into train/val/test sets.

        Args:
            examples: List of training examples.
            train_ratio: Ratio for training set.
            val_ratio: Ratio for validation set.

        Returns:
            Tuple of (train, val, test) lists.
        """
        # Shuffle first
        shuffled = examples.copy()
        random.shuffle(shuffled)

        n = len(shuffled)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        train = shuffled[:train_end]
        val = shuffled[train_end:val_end]
        test = shuffled[val_end:]

        print(f"\nDataset split:")
        print(f"  Train: {len(train)} ({len(train)/n*100:.1f}%)")
        print(f"  Val: {len(val)} ({len(val)/n*100:.1f}%)")
        print(f"  Test: {len(test)} ({len(test)/n*100:.1f}%)")

        return train, val, test


class DataExporter:
    """Exports training data to various formats."""

    def export_jsonl(
        self,
        examples: list[TrainingExample],
        output_path: Path,
    ) -> None:
        """Export to JSONL format.

        Args:
            examples: List of training examples.
            output_path: Output file path.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            for ex in examples:
                f.write(json.dumps(ex.to_dict()) + "\n")

        print(f"Exported {len(examples)} examples to {output_path}")

    def export_csv(
        self,
        examples: list[TrainingExample] | list[dict[str, Any]],
        output_path: Path,
    ) -> None:
        """Export to CSV format.

        Args:
            examples: List of training examples or dicts.
            output_path: Output file path.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dicts if needed
        if examples and isinstance(examples[0], TrainingExample):
            rows = [ex.to_dict() for ex in examples]
        else:
            rows = examples

        if not rows:
            print("No examples to export")
            return

        # Get all keys
        fieldnames = list(rows[0].keys())

        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for row in rows:
                # Flatten nested dicts
                flat_row = {}
                for k, v in row.items():
                    if isinstance(v, dict):
                        flat_row[k] = json.dumps(v)
                    else:
                        flat_row[k] = v
                writer.writerow(flat_row)

        print(f"Exported {len(rows)} examples to {output_path}")

    def export_huggingface(
        self,
        train: list[TrainingExample],
        val: list[TrainingExample],
        test: list[TrainingExample],
        output_dir: Path,
    ) -> None:
        """Export to HuggingFace datasets format.

        Creates a dataset directory with train.json, val.json, test.json
        and dataset_info.json.

        Args:
            train: Training examples.
            val: Validation examples.
            test: Test examples.
            output_dir: Output directory.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Export splits
        for split_name, examples in [("train", train), ("validation", val), ("test", test)]:
            split_path = output_dir / f"{split_name}.json"

            data = {
                "data": [
                    {"text": ex.text, "label": ex.label.value}
                    for ex in examples
                ]
            }

            with open(split_path, "w") as f:
                json.dump(data, f, indent=2)

            print(f"Exported {len(examples)} examples to {split_path}")

        # Create dataset info
        info = {
            "description": "Financial news sentiment dataset for fine-tuning",
            "citation": "",
            "homepage": "",
            "license": "proprietary",
            "features": {
                "text": {"dtype": "string"},
                "label": {"dtype": "string", "class_label": ["positive", "negative", "neutral"]},
            },
            "splits": {
                "train": {"num_examples": len(train)},
                "validation": {"num_examples": len(val)},
                "test": {"num_examples": len(test)},
            },
            "created": datetime.now(timezone.utc).isoformat(),
        }

        info_path = output_dir / "dataset_info.json"
        with open(info_path, "w") as f:
            json.dump(info, f, indent=2)

        print(f"Created dataset info at {info_path}")


def create_label_mapping_file(output_path: Path) -> None:
    """Create a label mapping file for fine-tuning.

    Args:
        output_path: Output file path.
    """
    mapping = {
        "id2label": {
            "0": "positive",
            "1": "negative",
            "2": "neutral",
        },
        "label2id": {
            "positive": 0,
            "negative": 1,
            "neutral": 2,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(mapping, f, indent=2)

    print(f"Created label mapping at {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Prepare financial news data for sentiment model fine-tuning"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./data/finetuning"),
        help="Output directory for training data",
    )

    parser.add_argument(
        "--format",
        type=str,
        choices=["jsonl", "csv", "huggingface"],
        default="huggingface",
        help="Output format",
    )

    parser.add_argument(
        "--split",
        type=float,
        default=0.8,
        help="Training set ratio (default: 0.8)",
    )

    parser.add_argument(
        "--balance",
        type=str,
        choices=["none", "undersample", "oversample"],
        default="undersample",
        help="Dataset balancing strategy",
    )

    parser.add_argument(
        "--min-alpha",
        type=float,
        default=None,
        help="Minimum alpha score filter",
    )

    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.6,
        help="Minimum sentiment confidence (default: 0.6)",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of examples",
    )

    parser.add_argument(
        "--export-unlabeled",
        action="store_true",
        help="Export unlabeled data for annotation",
    )

    parser.add_argument(
        "--database-url",
        type=str,
        default=os.environ.get(
            "DATABASE_SYNC_URL",
            "postgresql://user:password@localhost:5432/newsdb"
        ),
        help="Database connection URL",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )

    args = parser.parse_args()

    # Set random seed
    random.seed(args.seed)

    # Initialize
    preparer = FineTuningDataPreparer(args.database_url)
    exporter = DataExporter()

    if args.export_unlabeled:
        # Export unlabeled data for annotation
        unlabeled = preparer.export_unlabeled_data(limit=args.limit or 1000)

        output_path = args.output / "unlabeled_for_annotation.csv"
        exporter.export_csv(unlabeled, output_path)

        print(f"\nExported unlabeled data to {output_path}")
        print("Please annotate the 'label' column with: positive, negative, or neutral")
        print("Optionally fill 'confidence' (0.0-1.0) and 'notes' columns")
        return

    # Export labeled data
    print("\nExporting labeled data...")
    examples = preparer.export_labeled_data(
        min_alpha=args.min_alpha,
        limit=args.limit,
        min_confidence=args.min_confidence,
    )

    if not examples:
        print("No labeled examples found. Run sentiment analysis first.")
        return

    # Balance if requested
    if args.balance != "none":
        examples = preparer.balance_dataset(examples, strategy=args.balance)

    # Split dataset
    train, val, test = preparer.split_dataset(
        examples,
        train_ratio=args.split,
        val_ratio=(1 - args.split) / 2,
    )

    # Export based on format
    if args.format == "huggingface":
        exporter.export_huggingface(train, val, test, args.output)
        create_label_mapping_file(args.output / "label_mapping.json")

    elif args.format == "jsonl":
        exporter.export_jsonl(train, args.output / "train.jsonl")
        exporter.export_jsonl(val, args.output / "val.jsonl")
        exporter.export_jsonl(test, args.output / "test.jsonl")

    elif args.format == "csv":
        exporter.export_csv(train, args.output / "train.csv")
        exporter.export_csv(val, args.output / "val.csv")
        exporter.export_csv(test, args.output / "test.csv")

    print(f"\nData exported to {args.output}")
    print("\nNext steps:")
    print("1. Review the data quality")
    print("2. Run fine-tuning with: python scripts/finetune_finbert.py")
    print("3. See docs/FINETUNING.md for detailed instructions")


if __name__ == "__main__":
    main()
