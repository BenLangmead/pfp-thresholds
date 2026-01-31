"""
Author: Ben Langmead (with assistance from Codex)
Copyright 2026

Compare run-level LCP TSV outputs from two constructions: the pure Python
`utils/lcp.py` path (pydivsufsort) and the PFP pipeline that produces BWT/LCP
via the `pfp_lcp` binary, then converts them with `utils/bwt_run_lcps.py`.
The test cleans FASTA inputs, runs `newscanNT.x` and `pfp_lcp`, and asserts
that the resulting TSVs are identical after normalization.
"""

from __future__ import annotations

import collections
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
BIGBWT_PARSER = ROOT / "build" / "_deps" / "bigbwt-build" / "newscanNT.x"
PFP_LCP_BINARY = ROOT / "build" / "test" / "src" / "pfp_lcp"
PFP_LCP_SCRIPT = ROOT / "build" / "pfp_lcp"


def run_command(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            f"  cmd: {' '.join(args)}\n"
            f"  cwd: {cwd}\n"
            f"  stdout:\n{result.stdout}\n"
            f"  stderr:\n{result.stderr}\n"
        )
    return result.stdout


def parse_lcp_list(raw: str) -> list[int]:
    if not raw:
        return []
    return [int(val) for val in raw.split(",")]


def parse_lcp_py_tsv(raw: str) -> list[tuple[int, int, int, str, list[int]]]:
    lines = [line for line in raw.splitlines() if line.strip()]
    if not lines:
        return []
    header = lines[0].split("\t")
    if header != ["id", "len", "off", "c", "lcp"]:
        raise ValueError(f"Unexpected header from lcp.py: {header}")
    runs = []
    for line in lines[1:]:
        run_id, run_len, run_offset, run_char, lcp_raw = line.split("\t")
        runs.append(
            (
                int(run_id),
                int(run_offset),
                int(run_len),
                run_char,
                parse_lcp_list(lcp_raw),
            )
        )
    return runs


def parse_bwt_run_tsv(raw: str) -> list[tuple[int, int, int, str, list[int]]]:
    lines = [line for line in raw.splitlines() if line.strip()]
    runs = []
    for line in lines:
        run_id, run_offset, run_len, run_char, lcp_raw = line.split("\t")
        lcp_list = parse_lcp_list(lcp_raw)
        runs.append(
            (
                int(run_id),
                int(run_offset),
                int(run_len),
                run_char,
                lcp_list,
            )
        )
    return runs


def normalize_run_char(run_char: str) -> str:
    if run_char in {"\x00", "#"}:
        return "$"
    return run_char


def normalize_runs(
    runs: list[tuple[int, int, int, str, list[int]]],
) -> list[tuple[int, int, int, str, list[int]]]:
    normalized = []
    for run_id, run_offset, run_len, run_char, lcp_list in runs:
        if run_id == 0 and len(lcp_list) == run_len - 1:
            lcp_list = [0] + lcp_list
        normalized.append(
            (
                run_id,
                run_offset,
                run_len,
                normalize_run_char(run_char),
                lcp_list,
            )
        )
    return normalized


def summarize_runs(runs: list[tuple[int, int, int, str, list[int]]]) -> dict[str, object]:
    run_count = len(runs)
    total_run_length = sum(run_len for _, _, run_len, _, _ in runs)
    lcp_values = [val for _, _, _, _, lcp_list in runs for val in lcp_list]
    return {
        "run_count": run_count,
        "total_run_length": total_run_length,
        "total_lcp_values": len(lcp_values),
        "lcp_distribution": collections.Counter(lcp_values),
    }


def format_summary(summary: dict[str, object]) -> str:
    lcp_dist = summary["lcp_distribution"]
    lcp_items = sorted(lcp_dist.items())[:10]
    lcp_preview = ", ".join(f"{val}:{count}" for val, count in lcp_items)
    return (
        f"runs={summary['run_count']}, "
        f"total_run_length={summary['total_run_length']}, "
        f"total_lcp_values={summary['total_lcp_values']}, "
        f"lcp_dist_head=[{lcp_preview}]"
    )


def fasta_inputs() -> list[Path]:
    inputs = list(DATA_DIR.glob("*.fa")) + list(DATA_DIR.glob("*.fasta"))
    return sorted(inputs)


def clean_fasta(source: Path, dest: Path) -> bool:
    valid = set("ACGTacgt")
    has_non_acgt = False
    with source.open() as src, dest.open("w") as out:
        seq_buffer: list[str] = []
        for line in src:
            if line.startswith(">"):
                if seq_buffer:
                    seq = "".join(seq_buffer)
                    out.write(seq + "\n")
                    seq_buffer = []
                out.write(line.rstrip("\n") + "\n")
                continue
            clean = "".join(ch for ch in line.strip() if not ch.isspace())
            if clean:
                for ch in clean:
                    if ch not in valid:
                        has_non_acgt = True
                        break
                seq_buffer.append(clean)
        if seq_buffer:
            out.write("".join(seq_buffer) + "\n")
    return not has_non_acgt



@pytest.mark.parametrize("fasta_path", fasta_inputs(), ids=lambda p: p.name)
def test_run_lcp_tsvs_match(fasta_path: Path) -> None:
    if not BIGBWT_PARSER.exists():
        pytest.skip(f"Missing bigbwt parser: {BIGBWT_PARSER}")

    if PFP_LCP_BINARY.exists():
        pfp_lcp_exe = PFP_LCP_BINARY
    elif PFP_LCP_SCRIPT.exists():
        pfp_lcp_exe = PFP_LCP_SCRIPT
    else:
        pytest.skip("Missing pfp_lcp binary/script in build outputs")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        tmp_fasta = tmp_dir / fasta_path.name
        shutil.copyfile(fasta_path, tmp_fasta)
        clean_fasta_path = tmp_dir / f"cleaned_{fasta_path.name}"
        is_acgt = clean_fasta(tmp_fasta, clean_fasta_path)
        if not is_acgt:
            pytest.skip(f"Non-ACGT characters in {fasta_path.name}")

        run_command(
            [
                str(BIGBWT_PARSER),
                str(clean_fasta_path),
                "-w",
                "10",
                "-p",
                "100",
                "-s",
                "-f",
            ]
        )

        run_command([str(pfp_lcp_exe), str(clean_fasta_path), "-w", "10", "-f"])

        try:
            lcp_py_output = run_command(
                [
                    sys.executable,
                    str(ROOT / "utils" / "lcp.py"),
                    "--fasta",
                    str(clean_fasta_path),
                    "--no-truncate-lcp",
                ]
            )
        except RuntimeError as exc:
            if "only ACGT" in str(exc):
                pytest.skip(f"Non-ACGT characters in {fasta_path.name}")
            raise
        pfp_output = run_command(
            [
                sys.executable,
                str(ROOT / "utils" / "bwt_run_lcps.py"),
                str(clean_fasta_path) + ".bwt",
                str(clean_fasta_path) + ".lcp",
            ]
        )

    lcp_runs = normalize_runs(parse_lcp_py_tsv(lcp_py_output))
    pfp_runs = normalize_runs(parse_bwt_run_tsv(pfp_output))

    if lcp_runs != pfp_runs:
        lcp_summary = summarize_runs(lcp_runs)
        pfp_summary = summarize_runs(pfp_runs)
        mismatch_index = next(
            (idx for idx, pair in enumerate(zip(lcp_runs, pfp_runs)) if pair[0] != pair[1]),
            None,
        )
        mismatch_detail = ""
        if mismatch_index is not None:
            mismatch_detail = (
                f"\nFirst mismatch at run {mismatch_index}:\n"
                f"  lcp.py: {lcp_runs[mismatch_index]}\n"
                f"  pfp_lcp: {pfp_runs[mismatch_index]}"
            )
        raise AssertionError(
            "Run-level TSVs do not match.\n"
            f"lcp.py summary: {format_summary(lcp_summary)}\n"
            f"pfp_lcp summary: {format_summary(pfp_summary)}"
            f"{mismatch_detail}"
        )
