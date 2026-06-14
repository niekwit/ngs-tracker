"""
Create a demo SQLite database populated with fictional but realistic data.
Useful for documentation screenshots, demos, and testing.

Usage:
    conda run -n ngs-tracker python create_demo_db.py
    conda run -n ngs-tracker python create_demo_db.py --out /path/to/demo.db

The output file defaults to demo.db in the repo root.
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# ── Bootstrap Flask app pointing at the demo DB ───────────────────────────────

parser = argparse.ArgumentParser()
parser.add_argument("--out", default=str(Path(__file__).parent / "demo.db"))
args = parser.parse_args()

demo_db = Path(args.out).resolve()
if demo_db.exists():
    demo_db.unlink()
    print(f"Removed existing {demo_db}")

from flask import Flask

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{demo_db}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

from models import (
    AttachedFile,
    Project,
    ResearchGroup,
    Researcher,
    RunSample,
    Sample,
    WorkflowRun,
    db,
)

db.init_app(app)


# ── Helpers ───────────────────────────────────────────────────────────────────


def dt(days_ago: int, hour: int = 9) -> datetime:
    return datetime.now().replace(
        hour=hour, minute=0, second=0, microsecond=0
    ) - timedelta(days=days_ago)


def backups(*pairs) -> str:
    """pairs: ('Location', '/some/path') ..."""
    return json.dumps([{"location": loc, "path": path} for loc, path in pairs])


# ── Seed data ─────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()

    # ── Research Groups ───────────────────────────────────────────────────────

    grp_genomics = ResearchGroup(
        name="Genomics & Epigenetics",
        description="We study chromatin regulation and gene expression using next-generation sequencing approaches.",
        created_at=dt(400),
    )
    grp_compbio = ResearchGroup(
        name="Computational Biology",
        description="Development and benchmarking of bioinformatics pipelines for large-scale genomic data.",
        created_at=dt(380),
    )
    grp_dev = ResearchGroup(
        name="Developmental Genomics",
        description="Transcriptional networks controlling cell fate decisions during mammalian development.",
        created_at=dt(300),
    )
    db.session.add_all([grp_genomics, grp_compbio, grp_dev])
    db.session.flush()

    # ── Researchers ───────────────────────────────────────────────────────────

    # Genomics & Epigenetics
    alice = Researcher(
        name="Alice Morgan",
        email="a.morgan@uni.ac.uk",
        group_id=grp_genomics.id,
        created_at=dt(395),
    )
    ben = Researcher(
        name="Ben Hartley",
        email="b.hartley@uni.ac.uk",
        group_id=grp_genomics.id,
        created_at=dt(370),
    )
    chloe = Researcher(
        name="Chloe Nakamura",
        email="c.nakamura@uni.ac.uk",
        group_id=grp_genomics.id,
        created_at=dt(290),
    )

    # Computational Biology
    david = Researcher(
        name="David Osei",
        email="d.osei@uni.ac.uk",
        group_id=grp_compbio.id,
        created_at=dt(375),
    )
    emma = Researcher(
        name="Emma Thorpe",
        email="e.thorpe@uni.ac.uk",
        group_id=grp_compbio.id,
        created_at=dt(310),
    )

    # Developmental Genomics
    finn = Researcher(
        name="Finn Larsson",
        email="f.larsson@uni.ac.uk",
        group_id=grp_dev.id,
        created_at=dt(295),
    )
    grace = Researcher(
        name="Grace O'Brien",
        email="g.obrien@uni.ac.uk",
        group_id=grp_dev.id,
        created_at=dt(260),
    )

    db.session.add_all([alice, ben, chloe, david, emma, finn, grace])
    db.session.flush()

    # ── Projects ──────────────────────────────────────────────────────────────

    # Alice
    proj_chip = Project(
        name="H3K27ac ChIP-seq in MEFs",
        description="Mapping active enhancers during fibroblast reprogramming using H3K27ac ChIP-seq.",
        researcher_id=alice.id,
        created_at=dt(350),
        published=True,
        publication_url="https://doi.org/10.1038/s41467-024-00001-1",
    )
    proj_atac = Project(
        name="ATAC-seq differentiation timecourse",
        description="Chromatin accessibility dynamics across a 10-day iPSC differentiation timecourse.",
        researcher_id=alice.id,
        created_at=dt(200),
    )

    # Ben
    proj_crispr = Project(
        name="CRISPR screen — KRAS signalling",
        description="Genome-wide loss-of-function screen identifying synthetic lethal interactions with KRAS G12D.",
        researcher_id=ben.id,
        created_at=dt(280),
    )
    proj_rnaseq_drug = Project(
        name="RNA-seq after MEK inhibitor treatment",
        description="Transcriptional response to MEK inhibition at 6 h, 24 h, and 72 h time points.",
        researcher_id=ben.id,
        created_at=dt(160),
    )

    # Chloe
    proj_cutnrun = Project(
        name="CUT&RUN histone marks — stem cells",
        description="High-resolution profiling of H3K4me3, H3K27me3, and H3K9me3 in mouse embryonic stem cells.",
        researcher_id=chloe.id,
        created_at=dt(240),
    )

    # David
    proj_benchmark = Project(
        name="Nextflow RNA-seq pipeline benchmark",
        description="Benchmarking nf-core/rnaseq against in-house Snakemake pipeline on simulated and real data.",
        researcher_id=david.id,
        created_at=dt(320),
    )
    proj_sc = Project(
        name="Single-cell atlas — pancreatic cancer",
        description="scRNA-seq atlas of 12 pancreatic ductal adenocarcinoma samples and matched normal tissue.",
        researcher_id=david.id,
        created_at=dt(130),
    )

    # Emma
    proj_variant = Project(
        name="Germline variant calling — family cohort",
        description="GATK best-practices variant calling on 24 trio whole-genome sequences.",
        researcher_id=emma.id,
        created_at=dt(220),
    )

    # Finn
    proj_dev_chip = Project(
        name="ChIP-seq developmental timecourse",
        description="CTCF and cohesin occupancy during cardiomyocyte differentiation from E7.5 to E14.5.",
        researcher_id=finn.id,
        created_at=dt(270),
    )

    # Grace
    proj_cwl_atac = Project(
        name="CWL ATAC-seq pipeline",
        description="Standardised CWL workflow for ATAC-seq data processing submitted to WorkflowHub.",
        researcher_id=grace.id,
        created_at=dt(180),
    )
    proj_meth = Project(
        name="WGBS methylation analysis",
        description="Whole-genome bisulfite sequencing to map 5mC changes during gastrulation.",
        researcher_id=grace.id,
        created_at=dt(90),
    )

    db.session.add_all(
        [
            proj_chip,
            proj_atac,
            proj_crispr,
            proj_rnaseq_drug,
            proj_cutnrun,
            proj_benchmark,
            proj_sc,
            proj_variant,
            proj_dev_chip,
            proj_cwl_atac,
            proj_meth,
        ]
    )
    db.session.flush()

    # ── Samples ───────────────────────────────────────────────────────────────

    def add_samples(project, names):
        objs = [Sample(project_id=project.id, name=n) for n in names]
        db.session.add_all(objs)
        db.session.flush()
        return objs

    chip_samples = add_samples(
        proj_chip,
        [
            "MEF_H3K27ac_D0_rep1",
            "MEF_H3K27ac_D0_rep2",
            "MEF_H3K27ac_D3_rep1",
            "MEF_H3K27ac_D3_rep2",
            "MEF_Input_D0",
            "MEF_Input_D3",
        ],
    )
    atac_samples = add_samples(
        proj_atac, [f"iPSC_D{d}_rep{r}" for d in [0, 2, 4, 7, 10] for r in [1, 2]]
    )
    crispr_samples = add_samples(
        proj_crispr,
        [
            "Screen_T0",
            "Screen_T14_A",
            "Screen_T14_B",
            "Screen_T14_C",
        ],
    )
    cutnrun_samples = add_samples(
        proj_cutnrun,
        [
            "mESC_H3K4me3_rep1",
            "mESC_H3K4me3_rep2",
            "mESC_H3K27me3_rep1",
            "mESC_H3K27me3_rep2",
            "mESC_H3K9me3_rep1",
            "mESC_H3K9me3_rep2",
            "mESC_IgG_ctrl",
        ],
    )
    rnaseq_samples = add_samples(
        proj_rnaseq_drug,
        [f"MEK_inh_{t}h_rep{r}" for t in ["6", "24", "72"] for r in [1, 2, 3]]
        + [f"DMSO_ctrl_rep{r}" for r in [1, 2, 3]],
    )
    sc_samples = add_samples(
        proj_sc,
        [f"PDAC_sample_{i:02d}" for i in range(1, 13)]
        + [f"Normal_sample_{i:02d}" for i in range(1, 7)],
    )
    variant_samples = add_samples(
        proj_variant,
        [
            f"Family{f:02d}_{role}"
            for f in range(1, 9)
            for role in ["proband", "mother", "father"]
        ],
    )
    dev_chip_samples = add_samples(
        proj_dev_chip,
        [
            f"E{stage}_CTCF_rep{r}"
            for stage in ["7.5", "9.5", "11.5", "14.5"]
            for r in [1, 2]
        ],
    )

    # ── Workflow Runs ─────────────────────────────────────────────────────────

    # Helper to link samples to a run
    def link_samples(run, samples):
        for s in samples:
            db.session.add(RunSample(run_id=run.id, sample_id=s.id))

    # ── Alice / H3K27ac ChIP-seq ─────────────────────────────────────────────

    run_chip1 = WorkflowRun(
        project_id=proj_chip.id,
        workflow_name="chip-seq",
        workflow_tag="v1.3.0",
        workflow_system="snakemake",
        description="Initial ChIP-seq run — pilot experiment",
        status="completed",
        run_date=dt(340),
        created_by="Alice Morgan",
        tags="pilot,histone-mark,MEF",
        runtime_seconds=2847,  # ~47 min (4 samples)
        backups=backups(
            ("Local", "/data/alice/chip_pilot"), ("RCS", "/rcs/alice/chip_pilot")
        ),
        notes=(
            "## Pilot run\n\n"
            "First attempt with the ChIP-seq pipeline on D0 MEF samples.\n\n"
            "### QC summary\n"
            "- Library complexity: good (NRF > 0.8)\n"
            "- FRiP score: 0.12 (acceptable)\n"
            "- Input controls show low background\n\n"
            "Proceeding to full timecourse."
        ),
    )
    db.session.add(run_chip1)
    db.session.flush()
    link_samples(run_chip1, chip_samples[:4])

    run_chip2 = WorkflowRun(
        project_id=proj_chip.id,
        workflow_name="chip-seq",
        workflow_tag="v1.4.1",
        workflow_system="snakemake",
        description="Full timecourse — D0 and D3 replicates",
        status="completed",
        run_date=dt(290),
        created_by="Alice Morgan",
        tags="published,histone-mark,MEF,timecourse",
        runtime_seconds=4521,  # ~1h 15min (6 samples)
        backups=backups(
            ("Local", "/data/alice/chip_timecourse"),
            ("RCS", "/rcs/alice/chip_timecourse"),
            ("RFS", "/rfs/genomics/alice/chip_timecourse"),
        ),
        notes=(
            "## Full timecourse analysis\n\n"
            "All 6 samples (D0 ×2, D3 ×2, inputs ×2).\n\n"
            "### Key findings\n"
            "- 1,423 gained enhancers at D3\n"
            "- 856 lost enhancers at D3\n"
            "- Gained enhancers enriched for AP-1 motifs (HOMER, p < 1e-50)\n\n"
            "These results are the basis for **Figure 2** in the publication."
        ),
    )
    db.session.add(run_chip2)
    db.session.flush()
    link_samples(run_chip2, chip_samples)

    # ── Alice / ATAC-seq timecourse ───────────────────────────────────────────

    run_atac1 = WorkflowRun(
        project_id=proj_atac.id,
        workflow_name="atac-seq",
        workflow_tag="v2.0.0",
        workflow_system="snakemake",
        description="D0 and D2 samples — quality check",
        status="completed",
        run_date=dt(185),
        created_by="Alice Morgan",
        tags="ATAC-seq,iPSC,chromatin",
        runtime_seconds=1923,  # ~32 min (4 samples)
        backups=backups(("Local", "/data/alice/atac_tc")),
        notes="Initial two time points. D0 FRiP = 0.22, D2 FRiP = 0.19. Proceeding to full timecourse.",
    )
    db.session.add(run_atac1)
    db.session.flush()
    link_samples(run_atac1, atac_samples[:4])

    run_atac2 = WorkflowRun(
        project_id=proj_atac.id,
        workflow_name="atac-seq",
        workflow_tag="v2.1.0",
        workflow_system="snakemake",
        description="Full 5-point timecourse",
        status="completed",
        run_date=dt(140),
        created_by="Alice Morgan",
        tags="ATAC-seq,iPSC,chromatin,timecourse",
        runtime_seconds=6237,  # ~1h 44min (10 samples)
        backups=backups(
            ("Local", "/data/alice/atac_full"),
            ("RCS", "/rcs/alice/atac_full"),
        ),
        notes=(
            "## Full timecourse\n\n"
            "All 10 samples across D0, D2, D4, D7, D10.\n\n"
            "- 18,432 accessible peaks at D0\n"
            "- Progressive opening of cardiac lineage loci from D4 onwards\n"
            "- Strong correlation with H3K27ac data from ChIP-seq project\n\n"
            "Manuscript in preparation."
        ),
    )
    db.session.add(run_atac2)
    db.session.flush()
    link_samples(run_atac2, atac_samples)

    run_atac3 = WorkflowRun(
        project_id=proj_atac.id,
        workflow_name="atac-seq",
        workflow_tag="v2.1.0",
        workflow_system="snakemake",
        description="Re-run with updated blacklist (hg38 v3)",
        status="running",
        run_date=dt(2),
        created_by="Alice Morgan",
        tags="ATAC-seq,iPSC,reanalysis",
        backups=backups(("Local", "/data/alice/atac_reanalysis")),
        notes="Re-running after reviewer comment requesting updated ENCODE blacklist regions.",
    )
    db.session.add(run_atac3)
    db.session.flush()
    link_samples(run_atac3, atac_samples)

    # ── Ben / CRISPR screen ───────────────────────────────────────────────────

    run_crispr1 = WorkflowRun(
        project_id=proj_crispr.id,
        workflow_name="crispr-screens",
        workflow_tag="v1.1.2",
        workflow_system="snakemake",
        description="Brunello library screen — first replicate set",
        status="completed",
        run_date=dt(260),
        created_by="Ben Hartley",
        tags="CRISPR,screen,KRAS,oncology",
        runtime_seconds=1834,  # ~30 min
        backups=backups(
            ("Local", "/data/ben/crispr_screen"),
            ("RCS", "/rcs/ben/crispr_kras"),
        ),
        notes=(
            "## CRISPR screen — replicate set 1\n\n"
            "Brunello genome-wide library (~77k guides, 4 per gene).\n\n"
            "### Sequencing stats\n"
            "| Sample | Reads | % mapped |\n"
            "|---|---|---|\n"
            "| T0 | 42 M | 87% |\n"
            "| T14 A | 38 M | 85% |\n"
            "| T14 B | 41 M | 86% |\n"
            "| T14 C | 39 M | 85% |\n\n"
            "Top hit: **SOS1** (FDR < 0.001, log2FC = -2.8). Validates known KRAS dependency."
        ),
    )
    db.session.add(run_crispr1)
    db.session.flush()
    link_samples(run_crispr1, crispr_samples)

    run_crispr2 = WorkflowRun(
        project_id=proj_crispr.id,
        workflow_name="crispr-screens",
        workflow_tag="v1.2.0",
        workflow_system="snakemake",
        description="Validation screen with focused library (top 500 hits)",
        status="completed",
        run_date=dt(200),
        created_by="Ben Hartley",
        tags="CRISPR,screen,validation,KRAS",
        runtime_seconds=1502,  # ~25 min
        backups=backups(
            ("Local", "/data/ben/crispr_validation"),
            ("RCS", "/rcs/ben/crispr_validation"),
            ("RFS", "/rfs/genomics/ben/crispr_val"),
        ),
        notes="Focused re-screen of top 500 candidates. Confirmed 312/500 with FDR < 0.05.",
    )
    db.session.add(run_crispr2)
    db.session.flush()
    link_samples(run_crispr2, crispr_samples)

    # ── Ben / RNA-seq drug treatment ──────────────────────────────────────────

    run_rna1 = WorkflowRun(
        project_id=proj_rnaseq_drug.id,
        workflow_name="rna-seq",
        workflow_tag="v3.14.0",
        workflow_system="nextflow",
        description="nf-core/rnaseq — MEK inhibitor timecourse",
        status="completed",
        run_date=dt(145),
        created_by="Ben Hartley",
        tags="RNA-seq,MEK,drug-treatment,Nextflow",
        runtime_seconds=12543,  # ~3h 29min (12 samples, Nextflow)
        backups=backups(
            ("Local", "/data/ben/rnaseq_meki"),
            ("RCS", "/rcs/ben/rnaseq_meki"),
        ),
        notes=(
            "## MEK inhibitor RNA-seq\n\n"
            "Used nf-core/rnaseq v3.14.0 with STAR aligner and RSEM quantification.\n\n"
            "- 12 samples: 3 time points × 3 replicates + 3 DMSO controls\n"
            "- Reference: GRCh38 Ensembl 110\n"
            "- DESeq2 analysis downstream\n\n"
            "### Early response (6 h)\n"
            "823 DEGs (padj < 0.05, |log2FC| > 1). Strong downregulation of ERK target genes."
        ),
    )
    db.session.add(run_rna1)
    db.session.flush()
    link_samples(run_rna1, rnaseq_samples)

    run_rna2 = WorkflowRun(
        project_id=proj_rnaseq_drug.id,
        workflow_name="rna-seq",
        workflow_tag="v3.14.0",
        workflow_system="nextflow",
        description="Re-analysis with updated gene model (Ensembl 112)",
        status="pending",
        run_date=dt(0),
        created_by="Ben Hartley",
        tags="RNA-seq,MEK,reanalysis",
        backups=backups(),
        notes="Awaiting HPC allocation. Updating reference to Ensembl 112 per journal requirements.",
    )
    db.session.add(run_rna2)
    db.session.flush()

    # ── Chloe / CUT&RUN ──────────────────────────────────────────────────────

    run_cr1 = WorkflowRun(
        project_id=proj_cutnrun.id,
        workflow_name="cut_and_run",
        workflow_tag="v1.0.0",
        workflow_system="snakemake",
        description="H3K4me3 and H3K27me3 in mESCs",
        status="completed",
        run_date=dt(220),
        created_by="Chloe Nakamura",
        tags="CUT&RUN,histone-mark,mESC,bivalent",
        runtime_seconds=4128,  # ~1h 9min (5 samples)
        backups=backups(
            ("Local", "/data/chloe/cutnrun_mesc"),
            ("RCS", "/rcs/chloe/cutnrun"),
        ),
        notes=(
            "## CUT&RUN — bivalent domain profiling\n\n"
            "H3K4me3 and H3K27me3 to identify bivalent (poised) promoters in mESCs.\n\n"
            "- 2,341 bivalent promoters identified\n"
            "- Strong overlap with known developmental regulators (Hox, Pax, Sox families)\n"
            "- IgG background extremely low (< 0.1% of reads in peaks)"
        ),
    )
    db.session.add(run_cr1)
    db.session.flush()
    link_samples(run_cr1, cutnrun_samples[:5])

    run_cr2 = WorkflowRun(
        project_id=proj_cutnrun.id,
        workflow_name="cut_and_run",
        workflow_tag="v1.0.0",
        workflow_system="snakemake",
        description="H3K9me3 heterochromatin mark",
        status="failed",
        run_date=dt(190),
        created_by="Chloe Nakamura",
        tags="CUT&RUN,histone-mark,mESC,heterochromatin",
        runtime_seconds=743,  # ~12 min (failed early — QC abort)
        backups=backups(("Local", "/data/chloe/cutnrun_h3k9me3")),
        notes=(
            "## H3K9me3 run — FAILED\n\n"
            "> **Issue:** Antibody lot change caused >80% drop in signal-to-noise.\n\n"
            "FRiP dropped from expected ~0.3 to 0.02. Run aborted.\n\n"
            "Ordered new antibody (Abcam ab8898, lot GR3456). Re-run scheduled."
        ),
    )
    db.session.add(run_cr2)
    db.session.flush()
    link_samples(run_cr2, cutnrun_samples[4:7])

    run_cr3 = WorkflowRun(
        project_id=proj_cutnrun.id,
        workflow_name="cut_and_run",
        workflow_tag="v1.1.0",
        workflow_system="snakemake",
        description="H3K9me3 re-run with new antibody lot",
        status="completed",
        run_date=dt(155),
        created_by="Chloe Nakamura",
        tags="CUT&RUN,histone-mark,mESC,heterochromatin",
        runtime_seconds=3219,  # ~54 min (3 samples)
        backups=backups(
            ("Local", "/data/chloe/cutnrun_h3k9me3_v2"),
            ("RCS", "/rcs/chloe/cutnrun_h3k9me3_v2"),
        ),
        notes="New antibody lot gives FRiP = 0.28. 14,823 H3K9me3 peaks, enriched at repeat elements as expected.",
    )
    db.session.add(run_cr3)
    db.session.flush()
    link_samples(run_cr3, cutnrun_samples[4:7])

    # ── David / Nextflow benchmark ────────────────────────────────────────────

    run_bench1 = WorkflowRun(
        project_id=proj_benchmark.id,
        workflow_name="rna-seq",
        workflow_tag="v3.12.0",
        workflow_system="nextflow",
        description="nf-core/rnaseq — baseline benchmark run",
        status="completed",
        run_date=dt(300),
        created_by="David Osei",
        tags="benchmark,Nextflow,nf-core,RNA-seq",
        runtime_seconds=15720,  # 4h 22min (matches notes)
        backups=backups(("Local", "/data/david/benchmark_nfcore")),
        notes="Baseline run using nf-core/rnaseq v3.12. STAR + Salmon. Runtime: 4h 22min on 32 cores.",
    )
    db.session.add(run_bench1)
    db.session.flush()

    run_bench2 = WorkflowRun(
        project_id=proj_benchmark.id,
        workflow_name="rna-seq-snakemake",
        workflow_tag="v2.0.0",
        workflow_system="snakemake",
        description="In-house Snakemake pipeline — benchmark comparison",
        status="completed",
        run_date=dt(285),
        created_by="David Osei",
        tags="benchmark,Snakemake,RNA-seq",
        runtime_seconds=14280,  # 3h 58min (matches notes)
        backups=backups(("Local", "/data/david/benchmark_smk")),
        notes="Matched parameters. STAR + featureCounts. Runtime: 3h 58min. Gene-level correlation r=0.998 vs nf-core.",
    )
    db.session.add(run_bench2)
    db.session.flush()

    # ── David / Single-cell atlas ─────────────────────────────────────────────

    run_sc1 = WorkflowRun(
        project_id=proj_sc.id,
        workflow_name="scrnaseq",
        workflow_tag="v2.7.1",
        workflow_system="nextflow",
        description="nf-core/scrnaseq — Cell Ranger + Seurat clustering",
        status="completed",
        run_date=dt(110),
        created_by="David Osei",
        tags="scRNA-seq,atlas,PDAC,Nextflow,nf-core",
        runtime_seconds=34812,  # ~9h 40min (18 samples, Cell Ranger)
        backups=backups(
            ("Local", "/data/david/pdac_atlas"),
            ("RCS", "/rcs/david/pdac_atlas"),
            ("RFS", "/rfs/compbio/pdac_atlas"),
        ),
        notes=(
            "## PDAC single-cell atlas\n\n"
            "18 samples: 12 tumour + 6 matched normal.\n\n"
            "### Clustering summary\n"
            "- 84,231 cells after QC (doublet removal, MT% < 20%)\n"
            "- 22 distinct clusters identified\n"
            "- Major cell types: ductal (32%), fibroblasts (18%), T cells (14%), macrophages (11%)\n\n"
            "### Notable finding\n"
            "A novel ductal subpopulation (cluster 7) marked by *KRT17*/*MUC5AC* co-expression "
            "is enriched in samples from patients with poor survival (log-rank p = 0.003)."
        ),
    )
    db.session.add(run_sc1)
    db.session.flush()
    link_samples(run_sc1, sc_samples)

    run_sc2 = WorkflowRun(
        project_id=proj_sc.id,
        workflow_name="scrnaseq",
        workflow_tag="v2.7.1",
        workflow_system="nextflow",
        description="Re-clustering with updated cell type markers",
        status="running",
        run_date=dt(1),
        created_by="David Osei",
        tags="scRNA-seq,atlas,PDAC,reanalysis",
        backups=backups(("Local", "/data/david/pdac_atlas_v2")),
        notes="Incorporating updated pancreatic cell type marker gene sets from PanglaoDB v2024.",
    )
    db.session.add(run_sc2)
    db.session.flush()
    link_samples(run_sc2, sc_samples)

    # ── Emma / Variant calling ────────────────────────────────────────────────

    run_var1 = WorkflowRun(
        project_id=proj_variant.id,
        workflow_name="sarek",
        workflow_tag="v3.4.3",
        workflow_system="nextflow",
        description="nf-core/sarek — GATK HaplotypeCaller germline calling",
        status="completed",
        run_date=dt(200),
        created_by="Emma Thorpe",
        tags="WGS,variant-calling,germline,GATK,Nextflow",
        runtime_seconds=52438,  # ~14h 34min (WGS, 24 samples)
        backups=backups(
            ("Local", "/data/emma/variant_calling"),
            ("RCS", "/rcs/emma/wgs_cohort"),
        ),
        notes=(
            "## Germline variant calling — 8 trios\n\n"
            "GATK4 HaplotypeCaller with joint genotyping (24 samples).\n\n"
            "### Variant statistics (post-VQSR)\n"
            "- SNVs: 4,312,847 (Ti/Tv = 2.09)\n"
            "- Indels: 812,344\n"
            "- Mean per-sample depth: 32×\n\n"
            "### Rare variant burden\n"
            "3 de novo variants identified in probands (gnomAD AF < 1e-5). "
            "Two are in known disease genes (*MYH7*, *KCNQ4*). Referred to clinical genetics."
        ),
    )
    db.session.add(run_var1)
    db.session.flush()
    link_samples(run_var1, variant_samples)

    run_var2 = WorkflowRun(
        project_id=proj_variant.id,
        workflow_name="sarek",
        workflow_tag="v3.4.4",
        workflow_system="nextflow",
        description="Patch: updated dbSNP (b156) and gnomAD (v4.1) annotations",
        status="completed",
        run_date=dt(130),
        created_by="Emma Thorpe",
        tags="WGS,variant-calling,annotation,patch",
        runtime_seconds=50912,  # ~14h 8min
        backups=backups(
            ("Local", "/data/emma/variant_calling_v2"),
            ("RCS", "/rcs/emma/wgs_cohort_v2"),
        ),
        notes="Updated annotation databases. Pathogenicity classifications unchanged for the 3 candidate de novo variants.",
    )
    db.session.add(run_var2)
    db.session.flush()
    link_samples(run_var2, variant_samples)

    # ── Finn / Developmental ChIP-seq ─────────────────────────────────────────

    run_dev1 = WorkflowRun(
        project_id=proj_dev_chip.id,
        workflow_name="chip-seq",
        workflow_tag="v1.4.0",
        workflow_system="snakemake",
        description="CTCF ChIP-seq E7.5 and E9.5",
        status="completed",
        run_date=dt(250),
        created_by="Finn Larsson",
        tags="ChIP-seq,CTCF,cohesin,development,mouse",
        runtime_seconds=3124,  # ~52 min (4 samples)
        backups=backups(
            ("Local", "/data/finn/devchip_early"),
            ("RCS", "/rcs/finn/devchip"),
        ),
        notes="Early time points. CTCF occupancy highly dynamic between E7.5 and E9.5. 4,201 gained sites.",
    )
    db.session.add(run_dev1)
    db.session.flush()
    link_samples(run_dev1, dev_chip_samples[:4])

    run_dev2 = WorkflowRun(
        project_id=proj_dev_chip.id,
        workflow_name="chip-seq",
        workflow_tag="v1.4.1",
        workflow_system="snakemake",
        description="CTCF ChIP-seq E11.5 and E14.5",
        status="completed",
        run_date=dt(210),
        created_by="Finn Larsson",
        tags="ChIP-seq,CTCF,cohesin,development,mouse",
        runtime_seconds=3287,  # ~55 min (4 samples)
        backups=backups(
            ("Local", "/data/finn/devchip_late"),
            ("RCS", "/rcs/finn/devchip"),
        ),
        notes="Late time points. Convergence of CTCF landscape with mature cardiomyocyte pattern by E14.5.",
    )
    db.session.add(run_dev2)
    db.session.flush()
    link_samples(run_dev2, dev_chip_samples[4:])

    run_dev3 = WorkflowRun(
        project_id=proj_dev_chip.id,
        workflow_name="chip-seq",
        workflow_tag="v1.4.1",
        workflow_system="snakemake",
        description="Full timecourse merged analysis",
        status="completed",
        run_date=dt(170),
        created_by="Finn Larsson",
        tags="ChIP-seq,CTCF,timecourse,integration",
        runtime_seconds=5834,  # ~1h 37min (8 samples)
        backups=backups(
            ("Local", "/data/finn/devchip_merged"),
            ("RCS", "/rcs/finn/devchip_merged"),
            ("RFS", "/rfs/devgen/finn/devchip"),
        ),
        notes="Merged peak set from all 4 stages. 22,891 union CTCF peaks; 6,134 constitutive, 16,757 stage-specific.",
    )
    db.session.add(run_dev3)
    db.session.flush()
    link_samples(run_dev3, dev_chip_samples)

    # ── Grace / CWL ATAC-seq ──────────────────────────────────────────────────

    run_cwl1 = WorkflowRun(
        project_id=proj_cwl_atac.id,
        workflow_name="atac-seq-cwl",
        workflow_tag="v1.0.0",
        workflow_system="cwl",
        description="CWL ATAC-seq pipeline — initial validation",
        status="completed",
        run_date=dt(160),
        created_by="Grace O'Brien",
        tags="ATAC-seq,CWL,WorkflowHub,portability",
        runtime_seconds=4562,  # ~1h 16min
        backups=backups(("Local", "/data/grace/cwl_atac")),
        notes=(
            "## CWL ATAC-seq pipeline validation\n\n"
            "Validated on ENCODE GM12878 ATAC-seq data (ENCSR095QNB).\n\n"
            "Results match published ENCODE peaks (Jaccard index = 0.84).\n\n"
            "Submitted to WorkflowHub: https://workflowhub.eu/workflows/1234"
        ),
    )
    db.session.add(run_cwl1)
    db.session.flush()

    # ── Grace / WGBS methylation ──────────────────────────────────────────────

    run_meth1 = WorkflowRun(
        project_id=proj_meth.id,
        workflow_name="bismark-wgbs",
        workflow_tag="v0.9.0",
        workflow_system="snakemake",
        description="Bismark alignment and methylation extraction — E6.5 vs E7.5",
        status="completed",
        run_date=dt(75),
        created_by="Grace O'Brien",
        tags="WGBS,methylation,gastrulation,mouse",
        runtime_seconds=31847,  # ~8h 51min (WGBS bisulfite alignment)
        backups=backups(
            ("Local", "/data/grace/wgbs_gastrulation"),
            ("RCS", "/rcs/grace/wgbs"),
        ),
        notes=(
            "## WGBS — gastrulation methylation dynamics\n\n"
            "E6.5 epiblast vs E7.5 mesoderm.\n\n"
            "- Mean genome-wide CpG methylation: E6.5 = 82%, E7.5 = 74%\n"
            "- 34,512 differentially methylated regions (DMRs, |Δmeth| > 20%, FDR < 0.01)\n"
            "- Hypomethylated DMRs at E7.5 enriched for mesoderm TF motifs (T, HAND1, MESP1)"
        ),
    )
    db.session.add(run_meth1)
    db.session.flush()

    run_meth2 = WorkflowRun(
        project_id=proj_meth.id,
        workflow_name="bismark-wgbs",
        workflow_tag="v0.9.0",
        workflow_system="snakemake",
        description="Extended timecourse — E7.5, E8.5, E9.5",
        status="pending",
        run_date=dt(0),
        created_by="Grace O'Brien",
        tags="WGBS,methylation,gastrulation,timecourse",
        backups=backups(),
        notes="Samples from later stages being processed. Library prep complete; sequencing submitted to core facility.",
    )
    db.session.add(run_meth2)
    db.session.flush()

    # ── Mapping rates example (attached to run_rna1) ─────────────────────────

    demo_storage = Path(
        os.environ.get("NGS_STORAGE_PATH", demo_db.parent / "demo-files")
    )
    mr_run_dir = demo_storage / "runs" / str(run_rna1.id)
    mr_run_dir.mkdir(parents=True, exist_ok=True)

    mr_samples = [
        f"MEK_inh_{t}h_rep{r}" for t in ["6", "24", "72"] for r in [1, 2, 3]
    ] + [f"DMSO_ctrl_rep{r}" for r in [1, 2, 3]]
    mr_rates = [78.3, 76.1, 45.2, 82.4, 83.7, 81.9, 79.8, 38.5, 80.2, 85.3, 87.1, 86.4]

    mr_csv_lines = ["sample,mapping_rate"] + [
        f"{s},{r}" for s, r in zip(mr_samples, mr_rates)
    ]
    mr_filename = f"{uuid.uuid4().hex}_mapping_rates.csv"
    mr_path = mr_run_dir / mr_filename
    mr_path.write_text("\n".join(mr_csv_lines))

    mr_file = AttachedFile(
        workflow_run_id=run_rna1.id,
        original_filename="mapping_rates.csv",
        stored_path=str(mr_path),
        file_type="mapping_rates",
        description="STAR alignment mapping rates",
        parsed_config=json.dumps({"samples": mr_samples, "rates": mr_rates}),
    )
    db.session.add(mr_file)

    db.session.commit()

    # ── Summary ───────────────────────────────────────────────────────────────

    n_groups = ResearchGroup.query.count()
    n_researchers = Researcher.query.count()
    n_projects = Project.query.count()
    n_runs = WorkflowRun.query.count()
    n_samples = Sample.query.count()

    print(f"\nDemo database written to: {demo_db}")
    print(f"  Research groups : {n_groups}")
    print(f"  Researchers     : {n_researchers}")
    print(f"  Projects        : {n_projects}")
    print(f"  Workflow runs   : {n_runs}")
    print(f"  Samples         : {n_samples}")
