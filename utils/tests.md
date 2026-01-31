# Test Report

## Commands Run

- `pytest -q utils/test_run_lcps_compare.py`
  - Result: 2 passed in 143.99s (0:02:23)

## TSV Output Similarity

The run-level TSV outputs produced by `utils/lcp.py` and `utils/bwt_run_lcps.py`
were identical for the FASTA inputs exercised by the test suite above.

## FASTA Inputs and Coarse Statistics

Lengths are the total number of A/C/G/T bases after cleaning (line breaks
concatenated). Run counts are the number of BWT runs reported by
`utils/lcp.py --no-truncate-lcp` on the cleaned input.

- `data/minishred1_20_002.fa`: length 403,691; BWT runs 14,880
- `data/yeast.fasta`: length 12,156,306; BWT runs 8,380,587
