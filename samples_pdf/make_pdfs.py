"""
Regenerates the sample PDFs from samples.py. Only needed if the samples change.
Needs reportlab (not a runtime dependency):  pip install reportlab && python samples_pdf/make_pdfs.py
"""
import os
import re
import sys

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from samples import SAMPLE_APPLICATIONS  # noqa: E402


def write_pdf(name, text):
    c = canvas.Canvas(os.path.join(HERE, name), pagesize=A4, invariant=1)
    c.setTitle(name)
    y = A4[1] - 60
    for i, line in enumerate(text.strip().splitlines()):
        head = i == 0
        font, size = ("Helvetica-Bold", 12) if head else ("Helvetica", 10)
        while line and pdfmetrics.stringWidth(line, font, size) > A4[0] - 110:
            line = line[:-1]
        c.setFont(font, size)
        c.drawString(55, y, line)
        y -= 20 if head else 15
        if y < 60:
            c.showPage()
            y = A4[1] - 60
    c.save()


if __name__ == "__main__":
    write_pdf("alpha-logistics-application.pdf", SAMPLE_APPLICATIONS["alpha_logistics"]["raw_text"])
    parts = re.split(r"^=== (.+?) · page \d+ ===$", SAMPLE_APPLICATIONS["epsilon_foods"]["raw_text"], flags=re.M)
    for name, body in zip(parts[1::2], parts[2::2]):
        write_pdf("epsilon-foods-" + name, body)
    print(sorted(f for f in os.listdir(HERE) if f.endswith(".pdf")))
