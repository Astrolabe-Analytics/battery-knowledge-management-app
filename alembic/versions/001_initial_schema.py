"""Initial schema — papers, chunks, collections, query_history, settings.

Matches lib/models.py as of 2026-02-24.
Creates the pgvector extension, all tables, indexes, and constraints.

Revision ID: 001
Revises: None
Create Date: 2026-02-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- papers ---
    op.create_table(
        "papers",
        sa.Column("filename", sa.String(), primary_key=True),
        # Bibliographic
        sa.Column("title", sa.Text(), server_default=""),
        sa.Column("authors", JSONB(), server_default="[]"),
        sa.Column("year", sa.String(50), server_default=""),
        sa.Column("journal", sa.Text(), server_default=""),
        sa.Column("doi", sa.String(255), server_default=""),
        sa.Column("abstract", sa.Text(), server_default=""),
        sa.Column("volume", sa.String(50), server_default=""),
        sa.Column("issue", sa.String(50), server_default=""),
        sa.Column("pages", sa.String(100), server_default=""),
        sa.Column("author_keywords", JSONB(), server_default="[]"),
        # Classification
        sa.Column("chemistries", JSONB(), server_default="[]"),
        sa.Column("topics", JSONB(), server_default="[]"),
        sa.Column("application", sa.String(100), server_default="general"),
        sa.Column("paper_type", sa.String(100), server_default="Experimental"),
        # Provenance
        sa.Column("source_url", sa.Text(), server_default=""),
        sa.Column("pdf_status", sa.String(50), server_default=""),
        sa.Column("metadata_only", sa.Boolean(), server_default="false"),
        sa.Column("metadata_incomplete", sa.Boolean(), server_default="false"),
        sa.Column("crossref_verified", sa.Boolean(), server_default="false"),
        sa.Column("needs_processing", sa.Boolean(), server_default="false"),
        sa.Column("pdf_source", sa.String(100), server_default=""),
        sa.Column("pdf_found_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        # AI-generated content
        sa.Column("feed_blurb", sa.Text(), server_default=""),
        sa.Column("ai_summary", sa.Text(), server_default=""),
        sa.Column("summary_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary_model", sa.String(100), server_default=""),
        # User state
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column("is_read", sa.Boolean(), server_default="false"),
        sa.Column("read_marked_date", sa.DateTime(timezone=True), nullable=True),
        # Lifecycle
        sa.Column("date_added", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_papers_doi", "papers", ["doi"])
    op.create_index("ix_papers_year", "papers", ["year"])
    op.create_index("ix_papers_paper_type", "papers", ["paper_type"])
    op.create_index("ix_papers_deleted_at", "papers", ["deleted_at"])

    # --- paper_references ---
    op.create_table(
        "paper_references",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("paper_filename", sa.String(), sa.ForeignKey("papers.filename", ondelete="CASCADE"), nullable=False),
        sa.Column("ref_key", sa.String(255), server_default=""),
        sa.Column("doi", sa.String(255), server_default=""),
        sa.Column("doi_asserted_by", sa.String(50), server_default=""),
        sa.Column("article_title", sa.Text(), server_default=""),
        sa.Column("author", sa.String(255), server_default=""),
        sa.Column("year", sa.String(50), server_default=""),
        sa.Column("journal_title", sa.Text(), server_default=""),
        sa.Column("volume", sa.String(50), server_default=""),
        sa.Column("first_page", sa.String(50), server_default=""),
    )
    op.create_index("ix_paper_references_paper_filename", "paper_references", ["paper_filename"])
    op.create_index("ix_paper_references_doi", "paper_references", ["doi"])

    # --- chunks ---
    op.create_table(
        "chunks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("paper_filename", sa.String(), sa.ForeignKey("papers.filename", ondelete="CASCADE"), nullable=False),
        sa.Column("page_num", sa.Integer(), server_default="0"),
        sa.Column("chunk_index", sa.Integer(), server_default="0"),
        sa.Column("token_count", sa.Integer(), server_default="0"),
        sa.Column("section_name", sa.Text(), server_default="Content"),
        sa.Column("content", sa.Text(), nullable=False),
    )
    # Add pgvector column separately (384 dimensions for all-MiniLM-L6-v2)
    op.execute("ALTER TABLE chunks ADD COLUMN embedding vector(384)")
    )
    op.create_index("ix_chunks_paper_filename", "chunks", ["paper_filename"])
    op.create_index("ix_chunks_page_num", "chunks", ["page_num"])
    # HNSW index for vector similarity search
    op.execute("""
        CREATE INDEX ix_chunks_embedding_hnsw
        ON chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # --- collections ---
    op.create_table(
        "collections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("color", sa.String(20), server_default="#6c757d"),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("created_date", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("modified_date", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # --- collection_items ---
    op.create_table(
        "collection_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("collection_id", sa.Integer(), sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("paper_filename", sa.String(), sa.ForeignKey("papers.filename", ondelete="CASCADE"), nullable=False),
        sa.Column("added_date", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("collection_id", "paper_filename", name="uq_collection_paper"),
    )
    op.create_index("ix_collection_items_paper_filename", "collection_items", ["paper_filename"])
    op.create_index("ix_collection_items_collection_id", "collection_items", ["collection_id"])

    # --- query_history ---
    op.create_table(
        "query_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False, server_default=""),
        sa.Column("chunks_json", JSONB(), server_default="[]"),
        sa.Column("filters_json", JSONB(), server_default="{}"),
        sa.Column("is_starred", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # --- settings ---
    op.create_table(
        "settings",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("value", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_table("query_history")
    op.drop_table("collection_items")
    op.drop_table("collections")
    op.drop_index("ix_chunks_embedding_hnsw", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("paper_references")
    op.drop_table("papers")
    op.execute("DROP EXTENSION IF EXISTS vector")
