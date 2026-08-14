import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def clean_html(html_content: str) -> str:
    """
    Cleans raw HTML by removing unnecessary tags (scripts, styles, navigation, footers)
    and extracts meaningful text from the page.
    """
    if not html_content:
        return ""

    try:
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Remove noisy tags
        for tag in soup(["script", "style", "svg", "nav", "footer", "header", "aside", "noscript", "iframe"]):
            tag.decompose()
            
        # Try to prioritize main content areas first
        main_content = ""
        main_tags = soup.find_all(["article", "main", "div", "section"]) # We look at main structural elements
        
        # If we didn't find specific main tags, fallback to body text
        body = soup.find("body")
        if body:
            main_content = body.get_text(separator="\n", strip=True)
        else:
            main_content = soup.get_text(separator="\n", strip=True)
                
        # Clean up excessive whitespace
        lines = [line.strip() for line in main_content.splitlines() if line.strip()]
        cleaned_text = "\n".join(lines)
        
        # Also grab title and some meta description if available to prepend
        title = soup.title.string if soup.title else ""
        meta_desc = ""
        desc_tag = soup.find("meta", attrs={"name": "description"})
        if desc_tag and desc_tag.get("content"):
            meta_desc = desc_tag["content"]
            
        header_text = ""
        if title:
            header_text += f"TITLE: {title.strip()}\n"
        if meta_desc:
            header_text += f"META DESCRIPTION: {meta_desc.strip()}\n"
            
        if header_text:
            cleaned_text = f"{header_text}\n{cleaned_text}"
            
        return cleaned_text
    except Exception as e:
        logger.error(f"Error cleaning HTML: {e}")
        return html_content[:50000]
