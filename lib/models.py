"""
SQLAlchemy ORM models for the Astrolabe paper database.

Tables:
- papers          – one row per paper (replaces metadata.json + read_status.db)
- paper_references – normalized citation references
- chunks          – text chunks with pgvector embeddings (replaces ChromaDB)
- collections     – user-defined paper groupings (replaces collections.db)
- collection_items – many-to-many link between collections and papers
- query_history   – saved RAG queries & answers (replaces query_history.db)
- settings        – key/value app settings (replaces settings.json)
"""

from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


def _utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Papers
# ---------------------------------------------------------------------------

class Paper(Base):
    """One row per paper.  `filename` is the universal primary key
    (e.g. 'doi_10_1038_s41467-019-09792-9.pdf')."""

    __tablename__ = "papers"

    filename = Column(String, primary_key=True)

    # --- Bibliographic ---
    title = Column(Text, default="")
    authors = Column(JSONB, default=list)          # list[str]
    year = Column(String(50), default="")
    journal = Column(Text, default="")
    doi = Column(String(255), default="")
    abstract = Column(Text, default="")
    volume = Column(String(50), default="")
    issue = Column(String(50), default="")
    pages = Column(String(100), default="")
    author_keywords = Column(JSONB, default=list)   # list[str]

    # --- Classification (LLM-extracted) ---
    chemistries = Column(JSONB, default=list)       # list[str]  e.g. ["LFP","NMC"]
    topics = Column(JSONB, default=list)            # list[str]  e.g. ["degradation","soh"]
    application = Column(String(100), default="general")
    paper_type = Column(String(100), default="Experimental")

    # --- Provenance ---
    source_url = Column(Text, default="")
    pdf_status = Column(String(50), default="")     # "complete","metadata_only",""
    metadata_only = Column(Boolean, default=False)
    metadata_incomplete = Column(Boolean, default=False)
    crossref_verified = Column(Boolean, default=False)
    needs_processing = Column(Boolean, default=False)
    pdf_source = Column(String(100), default="")
    pdf_found_date = Column(DateTime(timezone=True), nullable=True)
    extracted_at = Column(DateTime(timezone=True), nullable=True)

    # --- AI-generated content ---
    feed_blurb = Column(Text, default="")
    ai_summary = Column(Text, default="")
    summary_generated_at = Column(DateTime(timezone=True), nullable=True)
    summary_model = Column(String(100), default="")

    # --- User state ---
    notes = Column(Text, default="")
    is_read = Column(Boolean, default=False)
    read_marked_date = Column(DateTime(timezone=True), nullable=True)

    # --- Lifecycle ---
    date_added = Column(DateTime(timezone=True), default=_utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # --- Relationships ---
    references = relationship("PaperReference", back_populates="paper",
                              cascade="all, delete-orphan", lazy="selectin")
    chunks = relationship("Chunk", back_populates="paper",
                          cascade="all, delete-orphan", lazy="select")
    collection_items = relationship("CollectionItem", back_populates="paper",
                                    cascade="all, delete-orphan")

    # --- Indexes ---
    __table_args__ = (
        Index("ix_papers_doi", "doi"),
        Index("ix_papers_year", "year"),
        Index("ix_papers_paper_type", "paper_type"),
        Index("ix_papers_deleted_at", "deleted_at"),
    )

    def to_library_dict(self) -> dict:
        """Serialize for the library list endpoint (matches current API shape)."""
        return {
            "filename": self.filename,
            "title": self.title or "",
            "authors": "; ".join(self.authors) if isinstance(self.authors, list) else (self.authors or ""),
            "year": self.year or "",
            "journal": self.journal or "",
            "doi": self.doi or "",
            "author_keywords": self.author_keywords or [],
            "chemistries": self.chemistries or [],
            "topics": self.topics or [],
            "application": self.application or "general",
            "paper_type": self.paper_type or "Experimental",
            "num_pages": 0,  # filled in by caller from chunk count
            "date_added": self.date_added.isoformat() if self.date_added else "",
            "pdf_status": self.pdf_status or "",
            "feed_blurb": self.feed_blurb or "",
            "ai_summary": self.ai_summary or "",
        }

    def to_detail_dict(self) -> dict:
        """Full detail for the paper detail endpoint."""
        d = self.to_library_dict()
        # Override authors as a proper list (to_library_dict joins them as a string)
        d["authors"] = self.authors if isinstance(self.authors, list) else (
            [a.strip() for a in (self.authors or "").split(";")] if self.authors else []
        )
        d.update({
            "abstract": self.abstract or "",
            "volume": self.volume or "",
            "issue": self.issue or "",
            "pages": self.pages or "",
            "source_url": self.source_url or "",
            "notes": self.notes or "",
            "metadata_only": self.metadata_only,
            "crossref_verified": self.crossref_verified,
            "references": [r.to_dict() for r in self.references],
        })
        return d


# ---------------------------------------------------------------------------
# Paper References
# ---------------------------------------------------------------------------

class PaperReference(Base):
    """A single bibliographic reference cited by a paper."""

    __tablename__ = "paper_references"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_filename = Column(String, ForeignKey("papers.filename", ondelete="CASCADE"), nullable=False)
    ref_key = Column(String(255), default="")       # CrossRef reference key
    doi = Column(String(255), default="")
    doi_asserted_by = Column(String(50), default="")
    article_title = Column(Text, default="")
    author = Column(String(255), default="")
    year = Column(String(50), default="")
    journal_title = Column(Text, default="")
    volume = Column(String(50), default="")
    first_page = Column(String(50), default="")

    paper = relationship("Paper", back_populates="references")

    __table_args__ = (
        Index("ix_paper_references_paper_filename", "paper_filename"),
        Index("ix_paper_references_doi", "doi"),
    )

    def to_dict(self) -> dict:
        """Serialize to the same shape the frontend expects (CrossRef-style keys)."""
        d = {}
        if self.ref_key:
            d["key"] = self.ref_key
        if self.doi:
            d["DOI"] = self.doi
        if self.doi_asserted_by:
            d["doi-asserted-by"] = self.doi_asserted_by
        if self.article_title:
            d["article-title"] = self.article_title
        if self.author:
            d["author"] = self.author
        if self.year:
            d["year"] = self.year
        if self.journal_title:
            d["journal-title"] = self.journal_title
        if self.volume:
            d["volume"] = self.volume
        if self.first_page:
            d["first-page"] = self.first_page
        return d


# ---------------------------------------------------------------------------
# Chunks  (replaces ChromaDB)
# ---------------------------------------------------------------------------

class Chunk(Base):
    """A text chunk with its pgvector embedding."""

    __tablename__ = "chunks"

    id = Column(String, primary_key=True)            # "{filename}_p{page}_c{idx}"
    paper_filename = Column(String, ForeignKey("papers.filename", ondelete="CASCADE"), nullable=False)

    page_num = Column(Integer, default=0)
    chunk_index = Column(Integer, default=0)
    token_count = Column(Integer, default=0)
    section_name = Column(Text, default="Content")
    content = Column(Text, nullable=False)

    # pgvector column – 384 dimensions for all-MiniLM-L6-v2
    embedding = Column(Vector(384), nullable=True)

    paper = relationship("Paper", back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_paper_filename", "paper_filename"),
        Index("ix_chunks_page_num", "page_num"),
        # HNSW index for fast approximate nearest-neighbour search
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    color = Column(String(20), default="#6c757d")
    description = Column(Text, default="")
    created_date = Column(DateTime(timezone=True), default=_utcnow)
    modified_date = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    items = relationship("CollectionItem", back_populates="collection",
                         cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color or "#6c757d",
            "description": self.description or "",
            "created_date": self.created_date.isoformat() if self.created_date else "",
            "modified_date": self.modified_date.isoformat() if self.modified_date else "",
            "paper_count": len(self.items) if self.items else 0,
        }


class CollectionItem(Base):
    __tablename__ = "collection_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=False)
    paper_filename = Column(String, ForeignKey("papers.filename", ondelete="CASCADE"), nullable=False)
    added_date = Column(DateTime(timezone=True), default=_utcnow)

    collection = relationship("Collection", back_populates="items")
    paper = relationship("Paper", back_populates="collection_items")

    __table_args__ = (
        UniqueConstraint("collection_id", "paper_filename", name="uq_collection_paper"),
        Index("ix_collection_items_paper_filename", "paper_filename"),
        Index("ix_collection_items_collection_id", "collection_id"),
    )


# ---------------------------------------------------------------------------
# Query History
# ---------------------------------------------------------------------------

class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), default=_utcnow)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False, default="")
    chunks_json = Column(JSONB, default=list)        # serialized list of chunk dicts
    filters_json = Column(JSONB, default=dict)       # serialized filter dict
    is_starred = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


# ---------------------------------------------------------------------------
# Settings (key-value)
# ---------------------------------------------------------------------------

class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(255), primary_key=True)
    value = Column(JSONB, nullable=True)
