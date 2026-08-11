import re
import unicodedata

def normalize_entity_name(name: str) -> str:
    """
    Normalizes a startup/company name for deterministic deduplication and matching.
    
    Performs:
    - Unicode normalization (NFKD)
    - Lowercasing
    - Removes common legal suffixes (inc, llc, corp, etc)
    - Removes all non-alphanumeric characters
    - Removes whitespace
    
    Examples:
    "Open AI" -> "openai"
    "OpenAI, Inc." -> "openai"
    "Apple" -> "apple"
    """
    if not name:
        return ""
        
    # 1. Unicode normalization and lowercasing
    normalized = unicodedata.normalize('NFKD', name).lower()
    
    # 2. Remove common legal suffixes (with word boundaries)
    legal_suffixes = [r'\binc\b', r'\bincorporated\b', r'\bllc\b', r'\bcorp\b', r'\bcorporation\b', r'\bltd\b', r'\blimited\b']
    for suffix in legal_suffixes:
        normalized = re.sub(suffix, '', normalized)
        
    # 3. Remove non-alphanumeric characters and whitespace
    normalized = re.sub(r'[^a-z0-9]', '', normalized)
    
    return normalized
