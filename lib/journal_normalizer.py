"""
Journal name normalization for battery research papers.

Maps various journal name formats (abbreviations, variations) to canonical full names.
"""

import re
from typing import Optional


# Comprehensive mapping of journal name variations to canonical full names
JOURNAL_MAPPING = {
    # Journal of Power Sources
    'journal of power sources': 'Journal of Power Sources',
    'j power sources': 'Journal of Power Sources',
    'j. power sources': 'Journal of Power Sources',
    'j power source': 'Journal of Power Sources',
    'j. power source': 'Journal of Power Sources',
    'jpowsour': 'Journal of Power Sources',

    # Journal of the Electrochemical Society
    'journal of the electrochemical society': 'Journal of The Electrochemical Society',
    'j electrochem soc': 'Journal of The Electrochemical Society',
    'j. electrochem. soc': 'Journal of The Electrochemical Society',
    'j electrochem. soc': 'Journal of The Electrochemical Society',
    'jes': 'Journal of The Electrochemical Society',
    'jelectrochemsoc': 'Journal of The Electrochemical Society',

    # Electrochimica Acta
    'electrochimica acta': 'Electrochimica Acta',
    'electrochim acta': 'Electrochimica Acta',
    'electrochim. acta': 'Electrochimica Acta',

    # Energy Storage Materials
    'energy storage materials': 'Energy Storage Materials',
    'energy stor mater': 'Energy Storage Materials',
    'energy stor. mater': 'Energy Storage Materials',
    'energ storage mater': 'Energy Storage Materials',

    # Journal of Energy Storage
    'journal of energy storage': 'Journal of Energy Storage',
    'j energy storage': 'Journal of Energy Storage',
    'j. energy storage': 'Journal of Energy Storage',
    'j energ storage': 'Journal of Energy Storage',

    # ACS Energy Letters
    'acs energy letters': 'ACS Energy Letters',
    'acs energy lett': 'ACS Energy Letters',
    'acs energy lett.': 'ACS Energy Letters',

    # Advanced Energy Materials
    'advanced energy materials': 'Advanced Energy Materials',
    'adv energy mater': 'Advanced Energy Materials',
    'adv. energy mater': 'Advanced Energy Materials',
    'adv energy mater.': 'Advanced Energy Materials',

    # Advanced Materials
    'advanced materials': 'Advanced Materials',
    'adv mater': 'Advanced Materials',
    'adv. mater': 'Advanced Materials',
    'adv mater.': 'Advanced Materials',

    # Nature Energy
    'nature energy': 'Nature Energy',
    'nat energy': 'Nature Energy',
    'nat. energy': 'Nature Energy',

    # Nature Communications
    'nature communications': 'Nature Communications',
    'nat commun': 'Nature Communications',
    'nat. commun': 'Nature Communications',
    'nat commun.': 'Nature Communications',

    # Applied Energy
    'applied energy': 'Applied Energy',
    'appl energy': 'Applied Energy',
    'appl. energy': 'Applied Energy',

    # Energy
    'energy': 'Energy',

    # Joule
    'joule': 'Joule',

    # Batteries
    'batteries': 'Batteries',
    'batteries (basel)': 'Batteries',

    # Batteries & Supercaps
    'batteries & supercaps': 'Batteries & Supercaps',
    'batteries and supercaps': 'Batteries & Supercaps',
    'batt supercaps': 'Batteries & Supercaps',

    # Cell Reports Physical Science
    'cell reports physical science': 'Cell Reports Physical Science',
    'cell rep phys sci': 'Cell Reports Physical Science',
    'cell reports phys science': 'Cell Reports Physical Science',

    # Renewable Energy
    'renewable energy': 'Renewable Energy',
    'renew energy': 'Renewable Energy',
    'renew. energy': 'Renewable Energy',

    # Journal of Cleaner Production
    'journal of cleaner production': 'Journal of Cleaner Production',
    'j clean prod': 'Journal of Cleaner Production',
    'j. clean. prod': 'Journal of Cleaner Production',
    'j cleaner prod': 'Journal of Cleaner Production',

    # Energy and AI
    'energy and ai': 'Energy and AI',
    'energy and artificial intelligence': 'Energy and AI',

    # eTransportation
    'etransportation': 'eTransportation',
    'e-transportation': 'eTransportation',

    # IEEE Transactions on Industrial Electronics
    'ieee transactions on industrial electronics': 'IEEE Transactions on Industrial Electronics',
    'ieee trans ind electron': 'IEEE Transactions on Industrial Electronics',
    'ieee trans. ind. electron': 'IEEE Transactions on Industrial Electronics',

    # IEEE Transactions on Transportation Electrification
    'ieee transactions on transportation electrification': 'IEEE Transactions on Transportation Electrification',
    'ieee trans transport electrif': 'IEEE Transactions on Transportation Electrification',
    'ieee trans. transp. electrif': 'IEEE Transactions on Transportation Electrification',

    # IEEE Access
    'ieee access': 'IEEE Access',

    # Journal of Energy Chemistry
    'journal of energy chemistry': 'Journal of Energy Chemistry',
    'j energy chem': 'Journal of Energy Chemistry',
    'j. energy chem': 'Journal of Energy Chemistry',

    # Energy Reviews
    'energy reviews': 'Energy Reviews',

    # Renewable and Sustainable Energy Reviews
    'renewable and sustainable energy reviews': 'Renewable and Sustainable Energy Reviews',
    'renew sustain energy rev': 'Renewable and Sustainable Energy Reviews',
    'renew. sustain. energy rev': 'Renewable and Sustainable Energy Reviews',

    # ChemSusChem
    'chemsuschem': 'ChemSusChem',
    'chem suschem': 'ChemSusChem',

    # Chemistry of Materials
    'chemistry of materials': 'Chemistry of Materials',
    'chem mater': 'Chemistry of Materials',
    'chem. mater': 'Chemistry of Materials',

    # ACS Applied Materials & Interfaces
    'acs applied materials & interfaces': 'ACS Applied Materials & Interfaces',
    'acs appl mater interfaces': 'ACS Applied Materials & Interfaces',
    'acs appl. mater. interfaces': 'ACS Applied Materials & Interfaces',

    # ACS Applied Energy Materials
    'acs applied energy materials': 'ACS Applied Energy Materials',
    'acs appl energy mater': 'ACS Applied Energy Materials',
    'acs appl. energy mater': 'ACS Applied Energy Materials',

    # Journal of Materials Chemistry A
    'journal of materials chemistry a': 'Journal of Materials Chemistry A',
    'j mater chem a': 'Journal of Materials Chemistry A',
    'j. mater. chem. a': 'Journal of Materials Chemistry A',

    # Energy & Environmental Science
    'energy & environmental science': 'Energy & Environmental Science',
    'energy and environmental science': 'Energy & Environmental Science',
    'energy environ sci': 'Energy & Environmental Science',
    'energy environ. sci': 'Energy & Environmental Science',

    # Small
    'small': 'Small',

    # Nano Energy
    'nano energy': 'Nano Energy',

    # Journal of Physical Chemistry C
    'journal of physical chemistry c': 'The Journal of Physical Chemistry C',
    'j phys chem c': 'The Journal of Physical Chemistry C',
    'j. phys. chem. c': 'The Journal of Physical Chemistry C',

    # Journal of Physical Chemistry Letters
    'journal of physical chemistry letters': 'The Journal of Physical Chemistry Letters',
    'j phys chem lett': 'The Journal of Physical Chemistry Letters',
    'j. phys. chem. lett': 'The Journal of Physical Chemistry Letters',

    # Physical Chemistry Chemical Physics
    'physical chemistry chemical physics': 'Physical Chemistry Chemical Physics',
    'phys chem chem phys': 'Physical Chemistry Chemical Physics',
    'phys. chem. chem. phys': 'Physical Chemistry Chemical Physics',
    'pccp': 'Physical Chemistry Chemical Physics',

    # Scientific Reports
    'scientific reports': 'Scientific Reports',
    'sci rep': 'Scientific Reports',
    'sci. rep': 'Scientific Reports',

    # Science
    'science': 'Science',

    # Science Advances
    'science advances': 'Science Advances',
    'sci adv': 'Science Advances',
    'sci. adv': 'Science Advances',

    # Cell
    'cell': 'Cell',

    # Energies
    'energies': 'Energies',
    'energies (basel)': 'Energies',

    # Sensors
    'sensors': 'Sensors',
    'sensors (basel)': 'Sensors',

    # Electronics
    'electronics': 'Electronics',
    'electronics (basel)': 'Electronics',

    # Sustainability
    'sustainability': 'Sustainability',
    'sustainability (basel)': 'Sustainability',
}


def normalize_journal_name(journal_name: str) -> str:
    """
    Normalize a journal name to its canonical full form.

    Args:
        journal_name: The journal name to normalize (any format)

    Returns:
        The canonical full journal name, or the original if no mapping exists
    """
    if not journal_name or not isinstance(journal_name, str):
        return journal_name

    # Clean the input
    cleaned = journal_name.strip()

    # Try exact match first
    if cleaned in JOURNAL_MAPPING.values():
        return cleaned

    # Try case-insensitive lookup
    cleaned_lower = cleaned.lower()
    if cleaned_lower in JOURNAL_MAPPING:
        return JOURNAL_MAPPING[cleaned_lower]

    # Try removing extra spaces, dashes, and punctuation variations
    normalized_input = re.sub(r'\s+', ' ', cleaned_lower)
    normalized_input = re.sub(r'\.+', '.', normalized_input)
    normalized_input = normalized_input.strip('. ')

    if normalized_input in JOURNAL_MAPPING:
        return JOURNAL_MAPPING[normalized_input]

    # Return original if no match found
    return cleaned


def get_normalization_stats(papers: dict) -> dict:
    """
    Analyze journal names in papers and return normalization statistics.

    Args:
        papers: Dictionary of papers from metadata.json

    Returns:
        Dict with statistics: total_papers, journals_normalized, changes (list of before/after)
    """
    stats = {
        'total_papers': len(papers),
        'papers_with_journal': 0,
        'papers_normalized': 0,
        'changes': []
    }

    for filename, paper in papers.items():
        journal = paper.get('journal', '')
        if journal:
            stats['papers_with_journal'] += 1

            normalized = normalize_journal_name(journal)
            if normalized != journal:
                stats['papers_normalized'] += 1
                stats['changes'].append({
                    'filename': filename,
                    'before': journal,
                    'after': normalized
                })

    # Group changes by journal for summary
    journal_changes = {}
    for change in stats['changes']:
        before = change['before']
        after = change['after']
        if after not in journal_changes:
            journal_changes[after] = {'variations': set(), 'count': 0}
        journal_changes[after]['variations'].add(before)
        journal_changes[after]['count'] += 1

    stats['journal_summary'] = journal_changes

    return stats


def normalize_all_journals(papers: dict) -> tuple[dict, dict]:
    """
    Normalize all journal names in the papers dictionary.

    Args:
        papers: Dictionary of papers from metadata.json

    Returns:
        Tuple of (updated_papers, stats)
    """
    stats = get_normalization_stats(papers)

    # Apply normalizations
    for filename, paper in papers.items():
        journal = paper.get('journal', '')
        if journal:
            normalized = normalize_journal_name(journal)
            if normalized != journal:
                paper['journal'] = normalized

    return papers, stats
