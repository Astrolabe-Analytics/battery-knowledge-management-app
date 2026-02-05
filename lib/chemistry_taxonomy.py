"""
Chemistry taxonomy and normalization utilities.

Provides canonical chemistry names with variant mappings for consistent
tagging across the paper database. Special handling for NMC variants
to enable both specific and parent-level filtering.
"""

# Canonical taxonomy with parent-child relationships
CHEMISTRY_TAXONOMY = {
    # Cathode materials
    "LFP": {
        "canonical_name": "LFP",
        "variants": [
            "lfp", "lifepo4", "lifePO4", "LiFePO4", "LiFePO 4",
            "lithium iron phosphate", "lithium-iron-phosphate",
            "iron phosphate"
        ],
        "parent": None,
        "full_name": "Lithium Iron Phosphate"
    },
    "NMC": {
        "canonical_name": "NMC",
        "variants": [
            "nmc", "nmc111", "li(nimn co)o2", "li(nimn)co2",
            "nickel manganese cobalt", "nickel-manganese-cobalt",
            "LiNiMnCoO2"
        ],
        "parent": None,
        "full_name": "Nickel Manganese Cobalt"
    },
    "NMC532": {
        "canonical_name": "NMC532",
        "variants": ["nmc532", "nmc 532", "532"],
        "parent": "NMC",
        "full_name": "NMC532"
    },
    "NMC622": {
        "canonical_name": "NMC622",
        "variants": ["nmc622", "nmc 622", "622"],
        "parent": "NMC",
        "full_name": "NMC622"
    },
    "NMC640": {
        "canonical_name": "NMC640",
        "variants": ["nmc640", "nmc 640", "640"],
        "parent": "NMC",
        "full_name": "NMC640"
    },
    "NMC811": {
        "canonical_name": "NMC811",
        "variants": ["nmc811", "nmc 811", "811"],
        "parent": "NMC",
        "full_name": "NMC811"
    },
    "NMC333": {
        "canonical_name": "NMC333",
        "variants": ["nmc333", "nmc 333", "333"],
        "parent": "NMC",
        "full_name": "NMC333"
    },
    "NCA": {
        "canonical_name": "NCA",
        "variants": [
            "nca", "linicaloalo2", "LiNiCoAlO2", "nickel cobalt aluminum",
            "nickel-cobalt-aluminum"
        ],
        "parent": None,
        "full_name": "Nickel Cobalt Aluminum"
    },
    "LCO": {
        "canonical_name": "LCO",
        "variants": [
            "lco", "licoo2", "LiCoO2", "lithium cobalt oxide",
            "cobalt oxide"
        ],
        "parent": None,
        "full_name": "Lithium Cobalt Oxide"
    },
    "LMO": {
        "canonical_name": "LMO",
        "variants": [
            "lmo", "limn2o4", "LiMn2O4", "lithium manganese oxide",
            "manganese oxide"
        ],
        "parent": None,
        "full_name": "Lithium Manganese Oxide"
    },

    # Anode materials
    "GRAPHITE": {
        "canonical_name": "GRAPHITE",
        "variants": ["graphite", "graphite anode", "graphitic carbon"],
        "parent": None,
        "full_name": "Graphite"
    },
    "SILICON": {
        "canonical_name": "SILICON",
        "variants": [
            "silicon", "si", "silicon anode", "si anode", "si/c",
            "silicon-carbon", "si-c"
        ],
        "parent": None,
        "full_name": "Silicon"
    },
    "LTO": {
        "canonical_name": "LTO",
        "variants": [
            "lto", "li4ti5o12", "Li4Ti5O12", "lithium titanate",
            "lithium-titanate"
        ],
        "parent": None,
        "full_name": "Lithium Titanate"
    },
    "HARD CARBON": {
        "canonical_name": "HARD CARBON",
        "variants": ["hard carbon", "hard-carbon", "hc"],
        "parent": None,
        "full_name": "Hard Carbon"
    },

    # General chemistry types
    "LI-ION": {
        "canonical_name": "LI-ION",
        "variants": [
            "li-ion", "lithium-ion", "lithium ion", "li ion",
            "lib", "libs"
        ],
        "parent": None,
        "full_name": "Lithium-ion"
    },
}

# Build reverse lookup for fast normalization: variant -> canonical
# Use lowercase for case-insensitive matching
VARIANT_TO_CANONICAL = {}
for canonical, data in CHEMISTRY_TAXONOMY.items():
    # Add canonical name itself
    VARIANT_TO_CANONICAL[canonical.lower()] = canonical
    # Add all variants
    for variant in data["variants"]:
        VARIANT_TO_CANONICAL[variant.lower()] = canonical


def normalize_chemistries(raw_chemistries: list[str]) -> list[str]:
    """
    Normalize a list of chemistry strings to canonical names.

    For NMC variants: returns BOTH the specific variant AND parent "NMC".
    Example: ["nmc811", "lfp"] -> ["LFP", "NMC", "NMC811"]

    Unknown chemistries are preserved as uppercase (graceful degradation).

    Args:
        raw_chemistries: List of chemistry strings from Claude or user input

    Returns:
        Deduplicated list of canonical chemistry names, sorted alphabetically

    Examples:
        >>> normalize_chemistries(["LiFePO4", "NMC811"])
        ['LFP', 'NMC', 'NMC811']

        >>> normalize_chemistries(["lfp", "LFP", "lithium iron phosphate"])
        ['LFP']

        >>> normalize_chemistries(["LNMO"])  # Unknown chemistry
        ['LNMO']
    """
    normalized = set()

    for raw in raw_chemistries:
        if not raw or not raw.strip():
            continue

        # Clean and normalize to lowercase for matching
        cleaned = raw.strip().lower()

        # Try exact match in taxonomy
        if cleaned in VARIANT_TO_CANONICAL:
            canonical = VARIANT_TO_CANONICAL[cleaned]
            normalized.add(canonical)

            # Add parent if exists (for NMC variants)
            taxonomy_entry = CHEMISTRY_TAXONOMY[canonical]
            if taxonomy_entry["parent"]:
                normalized.add(taxonomy_entry["parent"])
        else:
            # Unknown chemistry - preserve as uppercase
            # This allows for graceful handling of new chemistries
            normalized.add(raw.strip().upper())

    return sorted(list(normalized))


def get_chemistry_display_name(canonical: str) -> str:
    """
    Get full display name for a canonical chemistry.

    Args:
        canonical: Canonical chemistry name (e.g., "LFP", "NMC811")

    Returns:
        Full display name (e.g., "Lithium Iron Phosphate", "NMC811")
    """
    if canonical in CHEMISTRY_TAXONOMY:
        return CHEMISTRY_TAXONOMY[canonical]["full_name"]
    return canonical


def is_parent_chemistry(chemistry: str) -> bool:
    """
    Check if a chemistry has child variants (like NMC).

    Args:
        chemistry: Canonical chemistry name

    Returns:
        True if this chemistry has child variants
    """
    if chemistry not in CHEMISTRY_TAXONOMY:
        return False

    # Check if any other chemistry has this as parent
    for data in CHEMISTRY_TAXONOMY.values():
        if data["parent"] == chemistry:
            return True
    return False


def get_child_chemistries(parent: str) -> list[str]:
    """
    Get all child variants of a parent chemistry.

    Args:
        parent: Parent chemistry name (e.g., "NMC")

    Returns:
        Sorted list of child chemistry names (e.g., ["NMC532", "NMC622", "NMC811"])
    """
    children = []
    for canonical, data in CHEMISTRY_TAXONOMY.items():
        if data["parent"] == parent:
            children.append(canonical)
    return sorted(children)
