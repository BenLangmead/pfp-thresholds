#!/usr/bin/env python3
"""
Author: Ben Langmead (with assistance from Codex, Cursor)
Copyright 2026

Emit run-level LCP lists from a BWT and LCP array.

INPUT.bwt: 1 byte per BWT character (from pfp_lcp).
INPUT.lcp: 5-byte little-endian integers (THRBYTES=5, from pfp_lcp print_lcp()).
Optional INPUT.ssa: 5-byte little-endian (pos, sa) per run (from pfp_lcp); if given, the sa column uses actual SA values.
"""

from __future__ import annotations

import argparse
import sys
from contextlib import nullcontext

THRBYTES = 5
BWTBYTES = 5
SSABYTES = 5


def read_fixed_value(handle, byte_count: int, label: str) -> int | None:
    chunk = handle.read(byte_count)
    if not chunk:
        return None
    if len(chunk) != byte_count:
        raise ValueError(f"Trailing {label} bytes ({len(chunk)}) in input")
    return int.from_bytes(chunk, "little")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scan a BWT and LCP array and emit one TSV line per BWT run with its LCP list."
        )
    )
    parser.add_argument("bwt", help="Path to INPUT.bwt (1 byte per BWT character)")
    parser.add_argument("lcp", help="Path to INPUT.lcp (5-byte little-endian integers)")
    parser.add_argument(
        "--rle",
        action="store_true",
        help="Read a run-length encoded BWT heads file and lengths via --rle-lengths",
    )
    parser.add_argument(
        "--rle-lengths",
        help="Path to INPUT.bwt.len (5-byte little-endian run lengths)",
    )
    parser.add_argument(
        "--sa",
        metavar="FILE",
        help="Path to INPUT.ssa (5-byte LE pos, 5-byte LE sa per run from pfp_lcp); if set, sa column uses actual SA values",
    )
    args = parser.parse_args()

    if args.rle or args.rle_lengths:
        if not args.rle_lengths:
            raise ValueError("--rle-lengths is required when using --rle")

        run_id = 0
        run_offset = 0
        index = 0

        with (
            open(args.bwt, "rb") as heads_handle,
            open(args.rle_lengths, "rb") as len_handle,
            open(args.lcp, "rb") as lcp_handle,
            (open(args.sa, "rb") if args.sa else nullcontext(None)) as sa_handle,
        ):
            sys.stdout.write("id\toff\tlen\tc\tsa\tlcp\n")
            while True:
                head_byte = heads_handle.read(1)
                if not head_byte:
                    break
                run_length = read_fixed_value(len_handle, BWTBYTES, "BWT length")
                if run_length is None:
                    raise ValueError("BWT lengths shorter than BWT heads")

                if sa_handle is not None:
                    _ = read_fixed_value(sa_handle, SSABYTES, "SA pos")
                    sa_first = read_fixed_value(sa_handle, SSABYTES, "SA")
                    if sa_first is None:
                        raise ValueError("SA file shorter than runs")
                else:
                    sa_first = index
                lcp_list: list[int] = []
                for _ in range(run_length):
                    lcp_val = read_fixed_value(lcp_handle, THRBYTES, "LCP")
                    if lcp_val is None:
                        raise ValueError("LCP array shorter than BWT")
                    if index == 0:
                        lcp_list.append(0)  # first LCP in first run is always 0
                    else:
                        lcp_list.append(lcp_val)
                    index += 1

                lcp_str = ",".join(str(val) for val in lcp_list)
                sys.stdout.write(
                    f"{run_id}\t{run_offset}\t{run_length}\t{chr(head_byte[0])}\t{sa_first}\t{lcp_str}\n"
                )
                run_id += 1
                run_offset += run_length

            extra = lcp_handle.read(1)
            if extra:
                pass
    else:
        run_id = 0
        run_offset = 0
        run_char: int | None = None
        run_length = 0
        run_start_index = 0
        lcp_list: list[int] = []

        index = 0
        with (
            open(args.bwt, "rb") as bwt_handle,
            open(args.lcp, "rb") as lcp_handle,
            (open(args.sa, "rb") if args.sa else nullcontext(None)) as sa_handle,
        ):
            sys.stdout.write("id\toff\tlen\tc\tsa\tlcp\n")
            while True:
                bwt_byte = bwt_handle.read(1)
                if not bwt_byte:
                    break
                lcp_val = read_fixed_value(lcp_handle, THRBYTES, "LCP")
                if lcp_val is None:
                    raise ValueError("LCP array shorter than BWT")

                bwt_val = bwt_byte[0]
                if run_char is None or bwt_val != run_char:
                    if run_char is not None:
                        if sa_handle is not None:
                            _ = read_fixed_value(sa_handle, SSABYTES, "SA pos")
                            sa_val = read_fixed_value(sa_handle, SSABYTES, "SA")
                            if sa_val is None:
                                raise ValueError("SA file shorter than runs")
                            run_start_index = sa_val
                        lcp_str = ",".join(str(val) for val in lcp_list)
                        sys.stdout.write(
                            f"{run_id}\t{run_offset}\t{run_length}\t{chr(run_char)}\t{run_start_index}\t{lcp_str}\n"
                        )
                        run_id += 1
                        run_offset += run_length

                    run_char = bwt_val
                    run_length = 1
                    run_start_index = index
                    lcp_list = []
                    if index == 0:
                        lcp_list.append(0)  # first LCP in first run is always 0
                    else:
                        lcp_list.append(lcp_val)
                else:
                    run_length += 1
                    lcp_list.append(lcp_val)

                index += 1

            if run_char is not None:
                if sa_handle is not None:
                    _ = read_fixed_value(sa_handle, SSABYTES, "SA pos")
                    sa_val = read_fixed_value(sa_handle, SSABYTES, "SA")
                    if sa_val is None:
                        raise ValueError("SA file shorter than runs")
                    run_start_index = sa_val
                lcp_str = ",".join(str(val) for val in lcp_list)
                sys.stdout.write(
                    f"{run_id}\t{run_offset}\t{run_length}\t{chr(run_char)}\t{run_start_index}\t{lcp_str}\n"
                )

            extra = lcp_handle.read(1)
            if extra:
                # Consume remaining bytes but ignore them.
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
