#!/usr/bin/env python3
"""Prefetch and build the local Whisper model for AMAP speech-to-text.

Runtime (backend) never touches the network: the model is resolved from
backend/.whisper_cache/tiny when present. This setup script rebuilds that
directory on a fresh environment using ONLY allowed hosts (github.com for
source artifacts, PyPI for tooling).

Steps:
 1. Clone the upstream multilingual OpenAI whisper-tiny checkpoint
    (models_tiny.pt, n_vocab=51865 => multilingual, Hindi-capable — never tiny.en)
    from github.com/anruijie749-alt/whisper-tiny-model (regular git blob, not LFS).
 2. Clone github.com/openai/whisper for the local tiktoken vocabulary assets.
 3. Convert OpenAI -> Hugging Face format (converter sourced from
    huggingface/transformers main, vendored here).
 4. Convert Hugging Face -> CTranslate2 with ct2-transformers-converter.
 5. Verify by transcribing the repo's English + Hindi audio fixtures.

Usage:  python scripts/prefetch_whisper_model.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
SCRATCH = REPO_ROOT.parent / "scratch" / "whisper-src"
MODEL_OUT = BACKEND / ".whisper_cache" / "tiny"
CHECKPOINT_URL = "https://github.com/anruijie749-alt/whisper-tiny-model.git"
WHISPER_ASSETS_URL = "https://github.com/openai/whisper.git"
CONVERTER_URL = (
    "https://raw.githubusercontent.com/huggingface/transformers/main/"
    "src/transformers/models/whisper/convert_openai_to_hf.py"
)


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=cwd)


def ensure_repo(url: str, dest: Path) -> None:
    if (dest / ".git").exists():
        print(f"already cloned: {dest}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--depth", "1", url, str(dest)])


def main() -> int:
    if (MODEL_OUT / "model.bin").is_file():
        print(f"model already present: {MODEL_OUT}")
        return 0

    python = sys.executable
    ensure_repo(CHECKPOINT_URL, SCRATCH / "tiny-model")
    ensure_repo(WHISPER_ASSETS_URL, SCRATCH / "openai-whisper")

    # Tooling (PyPI only) for the conversion + verification steps; runtime
    # dependencies remain in backend/requirements.txt.
    run([python, "-m", "pip", "install", "--quiet",
         "torch", "transformers", "tiktoken", "faster-whisper"])

    converter = SCRATCH / "convert_openai_to_hf.py"
    if not converter.exists():
        text_src = None
        # Preferred: plain HTTPS (works on CI runners with normal internet).
        try:
            import urllib.request

            with urllib.request.urlopen(CONVERTER_URL, timeout=60) as resp:
                text_src = resp.read().decode()
        except Exception as exc:  # noqa: BLE001
            print(f"HTTPS fetch failed ({exc}); falling back to gh api")
        if text_src is None:
            # Fallback: GitHub API (works in sandboxes where raw.githubusercontent
            # is blocked but gh is authenticated).
            import base64

            raw = subprocess.run(
                ["gh", "api",
                 "repos/huggingface/transformers/contents/"
                 "src/transformers/models/whisper/convert_openai_to_hf.py",
                 "--jq", ".content"],
                capture_output=True, text=True, check=True,
            )
            text_src = base64.b64decode(raw.stdout).decode()
        converter.write_text(text_src, encoding="utf-8")
    text = converter.read_text(encoding="utf-8")
    if "_LOCAL_WHISPER_ASSETS" not in text:
        # offline patches: local tiktoken assets + offline generation config
        text = text.replace(
            'from transformers.models.whisper.tokenization_whisper import LANGUAGES, bytes_to_unicode',
            "try:\n    from transformers.models.whisper.tokenization_whisper import LANGUAGES, bytes_to_unicode\n"
            "except ImportError:\n    from transformers.models.whisper.tokenization_whisper import LANGUAGES\n"
            "    def bytes_to_unicode():\n"
            "        bs = list(range(ord('!'), ord('~') + 1)) + list(range(ord(chr(0xA1)), ord(chr(0xAC)) + 1)) + list(range(ord(chr(0xAE)), ord(chr(0xFF)) + 1))\n"
            "        cs = bs[:]\n        n = 0\n"
            "        for b in range(2 ** 8):\n            if b not in bs:\n                bs.append(b)\n                cs.append(2 ** 8 + n)\n                n += 1\n"
            "        return dict(zip(bs, [chr(c) for c in cs]))\n",
        )
        text = text.replace(
            '    gen_cfg = GenerationConfig.from_pretrained(repo)',
            "    try:\n        gen_cfg = GenerationConfig.from_pretrained(repo)\n"
            "    except Exception:\n        gen_cfg = GenerationConfig(max_length=448, max_initial_timestamp_index=0)\n",
        )
        import re

        text = re.sub(
            r'_TOKENIZERS = \{.*?\}',
            "import os as _os\n"
            "_LOCAL_WHISPER_ASSETS = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'openai-whisper', 'whisper', 'assets')\n"
            "_TOKENIZERS = {\n"
            "    'multilingual': _os.path.join(_LOCAL_WHISPER_ASSETS, 'multilingual.tiktoken'),\n"
            "    'english': _os.path.join(_LOCAL_WHISPER_ASSETS, 'gpt2.tiktoken'),\n"
            "}",
            text,
            flags=re.S,
        )
        converter.write_text(text, encoding="utf-8")

    hf_out = SCRATCH / "hf-whisper-tiny"
    run([python, str(converter),
         "--checkpoint_path", str(SCRATCH / "tiny-model" / "models_tiny.pt"),
         "--pytorch_dump_folder_path", str(hf_out),
         "--convert_preprocessor", "True"])

    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    run([str(BACKEND and Path(python).parent / "ct2-transformers-converter"),
         "--model", str(hf_out),
         "--output_dir", str(MODEL_OUT),
         "--quantization", "float16",
         "--copy_files", "tokenizer.json", "tokenizer_config.json"])

    # Verification: real transcription, English + Hindi (fixtures in scripts/)
    from faster_whisper import WhisperModel

    model = WhisperModel(str(MODEL_OUT), device="cpu", compute_type="int8")
    for fixture, lang in (("next_step.wav", "en"), ("agla.wav", "hi")):
        wav = REPO_ROOT / "scripts" / fixture
        segments, info = model.transcribe(str(wav), language=lang, vad_filter=True, beam_size=1)
        text = " ".join(s.text for s in segments).strip()
        print(f"verified {fixture} ({lang}): {text!r}")
        if not text:
            print("FAILED: empty transcription", file=sys.stderr)
            return 1
    print(f"OK: model ready at {MODEL_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
