import tiktoken
import logging

logger = logging.getLogger(__name__)

def get_token_count(text: str, model_name: str = "cl100k_base") -> int:
    """Estimates the token count of a given text."""
    try:
        encoding = tiktoken.get_encoding(model_name)
        return len(encoding.encode(text, disallowed_special=()))
    except Exception as e:
        logger.warning(f"Failed to encode text with tiktoken: {e}. Falling back to approx character count.")
        return len(text) // 4

def truncate_to_max_tokens(text: str, max_tokens: int, model_name: str = "cl100k_base") -> str:
    """
    Intelligently truncates text to stay within the max_tokens limit.
    Because news/jobs prioritize metadata and content at the top, we truncate from the bottom.
    """
    if not text:
        return ""
        
    try:
        encoding = tiktoken.get_encoding(model_name)
        tokens = encoding.encode(text, disallowed_special=())
        if len(tokens) <= max_tokens:
            return text
            
        logger.info(f"Truncating payload from {len(tokens)} to {max_tokens} tokens.")
        truncated_tokens = tokens[:max_tokens]
        return encoding.decode(truncated_tokens)
    except Exception as e:
        logger.warning(f"Failed to truncate text with tiktoken: {e}. Falling back to character slicing.")
        # Rough heuristic: 1 token ~= 4 chars
        max_chars = max_tokens * 4
        return text[:max_chars]

def halve_payload(text: str, model_name: str = "cl100k_base") -> str:
    """
    Reduces the payload size by 50% dynamically, used for 413 fallback handling.
    """
    current_tokens = get_token_count(text, model_name)
    target_tokens = max(100, current_tokens // 2)
    return truncate_to_max_tokens(text, target_tokens, model_name)
