# Detail Page Redesign - Metadata Hub

## Overview

Completely redesigned the paper detail page to be a **metadata and notes management hub**, following the Zotero approach. The embedded PDF viewer has been removed - PDFs now open in a separate browser tab for full reading experience.

## New Layout (2026-02-04)

### Top Bar
- **← Back to Library** button (left)
- **📄 Open PDF** button (right, prominent primary button)

### Sections

#### 1. Title
Large heading with clean HTML-stripped title

#### 2. 📚 Bibliographic Information
Two-column layout showing:
- **Left Column:**
  - Authors (full list, up to 10 shown)
  - Year
  - Paper Type

- **Right Column:**
  - Journal
  - DOI (clickable link)
  - Application

#### 3. 🏷️ Tags
- **Author Keywords:** Original keywords from the paper
- **AI-Generated Tags:** Chemistry, topics, etc.
- Clean tag pill display with color coding

#### 4. 📄 Abstract
- Shows abstract if available
- Placeholder for future abstract extraction

#### 5. 📝 Notes (Editable!)
- Text area for user notes
- Saves to `data/notes/{paper_filename}.txt`
- "Save Notes" button with toast confirmation
- Persistent across sessions

#### 6. 📚 References & Citations (Placeholder)
Collapsible expander for future features:
- Papers cited by this work
- Papers citing this work
- Related papers in library

#### 7. 📤 Upload PDF
- Only shown if no PDF exists
- Allows uploading PDF for papers without files

#### 8. Edit Metadata
- Collapsed expander at bottom
- DOI editing and CrossRef refresh

## Benefits

### ✅ Cleaner, More Focused
- No embedded viewer competing for attention
- All metadata visible without scrolling
- Professional, organized layout

### ✅ Better Reading Experience
- PDF opens in browser with full features
- Clickable links work
- Native zoom, search, annotations
- No performance issues with large PDFs

### ✅ Notes Management
- Dedicated space for user notes
- Persistent storage
- Easy to write while reading PDF in separate tab

### ✅ Zotero-Style Workflow
Users can now:
1. Open detail page to see metadata
2. Click "Open PDF" to read in browser
3. Take notes in the detail page
4. Switch back and forth easily

### ✅ Scalable
Easy to add future features:
- Abstract extraction
- Reference parsing
- Citation networks
- Related paper suggestions

## Technical Details

### Notes Storage
- Location: `data/notes/{paper_filename}.txt`
- Format: Plain text
- Excluded from git (in `.gitignore`)

### PDF Opening
- Uses `st.download_button` with `mime="application/pdf"`
- Opens in new browser tab (browser handles PDF rendering)
- Full PDF features: links, zoom, search, print, annotations

### Layout
- Two-column bibliographic info (efficient use of space)
- Dividers between sections (clear visual separation)
- Expandable sections for less critical info
- Primary action (Open PDF) prominently placed

## Removed Components

- ❌ Embedded PDF viewer (streamlit-pdf-viewer)
- ❌ PDF viewer CSS hacks
- ❌ Double scrollbar issues
- ❌ Compact metadata header

## File Structure

```
data/
  notes/
    paper1.pdf.txt      # User notes for paper1
    paper2.pdf.txt      # User notes for paper2
    ...
```

## Comparison

### Before (Embedded Viewer)
```
┌─────────────────────────────────┐
│ [← Back]                        │
│ **Title**                       │
│ Author · Year · Journal         │
│ [tags][tags][tags]              │
│ ┌─────────────────────────────┐ │
│ │                             │ │
│ │    PDF VIEWER               │ │ ← Embedded, scrollbar issues
│ │    (embedded)               │ │ ← No clickable links
│ │                             │ │
│ └─────────────────────────────┘ │
│ [Edit Metadata]                 │
└─────────────────────────────────┘
```

### After (Metadata Hub)
```
┌─────────────────────────────────┐
│ [← Back] [📄 Open PDF]          │ ← Prominent action
│ ─────────────────────────────── │
│ ## Title                        │
│                                 │
│ ### 📚 Bibliographic Info       │
│ [2-column layout]               │ ← Full metadata
│                                 │
│ ### 🏷️ Tags                    │
│ [author keywords + AI tags]     │
│                                 │
│ ### 📄 Abstract                 │
│ [abstract text]                 │
│                                 │
│ ### 📝 Notes                    │
│ [Editable text area]            │ ← NEW! User notes
│ [💾 Save Notes]                 │
│                                 │
│ ### 📚 References               │ ← Future feature
│ [collapsed]                     │
│                                 │
│ [Edit Metadata]                 │
└─────────────────────────────────┘

PDF opens in separate browser tab
with full features and clickable links
```

## User Workflow

### Reading a Paper
1. Browse library
2. Click paper to view details
3. Review metadata and tags
4. Click **"Open PDF"** → opens in new tab
5. Read PDF in browser (full features)
6. Switch back to detail page to take notes
7. Click **"Save Notes"**

### Taking Notes While Reading
1. Have PDF open in one tab
2. Detail page open in another tab
3. Switch between them as you read
4. Notes automatically saved

## Future Enhancements

Potential additions:
1. **Abstract extraction** during ingestion
2. **Reference parsing** from PDF
3. **Citation network** visualization
4. **Related papers** suggestions
5. **Export notes** as markdown
6. **Link notes to PDF pages** (page numbers in notes)
7. **Tags editing** directly from detail page
8. **Reading progress** tracking (pages read, time spent)
