"""Rank MAGeCK RRA output by combined score and export top hits."""
import pandas as pd
import matplotlib.pyplot as plt

rra = pd.read_csv("mageck_rra.gene_summary.txt", sep="\t")
rra = rra.sort_values("neg|score").head(50)
rra[["id", "neg|score", "neg|fdr"]].to_csv("top50_hits.csv", index=False)

fig, ax = plt.subplots(figsize=(8, 5))
ax.barh(rra["id"][:20][::-1], -rra["neg|score"][:20][::-1], color="steelblue")
ax.set_xlabel("−log10(RRA score)")
ax.set_title("Top 20 CRISPR screen hits (neg. selection)")
plt.tight_layout()
fig.savefig("top20_hits.pdf")
