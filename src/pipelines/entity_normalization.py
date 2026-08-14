import re
import unicodedata
import json
import os

SEED_FILE = os.path.join(os.path.dirname(__file__), '../../data/canonical_entities.json')
SEED_LIST = []
if os.path.exists(SEED_FILE):
    with open(SEED_FILE, 'r') as f:
        SEED_LIST = json.load(f)

def normalize_entity_name(name: str) -> str:
    if not name:
        return ""

    name_lower = name.strip().lower()
    name_stripped = name_lower.replace(" ", "").replace(",", "")

    for entry in SEED_LIST:
        canonical = entry["canonical_name"]
        aliases = entry["aliases"]
        if name_lower == canonical.lower() or name_lower in aliases:
            return canonical
        if name_stripped == canonical.lower().replace(" ", "") or name_stripped in aliases:
            return canonical
        if name_lower == canonical.lower() + ", inc.":
            return canonical

    normalized = unicodedata.normalize('NFKD', name).lower()

    legal_suffixes = [r'\binc\b', r'\bincorporated\b', r'\bllc\b', r'\bcorp\b', r'\bcorporation\b', r'\bltd\b', r'\blimited\b']
    for suffix in legal_suffixes:
        normalized = re.sub(suffix, '', normalized)

    normalized = re.sub(r'[^a-z0-9]', '', normalized)

    return normalized
