import fitz

def extract_text(file):
    doc = fitz.open(file)
    text = ""
    for page in doc:
        text += page.get_text()
    return text
