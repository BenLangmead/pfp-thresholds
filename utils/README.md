# Utils

## `bwt_run_lcps.py`

Emit one TSV line per BWT run with its associated LCP list.

### Inputs

* `INPUT.bwt`: 1 byte per BWT character, as produced by `pfp_lcp` in
  `include/pfp/pfp_lcp.hpp`.
* `INPUT.lcp`: 5-byte little-endian integers, emitted by
  `pfp_lcp::print_lcp()` using `THRBYTES` (5 bytes per entry).

If you have a run-length encoded BWT (e.g., from `pfp_thresholds -r`), you will
also have:

* `INPUT.bwt.heads`: 1 byte per BWT run head.
* `INPUT.bwt.len`: 5-byte little-endian run lengths (`BWTBYTES = 5`).

### From FASTA to TSV (end-to-end)

1. Build the project (from the repo root):

   ```console
   mkdir -p build
   cd build && cmake .. && make
   ```

2. Run the `pfp_lcp` pipeline on your FASTA file (the `-f` flag enables FASTA input):

   ```console
   pipeline/pfp_lcp -f INPUT.fa
   ```

   This produces `INPUT.fa.bwt` and `INPUT.fa.lcp` in the same directory as the
   input, using the 5-byte LCP encoding described above.

3. Convert the BWT/LCP outputs to run-level TSV:

   ```console
   ./utils/bwt_run_lcps.py INPUT.fa.bwt INPUT.fa.lcp > runs.tsv
   ```

### Usage

```console
./utils/bwt_run_lcps.py INPUT.bwt INPUT.lcp > runs.tsv
```

For a run-length encoded BWT:

```console
./utils/bwt_run_lcps.py INPUT.bwt.heads INPUT.lcp --rle --rle-lengths INPUT.bwt.len > runs.tsv
```

Each output line is:

```
run_id\trun_offset\trun_length\trun_char\tcomma_separated_LCPs
```

The LCP list is ordered in suffix array order:

* If the run head is at SA/BWT index `i > 0`, the first LCP is `LCP[i]`
  (between the tail of the previous run and the head of this run).
* Subsequent entries are `LCP[i+1]` through `LCP[i+run_length-1]` for
  consecutive suffixes inside the run.
