import asyncio
import time
import logging
from typing import Optional, Tuple
import aiohttp

logger = logging.getLogger(__name__)

class AsyncHttpClient:
    def __init__(
        self,
        global_concurrency: int = 20,
        per_host_concurrency: int = 5,
        total_timeout: int = 30,
        connect_timeout: int = 10,
        user_agent: str = "IntelligenceForge/0.1",
        verify_ssl: bool = True
    ):
        self.global_concurrency = global_concurrency
        self.per_host_concurrency = per_host_concurrency
        self.total_timeout = total_timeout
        self.connect_timeout = connect_timeout
        self.user_agent = user_agent
        self.verify_ssl = verify_ssl
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def start(self):
        """Initializes the aiohttp ClientSession with connection pooling."""
        if self.session is None:
            if not self.verify_ssl:
                logger.warning("SSL verification is EXPLICITLY DISABLED for this AsyncHttpClient.")
            connector = aiohttp.TCPConnector(
                limit=self.global_concurrency,
                limit_per_host=self.per_host_concurrency,
                ssl=self.verify_ssl
            )
            timeout = aiohttp.ClientTimeout(
                total=self.total_timeout,
                connect=self.connect_timeout,
                sock_read=self.total_timeout
            )
            headers = {
                'User-Agent': self.user_agent
            }
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=headers
            )
            logger.debug("AsyncHttpClient session started.")

    async def close(self):
        """Closes the aiohttp ClientSession cleanly."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            logger.debug("AsyncHttpClient session closed.")

    async def fetch(self, url: str) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[str], Optional[float], Optional[str], Optional[float]]:
        """
        Fetches a URL and returns:
        (raw_html, status_code, content_type, final_url, response_time_ms, error, retry_after)
        """
        if self.session is None:
            raise RuntimeError("AsyncHttpClient session is not started. Call start() first.")

        start_time = time.monotonic()
        try:
            async with self.session.get(url, allow_redirects=True, max_redirects=10) as response:
                status_code = response.status
                content_type = response.headers.get('Content-Type', '')
                final_url = str(response.url)
                retry_after_str = response.headers.get('Retry-After')
                retry_after = float(retry_after_str) if retry_after_str and retry_after_str.isdigit() else None
                
                raw_html = None
                # Only read body if we're not dealing with an error that doesn't need the body,
                # but usually we want to read the body if it's text/html.
                if status_code < 400:
                    raw_html = await response.text()
                else:
                    # Still try to read body on error if any, but ignore decoding errors
                    try:
                        raw_html = await response.text()
                    except Exception:
                        pass
                
                response_time_ms = (time.monotonic() - start_time) * 1000
                return raw_html, status_code, content_type, final_url, response_time_ms, None, retry_after
                
        except asyncio.TimeoutError:
            response_time_ms = (time.monotonic() - start_time) * 1000
            return None, None, None, None, response_time_ms, "TIMEOUT", None
        except aiohttp.ClientError as e:
            response_time_ms = (time.monotonic() - start_time) * 1000
            return None, None, None, None, response_time_ms, f"CLIENT_ERROR: {str(e)}", None
        except Exception as e:
            response_time_ms = (time.monotonic() - start_time) * 1000
            return None, None, None, None, response_time_ms, f"UNKNOWN_ERROR: {str(e)}", None
