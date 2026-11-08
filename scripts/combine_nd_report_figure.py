"""Combine retained ND image and statistics panels without changing their data.

Requires pypdf. Run regenerate_nd_summary_figure.py first if the signal plot
needs rebuilding. This is offline report layout, not image correction.
"""
from pathlib import Path
from pypdf import PdfReader, PdfWriter, Transformation

root = Path(__file__).resolve().parents[1] / "report/figures"
writer = PdfWriter()
page = writer.add_blank_page(width=300, height=300)
for name, y, available_height in [
    ("nd_APS_pair.pdf", 167, 133),
    ("nd_signal_summary.pdf", 0, 164),
]:
    source = PdfReader(root / name).pages[0]
    width, height = float(source.mediabox.width), float(source.mediabox.height)
    scale = min(300 / width, available_height / height)
    transform = Transformation().scale(scale).translate(
        (300 - width * scale) / 2,
        y + (available_height - height * scale) / 2,
    )
    page.merge_transformed_page(source, transform)
writer.write(root / "nd_visual_signal.pdf")
print(root / "nd_visual_signal.pdf")
