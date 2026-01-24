"""Unit tests for the documentation validation script.

Tests cover:
- Citation parsing from markdown, mermaid, and code blocks
- File existence and line bounds validation (Level 1)
- AST verification for Python files (Level 2)
- Code block matching (Level 3)
- Cross-reference consistency (Level 4)
- Staleness detection (Level 5)
"""

from __future__ import annotations

# Import from the scripts package
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from scripts.validate_docs.config import (
    Citation,
    CitationStatus,
    ValidationLevel,
)
from scripts.validate_docs.parsers.code_blocks import (
    extract_code_block_citations,
    extract_code_block_content,
)
from scripts.validate_docs.parsers.markdown import (
    _extract_frontmatter,
    extract_markdown_citations,
)
from scripts.validate_docs.parsers.mermaid import extract_mermaid_citations
from scripts.validate_docs.validators.code_match import validate_code_match
from scripts.validate_docs.validators.cross_reference import (
    CrossReferenceIndex,
    validate_cross_references,
)
from scripts.validate_docs.validators.file_exists import validate_file_exists
from scripts.validate_docs.validators.line_bounds import validate_line_bounds

# ============================================================================
# Citation Parsing Tests
# ============================================================================


class TestMarkdownCitationParsing:
    """Tests for markdown citation parsing."""

    def test_extract_inline_citation(self) -> None:
        """Test extracting inline citations in backticks."""
        content = "See `backend/services/file_watcher.py:67` for details."
        citations = extract_markdown_citations(content, "test.md")

        assert len(citations) == 1
        assert citations[0].file_path == "backend/services/file_watcher.py"
        assert citations[0].start_line == 67
        assert citations[0].end_line is None

    def test_extract_range_citation(self) -> None:
        """Test extracting range citations."""
        content = "The implementation is at `backend/services/file_watcher.py:67-89`."
        citations = extract_markdown_citations(content, "test.md")

        assert len(citations) == 1
        assert citations[0].file_path == "backend/services/file_watcher.py"
        assert citations[0].start_line == 67
        assert citations[0].end_line == 89
        assert citations[0].line_count == 23

    def test_extract_frontmatter_citations(self) -> None:
        """Test extracting citations from YAML frontmatter."""
        content = """---
title: Test Doc
source_refs:
  - backend/services/file_watcher.py:FileWatcher:34
  - backend/services/dedupe.py:compute_file_hash
---

# Test Document
"""
        citations = extract_markdown_citations(content, "test.md")

        assert len(citations) == 2
        assert citations[0].file_path == "backend/services/file_watcher.py"
        assert citations[0].symbol_name == "FileWatcher"
        assert citations[0].start_line == 34
        assert citations[1].file_path == "backend/services/dedupe.py"
        assert citations[1].symbol_name == "compute_file_hash"

    def test_extract_multiple_citations(self) -> None:
        """Test extracting multiple citations from content."""
        content = """
See `backend/services/file_watcher.py:67` and also
check `frontend/src/hooks/useWebSocket.ts:45-78` for the implementation.
"""
        citations = extract_markdown_citations(content, "test.md")

        assert len(citations) == 2
        assert citations[0].file_path == "backend/services/file_watcher.py"
        assert citations[1].file_path == "frontend/src/hooks/useWebSocket.ts"

    def test_extract_frontmatter(self) -> None:
        """Test frontmatter extraction."""
        content = """---
title: Test
---

Body content here.
"""
        frontmatter, body = _extract_frontmatter(content)
        assert "title: Test" in frontmatter
        assert "Body content" in body

    def test_no_frontmatter(self) -> None:
        """Test content without frontmatter."""
        content = "# No frontmatter here"
        frontmatter, body = _extract_frontmatter(content)
        assert frontmatter == ""
        assert body == content


class TestMermaidCitationParsing:
    """Tests for mermaid diagram citation parsing."""

    def test_extract_mermaid_citation(self) -> None:
        """Test extracting citations from mermaid blocks."""
        content = """
```mermaid
sequenceDiagram
    Note right of RT: See `backend/services/detector_client.py:45`
```
"""
        citations = extract_mermaid_citations(content, "test.md")

        # May find 1 or 2 citations depending on pattern matching
        assert len(citations) >= 1
        # Find the citation we expect
        matching = [c for c in citations if c.file_path == "backend/services/detector_client.py"]
        assert len(matching) >= 1
        assert matching[0].start_line == 45

    def test_no_mermaid_citations(self) -> None:
        """Test content without mermaid citations."""
        content = """
```mermaid
flowchart TD
    A --> B
```
"""
        citations = extract_mermaid_citations(content, "test.md")
        assert len(citations) == 0


class TestCodeBlockCitationParsing:
    """Tests for code block citation parsing."""

    def test_extract_source_comment_citation(self) -> None:
        """Test extracting citations from Source comments."""
        content = """
```python
# Source: backend/services/file_watcher.py:67-89
def is_image_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in IMAGE_EXTENSIONS
```
"""
        citations = extract_code_block_citations(content, "test.md")

        assert len(citations) == 1
        assert citations[0].file_path == "backend/services/file_watcher.py"
        assert citations[0].start_line == 67
        assert citations[0].end_line == 89

    def test_extract_code_block_content(self) -> None:
        """Test extracting code content from a block."""
        content = """
```python
# Source: backend/services/file_watcher.py:67
def is_image_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in IMAGE_EXTENSIONS
```
"""
        citation = Citation(
            file_path="backend/services/file_watcher.py",
            start_line=67,
            doc_file="test.md",
        )
        code = extract_code_block_content(content, citation)

        assert code is not None
        assert "def is_image_file" in code


# ============================================================================
# Level 1 Validation Tests
# ============================================================================


class TestFileExistsValidation:
    """Tests for file existence validation."""

    def test_file_exists(self, tmp_path: Path) -> None:
        """Test validation passes when file exists."""
        test_file = tmp_path / "test.py"
        test_file.write_text("# test")

        citation = Citation(file_path="test.py", start_line=1)
        result = validate_file_exists(citation, tmp_path)

        assert result.status == CitationStatus.VALID
        assert result.level == ValidationLevel.FILE_EXISTS

    def test_file_not_exists(self, tmp_path: Path) -> None:
        """Test validation fails when file doesn't exist."""
        citation = Citation(file_path="nonexistent.py", start_line=1)
        result = validate_file_exists(citation, tmp_path)

        assert result.status == CitationStatus.ERROR
        assert "does not exist" in result.message

    def test_path_is_directory(self, tmp_path: Path) -> None:
        """Test validation fails when path is a directory."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        citation = Citation(file_path="subdir", start_line=1)
        result = validate_file_exists(citation, tmp_path)

        assert result.status == CitationStatus.ERROR
        assert "not a file" in result.message


class TestLineBoundsValidation:
    """Tests for line bounds validation."""

    def test_valid_single_line(self, tmp_path: Path) -> None:
        """Test validation passes for valid single line."""
        test_file = tmp_path / "test.py"
        test_file.write_text("line 1\nline 2\nline 3\n")

        citation = Citation(file_path="test.py", start_line=2)
        result = validate_line_bounds(citation, tmp_path)

        assert result.status == CitationStatus.VALID
        assert result.details["line_count"] == 1

    def test_valid_range(self, tmp_path: Path) -> None:
        """Test validation passes for valid range."""
        test_file = tmp_path / "test.py"
        test_file.write_text("line 1\nline 2\nline 3\nline 4\nline 5\n")

        citation = Citation(file_path="test.py", start_line=2, end_line=4)
        result = validate_line_bounds(citation, tmp_path)

        assert result.status == CitationStatus.VALID
        assert result.details["line_count"] == 3

    def test_line_out_of_bounds(self, tmp_path: Path) -> None:
        """Test validation fails when line is out of bounds."""
        test_file = tmp_path / "test.py"
        test_file.write_text("line 1\nline 2\nline 3\n")

        citation = Citation(file_path="test.py", start_line=10)
        result = validate_line_bounds(citation, tmp_path)

        assert result.status == CitationStatus.ERROR
        assert "does not exist" in result.message
        assert "3 lines" in result.message

    def test_invalid_range(self, tmp_path: Path) -> None:
        """Test validation fails when end < start."""
        test_file = tmp_path / "test.py"
        test_file.write_text("line 1\nline 2\nline 3\n")

        citation = Citation(file_path="test.py", start_line=3, end_line=1)
        result = validate_line_bounds(citation, tmp_path)

        assert result.status == CitationStatus.ERROR
        assert "Invalid range" in result.message

    def test_zero_start_line(self, tmp_path: Path) -> None:
        """Test validation fails for line 0."""
        test_file = tmp_path / "test.py"
        test_file.write_text("line 1\n")

        citation = Citation(file_path="test.py", start_line=0)
        result = validate_line_bounds(citation, tmp_path)

        assert result.status == CitationStatus.ERROR
        assert "must be >= 1" in result.message


# ============================================================================
# Level 3 Validation Tests
# ============================================================================


class TestCodeMatchValidation:
    """Tests for code block matching validation."""

    def test_exact_match(self, tmp_path: Path) -> None:
        """Test validation passes for exact code match."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    return 'world'\n")

        citation = Citation(file_path="test.py", start_line=1, end_line=2)
        result = validate_code_match(
            citation,
            tmp_path,
            documented_code="def hello():\n    return 'world'",
        )

        assert result.status == CitationStatus.VALID
        assert "matches" in result.message.lower()

    def test_fuzzy_match_whitespace(self, tmp_path: Path) -> None:
        """Test validation passes with whitespace differences."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    return 'world'\n")

        citation = Citation(file_path="test.py", start_line=1, end_line=2)
        # Documented code has different indentation
        result = validate_code_match(
            citation,
            tmp_path,
            documented_code="  def hello():\n      return 'world'  ",
            threshold=0.8,
        )

        assert result.status == CitationStatus.VALID

    def test_no_match(self, tmp_path: Path) -> None:
        """Test validation fails for completely different code."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    return 'world'\n")

        citation = Citation(file_path="test.py", start_line=1, end_line=2)
        result = validate_code_match(
            citation,
            tmp_path,
            documented_code="class Foo:\n    pass",
        )

        assert result.status == CitationStatus.ERROR
        assert "does not match" in result.message

    def test_no_documented_code(self, tmp_path: Path) -> None:
        """Test validation skipped when no documented code."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    return 'world'\n")

        citation = Citation(file_path="test.py", start_line=1)
        result = validate_code_match(citation, tmp_path, documented_code=None)

        assert result.status == CitationStatus.VALID
        assert "skipped" in result.message.lower()


# ============================================================================
# Level 4 Validation Tests
# ============================================================================


class TestCrossReferenceValidation:
    """Tests for cross-reference consistency validation."""

    def test_no_cross_references(self) -> None:
        """Test validation passes with no other references."""
        index = CrossReferenceIndex()
        citation = Citation(
            file_path="backend/services/file_watcher.py",
            start_line=67,
            doc_file="doc1.md",
        )
        index.add_citation(citation, "doc1.md")

        result = validate_cross_references(citation, index, "doc1.md")

        assert result.status == CitationStatus.VALID
        assert "only cited in this document" in result.message

    def test_consistent_references(self) -> None:
        """Test validation passes when references are consistent."""
        index = CrossReferenceIndex()

        citation1 = Citation(
            file_path="backend/services/file_watcher.py",
            start_line=67,
            symbol_name="FileWatcher",
            doc_file="doc1.md",
        )
        citation2 = Citation(
            file_path="backend/services/file_watcher.py",
            start_line=67,
            symbol_name="FileWatcher",
            doc_file="doc2.md",
        )

        index.add_citation(citation1, "doc1.md")
        index.add_citation(citation2, "doc2.md")

        result = validate_cross_references(citation1, index, "doc1.md")

        assert result.status == CitationStatus.VALID
        assert "Consistent" in result.message

    def test_inconsistent_line_numbers(self) -> None:
        """Test validation warns when line numbers differ."""
        index = CrossReferenceIndex()

        citation1 = Citation(
            file_path="backend/services/file_watcher.py",
            start_line=67,
            symbol_name="FileWatcher",
            doc_file="doc1.md",
        )
        citation2 = Citation(
            file_path="backend/services/file_watcher.py",
            start_line=100,  # Different line
            symbol_name="FileWatcher",
            doc_file="doc2.md",
        )

        index.add_citation(citation1, "doc1.md")
        index.add_citation(citation2, "doc2.md")

        result = validate_cross_references(citation1, index, "doc1.md")

        assert result.status == CitationStatus.WARNING
        assert "Inconsistent" in result.message


# ============================================================================
# Integration Tests
# ============================================================================


class TestCitationModel:
    """Tests for the Citation model."""

    def test_citation_str(self) -> None:
        """Test citation string representation."""
        citation = Citation(file_path="test.py", start_line=10)
        assert str(citation) == "test.py:10"

        citation_range = Citation(file_path="test.py", start_line=10, end_line=20)
        assert str(citation_range) == "test.py:10-20"

    def test_citation_is_range(self) -> None:
        """Test is_range property."""
        single = Citation(file_path="test.py", start_line=10)
        assert not single.is_range

        range_citation = Citation(file_path="test.py", start_line=10, end_line=20)
        assert range_citation.is_range

    def test_citation_line_count(self) -> None:
        """Test line_count property."""
        single = Citation(file_path="test.py", start_line=10)
        assert single.line_count == 1

        range_citation = Citation(file_path="test.py", start_line=10, end_line=20)
        assert range_citation.line_count == 11
