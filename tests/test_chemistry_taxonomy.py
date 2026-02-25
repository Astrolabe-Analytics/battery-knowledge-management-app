"""Tests for lib/chemistry_taxonomy.py — chemistry variant normalization."""

from lib.chemistry_taxonomy import (
    CHEMISTRY_TAXONOMY,
    VARIANT_TO_CANONICAL,
    normalize_chemistries,
    get_chemistry_display_name,
    is_parent_chemistry,
    get_child_chemistries,
)


class TestNormalizeChemistries:
    """Tests for normalize_chemistries()."""

    def test_canonical_names_passthrough(self):
        assert normalize_chemistries(["LFP"]) == ["LFP"]
        assert normalize_chemistries(["NMC"]) == ["NMC"]
        assert normalize_chemistries(["NCA"]) == ["NCA"]

    def test_variant_to_canonical(self):
        assert normalize_chemistries(["LiFePO4"]) == ["LFP"]
        assert normalize_chemistries(["lithium iron phosphate"]) == ["LFP"]
        assert normalize_chemistries(["lifepo4"]) == ["LFP"]

    def test_nmc_variant_adds_parent(self):
        result = normalize_chemistries(["nmc811"])
        assert "NMC811" in result
        assert "NMC" in result

    def test_nmc_variant_622(self):
        result = normalize_chemistries(["nmc622"])
        assert result == ["NMC", "NMC622"]

    def test_nmc_variant_532(self):
        result = normalize_chemistries(["nmc532"])
        assert result == ["NMC", "NMC532"]

    def test_multiple_chemistries_with_parent(self):
        result = normalize_chemistries(["LiFePO4", "NMC811"])
        assert result == ["LFP", "NMC", "NMC811"]

    def test_deduplication(self):
        result = normalize_chemistries(["lfp", "LFP", "lithium iron phosphate"])
        assert result == ["LFP"]

    def test_unknown_chemistry_uppercase(self):
        result = normalize_chemistries(["LNMO"])
        assert result == ["LNMO"]

    def test_unknown_preserves_as_uppercase(self):
        result = normalize_chemistries(["some new chemistry"])
        assert result == ["SOME NEW CHEMISTRY"]

    def test_empty_list(self):
        assert normalize_chemistries([]) == []

    def test_empty_strings_filtered(self):
        assert normalize_chemistries([""]) == []
        assert normalize_chemistries(["  "]) == []
        assert normalize_chemistries(["", "  ", ""]) == []

    def test_mixed_empty_and_valid(self):
        result = normalize_chemistries(["", "LFP", "  "])
        assert result == ["LFP"]

    def test_li_ion_variants(self):
        result = normalize_chemistries(["li-ion", "lithium-ion"])
        assert result == ["LI-ION"]

    def test_silicon_and_graphite(self):
        result = normalize_chemistries(["silicon", "graphite"])
        assert result == ["GRAPHITE", "SILICON"]

    def test_results_sorted_alphabetically(self):
        result = normalize_chemistries(["silicon", "lfp", "nmc811", "graphite"])
        assert result == sorted(result)

    def test_lto_variants(self):
        result = normalize_chemistries(["li4ti5o12"])
        assert result == ["LTO"]

    def test_hard_carbon(self):
        result = normalize_chemistries(["hard carbon"])
        assert result == ["HARD CARBON"]

    def test_lco_variants(self):
        result = normalize_chemistries(["LiCoO2"])
        assert result == ["LCO"]

    def test_nca_variants(self):
        result = normalize_chemistries(["nickel cobalt aluminum"])
        assert result == ["NCA"]

    def test_lmo_variants(self):
        result = normalize_chemistries(["LiMn2O4"])
        assert result == ["LMO"]


class TestGetChemistryDisplayName:
    """Tests for get_chemistry_display_name()."""

    def test_known_chemistry(self):
        assert get_chemistry_display_name("LFP") == "Lithium Iron Phosphate"

    def test_nmc_parent(self):
        assert get_chemistry_display_name("NMC") == "Nickel Manganese Cobalt"

    def test_nmc_variant(self):
        assert get_chemistry_display_name("NMC811") == "NMC811"

    def test_unknown_passthrough(self):
        assert get_chemistry_display_name("UNKNOWN") == "UNKNOWN"

    def test_silicon(self):
        assert get_chemistry_display_name("SILICON") == "Silicon"


class TestIsParentChemistry:
    """Tests for is_parent_chemistry()."""

    def test_nmc_is_parent(self):
        assert is_parent_chemistry("NMC") is True

    def test_lfp_not_parent(self):
        assert is_parent_chemistry("LFP") is False

    def test_nmc811_not_parent(self):
        assert is_parent_chemistry("NMC811") is False

    def test_unknown_not_parent(self):
        assert is_parent_chemistry("UNKNOWN") is False


class TestGetChildChemistries:
    """Tests for get_child_chemistries()."""

    def test_nmc_children(self):
        children = get_child_chemistries("NMC")
        assert "NMC532" in children
        assert "NMC622" in children
        assert "NMC811" in children
        assert "NMC333" in children
        assert "NMC640" in children

    def test_nmc_children_sorted(self):
        children = get_child_chemistries("NMC")
        assert children == sorted(children)

    def test_lfp_no_children(self):
        assert get_child_chemistries("LFP") == []

    def test_unknown_no_children(self):
        assert get_child_chemistries("UNKNOWN") == []


class TestTaxonomyConsistency:
    """Verify the taxonomy data structure is self-consistent."""

    def test_all_parents_exist_in_taxonomy(self):
        for canonical, data in CHEMISTRY_TAXONOMY.items():
            if data["parent"] is not None:
                assert data["parent"] in CHEMISTRY_TAXONOMY, (
                    f"{canonical} has parent {data['parent']} which is not in taxonomy"
                )

    def test_variant_lookup_covers_all_variants(self):
        for canonical, data in CHEMISTRY_TAXONOMY.items():
            for variant in data["variants"]:
                assert variant.lower() in VARIANT_TO_CANONICAL, (
                    f"Variant '{variant}' of {canonical} missing from VARIANT_TO_CANONICAL"
                )

    def test_canonical_names_in_lookup(self):
        for canonical in CHEMISTRY_TAXONOMY:
            assert canonical.lower() in VARIANT_TO_CANONICAL
