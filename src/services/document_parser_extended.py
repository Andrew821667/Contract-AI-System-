# -*- coding: utf-8 -*-
"""
Extended Document Parser - Support for all document formats
Formats: DOCX, DOC, PDF (with OCR), RTF, ODT, XML
"""
import os
from pathlib import Path
from typing import Optional
from loguru import logger

# Import original parser
from .document_parser import DocumentParser as BaseDocumentParser


class ExtendedDocumentParser(BaseDocumentParser):
    """
    Extended parser with support for:
    - DOCX/DOC (with tracked changes)
    - PDF (with OCR if needed)
    - RTF
    - ODT
    - XML (passthrough)
    """

    def __init__(self):
        super().__init__()
        self.supported_formats = ['.docx', '.doc', '.pdf', '.rtf', '.odt', '.xml']

    def parse(self, file_path: str, enable_ocr: bool = True) -> str:
        """
        Parse document to XML with auto-format detection

        Args:
            file_path: Path to document
            enable_ocr: Enable OCR for scanned PDFs

        Returns:
            XML string
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Detect file type
        ext = Path(file_path).suffix.lower()

        logger.info(f"Parsing {ext} document: {file_path}")

        if ext == '.xml':
            return self._parse_xml(file_path)
        elif ext in ['.docx', '.doc']:
            return self.parse_docx(file_path)  # Uses base class method
        elif ext == '.pdf':
            return self._parse_pdf_extended(file_path, enable_ocr)
        elif ext == '.rtf':
            return self._parse_rtf(file_path)
        elif ext == '.odt':
            return self._parse_odt(file_path)
        else:
            raise ValueError(f"Unsupported format: {ext}")

    def _parse_xml(self, file_path: str) -> str:
        """XML passthrough"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _parse_pdf_extended(self, file_path: str, enable_ocr: bool) -> str:
        """
        Parse PDF with OCR support

        Note: OCR requires tesseract installed on system
        For now, falls back to base PDF parser
        """
        try:
            # Try base parser first
            return self.parse_pdf(file_path)
        except Exception as e:
            if enable_ocr:
                logger.warning(f"Base PDF parser failed, OCR needed but not yet implemented: {e}")
                # TODO: Implement OCR with pytesseract + pdf2image
                # This requires tesseract system binary
            raise

    def _parse_rtf(self, file_path: str) -> str:
        """
        Parse RTF to XML

        Note: Requires striprtf or pypandoc
        For now, returns stub - will be implemented when dependencies installed
        """
        logger.warning("RTF parsing not yet fully implemented, returning stub")

        # Stub implementation - extract raw text
        try:
            with open(file_path, 'rb') as f:
                content = f.read().decode('latin-1', errors='ignore')

            # Very basic RTF text extraction
            import re
            # Remove RTF control words
            text = re.sub(r'\\[a-z]+\d*\s?', '', content)
            text = re.sub(r'[{}]', '', text)
            text = text.strip()

            # Convert to basic XML
            from lxml import etree
            root = etree.Element("contract")
            content_elem = etree.SubElement(root, "content")
            content_elem.text = text

            xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
            xml_str += etree.tostring(root, encoding='unicode', pretty_print=True)

            return xml_str
        except Exception as e:
            logger.error(f"RTF parsing error: {e}")
            raise

    def _parse_odt(self, file_path: str) -> str:
        """
        Parse ODT to XML

        Note: Requires odfpy
        For now, returns stub - will be implemented when dependencies installed
        """
        logger.warning("ODT parsing not yet fully implemented, returning stub")

        # Stub implementation
        try:
            from lxml import etree
            root = etree.Element("contract")
            content_elem = etree.SubElement(root, "content")
            content_elem.text = f"ODT document: {os.path.basename(file_path)}"

            xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
            xml_str += etree.tostring(root, encoding='unicode', pretty_print=True)

            return xml_str
        except Exception as e:
            logger.error(f"ODT parsing error: {e}")
            raise


# Convenience function
def parse_document(file_path: str, enable_ocr: bool = True) -> str:
    """
    Parse any supported document format to XML

    Args:
        file_path: Path to document
        enable_ocr: Enable OCR for scanned PDFs

    Returns:
        XML string
    """
    parser = ExtendedDocumentParser()
    return parser.parse(file_path, enable_ocr=enable_ocr)


__all__ = ["ExtendedDocumentParser", "parse_document"]
