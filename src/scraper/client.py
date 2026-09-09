"""
HTTP client for SUME scraping with retry logic, rate limiting, and observability.

Provides a robust HTTP client with:
- Session management with connection pooling
- Exponential backoff retries (1s, 2s, 4s)
- Configurable rate limiting between requests
- 429 Too Many Requests handling with extended wait
- Request/response logging with timing
- Timeout handling
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.scraper.config import ScraperConfig

logger = logging.getLogger(__name__)


@dataclass
class RequestResult:
    """Result of an HTTP request."""
    url: str
    status_code: int
    duration_ms: float
    content: str
    error: Optional[str] = None


class SUMEClient:
    """
    HTTP client for SUME with built-in retry logic and rate limiting.

    Features:
    - Connection pooling via requests.Session
    - Exponential backoff: 1s, 2s, 4s (configurable base)
    - Rate limiting: configurable delay between requests
    - 429 handling: 60s wait, up to 3 retries
    - Request logging: URL, status, duration
    - Timeout handling: 30s default
    """

    def __init__(self, config: Optional[ScraperConfig] = None):
        """
        Initialize the SUME client.

        Args:
            config: Scraper configuration. If None, loads from global settings.
        """
        self.config = config or get_scraper_config()
        self._session: Optional[requests.Session] = None
        self._last_request_time: float = 0.0
        self._request_count: int = 0

    @property
    def session(self) -> requests.Session:
        """Get or create the requests session with retry adapter."""
        if self._session is None:
            self._session = self._create_session()
        return self._session

    def _create_session(self) -> requests.Session:
        """Create a configured requests session with retry strategy."""
        session = requests.Session()

        # Configure retry strategy for transient errors
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.backoff_base,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
            raise_on_status=False,  # We handle status codes manually
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set default headers
        session.headers.update({
            "User-Agent": self.config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        })

        return session

    def _respect_rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self.config.delay_seconds:
            sleep_time = self.config.delay_seconds - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

    def _log_request(self, method: str, url: str, status_code: int, duration_ms: float, error: Optional[str] = None) -> None:
        """Log request details."""
        self._request_count += 1
        log_data = {
            "request_number": self._request_count,
            "method": method,
            "url": url,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
        }
        if error:
            log_data["error"] = error
            logger.warning("HTTP request failed", extra=log_data)
        else:
            logger.info("HTTP request completed", extra=log_data)

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> RequestResult:
        """
        Make an HTTP request with retry logic and rate limiting.

        Args:
            method: HTTP method (GET, POST)
            url: Target URL
            params: Query parameters
            data: Form data for POST requests
            timeout: Request timeout in seconds (default from config)

        Returns:
            RequestResult with response data or error info.
        """
        self._respect_rate_limit()

        timeout = timeout or self.config.timeout_seconds
        start_time = time.monotonic()
        self._last_request_time = start_time

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                timeout=timeout,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            self._log_request(method, url, response.status_code, duration_ms)

            # Handle 429 specifically (not covered by urllib3 retry)
            if response.status_code == 429:
                return self._handle_rate_limit(method, url, params, data, timeout, start_time)

            return RequestResult(
                url=url,
                status_code=response.status_code,
                duration_ms=duration_ms,
                content=response.text,
            )

        except requests.exceptions.Timeout as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            error_msg = f"Request timeout after {timeout}s"
            self._log_request(method, url, 0, duration_ms, error_msg)
            return RequestResult(
                url=url,
                status_code=0,
                duration_ms=duration_ms,
                content="",
                error=error_msg,
            )

        except requests.exceptions.RequestException as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            error_msg = f"Request failed: {type(e).__name__}: {e}"
            self._log_request(method, url, 0, duration_ms, error_msg)
            return RequestResult(
                url=url,
                status_code=0,
                duration_ms=duration_ms,
                content="",
                error=error_msg,
            )

    def _handle_rate_limit(
        self,
        method: str,
        url: str,
        params: Optional[dict],
        data: Optional[dict],
        timeout: int,
        original_start: float,
    ) -> RequestResult:
        """Handle 429 response with extended wait and retries."""
        for attempt in range(1, self.config.rate_limit_retries + 1):
            wait_time = self.config.rate_limit_wait
            logger.warning(
                f"Rate limited (429), waiting {wait_time}s before retry {attempt}/{self.config.rate_limit_retries}",
                extra={"url": url, "attempt": attempt},
            )
            time.sleep(wait_time)

            self._respect_rate_limit()
            retry_start = time.monotonic()

            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    timeout=timeout,
                )

                duration_ms = (time.monotonic() - original_start) * 1000
                self._log_request(method, url, response.status_code, duration_ms)

                if response.status_code != 429:
                    return RequestResult(
                        url=url,
                        status_code=response.status_code,
                        duration_ms=duration_ms,
                        content=response.text,
                    )

            except requests.exceptions.RequestException as e:
                duration_ms = (time.monotonic() - original_start) * 1000
                error_msg = f"Retry {attempt} failed: {type(e).__name__}: {e}"
                self._log_request(method, url, 0, duration_ms, error_msg)

        # All retries exhausted
        duration_ms = (time.monotonic() - original_start) * 1000
        error_msg = f"Rate limit retries exhausted after {self.config.rate_limit_retries} attempts"
        self._log_request(method, url, 429, duration_ms, error_msg)
        return RequestResult(
            url=url,
            status_code=429,
            duration_ms=duration_ms,
            content="",
            error=error_msg,
        )

    def get(self, url: str, params: Optional[dict] = None) -> RequestResult:
        """Make a GET request."""
        return self.request("GET", url, params=params)

    def post(self, url: str, data: Optional[dict] = None, params: Optional[dict] = None) -> RequestResult:
        """Make a POST request."""
        return self.request("POST", url, params=params, data=data)

    def search(self, params: dict) -> RequestResult:
        """Execute a search request to SUME."""
        search_url = self.config.get_search_url()
        return self.post(search_url, data=params)

    def get_detail(self, detail_id: str) -> RequestResult:
        """Fetch an expediente detail page."""
        detail_url = self.config.get_detail_url(detail_id)
        return self.get(detail_url)

    def save_raw_html(self, content: str, filename: str) -> Path:
        """
        Save raw HTML content to the raw data directory.

        Args:
            content: HTML content to save
            filename: Base filename (without extension)

        Returns:
            Path to the saved file.
        """
        raw_dir = Path(self.config.raw_html_dir)
        raw_dir.mkdir(parents=True, exist_ok=True)

        filepath = raw_dir / f"{filename}.html"
        filepath.write_text(content, encoding="utf-8")
        logger.debug(f"Saved raw HTML to {filepath}")
        return filepath

    def close(self) -> None:
        """Close the HTTP session."""
        if self._session is not None:
            self._session.close()
            self._session = None

    def __enter__(self) -> "SUMEClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def get_scraper_config() -> ScraperConfig:
    """Load scraper configuration from global settings."""
    from src.config import get_settings
    settings = get_settings()
    return ScraperConfig(
        delay_seconds=settings.scraper.delay_seconds,
        timeout_seconds=settings.scraper.timeout_seconds,
        max_retries=settings.scraper.max_retries,
        backoff_base=settings.scraper.backoff_base,
        rate_limit_wait=settings.scraper.rate_limit_wait,
        user_agent=settings.scraper.user_agent,
        base_url=settings.sume.base_url,
        search_path=settings.sume.search_path,
        detail_path=settings.sume.detail_path,
        faculty_filter=settings.sume.faculty_filter,
        normalization_rules_path=settings.normalizer.rules_path,
    )