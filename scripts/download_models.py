"""Download the models the app actually uses.

Runs from the backend/ directory:

    cd backend && python ../scripts/download_models.py
    cd backend && python ../scripts/download_models.py --with-llm   # also fetch the GGUF

Only the spaCy model is downloaded by default. The old version also fetched
distilbert-base-uncased and google/flan-t5-base (~1.5 GB) — neither is used at
runtime: the classifier only loads a *fine-tuned* checkpoint from
.cache/models/classifier_model, and flan-t5 is referenced nowhere in the code.

The GGUF model is only needed with ENABLE_LOCAL_LLM=true
(pip install -r requirements-local-llm.txt).
"""

import argparse
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help="also download the local GGUF model for ENABLE_LOCAL_LLM",
    )
    args = parser.parse_args()

    print("Downloading spaCy model...")
    subprocess.run(
        [sys.executable, "-m", "spacy", "download", "en_core_web_sm"], check=True
    )

    if args.with_llm:
        from huggingface_hub import hf_hub_download

        print("Downloading GGUF model (Ambuj-Tripathi-Indian-Legal-Llama-GGUF)...")
        hf_hub_download(
            repo_id="invincibleambuj/Ambuj-Tripathi-Indian-Legal-Llama-GGUF",
            filename="llama-3.2-1b-instruct.Q4_K_M.gguf",
            local_dir=".cache/models",
            local_dir_use_symlinks=False,
        )

    print("All models ready.")


if __name__ == "__main__":
    main()
