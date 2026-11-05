"""
Fine-tune spaCy NER model on annotated legal case data.
Usage: python train_ner.py --data annotations.jsonl --output ./ner_model
"""

import argparse
import json
import random
import spacy
from spacy.training import Example
from pathlib import Path


def load_annotations(path: str):
    """Load JSONL annotations in spaCy format."""
    data = []
    with open(path) as f:
        for line in f:
            item = json.loads(line)
            # Expected format: {"text": "...", "entities": [[start, end, label], ...]}
            data.append((item["text"], {"entities": item["entities"]}))
    return data


def train(data_path: str, output_dir: str, n_iter: int = 30):
    nlp = spacy.load("en_core_web_sm")

    # Add custom labels
    ner = nlp.get_pipe("ner") if nlp.has_pipe("ner") else nlp.add_pipe("ner")
    custom_labels = ["STATUTE", "COURT", "MONEY_LEGAL", "SECTION"]
    for label in custom_labels:
        ner.add_label(label)

    train_data = load_annotations(data_path)

    other_pipes = [p for p in nlp.pipe_names if p != "ner"]
    with nlp.disable_pipes(*other_pipes):
        nlp.begin_training()
        for i in range(n_iter):
            random.shuffle(train_data)
            losses = {}
            for text, annotations in train_data:
                doc = nlp.make_doc(text)
                example = Example.from_dict(doc, annotations)
                nlp.update([example], drop=0.35, losses=losses)
            print(f"Iteration {i+1}/{n_iter} — Loss: {losses.get('ner', 0):.4f}")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    nlp.to_disk(output_dir)
    print(f"Model saved to {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", default="./ner_model")
    parser.add_argument("--iterations", type=int, default=30)
    args = parser.parse_args()
    train(args.data, args.output, args.iterations)
