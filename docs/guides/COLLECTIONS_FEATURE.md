# Collections Feature Guide

## Overview
The Collections feature allows you to organize papers into named groups (folders). Papers can belong to multiple collections, making it easy to organize your research by topic, project, or any other category.

## Features

### 1. Create Collections
- Create named collections (e.g., "SOH Methods", "Grant Proposal", "EIS Papers")
- Assign custom colors to collections for visual identification
- Add optional descriptions
- Each collection tracks the number of papers it contains

### 2. Organize Papers
- Add papers to multiple collections
- Remove papers from collections
- View all collections a paper belongs to
- Filter library view by collection

### 3. Manage Collections
- Rename collections
- Change collection colors
- Update descriptions
- Delete collections (papers are not deleted, only the collection)

## How to Use

### Creating Collections

**From Paper Detail Page:**
1. Open any paper detail page
2. Scroll to the "📁 Collections" section
3. Click "➕ Create New Collection"
4. Enter a name, choose a color, and optionally add a description
5. Click "Create Collection"
6. The current paper is automatically added to the new collection

**From Settings Tab:**
1. Go to Settings tab
2. Scroll to "📁 Collections Management"
3. Click "➕ Create New Collection"
4. Enter collection details and click "Create Collection"

### Adding Papers to Collections

**From Paper Detail Page:**
1. Open a paper detail page
2. Scroll to "📁 Collections" section
3. Select a collection from the "Add to Collection" dropdown
4. Click the ➕ button
5. The paper is instantly added

**Result:** Papers appear with collection tags on the detail page and in the library table.

### Removing Papers from Collections

1. Open the paper detail page
2. In the "📁 Collections" section
3. Select the collection from "Remove from Collection" dropdown
4. Click the ➖ button

### Filtering by Collection

**In Library Tab:**
1. Use the "📁 Collection" filter dropdown (4th column in filters)
2. Select a collection name
3. The library table updates to show only papers in that collection

### Managing Collections

**In Settings Tab:**
1. Go to Settings → "📁 Collections Management"
2. Each collection shows:
   - Name with color badge
   - Number of papers
   - Edit button (✏️) - to rename or change color/description
   - Delete button (🗑️) - to remove the collection (requires confirmation)

## Database Structure

### Tables

**collections:**
- `id` - Primary key
- `name` - Unique collection name
- `color` - Hex color code (default: #6c757d)
- `description` - Optional description
- `created_date` - ISO timestamp
- `modified_date` - ISO timestamp

**collection_items:**
- `id` - Primary key
- `collection_id` - Foreign key to collections
- `filename` - Paper filename
- `added_date` - ISO timestamp
- Unique constraint on (collection_id, filename)

### Indexes
- `idx_collection_items_filename` - Fast lookup by paper
- `idx_collection_items_collection_id` - Fast lookup by collection

## Backup Integration

Collections are automatically included in all backups:
- Database file: `data/collections.db`
- Included in zip backups in `data_backups/`
- Restored when you restore a backup

## Use Cases

1. **Research Topics:** Organize papers by research area
   - "Lithium-Ion Batteries"
   - "Solid-State Batteries"
   - "EIS Analysis"

2. **Projects:** Group papers by project or grant
   - "NSF Grant 2024"
   - "PhD Dissertation"
   - "Collaboration with Dr. Smith"

3. **Paper Type:** Categorize by paper characteristics
   - "Key Methods Papers"
   - "Review Papers"
   - "Experimental Studies"

4. **Status:** Track reading/analysis status
   - "To Read"
   - "Read and Summarized"
   - "Cited in Paper"

5. **Courses:** Organize papers for teaching
   - "CHEM 401 - Electrochemistry"
   - "Seminar Presentations"

## Implementation Details

### Module: `lib/collections.py`

**Key Functions:**
- `create_collection(name, color, description)` - Create new collection
- `get_all_collections()` - List all collections with paper counts
- `add_paper_to_collection(collection_id, filename)` - Add paper
- `remove_paper_from_collection(collection_id, filename)` - Remove paper
- `get_paper_collections(filename)` - Get collections for a paper
- `get_collection_papers(collection_id)` - Get papers in a collection
- `delete_collection(collection_id)` - Delete collection (cascade)
- `update_collection(collection_id, name, color, description)` - Update properties

### UI Integration

**Library Table:**
- New "📁 Collections" column shows comma-separated collection names
- Column uses flex sizing (1.5 parts) with text wrapping
- Tooltip shows full list if truncated

**Paper Detail Page:**
- Collections section between Notes and References
- Color-coded tags for current collections
- Add/remove controls with dropdowns
- Create new collection expander

**Settings Tab:**
- Full CRUD interface for collections
- Inline editing with forms
- Delete confirmation (two-click)
- Shows paper counts

## Performance

- SQLite database with indexes for fast lookups
- Efficient queries with JOIN operations
- Minimal UI impact (collections loaded once per page)
- Cascade deletes handle cleanup automatically

## Edge Cases Handled

1. **Duplicate prevention:** UNIQUE constraint prevents adding paper to same collection twice
2. **Deleted papers:** Cascade delete removes collection_items when collection deleted
3. **Empty collections:** Allowed, shows "0 papers" count
4. **Long names:** Text wrapping in UI, tooltips for full text
5. **Color validation:** Defaults to gray (#6c757d) if not provided
6. **Database initialization:** Tables created automatically on first use

## Future Enhancements (Potential)

- Bulk add/remove papers to collections
- Collection hierarchies (sub-collections)
- Export/import collections
- Collection-based statistics
- Smart collections with auto-filtering rules
- Collection sharing/collaboration

---

**Implementation Date:** 2026-02-05
**Version:** 1.0
