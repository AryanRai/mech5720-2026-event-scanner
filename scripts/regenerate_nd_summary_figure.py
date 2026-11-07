"""Regenerate the report ND figure from retained summary statistics; no hardware."""
from pathlib import Path
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
root = Path(__file__).resolve().parents[1]
rows = json.loads((root / "results/evidence/08_comparison.json").read_text())["condition_summary"]
plt.rcParams.update({"font.size": 10, "pdf.fonttype": 42})
fig, ax = plt.subplots(figsize=(4.15, 2.05))
fig.subplots_adjust(left=.18, right=.98, bottom=.23, top=.94)
means = [r["mean_camera_signal_levels"] for r in rows]
sd = [r["sample_sd_camera_signal_levels"] for r in rows]
ax.bar([0, 1], means, yerr=sd, capsize=5, width=.55, color=["#4b728b", "#bb7a45"])
ax.set_xticks([0, 1], ["No filter (n=2)", "Unknown ND (n=3)"])
ax.set_ylabel("Stripe signal (levels)")
ax.set_ylim(0, 33)
for i, (m, v) in enumerate(zip(means, sd)):
    ax.text(i, m+1, f"{m:.3f} +/- {v:.3f}", ha="center", fontsize=8)
ax.spines[["top", "right"]].set_visible(False)
ax.yaxis.grid(alpha=.2)
ax.set_axisbelow(True)
out = root / "report/figures/nd_signal_summary.pdf"
fig.savefig(out)
print(out)
