"""Bounded text-PDF reader. Scans deliberately return no invented text."""
import base64, io, json, sys
from pypdf import PdfReader

try:
    request = json.load(sys.stdin)
    raw = base64.b64decode(request['base64'], validate=True)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('PDF exceeds 4 MB limit')
    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted:
        raise ValueError('Encrypted PDFs are not supported')
    if len(reader.pages) > 30:
        raise ValueError('PDF exceeds 30-page limit')
    pages = [{'number': i + 1, 'text': p.extract_text() or ''} for i, p in enumerate(reader.pages)]
    if sum(len(p['text']) for p in pages) > 160000:
        raise ValueError('Extracted PDF text exceeds the limit')
    print(json.dumps({'pages': pages}, ensure_ascii=True))
except Exception as exc:
    print(json.dumps({'error': str(exc)}, ensure_ascii=True))
    sys.exit(1)
