"""
Obsidian PDF Converter Module
Converts PDFs to Obsidian-compatible markdown files using pdfplumber
"""

import pdfplumber
from pathlib import Path
from typing import Optional
import re


class ObsidianPDFConverter:
    """Converter class for transforming PDFs into Obsidian-compatible markdown."""

    def __init__(self, vault_root: str, llamaparse_api_key: Optional[str] = None):
        """
        Initialize the Obsidian PDF converter.

        Args:
            vault_root: Root directory where PDFs and markdown files will be stored
            llamaparse_api_key: API key for LlamaParse (used as fallback, optional)
        """
        self.vault_root = Path(vault_root)
        self.llamaparse_api_key = llamaparse_api_key
        self.tracking_data = {
            'processed': {}
        }

    def convert_pdf(self, pdf_path: Path, force: bool = False) -> bool:
        """
        Convert a PDF file to markdown format.

        Args:
            pdf_path: Path to the PDF file
            force: If True, overwrite existing markdown file

        Returns:
            True if conversion successful, False otherwise
        """
        try:
            pdf_path = Path(pdf_path)
            md_path = pdf_path.with_suffix('.md')

            # Check if already converted
            if md_path.exists() and not force:
                print(f"[Obsidian] Markdown file already exists: {md_path}")
                return True

            # Extract text from PDF using pdfplumber
            markdown_content = self._extract_text_from_pdf(pdf_path)

            if not markdown_content:
                print(f"[Obsidian] Failed to extract text from {pdf_path}")
                return False

            # Write markdown file
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            # Update tracking data
            pdf_rel_path = pdf_path.name
            self.tracking_data['processed'][pdf_rel_path] = {
                'category': 'general',
                'tags': ['pdf-conversion'],
                'pages': self._count_pages(pdf_path),
                'source_file': str(pdf_path),
                'output_file': str(md_path)
            }

            print(f"[Obsidian] Successfully converted {pdf_path} to {md_path}")
            return True

        except Exception as e:
            print(f"[Obsidian] Error converting {pdf_path}: {str(e)}")
            return False

    def _extract_text_from_pdf(self, pdf_path: Path) -> str:
        """
        Extract text from PDF using pdfplumber.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text formatted as markdown
        """
        try:
            markdown_lines = []
            markdown_lines.append(f"# {pdf_path.stem}\n")
            markdown_lines.append(f"*Source: {pdf_path.name}*\n")
            markdown_lines.append("---\n")

            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Add page header
                    markdown_lines.append(f"\n## Page {page_num}\n")

                    # Extract text from page
                    text = page.extract_text()

                    if text:
                        # Clean up text
                        text = self._clean_text(text)
                        markdown_lines.append(text)
                        markdown_lines.append("\n")
                    else:
                        markdown_lines.append("*[No text extracted from this page]*\n")

            return "\n".join(markdown_lines)

        except Exception as e:
            print(f"[Obsidian] Error extracting text: {str(e)}")
            return ""

    def _clean_text(self, text: str) -> str:
        """
        Clean and format extracted text.

        Args:
            text: Raw text from PDF

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Remove trailing whitespace from lines
        lines = [line.rstrip() for line in text.split('\n')]
        text = '\n'.join(lines)

        return text

    def _count_pages(self, pdf_path: Path) -> int:
        """
        Count the number of pages in a PDF.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Number of pages, or 0 if error
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                return len(pdf.pages)
        except Exception:
            return 0
