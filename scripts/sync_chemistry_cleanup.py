"""One-time script to sync normalized chemistry names into ChromaDB."""
import json
import sys
sys.path.insert(0, '.')
from lib.rag import DatabaseClient

CHEM_NORMALIZE = {
    'LI-ION': 'Lithium-ion', 'LITHIUM-ION': 'Lithium-ion', 'LITHIUM ION': 'Lithium-ion',
    'LI-S': 'Li-S', 'LITHIUM-SULFUR': 'Li-S',
    'NA-ION': 'Na-ion', 'SODIUM-ION': 'Na-ion',
    'ZN-ION': 'Zn-ion', 'ZINC-ION': 'Zn-ion',
    'LIFEPO4': 'LFP', 'NIMH': 'NiMH', 'NI-MH': 'NiMH',
    'LICOO2': 'LCO', 'LIMN2O4': 'LMO', 'LINI0.8MN0.1CO0.1O2': 'NMC811',
    'LIB': 'Lithium-ion', 'NCM': 'NMC', 'LITHIUM': 'Lithium-ion',
    'LEAD-ACID': 'Lead-acid', 'SOLID-STATE': 'Solid-state',
    'LITHIUM METAL': 'Lithium metal', 'LITHIUM-RICH LAYERED OXIDE': 'Li-rich layered oxide',
    'SILICON OXIDE': 'Silicon oxide', 'SILICON': 'Silicon',
    'HARD CARBON': 'Hard carbon', 'GRAPHITE': 'Graphite',
}

def normalize(c):
    c = c.strip()
    return CHEM_NORMALIZE.get(c.upper(), c)

collection = DatabaseClient.get_collection()
all_results = collection.get(include=['metadatas'])
total = len(all_results['ids'])

ids_to_update = []
metas_to_update = []

for doc_id, md in zip(all_results['ids'], all_results['metadatas']):
    if md.get('chemistries'):
        raw = md['chemistries']
        parts = [normalize(x) for x in raw.split(',') if x.strip() and len(x.strip()) >= 2]
        clean = ','.join(sorted(set(parts)))
        if clean != raw:
            md['chemistries'] = clean
            ids_to_update.append(doc_id)
            metas_to_update.append(md)

print(f"ChromaDB chunks to update: {len(ids_to_update)} / {total}")

BATCH = 500
for start in range(0, len(ids_to_update), BATCH):
    end = min(start + BATCH, len(ids_to_update))
    collection.update(
        ids=ids_to_update[start:end],
        metadatas=metas_to_update[start:end],
    )
    print(f"  Updated batch {start}-{end}")

print("Done syncing ChromaDB")
