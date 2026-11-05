"""
Fine-tune DistilBERT for legal case type classification.
Usage: python train_classifier.py --data dataset.csv --output ./classifier_model
"""

import argparse
import pandas as pd
import torch
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    Trainer, TrainingArguments, EvalPrediction
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import numpy as np

LABEL_MAP = {
    "Criminal": 0, "Civil": 1, "Family Law": 2,
    "Labour / Employment": 3, "Constitutional": 4, "Property Dispute": 5,
}


class LegalDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len=512):
        self.encodings = tokenizer(texts, truncation=True, padding=True, max_length=max_len)
        self.labels = labels

    def __len__(self): return len(self.labels)

    def __getitem__(self, idx):
        return {
            "input_ids": torch.tensor(self.encodings["input_ids"][idx]),
            "attention_mask": torch.tensor(self.encodings["attention_mask"][idx]),
            "labels": torch.tensor(self.labels[idx], dtype=torch.long),
        }


def compute_metrics(pred: EvalPrediction):
    preds = np.argmax(pred.predictions, axis=1)
    accuracy = (preds == pred.label_ids).mean()
    return {"accuracy": accuracy}


def train(data_path: str, output_dir: str, model_name: str = "distilbert-base-uncased", epochs: int = 5):
    df = pd.read_csv(data_path)  # Expects columns: 'text', 'label'
    assert "text" in df.columns and "label" in df.columns

    le = LabelEncoder()
    df["label_id"] = le.fit_transform(df["label"])

    train_df, val_df = train_test_split(df, test_size=0.2, stratify=df["label_id"], random_state=42)

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=len(LABEL_MAP)
    )

    train_ds = LegalDataset(train_df["text"].tolist(), train_df["label_id"].tolist(), tokenizer)
    val_ds = LegalDataset(val_df["text"].tolist(), val_df["label_id"].tolist(), tokenizer)

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=32,
        evaluation_strategy="epoch",
        save_strategy="best",
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
        logging_steps=50,
        fp16=torch.cuda.is_available(),
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"Classifier model saved to {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", default="./classifier_model")
    parser.add_argument("--model", default="distilbert-base-uncased")
    parser.add_argument("--epochs", type=int, default=5)
    args = parser.parse_args()
    train(args.data, args.output, args.model, args.epochs)
