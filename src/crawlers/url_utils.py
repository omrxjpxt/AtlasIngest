import hashlib
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

# List of obvious tracking parameters to remove
TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'fbclid', 'gclid', 'ref', 'source', 'click_id'
}

def canonicalize_url(url: str) -> str:
    """
    Normalizes a URL to a canonical form to facilitate duplicate detection.
    - normalizes scheme (http/https to lowercase)
    - lowercases hostname
    - removes URL fragments (#...)
    - normalizes default ports (e.g., removes :80 for http, :443 for https)
    - removes trailing slash from path (if it's just '/' or ending with '/')
    - removes obvious tracking parameters, preserves others.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return url

    # Scheme and Netloc
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    # Remove default ports
    if scheme == 'http' and netloc.endswith(':80'):
        netloc = netloc[:-3]
    elif scheme == 'https' and netloc.endswith(':443'):
        netloc = netloc[:-4]
        
    # Path
    path = parsed.path
    if path == '/':
        path = ''
    elif len(path) > 1 and path.endswith('/'):
        path = path.rstrip('/')
        
    # Query parameters
    if parsed.query:
        query_params = parse_qsl(parsed.query, keep_blank_values=True)
        # Filter out tracking params
        filtered_params = [(k, v) for k, v in query_params if k.lower() not in TRACKING_PARAMS]
        # Sort to ensure consistent order
        filtered_params.sort(key=lambda x: x[0])
        query = urlencode(filtered_params)
    else:
        query = ''
        
    # Fragments are deliberately omitted
    
    canonical_parsed = (scheme, netloc, path, parsed.params, query, '')
    return urlunparse(canonical_parsed)

def hash_content(content: str) -> str:
    """
    Calculates deterministic SHA-256 hash of string content.
    """
    if not content:
        return ""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
