import pdfplumber

def extract_text_from_pdf(file_path):
    """Extracts the entire text content from a PDF file."""
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                content = page.extract_text()
                if content:
                    text += content + "\n"
    except Exception as e:
        print(f"Extraction error: {e}")
    return text.strip()