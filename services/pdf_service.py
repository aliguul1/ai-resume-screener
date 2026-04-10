"""
Service for PDF text extraction.
"""
import pdfplumber

def extract_text_from_pdf(path):
    """Extracts all text from a PDF file."""
    text_parts = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                content = page.extract_text()
                if content:
                    text_parts.append(content)
    except Exception:
        return ""
    return "\n".join(text_parts)