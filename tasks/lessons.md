# Knowledge App — Agent Lessons

Accumulated corrections from past sessions. Read at every session start.
After any user correction: append a rule that prevents the mistake — not a description of what happened.

---

## Established Invariants

**Rule:** Never write `Path("papers") / filename` in route handlers. Always use `from lib.s3_storage import pdf_exists, save_pdf, get_presigned_url`.
**Why:** ECS Fargate has ephemeral local storage. Raw filesystem writes work in dev but silently lose data in production.

**Rule:** `lib/db_operations.py` is the only place for database reads and writes. Never write SQLAlchemy inline in `api/routes/`.
**Why:** Keeps routes thin and avoids scattered query logic that's hard to test or audit.
