"""Extract citations from markdown prose and frontmatter.

This module handles:
- YAML frontmatter source_refs parsing
- Inline citations in backticks: `path/file.py:123`
- Function/class name extraction from context
"""

from __future__ import annotations

import re
from pathlib import Path

from ..config import (
    INLINE_CITATION_PATTERN,
    SYMBOL_CONTEXT_PATTERN,
    Citation,
    looks_like_host_address,
)


def _extract_frontmatter(content: str) -> tuple[str, str]:
    """Extract YAML frontmatter from markdown content.

    Args:
        content: Full markdown content

    Returns:
        Tuple of (frontmatter, body) where frontmatter may be empty
    """
    if not content.startswith("---"):
        return "", content

    # Find the closing ---
    end_match = re.search(r"\n---\n", content[3:])
    if not end_match:
        return "", content

    end_pos = end_match.end() + 3
    frontmatter = content[3 : end_pos - 4]  # Strip the --- markers
    body = content[end_pos:]

    return frontmatter, body


def _parse_frontmatter_citations(frontmatter: str, doc_file: str) -> list[Citation]:
    """Parse source_refs from YAML frontmatter.

    Handles formats like:
    - backend/services/file_watcher.py:FileWatcher:34
    - backend/services/file_watcher.py:is_image_file
    - backend/services/file_watcher.py:67

    Args:
        frontmatter: YAML frontmatter content
        doc_file: Path to the documentation file

    Returns:
        List of Citation objects
    """
    citations: list[Citation] = []

    # Find source_refs section
    source_refs_match = re.search(r"source_refs:\s*\n((?:\s+-\s+.+\n?)+)", frontmatter)
    if not source_refs_match:
        return citations

    source_refs_block = source_refs_match.group(1)

    # Parse each reference
    for line_num, raw_line in enumerate(source_refs_block.split("\n"), start=1):
        line = raw_line.strip()
        if not line or not line.startswith("-"):
            continue

        # Extract the reference (after the "- ")
        ref = line[1:].strip()
        if not ref:
            continue

        # Parse the reference: path:symbol:line or path:symbol or path:line
        parts = ref.split(":")
        if len(parts) < 1:
            continue

        file_path = parts[0]
        symbol_name: str | None = None
        line_number: int | None = None

        if len(parts) >= 2:
            # Could be symbol name or line number
            second_part = parts[1]
            if second_part.isdigit():
                line_number = int(second_part)
            else:
                symbol_name = second_part
                # Check for line number in third part
                if len(parts) >= 3 and parts[2].isdigit():
                    line_number = int(parts[2])

        # Create citation with available info
        citations.append(
            Citation(
                file_path=file_path,
                start_line=line_number or 1,  # Default to line 1 if not specified
                end_line=None,
                symbol_name=symbol_name,
                doc_file=doc_file,
                doc_line=line_num,  # Approximate line in frontmatter
                raw_text=ref,
            )
        )

    return citations


_CODE_SPAN_PATTERN = re.compile(r"`[^`\n]+`")
_FENCE_LINE_PATTERN = re.compile(r"^```[ \t]*([A-Za-z0-9_+-]*)[ \t]*$", re.MULTILINE)

# Fence info strings whose body is real code the author meant as code. Closed to
# what `docs/` actually uses for code; `bash`/`yaml`/`toml`/`json`/`text`/`markdown`
# and an empty tag are excluded on purpose — a transcript or a config sample is not
# a signature, and a name lifted out of one is a guess about someone else's log.
CODE_FENCE_LANGUAGES = frozenset(
    {
        "python",
        "py",
        "typescript",
        "ts",
        "tsx",
        "javascript",
        "js",
        "jsx",
        "mjs",
    }
)


def _fenced_ranges(content: str) -> list[tuple[int, int]]:
    """``(body_start, close_start)`` for each code-fenced block in ``content``.

    Only a fence with a CODE info string counts. Bare fences are the largest group
    in ``docs/`` (5,792 of them, against 1,369 ```python) and they hold transcripts,
    logs and quoted English — accepting them would hand the keyword pattern prose to
    infer from, which is the defect this tier exists to close. An unlisted tag misses
    rather than misfires.

    Fence lines pair up: the line after an opener begins a block and the next fence
    line ends it. A trailing opener with no closer is no block at all.
    """
    ranges: list[tuple[int, int]] = []
    open_body: int | None = None
    for marker in _FENCE_LINE_PATTERN.finditer(content):
        tag = marker.group(1).lower()
        if open_body is None:
            if tag in CODE_FENCE_LANGUAGES:
                open_body = marker.end()
        else:
            ranges.append((open_body, marker.start()))
            open_body = None
    return ranges


def _is_coded_reference(line: str, name_offset: int) -> bool:
    """True if the offset falls inside a backticked code span on ``line``.

    Backticks are the author's own mark that a token is code. Requiring them is
    what separates "class ``_ThreadWatchdog``" (a symbol reference) from
    "a class docstring" (English) without maintaining a list of English words.
    """
    return any(
        span.start() <= name_offset < span.end() - 1 for span in _CODE_SPAN_PATTERN.finditer(line)
    )


def _is_fenced_reference(fences: list[tuple[int, int]], name_offset: int, cite_offset: int) -> bool:
    """True if the name sits inside a fenced block that OPENS AFTER the citation.

    The architecture-doc convention is cite, then a fenced signature — 390 such
    cite/fence pairs across 70 documents. A fence is the author's strongest code
    mark, so a rule that accepts the same-line backtick but refuses the fence below
    the cite quietly retires the drift those pairs were written to catch. Requiring
    that the block open after this citation stops a fence belonging to an earlier
    passage from vouching for this one.
    """
    return any(
        body_start > cite_offset and body_start <= name_offset < body_end
        for body_start, body_end in fences
    )


def _extract_symbol_from_context(
    content: str,
    position: int,
    window: int = 100,
    fences: list[tuple[int, int]] | None = None,
) -> str | None:
    """Try to extract a symbol name from the context around a citation.

    Only code-evidenced candidates are accepted. Evidence is about the NAME, not the
    keyword: the name must sit inside a backticked span on its own line, or inside a
    fenced block that opens after this citation; the name must not run on into path
    or member syntax; and the name must be intact in the FULL content — a candidate
    the window clipped is not evidence of anything.

    Args:
        content: Document content
        position: Position of the citation in the content
        window: Number of characters to look before and after
        fences: The document's code-fence ranges, precomputed by the caller. The
            fence set is a property of the DOCUMENT, so a caller parsing many
            citations computes it once and passes it — computing it here instead
            is O(citations x document) and timed this suite out against the root
            pytest ``timeout = 5`` (1,207 cites in one reference doc). Computed on
            demand only when a caller has none to give.

    Returns:
        Symbol name if found, None otherwise
    """
    start = max(0, position - window)
    end = min(len(content), position + window)
    context = content[start:end]
    if fences is None:
        fences = _fenced_ranges(content)

    # Look for function/class/method mentions; keep scanning past prose hits.
    for match in SYMBOL_CONTEXT_PATTERN.finditer(context):
        name_start = start + match.start(1)
        name_end = start + match.end(1)

        # Judge the word against the full document, never the window: the
        # window's own edge otherwise reads as a word boundary, so the clipped
        # tail of a path ("bac", "b") becomes a required symbol.
        tail = content[name_end : name_end + 1]
        if re.match(r"[A-Za-z0-9_]", tail) or tail in ("/", "."):
            continue
        if content[name_start - 1 : name_start] == "/":
            continue

        line_start = content.rfind("\n", 0, name_start) + 1
        line_end = content.find("\n", name_start)
        if line_end == -1:
            line_end = len(content)
        if not (
            _is_coded_reference(content[line_start:line_end], name_start - line_start)
            or _is_fenced_reference(fences, name_start, position)
        ):
            continue

        return match.group(1)

    return None


def extract_markdown_citations(content: str, doc_file: str = "") -> list[Citation]:
    """Extract all citations from markdown content.

    This includes:
    - YAML frontmatter source_refs
    - Inline citations in backticks

    Args:
        content: Markdown content to parse
        doc_file: Path to the documentation file (for error messages)

    Returns:
        List of Citation objects
    """
    citations: list[Citation] = []

    # Parse frontmatter
    frontmatter, body = _extract_frontmatter(content)
    if frontmatter:
        citations.extend(_parse_frontmatter_citations(frontmatter, doc_file))

    # Calculate line number offset for body content
    frontmatter_lines = content.count("\n", 0, len(content) - len(body))

    # The fence set belongs to the document, not to the citation: one sweep here,
    # passed to every per-citation judgement below. Sweeping inside the extractor
    # made this loop O(citations x document) and timed the gate's own suite out.
    body_fences = _fenced_ranges(body)

    # Extract inline citations from body
    for match in INLINE_CITATION_PATTERN.finditer(body):
        file_path = match.group(1)

        # `smtp.example.com:587` matches the citation shape exactly; a host is
        # not a path, so it is dropped before it can be reported as a missing file.
        if looks_like_host_address(file_path):
            continue

        start_line = int(match.group(2))
        end_line = int(match.group(3)) if match.group(3) else None

        # Calculate line number in original document
        doc_line = body[: match.start()].count("\n") + frontmatter_lines + 1

        # Try to extract symbol name from context
        symbol_name = _extract_symbol_from_context(body, match.start(), fences=body_fences)

        citations.append(
            Citation(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                symbol_name=symbol_name,
                doc_file=doc_file,
                doc_line=doc_line,
                raw_text=match.group(0),
                # This name was guessed from surrounding prose; the author
                # never typed it, so it may inform but must not block.
                symbol_inferred=symbol_name is not None,
            )
        )

    return citations


def parse_document(doc_path: str | Path) -> tuple[str, list[Citation]]:
    """Parse a documentation file and extract all citations.

    Args:
        doc_path: Path to the documentation file

    Returns:
        Tuple of (content, citations)

    Raises:
        FileNotFoundError: If the document doesn't exist
        OSError: If the document can't be read
    """
    doc_path = Path(doc_path)
    content = doc_path.read_text(encoding="utf-8")
    citations = extract_markdown_citations(content, str(doc_path))
    return content, citations
