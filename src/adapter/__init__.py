"""Adapter layer: turn MIDI corpora into FIMI transaction sets and engine calls.

Upstream engines (AnyFIM / TensorFIM) are READ-ONLY during review.
All adaptation — including the G3.5 dense item-ID remapping — lives here.
See docs/adapter_design.md for the full contract.
"""
from .fimi import read_fimi, write_fimi, item_counts, dense_remap
from .engines import (
    EXE,
    run_tensorfim,
    run_anyfim_gt,
    run_anyfim_anytime,
    parse_results,
    sha256_file,
)

__all__ = [
    "read_fimi", "write_fimi", "item_counts", "dense_remap",
    "EXE", "run_tensorfim", "run_anyfim_gt", "run_anyfim_anytime",
    "parse_results", "sha256_file",
]
