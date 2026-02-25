"""Tests for lib/journal_normalizer.py — journal name normalization."""

from lib.journal_normalizer import (
    JOURNAL_MAPPING,
    normalize_journal_name,
    get_normalization_stats,
)


class TestNormalizeJournalName:
    """Tests for normalize_journal_name()."""

    # Exact canonical names should pass through unchanged
    def test_canonical_passthrough(self):
        assert normalize_journal_name("Journal of Power Sources") == "Journal of Power Sources"

    def test_canonical_passthrough_nature(self):
        assert normalize_journal_name("Nature Energy") == "Nature Energy"

    # Abbreviation lookups
    def test_abbreviation_power_sources(self):
        assert normalize_journal_name("j. power sources") == "Journal of Power Sources"

    def test_abbreviation_electrochem_soc(self):
        assert normalize_journal_name("j. electrochem. soc") == "Journal of The Electrochemical Society"

    def test_abbreviation_electrochim_acta(self):
        assert normalize_journal_name("electrochim. acta") == "Electrochimica Acta"

    def test_abbreviation_adv_energy_mater(self):
        assert normalize_journal_name("adv. energy mater") == "Advanced Energy Materials"

    def test_abbreviation_nat_commun(self):
        assert normalize_journal_name("nat. commun") == "Nature Communications"

    def test_abbreviation_acs_energy_lett(self):
        assert normalize_journal_name("acs energy lett") == "ACS Energy Letters"

    # Case insensitivity
    def test_case_insensitive_upper(self):
        assert normalize_journal_name("JOURNAL OF POWER SOURCES") == "Journal of Power Sources"

    def test_case_insensitive_mixed(self):
        assert normalize_journal_name("Journal Of Power Sources") == "Journal of Power Sources"

    # Extra whitespace / punctuation handling
    def test_extra_spaces(self):
        result = normalize_journal_name("j.  power   sources")
        # The function normalizes spaces, so this should match
        assert result == "Journal of Power Sources"

    def test_trailing_dots_stripped(self):
        result = normalize_journal_name("j. power sources.")
        assert result == "Journal of Power Sources"

    # Unknown journals pass through
    def test_unknown_journal_passthrough(self):
        assert normalize_journal_name("Obscure Battery Journal") == "Obscure Battery Journal"

    def test_unknown_preserves_original_case(self):
        assert normalize_journal_name("My Custom Journal") == "My Custom Journal"

    # Edge cases
    def test_empty_string(self):
        assert normalize_journal_name("") == ""

    def test_none_input(self):
        assert normalize_journal_name(None) is None

    def test_non_string_input(self):
        assert normalize_journal_name(123) == 123

    def test_whitespace_only(self):
        # After stripping, empty string won't match anything
        result = normalize_journal_name("   ")
        assert result == ""

    # Battery-specific journals
    def test_batteries(self):
        assert normalize_journal_name("batteries") == "Batteries"

    def test_batteries_basel(self):
        assert normalize_journal_name("batteries (basel)") == "Batteries"

    def test_energy_storage_materials(self):
        assert normalize_journal_name("energy stor. mater") == "Energy Storage Materials"

    def test_renewable_sustainable_energy_reviews(self):
        assert normalize_journal_name("renew. sustain. energy rev") == "Renewable and Sustainable Energy Reviews"

    # IEEE journals
    def test_ieee_access(self):
        assert normalize_journal_name("ieee access") == "IEEE Access"

    def test_ieee_trans_ind_electron(self):
        assert normalize_journal_name("ieee trans. ind. electron") == "IEEE Transactions on Industrial Electronics"

    # ACS journals
    def test_acs_appl_mater_interfaces(self):
        assert normalize_journal_name("acs appl. mater. interfaces") == "ACS Applied Materials & Interfaces"

    # Physical chemistry
    def test_pccp(self):
        assert normalize_journal_name("pccp") == "Physical Chemistry Chemical Physics"

    def test_j_phys_chem_c(self):
        assert normalize_journal_name("j. phys. chem. c") == "The Journal of Physical Chemistry C"


class TestGetNormalizationStats:
    """Tests for get_normalization_stats()."""

    def test_counts_normalizable_journals(self, sample_metadata):
        stats = get_normalization_stats(sample_metadata)
        assert stats["total_papers"] == 3
        assert stats["papers_with_journal"] == 3

    def test_identifies_changes(self, sample_metadata):
        stats = get_normalization_stats(sample_metadata)
        # "J. Electrochem. Soc." and "Adv. Energy Mater." should be normalized
        # "Applied Energy" is already canonical
        assert stats["papers_normalized"] >= 2

    def test_empty_papers(self):
        stats = get_normalization_stats({})
        assert stats["total_papers"] == 0
        assert stats["papers_with_journal"] == 0
        assert stats["papers_normalized"] == 0

    def test_papers_without_journals(self):
        papers = {
            "paper.pdf": {"title": "Test", "journal": ""},
        }
        stats = get_normalization_stats(papers)
        assert stats["papers_with_journal"] == 0


class TestJournalMappingConsistency:
    """Verify the journal mapping data is self-consistent."""

    def test_all_keys_are_lowercase(self):
        for key in JOURNAL_MAPPING:
            assert key == key.lower(), f"Key '{key}' is not lowercase"

    def test_all_values_are_nonempty(self):
        for key, value in JOURNAL_MAPPING.items():
            assert value.strip(), f"Empty value for key '{key}'"

    def test_no_duplicate_canonical_values_with_different_casing(self):
        # All canonical values for the same journal should be identical
        seen = {}
        for key, value in JOURNAL_MAPPING.items():
            lower_val = value.lower()
            if lower_val in seen:
                assert seen[lower_val] == value, (
                    f"Inconsistent casing: '{seen[lower_val]}' vs '{value}'"
                )
            seen[lower_val] = value
