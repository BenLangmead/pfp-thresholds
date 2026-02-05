#!/usr/bin/env python3

"""
Author: Ben Langmead (with assistance from Codex, Cursor)
Copyright 2026

Compare run-level LCP TSV outputs: pure Python lcp.py (pydivsufsort) vs the PFP
pipeline (pfp_lcp binary + bwt_run_lcps.py). Cleans FASTA, runs newscanNT.x and
pfp_lcp, then asserts the two TSV outputs are byte-identical after normalizing
line endings and the terminator in the c column (\\x00 and # -> $). Parsed
comparison includes the SA column and full LCP lists; no normalization that
would hide differences (e.g. missing first LCP value in the first run) is applied.
"""

from __future__ import annotations

import argparse
import collections
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
BIGBWT_PARSER = ROOT / "build" / "_deps" / "bigbwt-build" / "newscanNT.x"
PFP_LCP_BINARY = ROOT / "build" / "test" / "src" / "pfp_lcp"
PFP_LCP_SCRIPT = ROOT / "build" / "pfp_lcp"
LCP_PY = ROOT / "utils" / "lcp.py"
BWT_RUN_LCPS = ROOT / "utils" / "bwt_run_lcps.py"


def run_cmd(args: list[str], cwd: Path | None = None) -> str:
    print("Running:", " ".join(args), file=sys.stderr)
    r = subprocess.run(args, cwd=str(cwd) if cwd else None, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(args)}\nstdout: {r.stdout}\nstderr: {r.stderr}")
    return r.stdout


def parse_lcp_list(raw: str) -> list[int]:
    return [int(x) for x in raw.split(",")] if raw else []


# Parsed run: (run_id, run_offset, run_len, run_char, sa, lcp_list)
RunTuple = tuple[int, int, int, str, int, list[int]]


def parse_lcp_py_tsv(raw: str) -> list[RunTuple]:
    lines = [l for l in raw.splitlines() if l.strip()]
    if not lines or lines[0].split("\t") != ["id", "off", "len", "c", "sa", "lcp"]:
        return []
    runs = []
    for line in lines[1:]:
        parts = line.split("\t")
        # id, off, len, c, sa, lcp (column order matches RunTuple)
        run_id = int(parts[0])
        run_offset = int(parts[1])
        run_len = int(parts[2])
        run_char = parts[3]
        sa = int(parts[4])
        lcp_raw = parts[5]
        runs.append((run_id, run_offset, run_len, run_char, sa, parse_lcp_list(lcp_raw)))
    return runs


def parse_bwt_run_tsv(raw: str) -> list[RunTuple]:
    runs = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if parts[0] == "id":
            continue  # skip header line
        # id, off, len, c, sa, lcp (6 columns, matches RunTuple order)
        run_id = int(parts[0])
        run_offset = int(parts[1])
        run_len = int(parts[2])
        run_char = parts[3]
        sa = int(parts[4]) if len(parts) > 5 else run_offset  # fallback when no sa column
        lcp_raw = parts[5] if len(parts) > 5 else parts[4]
        runs.append((run_id, run_offset, run_len, run_char, sa, parse_lcp_list(lcp_raw)))
    return runs


def normalize_line_endings(s: str) -> str:
    """Normalize to Unix newlines and strip trailing whitespace."""
    return s.replace("\r\n", "\n").replace("\r", "\n").strip()


def normalize_tsv_for_byte_compare(s: str) -> str:
    """Normalize so byte comparison ignores terminator representation (c column: # and \\x00 -> $)."""
    s = normalize_line_endings(s)
    # Only normalize the run-char column (between 3rd and 4th tab): \t#\t and \t\x00\t -> \t$\t
    s = s.replace("\t#\t", "\t$\t").replace("\t\x00\t", "\t$\t")
    return s


def normalize_run_char(c: str) -> str:
    return "$" if c in {"\x00", "#"} else c


def normalize_runs(runs: list[RunTuple]) -> list[RunTuple]:
    """Normalize only run_char (terminator). No change to LCP lists so missing first 0 fails."""
    return [
        (run_id, run_offset, run_len, normalize_run_char(run_char), sa, lcp_list)
        for run_id, run_offset, run_len, run_char, sa, lcp_list in runs
    ]


def summarize(runs: list) -> str:
    lcp_vals = [v for _, _, _, _, _, lcp in runs for v in lcp]
    dist = sorted(collections.Counter(lcp_vals).items())[:10]
    return f"runs={len(runs)}, lcp_vals={len(lcp_vals)}, dist_head={dict(dist)}"


def clean_fasta(source: Path, dest: Path) -> bool:
    valid = set("ACGTacgt")
    has_invalid = False
    with source.open() as src, dest.open("w") as out:
        buf = []
        for line in src:
            if line.startswith(">"):
                if buf:
                    out.write("".join(buf) + "\n")
                    buf = []
                out.write(line.rstrip("\n") + "\n")
                continue
            s = "".join(c for c in line.strip() if not c.isspace())
            if s and any(c not in valid for c in s):
                has_invalid = True
            if s:
                buf.append(s)
        if buf:
            out.write("".join(buf) + "\n")
    return not has_invalid


def check_prerequisites() -> Path:
    """Resolve pfp_lcp executable. Exits with message if any required path is missing."""
    if not DATA_DIR.is_dir():
        print(f"Error: data directory not found: {DATA_DIR}", file=sys.stderr)
        print("  Create data/ and add .fa/.fasta files to compare.", file=sys.stderr)
        sys.exit(1)
    fastas = sorted(DATA_DIR.glob("*.fa")) + sorted(DATA_DIR.glob("*.fasta"))
    if not fastas:
        print(f"Error: no .fa or .fasta files in {DATA_DIR}", file=sys.stderr)
        sys.exit(1)
    if not BIGBWT_PARSER.is_file():
        print(f"Error: BigBWT parser not found: {BIGBWT_PARSER}", file=sys.stderr)
        print("  Build the project (e.g. cmake + make); newscanNT.x is provided by the bigbwt dependency.", file=sys.stderr)
        sys.exit(1)
    if PFP_LCP_BINARY.is_file():
        return PFP_LCP_BINARY
    if PFP_LCP_SCRIPT.is_file():
        return PFP_LCP_SCRIPT
    print("Error: pfp_lcp not found. Tried:", file=sys.stderr)
    print(f"  {PFP_LCP_BINARY}", file=sys.stderr)
    print(f"  {PFP_LCP_SCRIPT}", file=sys.stderr)
    print("  Build the project so that one of these exists.", file=sys.stderr)
    sys.exit(1)


def compare_one(fasta_path: Path, pfp_lcp_exe: Path, keep_dir: Path | None = None) -> bool:
    """Run comparison for one FASTA. Returns True if match or skipped (non-ACGT), False if mismatch."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        shutil.copyfile(fasta_path, tmp / fasta_path.name)
        clean_path = tmp / f"cleaned_{fasta_path.name}"
        if not clean_fasta(tmp / fasta_path.name, clean_path):
            print(f"  Skip {fasta_path.name}: contains non-ACGT characters")
            return True
        run_cmd([str(BIGBWT_PARSER), str(clean_path), "-w", "10", "-p", "100", "-s", "-f"])
        run_cmd([str(pfp_lcp_exe), str(clean_path), "-w", "10", "-f"])
        try:
            lcp_out = run_cmd([sys.executable, str(LCP_PY), "--fasta", str(clean_path), "--no-truncate-lcp"])
        except RuntimeError as e:
            if "only ACGT" in str(e):
                print(f"  Skip {fasta_path.name}: non-ACGT (lcp.py)")
                return True
            raise
        bwt_path = str(clean_path) + ".bwt"
        lcp_path = str(clean_path) + ".lcp"
        sa_path = str(clean_path) + ".ssa"
        pfp_args = [sys.executable, str(BWT_RUN_LCPS), bwt_path, lcp_path]
        if Path(sa_path).exists():
            pfp_args += ["--sa", sa_path]
        pfp_out = run_cmd(pfp_args)
    if keep_dir:
        keep_dir.mkdir(parents=True, exist_ok=True)
        stem = fasta_path.stem
        (keep_dir / f"{stem}_lcp.tsv").write_text(lcp_out)
        (keep_dir / f"{stem}_pfp.tsv").write_text(pfp_out)
    # Require byte-identical TSV output (after normalizing line endings and terminator in c column)
    lcp_norm = normalize_tsv_for_byte_compare(lcp_out)
    pfp_norm = normalize_tsv_for_byte_compare(pfp_out)
    if lcp_norm != pfp_norm:
        print(f"  FAIL {fasta_path.name}: TSV outputs are not byte-identical (after normalizing line endings)")
        if len(lcp_norm) != len(pfp_norm):
            print(f"    lcp.py length: {len(lcp_norm)}, pfp_lcp length: {len(pfp_norm)}")
        else:
            first_diff = next((i for i, (a, b) in enumerate(zip(lcp_norm, pfp_norm)) if a != b), None)
            if first_diff is not None:
                print(f"    First byte difference at position {first_diff}")
        return False

    lcp_runs = normalize_runs(parse_lcp_py_tsv(lcp_out))
    pfp_runs = normalize_runs(parse_bwt_run_tsv(pfp_out))
    if lcp_runs != pfp_runs:
        idx = next((i for i, p in enumerate(zip(lcp_runs, pfp_runs)) if p[0] != p[1]), None)
        print(f"  FAIL {fasta_path.name}: parsed runs differ" + (f" at run {idx}" if idx is not None else ""))
        print(f"    lcp.py: {summarize(lcp_runs)}")
        print(f"    pfp_lcp: {summarize(pfp_runs)}")
        return False
    return True


def main() -> None:
    p = argparse.ArgumentParser(description="Compare LCP TSV from lcp.py vs pfp_lcp + bwt_run_lcps.py")
    p.add_argument("--keep", type=Path, metavar="DIR", help="Write final .tsv outputs (lcp and pfp) into DIR")
    args = p.parse_args()
    pfp_exe = check_prerequisites()
    fastas = sorted(DATA_DIR.glob("*.fa")) + sorted(DATA_DIR.glob("*.fasta"))
    ok, fail = 0, 0
    for path in fastas:
        if compare_one(path, pfp_exe, keep_dir=args.keep):
            ok += 1
        else:
            fail += 1
    print(f"Result: {ok} passed/skipped, {fail} failed")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
