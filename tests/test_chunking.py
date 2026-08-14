import pytest
from src.extraction.chunking import get_token_count, truncate_to_max_tokens, halve_payload
from src.extraction.cleaner import clean_html

def test_get_token_count():
    text = "hello world"
    count = get_token_count(text)
    assert count > 0
    assert count < 5

def test_truncate_to_max_tokens():
    text = "word " * 1000
    truncated = truncate_to_max_tokens(text, 100)
    assert get_token_count(truncated) <= 100

def test_halve_payload():
    text = "word " * 1000
    initial_tokens = get_token_count(text)
    halved = halve_payload(text)
    halved_tokens = get_token_count(halved)
    assert halved_tokens <= (initial_tokens // 2) + 5

def test_clean_html():
    html = """
    <html>
        <head><title>Test Title</title></head>
        <body>
            <script>alert('bad');</script>
            <nav>Menu</nav>
            <article>
                <p>Main content here.</p>
            </article>
            <footer>Copyright</footer>
        </body>
    </html>
    """
    cleaned = clean_html(html)
    assert "alert('bad')" not in cleaned
    assert "Menu" not in cleaned
    assert "Copyright" not in cleaned
    assert "TITLE: Test Title" in cleaned
    assert "Main content here." in cleaned
