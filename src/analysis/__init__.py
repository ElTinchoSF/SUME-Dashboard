"""
Analysis package for SUME Dashboard.

Provides circuit reconstruction, frequency analysis, statistics computation,
and report generation for administrative process mining.
"""

from src.analysis.circuits import (
    compute_circuit_frequencies,
    identify_modal_circuits,
    reconstruct_circuit,
)
from src.analysis.reports import main as reports_main
from src.analysis.statistics import (
    compute_concept_distribution,
    compute_dependency_traffic,
    compute_permanence_times,
    compute_step_statistics,
    detect_outliers,
)

__all__ = [
    # Circuits
    "reconstruct_circuit",
    "compute_circuit_frequencies",
    "identify_modal_circuits",
    # Statistics
    "compute_step_statistics",
    "compute_permanence_times",
    "detect_outliers",
    "compute_dependency_traffic",
    "compute_concept_distribution",
    # Reports
    "reports_main",
]

__version__ = "1.0.0"
