"""
Reactions API — lightweight emoji reactions for the mobile feed.

Storage: data/reactions.json  (simple JSON file, no DB migration needed)
Format: { "paper_filename": { "🤯": 1, "💡": 0, "🔬": 1, "📌": 0 }, ... }
"""
import json
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

REACTIONS_FILE = Path("data/reactions.json")
VALID_EMOJIS = {"🤯", "💡", "🔬", "🔋", "⚡", "📌"}


def _load_reactions() -> dict:
    if REACTIONS_FILE.exists():
        return json.loads(REACTIONS_FILE.read_text(encoding="utf-8"))
    return {}


def _save_reactions(data: dict):
    REACTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    REACTIONS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class ReactionToggle(BaseModel):
    emoji: str


@router.get("")
def get_all_reactions() -> Dict[str, dict]:
    """Return all reactions for all papers."""
    return _load_reactions()


@router.post("/{filename}")
def toggle_reaction(filename: str, body: ReactionToggle):
    """Toggle a single emoji reaction on/off for a paper."""
    if not body.emoji or len(body.emoji) > 4:
        raise HTTPException(status_code=400, detail="Invalid emoji")

    data = _load_reactions()
    paper_reactions = data.get(filename, {})

    # Toggle: if it's on (1), turn off (0); if off or missing, turn on (1)
    current = paper_reactions.get(body.emoji, 0)
    paper_reactions[body.emoji] = 0 if current else 1

    data[filename] = paper_reactions
    _save_reactions(data)

    return {"filename": filename, "reactions": paper_reactions}
