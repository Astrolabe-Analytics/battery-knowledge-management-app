"""Shared fixtures for Astrolabe test suite."""

import sys
from pathlib import Path

import pytest

# Ensure lib/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_paper():
    """A realistic paper metadata dict matching the canonical schema."""
    return {
        "title": "State of Health Estimation for Lithium-Ion Batteries Using Machine Learning",
        "authors": ["Zhang, Wei", "Li, Xuan", "Chen, Yu"],
        "year": "2023",
        "journal": "Journal of Power Sources",
        "doi": "10.1016/j.jpowsour.2023.233456",
        "chemistries": ["NMC811", "LFP"],
        "topics": ["SOH", "Machine Learning"],
        "source_url": "https://doi.org/10.1016/j.jpowsour.2023.233456",
        "pdf_filename": None,
        "metadata_only": True,
    }


@pytest.fixture
def sample_metadata():
    """A small metadata dict (like metadata.json) with multiple papers."""
    return {
        "paper_001.pdf": {
            "title": "Capacity Fade in NMC811 Cathodes",
            "authors": ["Smith, John"],
            "year": "2022",
            "journal": "J. Electrochem. Soc.",
            "doi": "10.1149/1945-7111/ac1234",
            "chemistries": ["NMC811"],
            "topics": ["Degradation"],
        },
        "paper_002.pdf": {
            "title": "Silicon Anode Performance Under Fast Charging",
            "authors": ["Lee, Sarah", "Park, Min"],
            "year": "2023",
            "journal": "Adv. Energy Mater.",
            "doi": "10.1002/aenm.202301234",
            "chemistries": ["Silicon"],
            "topics": ["Fast Charging"],
        },
        "paper_003.pdf": {
            "title": "Review of Battery Management Systems",
            "authors": ["Wang, Tao"],
            "year": "2021",
            "journal": "Applied Energy",
            "doi": "",
            "chemistries": ["LI-ION"],
            "topics": ["BMS"],
        },
    }
