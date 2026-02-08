"""
Select 10 papers for AI summary generation.
Prioritizes papers with complete status and variety in chemistries/topics.
"""
import json
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"

def main():
    # Load metadata
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    print("Analyzing papers for AI summary candidates...")
    print("=" * 70)

    # Filter for papers with pdf_status='complete' (has PDF + fully processed)
    complete_papers = []
    for filename, data in metadata.items():
        if data.get('pdf_status') == 'complete':
            complete_papers.append({
                'filename': filename,
                'title': data.get('title', 'Unknown'),
                'chemistries': data.get('chemistries', []),
                'topics': data.get('topics', []),
                'year': data.get('year', ''),
                'journal': data.get('journal', ''),
                'authors': data.get('authors', [])
            })

    print(f"Total papers with 'complete' status: {len(complete_papers)}")

    if len(complete_papers) < 10:
        print(f"\nWarning: Only {len(complete_papers)} complete papers available.")
        print("Will select all available papers.")
        selected = complete_papers
    else:
        # Analyze chemistry and topic distribution
        all_chemistries = []
        all_topics = []
        for p in complete_papers:
            all_chemistries.extend(p['chemistries'])
            all_topics.extend(p['topics'])

        chemistry_counts = Counter(all_chemistries)
        topic_counts = Counter(all_topics)

        print(f"\nChemistry distribution in complete papers:")
        for chem, count in chemistry_counts.most_common(10):
            print(f"  {chem}: {count}")

        print(f"\nTopic distribution (top 15):")
        for topic, count in topic_counts.most_common(15):
            print(f"  {topic}: {count}")

        # Select papers with diversity
        # Strategy: Pick papers that cover different chemistries and topics
        selected = []
        used_chemistries = set()
        used_topics = set()

        # Sort by number of unique chemistries/topics not yet used
        def diversity_score(paper):
            new_chemistries = len(set(paper['chemistries']) - used_chemistries)
            new_topics = len(set(paper['topics']) - used_topics)
            return new_chemistries * 2 + new_topics  # Weight chemistries higher

        remaining_papers = complete_papers.copy()

        while len(selected) < 10 and remaining_papers:
            # Score papers by diversity
            scored_papers = [(diversity_score(p), p) for p in remaining_papers]
            scored_papers.sort(reverse=True, key=lambda x: x[0])

            # Select the most diverse paper
            best_paper = scored_papers[0][1]
            selected.append(best_paper)

            # Update used chemistries and topics
            used_chemistries.update(best_paper['chemistries'])
            used_topics.update(best_paper['topics'])

            # Remove from remaining
            remaining_papers.remove(best_paper)

    # Display selected papers
    print("\n" + "=" * 70)
    print(f"SELECTED {len(selected)} PAPERS FOR AI SUMMARY GENERATION:")
    print("=" * 70)

    for idx, paper in enumerate(selected, 1):
        print(f"\n{idx}. {paper['title']}")
        print(f"   File: {paper['filename']}")
        print(f"   Year: {paper['year']} | Journal: {paper['journal']}")
        print(f"   Chemistries: {', '.join(paper['chemistries']) if paper['chemistries'] else 'None'}")
        print(f"   Topics: {', '.join(paper['topics'][:5]) if paper['topics'] else 'None'}")
        if len(paper['topics']) > 5:
            print(f"           + {len(paper['topics']) - 5} more topics...")

    # Save selected papers to JSON for next script
    output_file = BASE_DIR / "data" / "selected_papers_for_summary.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump([p['filename'] for p in selected], f, indent=2)

    print("\n" + "=" * 70)
    print(f"Saved selected papers to: {output_file}")
    print("\nNext step: Run abstract extraction and AI summary generation script.")

if __name__ == "__main__":
    main()
