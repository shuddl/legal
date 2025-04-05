"""Unit tests for the document parser module."""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import os
import sys
from pathlib import Path
import io

from perera_lead_scraper.legal.document_parser import (
    DocumentParser,
    ParseError,
    UnsupportedFormatError
)
from perera_lead_scraper.config import AppConfig


# Mock the modules we'll need for tests
sys.modules['PyPDF2'] = MagicMock(name='PyPDF2')
sys.modules['PyPDF2.PdfReader'] = MagicMock(name='PyPDF2.PdfReader')
sys.modules['docx'] = MagicMock(name='docx')
sys.modules['pdfplumber'] = MagicMock(name='pdfplumber')

class TestDocumentParser(unittest.TestCase):
    """Test cases for the DocumentParser class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock config
        self.mock_config = MagicMock(spec=AppConfig)
        
        # Create parser instance
        with patch('src.perera_lead_scraper.legal.document_parser.HAS_PYPDF2', True), \
             patch('src.perera_lead_scraper.legal.document_parser.HAS_DOCX', True), \
             patch('src.perera_lead_scraper.legal.document_parser.HAS_BS4', True), \
             patch('src.perera_lead_scraper.legal.document_parser.HAS_PDFPLUMBER', True):
            self.parser = DocumentParser(self.mock_config)
        
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.temp_dir.cleanup()
    
    def test_initialization(self):
        """Test parser initialization."""
        self.assertIsNotNone(self.parser)
        self.assertEqual(self.parser.config, self.mock_config)
    
    def test_is_supported_format(self):
        """Test format support checking."""
        # Supported formats
        self.assertTrue(self.parser.is_supported_format('/path/to/file.pdf'))
        self.assertTrue(self.parser.is_supported_format('/path/to/file.docx'))
        self.assertTrue(self.parser.is_supported_format('/path/to/file.doc'))
        self.assertTrue(self.parser.is_supported_format('/path/to/file.txt'))
        self.assertTrue(self.parser.is_supported_format('/path/to/file.html'))
        self.assertTrue(self.parser.is_supported_format('/path/to/file.htm'))
        self.assertTrue(self.parser.is_supported_format('/path/to/file.rtf'))
        
        # Unsupported formats
        self.assertFalse(self.parser.is_supported_format('/path/to/file.xlsx'))
        self.assertFalse(self.parser.is_supported_format('/path/to/file.ppt'))
        self.assertFalse(self.parser.is_supported_format('/path/to/file.jpg'))
    
    def test_detect_format(self):
        """Test format detection."""
        self.assertEqual(self.parser.detect_format('/path/to/file.pdf'), 'pdf')
        self.assertEqual(self.parser.detect_format('/path/to/file.docx'), 'docx')
        self.assertEqual(self.parser.detect_format('/path/to/file.doc'), 'docx')
        self.assertEqual(self.parser.detect_format('/path/to/file.txt'), 'txt')
        self.assertEqual(self.parser.detect_format('/path/to/file.html'), 'html')
        self.assertEqual(self.parser.detect_format('/path/to/file.htm'), 'html')
        self.assertEqual(self.parser.detect_format('/path/to/file.rtf'), 'rtf')
        
        with self.assertRaises(UnsupportedFormatError):
            self.parser.detect_format('/path/to/file.xlsx')
    
    def test_parse_txt_file(self):
        """Test parsing a text file."""
        txt_content = "This is a sample text document."
        txt_path = self.temp_path / 'test.txt'
        
        with open(txt_path, 'w') as f:
            f.write(txt_content)
        
        result = self.parser._parse_txt(txt_path)
        self.assertEqual(result, txt_content)
    
    def test_parse_html_file_with_bs4(self):
        """Test parsing an HTML file with BeautifulSoup."""
        html_content = "<html><body><h1>Title</h1><p>This is a sample HTML document.</p></body></html>"
        html_path = self.temp_path / 'test.html'
        
        with open(html_path, 'w') as f:
            f.write(html_content)
        
        # We can't reliably patch BeautifulSoup after our local import fix
        # So we'll just test that it works when HAS_BS4 is True
        with patch('src.perera_lead_scraper.legal.document_parser.HAS_BS4', True):
            # Only run this test if BeautifulSoup is actually available
            try:
                from bs4 import BeautifulSoup
                result = self.parser._parse_html(html_path)
                # Allow flexibility in how the text is formatted, as long as it contains both parts
                self.assertIn("Title", result)
                self.assertIn("This is a sample HTML document", result)
            except ImportError:
                # Skip this test if BeautifulSoup isn't available
                self.skipTest("BeautifulSoup not available")
    
    def test_parse_html_file_without_bs4(self):
        """Test parsing an HTML file without BeautifulSoup."""
        html_content = "<html><body><h1>Title</h1><p>This is a sample HTML document.</p></body></html>"
        html_path = self.temp_path / 'test.html'
        
        with open(html_path, 'w') as f:
            f.write(html_content)
        
        with patch('src.perera_lead_scraper.legal.document_parser.HAS_BS4', False):
            result = self.parser._parse_html(html_path)
            
        # Simple regex parsing will convert tags to spaces
        self.assertTrue("Title" in result)
        self.assertTrue("This is a sample HTML document" in result)
    
    def test_parse_rtf_file(self):
        """Test parsing an RTF file."""
        rtf_content = r"{\rtf1\ansi\ansicpg1252\cocoartf2580\cocoasubrtf220 This is a sample RTF document.}"
        rtf_path = self.temp_path / 'test.rtf'
        
        with open(rtf_path, 'w') as f:
            f.write(rtf_content)
        
        result = self.parser._parse_rtf(rtf_path)
        self.assertTrue("This is a sample RTF document" in result)
    
    @patch('PyPDF2.PdfReader')
    def test_parse_pdf_file_with_pypdf2(self, mock_pdfreader):
        """Test parsing a PDF file with PyPDF2."""
        pdf_path = self.temp_path / 'test.pdf'
        
        # Create an empty PDF file
        with open(pdf_path, 'wb') as f:
            f.write(b'%PDF-1.4\n%EOF')
        
        # Mock PdfReader and pages
        mock_reader = MagicMock()
        mock_pdfreader.return_value = mock_reader
        
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page 1 content"
        
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page 2 content"
        
        mock_reader.pages = [mock_page1, mock_page2]
        
        with patch('perera_lead_scraper.legal.document_parser.HAS_PYPDF2', True), \
             patch('perera_lead_scraper.legal.document_parser.HAS_PDFPLUMBER', False):
            result = self.parser._parse_pdf(pdf_path)
        
        self.assertEqual(result, "Page 1 content\n\nPage 2 content")
    
    @patch('pdfplumber.open')
    def test_parse_pdf_file_with_pdfplumber(self, mock_pdfplumber_open):
        """Test parsing a PDF file with pdfplumber."""
        pdf_path = self.temp_path / 'test.pdf'
        
        # Create an empty PDF file
        with open(pdf_path, 'wb') as f:
            f.write(b'%PDF-1.4\n%EOF')
        
        # Mock pdfplumber
        mock_pdf = MagicMock()
        mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf
        
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page 1 content"
        
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page 2 content"
        
        mock_pdf.pages = [mock_page1, mock_page2]
        
        with patch('src.perera_lead_scraper.legal.document_parser.HAS_PDFPLUMBER', True):
            result = self.parser._parse_pdf(pdf_path)
        
        self.assertEqual(result, "Page 1 content\n\nPage 2 content")
    
    @patch('docx.Document')
    def test_parse_docx_file(self, mock_document):
        """Test parsing a DOCX file."""
        docx_path = self.temp_path / 'test.docx'
        
        # Create an empty DOCX file (not a real DOCX, just for the test)
        with open(docx_path, 'wb') as f:
            f.write(b'fake docx content')
        
        # Mock Document and paragraphs
        mock_doc = MagicMock()
        mock_document.return_value = mock_doc
        
        mock_paragraph1 = MagicMock()
        mock_paragraph1.text = "Paragraph 1 content"
        
        mock_paragraph2 = MagicMock()
        mock_paragraph2.text = "Paragraph 2 content"
        
        mock_doc.paragraphs = [mock_paragraph1, mock_paragraph2]
        
        with patch('perera_lead_scraper.legal.document_parser.HAS_DOCX', True):
            result = self.parser._parse_docx(docx_path)
        
        self.assertEqual(result, "Paragraph 1 content\nParagraph 2 content")
    
    def test_parse_docx_without_module(self):
        """Test parsing a DOCX file without python-docx."""
        docx_path = self.temp_path / 'test.docx'
        
        # Create an empty DOCX file
        with open(docx_path, 'wb') as f:
            f.write(b'fake docx content')
        
        with patch('perera_lead_scraper.legal.document_parser.HAS_DOCX', False):
            with self.assertRaises(ParseError):
                self.parser._parse_docx(docx_path)
    
    def test_parse_file_nonexistent(self):
        """Test parsing a non-existent file."""
        with self.assertRaises(ParseError):
            self.parser.parse_file('/path/to/nonexistent/file.txt')
    
    def test_parse_content_bytes(self):
        """Test parsing content from bytes."""
        # Mock parse_file method
        self.parser.parse_file = MagicMock(return_value="Parsed content")
        
        content = b'This is test content'
        result = self.parser.parse_content(content, 'txt')
        
        self.assertEqual(result, "Parsed content")
    
    def test_parse_content_file_object(self):
        """Test parsing content from a file-like object."""
        # Mock parse_file method
        self.parser.parse_file = MagicMock(return_value="Parsed content")
        
        content = io.BytesIO(b'This is test content')
        result = self.parser.parse_content(content, 'txt')
        
        self.assertEqual(result, "Parsed content")
    
    def test_parse_content_unsupported_format(self):
        """Test parsing content with an unsupported format."""
        with self.assertRaises(UnsupportedFormatError):
            self.parser.parse_content(b'content', 'xlsx')
    
    def test_batch_parse(self):
        """Test batch parsing of files."""
        # Create test files
        txt_path = self.temp_path / 'test1.txt'
        with open(txt_path, 'w') as f:
            f.write("Text file content")
        
        html_path = self.temp_path / 'test2.html'
        with open(html_path, 'w') as f:
            f.write("<html><body>HTML content</body></html>")
        
        # Path that doesn't exist
        nonexistent_path = self.temp_path / 'nonexistent.txt'
        
        # Mock parse methods
        self.parser._parse_txt = MagicMock(return_value="Text file content")
        self.parser._parse_html = MagicMock(return_value="HTML content")
        
        # Batch parse
        results = self.parser.batch_parse([txt_path, html_path, nonexistent_path])
        
        self.assertEqual(len(results), 3)
        self.assertEqual(results[str(txt_path)], "Text file content")
        self.assertEqual(results[str(html_path)], "HTML content")
        self.assertIn("error", results[str(nonexistent_path)])


if __name__ == '__main__':
    unittest.main()