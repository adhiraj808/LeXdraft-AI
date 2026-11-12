"""
Case type classification using DistilBERT.
Classifies legal cases into: Criminal, Civil, Family, Labour, Constitutional, Property.
"""

import asyncio
import logging
import os
from typing import Dict, List, Tuple

from app.core.config import settings

# torch and transformers are imported lazily in CaseClassifier.load(), and only when a
# fine-tuned checkpoint exists on disk. Importing them eagerly costs ~0.3-0.5 GB of RAM
# (and a lot of Windows commit charge) although the keyword classifier, which is what
# runs by default, needs neither.

logger = logging.getLogger(__name__)

# Label mapping
CASE_LABELS = {
    0: "Criminal",
    1: "Civil",
    2: "Family Law",
    3: "Labour / Employment",
    4: "Constitutional",
    5: "Property Dispute",
}

# Keyword-based fallback classifier (used when model is unavailable)
# Using word-boundary patterns for more precise matching
KEYWORD_PATTERNS = {
    "Criminal": [
        r"\bmurder\b", r"\bassault\b", r"\btheft\b", r"\brobbery\b",
        r"\bfraud\b", r"\bcheating\b", r"\brape\b", r"\bkidnapping\b",
        r"\bphishing\b", r"\bcyber\b", r"\bfir\b", r"\bbail\b",
        r"\barrest\b", r"\baccused\b", r"\boffence\b", r"\bcrime\b",
        r"\bpolice\b", r"\bjail\b", r"\bprison\b",
        r"\bcheque\b", r"\bdishono(u?)r\b", r"\bbounce\b", r"\bbounced\b",
        r"\bni act\b", r"\bnegotiable\b", r"\b138\b",
        r"\bsection\s+\d+\s+ipc\b", r"\bsection\s+\d+\s+crpc\b(?!\s*125)",
        r"\bsection\s+\d+\s+ipc\b", r"\bsection\s+\d+\s+crpc\b",
        r"\bit act\b",
        r"\bprosecution\b", r"\bconviction\b", r"\bsentence\b",
        r"\bcyber cell\b", r"\bcyber police\b",
    ],
    "Civil": [
        r"\bcontract\b", r"\bbreach\b", r"\bdamages\b", r"\binjunction\b",
        r"\btort\b", r"\bnegligence\b", r"\bspecific performance\b",
        r"\bdeclaration\b", r"\bcivil suit\b", r"\bplaintiff\b", r"\bdefendant\b",
        r"\brecovery\b", r"\bspecific relief\b", r"\bsection\s+73\b",
        r"\bsection\s+74\b", r"\bsection\s+75\b", r"\bindian contract act\b",
        r"\bsuit for\b", r"\bdecree\b", r"\bexecution\b",
        r"\bconsumer\b", r"\brefund\b", r"\brera\b", r"\bbuilder\b",
    ],
    "Family Law": [
        r"\bdivorce\b", r"\bmatrimonial\b", r"\bcustody\b", r"\bmaintenance\b",
        r"\balimony\b", r"\bdowry\b", r"\bdomestic violence\b",
        r"\badoption\b", r"\bguardianship\b", r"\bmarriage\b",
        r"\bsection\s+125\b", r"\bhindu marriage act\b", r"\bspecial marriage act\b",
        r"\bfamily court\b", r"\bmutual consent\b", r"\bdesertion\b",
        r"\bcruelty\b", r"\btalak\b", r"\bdivorce petition\b",
        r"\bwife\b", r"\bhusband\b", r"\bchild\b", r"\bson\b", r"\bdaughter\b",
    ],
    "Labour / Employment": [
        r"\btermination\b", r"\bdismissal\b", r"\bwages\b", r"\bsalary\b",
        r"\bemployment\b", r"\bworkman\b", r"\blabour\b",
        r"\bindustrial dispute\b", r"\bretrenchment\b", r"\breinstatement\b",
        r"\bpf\b", r"\bgratuity\b", r"\besic\b",
        r"\blabour court\b", r"\bindustrial tribunal\b", r"\bmaternity benefit\b",
    ],
    "Constitutional": [
        r"\bfundamental rights\b", r"\barticle\s+14\b", r"\barticle\s+21\b",
        r"\bwrit\b", r"\bmandamus\b", r"\bcertiorari\b", r"\bhabeas corpus\b",
        r"\bprohibition\b", r"\bquo warranto\b", r"\bultra vires\b",
        r"\bconstitutional validity\b", r"\bstate action\b",
        r"\barticle\s+32\b", r"\barticle\s+226\b", r"\bpil\b",
    ],
    "Property Dispute": [
        r"\bproperty\b(?!\s+damage)", r"\bland\b", r"\bpossession\b",
        r"\beviction\b", r"\btenant\b", r"\blandlord\b", r"\btitle\b",
        r"\bmutation\b", r"\bpartition\b", r"\bencroachment\b",
        r"\btrespass\b", r"\bregistry\b", r"\bsale deed\b", r"\bmortgage\b",
        r"\bflat\b", r"\bbuilder\b",
        r"\brera\b", r"\breal estate\b",
    ],
}


class CaseClassifier:
    """
    Classifies legal case descriptions into predefined categories.
    Primary: transformer model. Fallback: keyword scoring.
    """

    def __init__(self):
        self.tokenizer = None
        self.model = None
        self.use_model = False
        self._torch = None
        self._F = None

    async def load(self):
        """
        Load a fine-tuned classifier checkpoint if one exists on disk.
        The base HF_MODEL_CLASSIFIER has no trained classification head, so its
        logits are meaningless noise — it is never used directly. Without a real
        checkpoint (produced by app/nlp/training/train_classifier.py), the keyword
        classifier remains the active method.
        """
        checkpoint_dir = settings.resolve_backend_path(settings.CLASSIFIER_MODEL_PATH)
        if not os.path.isdir(checkpoint_dir) or not os.path.exists(
            os.path.join(checkpoint_dir, "config.json")
        ):
            logger.info(
                f"No fine-tuned classifier checkpoint at {checkpoint_dir}. Using keyword classifier."
            )
            self.use_model = False
            return

        try:
            logger.info(f"Loading fine-tuned classifier checkpoint: {checkpoint_dir}")
            # Heavy imports happen here, off the event loop, and only because a checkpoint exists.
            import torch
            import torch.nn.functional as F
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            def _load():
                tokenizer = AutoTokenizer.from_pretrained(checkpoint_dir)
                model = AutoModelForSequenceClassification.from_pretrained(
                    checkpoint_dir
                )
                return tokenizer, model

            self.tokenizer, self.model = await asyncio.to_thread(_load)
            if self.model.config.num_labels != len(CASE_LABELS):
                raise ValueError(
                    f"Checkpoint has {self.model.config.num_labels} labels, expected {len(CASE_LABELS)}"
                )
            self.model.eval()
            if settings.USE_GPU and torch.cuda.is_available():
                self.model = self.model.cuda()
            self._torch, self._F = torch, F
            self.use_model = True
            logger.info("Fine-tuned classifier model loaded.")
        except Exception as e:
            logger.warning(
                f"Could not load classifier checkpoint ({e}). Using keyword fallback."
            )
            self.tokenizer = self.model = self._torch = self._F = None
            self.use_model = False

    def _keyword_classify(self, text: str) -> Tuple[str, float]:
        """Score each category by keyword pattern frequency with word boundaries."""
        import re
        text_lower = text.lower()
        scores = {}
        for category, patterns in KEYWORD_PATTERNS.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
                score += matches
            scores[category] = score

        if all(v == 0 for v in scores.values()):
            return "Civil", 0.3  # Default

        best = max(scores, key=scores.get)
        total = sum(scores.values())
        confidence = round(scores[best] / total, 3) if total > 0 else 0.5
        return best, min(confidence, 0.95)

    def classify(self, text: str) -> Dict:
        """
        Classify the legal case text.
        Returns label, confidence, and probability distribution over all classes.
        Hybrid: transformer and keyword runs are compared and the more
        confident one wins (protects against a weak model on odd texts).
        """
        kw_label, kw_conf = self._keyword_classify(text)
        if self.use_model and self.tokenizer and self.model and self._torch is not None:
            torch, F = self._torch, self._F
            try:
                inputs = self.tokenizer(
                    text,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512,
                    padding=True,
                )
                if settings.USE_GPU and torch.cuda.is_available():
                    inputs = {k: v.cuda() for k, v in inputs.items()}

                with torch.no_grad():
                    logits = self.model(**inputs).logits
                    probs = F.softmax(logits, dim=-1)[0]

                pred_idx = probs.argmax().item()
                label = CASE_LABELS[pred_idx]
                confidence = round(probs[pred_idx].item(), 4)

                all_probs = {
                    CASE_LABELS[i]: round(probs[i].item(), 4)
                    for i in range(len(CASE_LABELS))
                }
                if confidence >= kw_conf:
                    return {
                        "case_type": label,
                        "confidence": confidence,
                        "probabilities": all_probs,
                        "method": "transformer",
                    }
                logger.info(
                    f"Keyword ({kw_label} {kw_conf}) beat transformer "
                    f"({label} {confidence}); using keyword."
                )
            except Exception as e:
                logger.warning(
                    f"Model inference failed: {e}. Falling back to keywords."
                )

        # Keyword fallback
        return {
            "case_type": kw_label,
            "confidence": kw_conf,
            "probabilities": {k: 0.0 for k in CASE_LABELS.values()},
            "method": "keyword",
        }

    def get_all_labels(self) -> List[str]:
        return list(CASE_LABELS.values())
