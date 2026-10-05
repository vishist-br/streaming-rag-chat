"""Turn raw files into `Block`s: paragraphs tagged with their section and page.

Keeping structure here is what makes the chunker "structure-aware": it never
has to guess where a section starts.
"""

import io
import re
from dataclasses import dataclass
from pathlib import PurePath

from pypdf import PdfReader

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")
BLANK_LINES_RE = re.compile(r"\n\s*\n")

SUPPORTED_EXTENSIONS = (".md", ".markdown", ".txt", ".pdf")


class UnsupportedFileTypeError(ValueError):
    pass


@dataclass(frozen=True)
class Block:
    text: str
    section: str = ""  # heading path, e.g. "Battery > Charging"
    page: int | None = None  # 1-based, PDFs only


def parse_document(filename: str, data: bytes) -> list[Block]:
    extension = PurePath(filename).suffix.lower()
    if extension in (".md", ".markdown"):
        return parse_markdown(data.decode("utf-8", errors="replace"))
    if extension == ".txt":
        return parse_text(data.decode("utf-8", errors="replace"))
    if extension == ".pdf":
        return parse_pdf(data)
    raise UnsupportedFileTypeError(
        f"unsupported file type '{extension}'; expected one of {', '.join(SUPPORTED_EXTENSIONS)}"
    )


def parse_markdown(text: str) -> list[Block]:
    blocks: list[Block] = []
    headings: list[tuple[int, str]] = []  # stack of (level, title)
    paragraph: list[str] = []
    in_code_fence = False

    def flush() -> None:
        body = "\n".join(paragraph).strip()
        if body:
            blocks.append(Block(text=body, section=" > ".join(title for _, title in headings)))
        paragraph.clear()

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_code_fence = not in_code_fence
            paragraph.append(line)
            continue
        heading = None if in_code_fence else HEADING_RE.match(line)
        if heading:
            flush()
            level = len(heading.group(1))
            # A new "##" closes any open "##" or deeper heading.
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, heading.group(2).strip()))
        elif not line.strip() and not in_code_fence:
            flush()
        else:
            paragraph.append(line)
    flush()
    return blocks


def parse_text(text: str, page: int | None = None) -> list[Block]:
    paragraphs = (p.strip() for p in BLANK_LINES_RE.split(text))
    return [Block(text=p, page=page) for p in paragraphs if p]


def parse_pdf(data: bytes) -> list[Block]:
    reader = PdfReader(io.BytesIO(data))
    blocks: list[Block] = []
    for number, page in enumerate(reader.pages, start=1):
        blocks.extend(parse_text(page.extract_text() or "", page=number))
    return blocks
