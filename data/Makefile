# Build _lcp.tsv and _pfp.tsv from .fa / .fasta in this directory.
# Run from the repo root: make -C data
# Or from data/: make
#
# Prerequisites: project built (newscanNT.x, pfp_lcp), and Python utils available.
# Inputs should be ACGT-only FASTA (no N or other bases).

ROOT := ..
BUILD := $(ROOT)/build
UTILS := $(ROOT)/utils
BIGBWT := $(BUILD)/_deps/bigbwt-build/newscanNT.x
PFP_LCP := $(BUILD)/test/src/pfp_lcp
LCP_PY := $(UTILS)/lcp.py
BWT_RUN_LCPS := $(UTILS)/bwt_run_lcps.py

PYTHON ?= python3

# --- .fa ---
%_lcp.tsv: %.fa
	$(PYTHON) $(LCP_PY) --fasta $< --no-truncate-lcp > $@

%.fa.bwt %.fa.lcp %.fa.ssa: %.fa
	$(BIGBWT) $< -w 10 -p 100 -s -f
	$(PFP_LCP) $< -w 10 -f

%_pfp.tsv: %.fa.bwt %.fa.lcp %.fa.ssa
	$(PYTHON) $(BWT_RUN_LCPS) $< $(word 2,$^) --sa $(word 3,$^) > $@

# --- .fasta ---
%_lcp.tsv: %.fasta
	$(PYTHON) $(LCP_PY) --fasta $< --no-truncate-lcp > $@

%.fasta.bwt %.fasta.lcp %.fasta.ssa: %.fasta
	$(BIGBWT) $< -w 10 -p 100 -s -f
	$(PFP_LCP) $< -w 10 -f

%_pfp.tsv: %.fasta.bwt %.fasta.lcp %.fasta.ssa
	$(PYTHON) $(BWT_RUN_LCPS) $< $(word 2,$^) --sa $(word 3,$^) > $@

# Keep pipeline outputs (.bwt, .lcp, .ssa) so they are not removed as intermediates
.PRECIOUS: %.fa.bwt %.fa.lcp %.fa.ssa %.fasta.bwt %.fasta.lcp %.fasta.ssa

.PHONY: all clean
all: $(patsubst %.fa,%_lcp.tsv,$(wildcard *.fa)) $(patsubst %.fa,%_pfp.tsv,$(wildcard *.fa)) \
     $(patsubst %.fasta,%_lcp.tsv,$(wildcard *.fasta)) $(patsubst %.fasta,%_pfp.tsv,$(wildcard *.fasta))

clean:
	rm -f *.bwt *.lcp *.ssa *_lcp.tsv *_pfp.tsv
