from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import TextIO


class Logger:
    def __init__(self, log_file: Path, stream: TextIO = sys.stdout) -> None:
        self.log_file = log_file
        self.stream = stream

    def reset(self) -> None:
        self.log_file.write_text("")

    def log(self, message: str) -> None:
        line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}"
        print(line, file=self.stream)
        with self.log_file.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")
