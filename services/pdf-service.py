import pdfplumber


def extract_text_from_pdf(path):

    text_parts = []

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:

            page_text = page.extract_text()

            if page_text:
                text_parts.append(page_text)

    return "\n".join(text_parts)