"""Draw the documented static reconstruction workflow; no hardware or new data."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

root = Path(__file__).resolve().parents[1]
plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42})
fig, ax = plt.subplots(figsize=(7.1, 1.30))
fig.subplots_adjust(left=.005, right=.995, bottom=.02, top=.99)
ax.set(xlim=(0, 7.1), ylim=(0, 1.3)); ax.axis("off")
labels = [
    ("1  Calibrate", "K and distortion\nA-C plane fits"),
    ("2  Hold and pulse", "Fixed command u\n3 s dark / 1 s lit"),
    ("3  Detect", "APS subtraction OR\nON/OFF event groups"),
    ("4  Triangulate", "Undistort pixels\nIntersect ray + plane"),
    ("5  Evaluate", "Frozen model, board D\nCoverage / repeats"),
]
for i, (title, body) in enumerate(labels):
    x = i * 1.43
    ax.add_patch(Rectangle((x, .34), 1.30, .88, facecolor="#f0f5f8", edgecolor="#506b7a", linewidth=.8))
    ax.text(x+.65, 1.04, title, ha="center", va="center", weight="bold", fontsize=9)
    ax.text(x+.65, .66, body, ha="center", va="center", fontsize=8)
    if i < 4:
        ax.annotate("", xy=(x+1.42, .78), xytext=(x+1.30, .78), arrowprops={"arrowstyle":"->", "color":"#506b7a", "lw":1})
ax.text(3.55, .12, "Static held planes: no continuous time-to-plane association or plane interpolation is used.", ha="center", fontsize=8)
out = root / "report/figures/pipeline_static.pdf"
fig.savefig(out); plt.close(fig)
print(out)

