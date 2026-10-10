#!/usr/bin/env python3
"""Catch stale bootstrap SHA-256 expectations before a real VM deployment.

No dependencies or credentials; only examines static quoted heredocs in bootstrap.sh.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "bootstrap.sh").read_text()
DOTFILES = {
    ".zshenv": "__JQ_ZSHENV_EOF__",
    ".zshrc": "__JQ_ZSHRC_EOF__",
    ".zsh_aliases": "__JQ_ALIASES_EOF__",
    ".p10k.zsh": "__JQ_P10K_EOF__",
}


def heredoc(delimiter: str) -> bytes:
    expression = re.compile(r"<<'" + re.escape(delimiter) + r"'\n(.*?)\n" + re.escape(delimiter) + r"(?=\n)", re.S)
    matches = expression.findall(SOURCE)
    if len(matches) != 1:
        raise AssertionError(f"Expected one {delimiter} heredoc, got {len(matches)}")
    return (matches[0] + "\n").encode()


def verify() -> None:
    for name, marker in DOTFILES.items():
        generated = hashlib.sha256(heredoc(marker)).hexdigest()
        check = re.search(r'hash_is "([a-f0-9]{64})" "\$TARGET_HOME/' + re.escape(name) + r'"', SOURCE)
        if not check:
            raise AssertionError(f"Missing expected SHA-256 for {name}")
        if generated != check.group(1):
            raise AssertionError(f"{name} expected {check.group(1)} but emitted {generated}")
        print(f"PASS {name}: SHA-256 matches generated content")

    prefix = hashlib.sha256(heredoc("__JQ_NANORC_EOF__")).hexdigest()
    if prefix not in SOURCE.split("verify_dotfiles()", 1)[1].split("setup_dotfiles()", 1)[0]:
        raise AssertionError("Nano static prefix SHA-256 not aligned")
    print("PASS .nanorc: generated static prefix SHA-256 matches")


if __name__ == "__main__":
    verify()
