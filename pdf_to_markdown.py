#!/usr/bin/env python3
# ---------------------------------------------------------------------------
#  Install dependencies first (run this once in your terminal):
#
#      pip install --upgrade pymupdf4llm tqdm
#
# ---------------------------------------------------------------------------
"""
Batch-convert scientific-paper PDFs to Markdown, saving each .md beside its
source PDF (same folder, same name).

    Source :  E:\\publications\\noori_7\\manuscript\\2026-04-16\\pdf\\<sub>\\paper.pdf
    Output :  E:\\publications\\noori_7\\manuscript\\2026-04-16\\pdf\\<sub>\\paper.md

Engine: pymupdf4llm (built on PyMuPDF). It is fast, dependency-light, and
layout-aware: it recovers multi-column reading order, detects tables and
renders them as Markdown tables, and keeps heading structure. No GPU and no
model downloads are required, which makes it well suited to large batch jobs
of born-digital scientific papers.

Robustness features:
  * Writes each Markdown file directly beside its source PDF (same folder).
  * Per-file error isolation: one corrupt/encrypted PDF can never abort the run.
  * Resume-friendly: already-converted files are skipped unless OVERWRITE=True.
  * Optional multi-process parallelism for fast throughput on many files.
  * Flags empty results (image-only / scanned PDFs that yield no text).
  * Writes a full per-file report log and prints a summary at the end.
"""

from __future__ import annotations

import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pymupdf4llm
from tqdm import tqdm

# ============================== CONFIGURATION ==============================
PDF_ROOT = Path(r"E:\publications\noori_7\manuscript\2026-04-16\pdf")

OVERWRITE    = False  # False -> skip PDFs already converted (safe to re-run / resume)
RECURSIVE    = True   # True  -> walk every nested sub-folder under PDF_ROOT
WRITE_IMAGES = False  # True  -> also export figures as PNGs into an "images" subfolder
MAX_WORKERS  = max(1, (os.cpu_count() or 2) - 1)  # 1 = sequential; >1 = parallel
LOG_FILENAME = "_conversion_report.log"
# ==========================================================================


def _init_worker() -> None:
    """Runs once per process: silence MuPDF's native parser/OCR chatter so it
    cannot clutter the console or the tqdm bar. Recoverable warnings are
    dropped; genuine failures still surface as Python exceptions and get
    logged per file by convert_one()."""
    try:
        import pymupdf
        pymupdf.TOOLS.mupdf_display_errors(False)
        pymupdf.set_messages(path=os.devnull)  # os.devnull -> 'nul' on Windows
    except Exception:
        pass


def convert_one(pdf_path: Path, pdf_root: Path,
                overwrite: bool, write_images: bool) -> tuple[str, str, str]:
    """Convert a single PDF -> Markdown, writing the .md beside the source PDF.

    Returns (status, relative_path, message) where status is one of
    "ok" | "skipped" | "empty" | "error". Runs inside a worker process, so it
    is intentionally self-contained and picklable.
    """
    rel_str = str(pdf_path.relative_to(pdf_root))   # for tidy log/summary lines
    out_path = pdf_path.with_suffix(".md")          # same folder, same name

    try:
        if out_path.exists() and not overwrite:
            return "skipped", rel_str, "already converted"

        out_path.parent.mkdir(parents=True, exist_ok=True)

        md_text = pymupdf4llm.to_markdown(
            str(pdf_path),
            show_progress=False,            # we drive our own tqdm bar instead
            write_images=write_images,
            image_path=str(out_path.parent / "images") if write_images else "",
            table_strategy="lines_strict",  # robust for ruled scientific tables
        )

        out_path.write_text(md_text, encoding="utf-8")

        if not md_text.strip():
            return "empty", rel_str, "no extractable text (image-only / scanned?)"
        return "ok", rel_str, f"{len(md_text):,} chars"

    except Exception as exc:  # never let a single bad file kill the whole batch
        return "error", rel_str, f"{type(exc).__name__}: {exc}"


def record(status: str, rel_str: str, msg: str,
           counters: dict, failures: list, bar: tqdm) -> None:
    """Tally a result, log it, surface problems live, and advance the bar."""
    counters[status] = counters.get(status, 0) + 1
    if status == "ok":
        logging.info("OK    | %s | %s", rel_str, msg)
    elif status == "skipped":
        logging.info("SKIP  | %s | %s", rel_str, msg)
    elif status == "empty":
        logging.warning("EMPTY | %s | %s", rel_str, msg)
        bar.write(f"  [empty] {rel_str} -> {msg}")
    else:  # error
        logging.error("ERROR | %s | %s", rel_str, msg)
        failures.append((rel_str, msg))
        bar.write(f"  [ERROR] {rel_str} -> {msg}")
    bar.update(1)


def main() -> None:
    if not PDF_ROOT.exists():
        sys.exit(f"[abort] Source folder does not exist:\n  {PDF_ROOT}")

    # Case-insensitive .pdf match so .PDF / .Pdf are picked up too.
    walker = PDF_ROOT.rglob("*") if RECURSIVE else PDF_ROOT.glob("*/*")
    pdfs = sorted(p for p in walker if p.is_file() and p.suffix.lower() == ".pdf")
    if not pdfs:
        sys.exit(f"[abort] No PDF files found under:\n  {PDF_ROOT}")

    logging.basicConfig(
        filename=str(PDF_ROOT / LOG_FILENAME), filemode="w", level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    logging.info("Discovered %d PDF(s). workers=%s overwrite=%s (writing .md in place)",
                 len(pdfs), MAX_WORKERS, OVERWRITE)

    print(f"Found {len(pdfs)} PDF(s) under {PDF_ROOT}")
    print("Writing each .md next to its source PDF")
    print(f"workers={MAX_WORKERS}  overwrite={OVERWRITE}  write_images={WRITE_IMAGES}\n")

    counters: dict[str, int] = {}
    failures: list[tuple[str, str]] = []
    bar = tqdm(total=len(pdfs), desc="Converting", unit="pdf", dynamic_ncols=True)

    if MAX_WORKERS <= 1:
        _init_worker()
        for pdf in pdfs:
            status, rel_str, msg = convert_one(
                pdf, PDF_ROOT, OVERWRITE, WRITE_IMAGES)
            record(status, rel_str, msg, counters, failures, bar)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS,
                                 initializer=_init_worker) as pool:
            futures = [
                pool.submit(convert_one, pdf, PDF_ROOT,
                            OVERWRITE, WRITE_IMAGES)
                for pdf in pdfs
            ]
            for fut in as_completed(futures):
                status, rel_str, msg = fut.result()
                record(status, rel_str, msg, counters, failures, bar)

    bar.close()

    # ------------------------------ summary -------------------------------
    print("\n" + "=" * 62)
    print("  CONVERSION SUMMARY")
    print("=" * 62)
    print(f"  Converted : {counters.get('ok', 0)}")
    print(f"  Skipped   : {counters.get('skipped', 0)}  (already existed)")
    print(f"  Empty     : {counters.get('empty', 0)}  (no text extracted)")
    print(f"  Errors    : {counters.get('error', 0)}")
    if failures:
        print("\n  Files that failed:")
        for rel_str, msg in failures:
            print(f"    - {rel_str}: {msg}")
    print(f"\n  Full per-file report: {PDF_ROOT / LOG_FILENAME}")
    print("=" * 62)


if __name__ == "__main__":
    main()