
import csv
from pathlib import Path
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"
FIGURES.mkdir(parents=True, exist_ok=True)


def get_result(filename, scenario):
    with (RESULTS / filename).open(newline="") as f:
        for row in csv.DictReader(f):
            if row["scenario"] == scenario:
                return row
    raise ValueError(f"Scenario not found: {scenario}")


original = "zara_sensitivity_detailed.csv"
updated = "zara_sensitivity_detailed_rerun.csv"

rows = [
    get_result(original, "threshold=2"),
    get_result(original, "Baseline"),
    get_result(updated, "threshold=4"),
]

labels = [r"$T^F=2$", r"$T^F=3$", r"$T^F=4$"]
full = [int(r["full_exposure"]) for r in rows]
partial = [int(r["partial_only"]) for r in rows]
none = [int(r["no_exposure"]) for r in rows]
values = [
    float(r["best_feasible_objective_eur"])
    for r in rows
]

fig, ax = plt.subplots(figsize=(8, 4.5))
positions = range(3)

ax.barh(positions, full, label="Full exposure")
ax.barh(positions, partial, left=full, label="Partial exposure")
ax.barh(
    positions, none,
    left=[f + p for f, p in zip(full, partial)],
    label="No exposure"
)

for i in positions:
    ax.text(
        52, i, f"EUR {values[i]:,.2f}",
        va="center", fontsize=10
    )

ax.set_yticks(list(positions), labels)
ax.invert_yaxis()
ax.set_xlim(0, 68)
ax.set_xlabel("Store-article combinations")
ax.set_title("Full-exposure threshold sensitivity")
ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.32),
          ncol=3, frameon=False)

fig.tight_layout()

for extension in ["png", "pdf"]:
    path = FIGURES / f"threshold_sensitivity_updated.{extension}"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    print(f"Saved: {path}")

plt.close(fig)
