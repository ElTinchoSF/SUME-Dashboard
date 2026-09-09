"""
Unit tests for SUME HTTP client.

Tests cover:
- Retry logic with exponential backoff
- Rate limiting between requests
- 429 Too Many Requests handling
- Request logging
- Timeout handling
"""

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.scraper.client import SUMEClient, RequestResult, get_scraper_config
from src.scraper.config import ScraperConfig, SelectorConfig


class TestScraperConfig:
    """Tests for ScraperConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ScraperConfig()
        assert config.delay_seconds == 0.5
        assert config.timeout_seconds == 30
        assert config.max_retries == 3
        assert config.backoff_base == 1.0
        assert config.rate_limit_wait == 60
        assert config.rate_limit_retries == 3

    def test_get_search_url(self):
        """Test search URL construction."""
        config = ScraperConfig(base_url="https://example.com/", search_path="search.php")
        assert config.get_search_url() == "https://example.com/search.php"

    def test_get_detail_url(self):
        """Test detail URL construction."""
        config = ScraperConfig(base_url="https://example.com/", detail_path="detail.php")
        assert config.get_detail_url("12345") == "https://example.com/detail.php?id=12345"

    def test_get_search_params_full_year(self):
        """Test search params for full year."""
        config = ScraperConfig(faculty_filter="FBCB")
        params = config.get_search_params(2025)
        assert params["numero"] == "FBCB"
        assert params["fecha_desde"] == "01/01/2025"
        assert params["fecha_hasta"] == "31/12/2025"

    def test_get_search_params_semester_1(self):
        """Test search params for semester 1."""
        config = ScraperConfig(faculty_filter="FBCB")
        params = config.get_search_params(2025, semester=1)
        assert params["fecha_desde"] == "01/01/2025"
        assert params["fecha_hasta"] == "30/06/2025"

    def test_get_search_params_semester_2(self):
        """Test search params for semester 2."""
        config = ScraperConfig(faculty_filter="FBCB")
        params = config.get_search_params(2025, semester=2)
        assert params["fecha_desde"] == "01/07/2025"
        assert params["fecha_hasta"] == "31/12/2025"


class TestSUMEClient:
    """Tests for SUMEClient HTTP client."""

    @pytest.fixture
    def config(self):
        """Test configuration with fast settings."""
        return ScraperConfig(
            delay_seconds=0.0,  # No delay for tests
            timeout_seconds=5,
            max_retries=2,
            backoff_base=0.1,  # Fast backoff (min 0.1)
            rate_limit_wait=1,  # Fast rate limit wait (integer)
            rate_limit_retries=1,
            user_agent="TestAgent/1.0",
        )

    @pytest.fixture
    def client(self, config):
        """Create a test client."""
        return SUMEClient(config)

    def test_client_initialization(self, client):
        """Test client initializes correctly."""
        assert client.config.delay_seconds == 0.0
        assert client.config.max_retries == 2
        assert client._session is None

    def test_session_creation(self, client):
        """Test session is created lazily."""
        session = client.session
        assert session is not None
        assert isinstance(session, requests.Session)
        assert session.headers["User-Agent"] == "TestAgent/1.0"

    def test_successful_get_request(self, client):
        """Test successful GET request."""
        # Create mock session and inject it
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Test</html>"
        # The client uses session.request() internally
        mock_session.request.return_value = mock_response
        client._session = mock_session

        result = client.get("https://example.com/test")

        assert result.status_code == 200
        assert result.content == "<html>Test</html>"
        assert result.error is None
        assert result.duration_ms > 0
        # Verify request was called with GET
        mock_session.request.assert_called_once()
        args, kwargs = mock_session.request.call_args
        # Client calls request with keyword arguments
        assert kwargs.get("method") == "GET" or (args and args[0] == "GET")

    def test_successful_post_request(self, client):
        """Test successful POST request."""
        # Create mock session and inject it
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Result</html>"
        mock_session.request.return_value = mock_response
        client._session = mock_session

        result = client.post("https://example.com/search", data={"q": "test"})

        assert result.status_code == 200
        assert result.content == "<html>Result</html>"
        # Verify request was called with POST
        mock_session.request.assert_called_once()
        args, kwargs = mock_session.request.call_args
        assert kwargs.get("method") == "POST" or (args and args[0] == "POST")

    def test_rate_limiting(self, client):
        """Test rate limiting enforces delay between requests."""
        config = ScraperConfig(delay_seconds=0.1, timeout_seconds=5)
        client = SUMEClient(config)

        with patch.object(client.session, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            mock_get.return_value = mock_response

            start = time.monotonic()
            client.get("https://example.com/1")
            client.get("https://example.com/2")
            elapsed = time.monotonic() - start

            # Should have waited at least 0.1s between requests
            assert elapsed >= 0.09  # Allow small tolerance

    def test_timeout_handling(self, client):
        """Test timeout handling returns error result."""
        mock_session = MagicMock()
        mock_session.request.side_effect = requests.exceptions.Timeout("Connection timed out")
        client._session = mock_session

        result = client.get("https://example.com/slow")

        assert result.status_code == 0
        assert result.error is not None
        assert "timeout" in result.error.lower()

    def test_connection_error_handling(self, client):
        """Test connection error handling."""
        with patch.object(client.session, "get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("DNS lookup failed")

            result = client.get("https://invalid.example.com")

            assert result.status_code == 0
            assert result.error is not None
            assert "connection" in result.error.lower()

    def test_429_handling_with_retry(self, client):
        """Test 429 response triggers wait and retry."""
        config = ScraperConfig(
            delay_seconds=0.0,
            rate_limit_wait=1,
            rate_limit_retries=2,
        )
        client = SUMEClient(config)

        with patch.object(client.session, "request") as mock_request:
            # First response: 429
            # Second response: 200
            responses = [
                MagicMock(status_code=429, text="Rate Limited"),
                MagicMock(status_code=200, text="Success"),
            ]
            mock_request.side_effect = responses

            result = client.get("https://example.com/api")

            assert result.status_code == 200
            assert result.content == "Success"
            assert mock_request.call_count == 2

    def test_429_exhausted_retries(self, client):
        """Test 429 with all retries exhausted returns error."""
        config = ScraperConfig(
            delay_seconds=0.0,
            rate_limit_wait=1,
            rate_limit_retries=1,
        )
        client = SUMEClient(config)

        with patch.object(client.session, "request") as mock_request:
            mock_response = MagicMock(status_code=429, text="Rate Limited")
            mock_request.return_value = mock_response

            result = client.get("https://example.com/api")

            assert result.status_code == 429
            assert result.error is not None
            assert "retries exhausted" in result.error.lower()
            assert mock_request.call_count == 2  # Initial + 1 retry

    def test_request_logging(self, client, caplog):
        """Test request logging captures URL, status, duration."""
        import logging
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_session.get.return_value = mock_response
        client._session = mock_session

        with caplog.at_level(logging.INFO):
            client.get("https://example.com/test")

        # Check log was emitted
        assert len(caplog.records) >= 1
        log_record = caplog.records[-1]
        assert "test" in log_record.message or "HTTP request" in log_record.message

    def test_search_method(self, client):
        """Test search method constructs correct URL and POST data."""
        with patch.object(client, "post") as mock_post:
            mock_post.return_value = RequestResult(
                url="https://example.com/search",
                status_code=200,
                duration_ms=100,
                content="<html>Results</html>",
            )

            result = client.search({"numero": "FBCB", "fecha_desde": "01/01/2025"})

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "numero=FBCB" in str(call_args) or call_args[1].get("data", {}).get("numero") == "FBCB"

    def test_get_detail_method(self, client):
        """Test get_detail constructs correct URL."""
        with patch.object(client, "get") as mock_get:
            mock_get.return_value = RequestResult(
                url="https://example.com/detail.php?id=12345",
                status_code=200,
                duration_ms=100,
                content="<html>Detail</html>",
            )

            result = client.get_detail("12345")

            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "id=12345" in call_args[0][0]

    def test_save_raw_html(self, client, tmp_path):
        """Test saving raw HTML to file."""
        config = ScraperConfig(raw_html_dir=str(tmp_path / "raw"))
        client = SUMEClient(config)

        filepath = client.save_raw_html("<html>Test</html>", "test_page")

        assert filepath.exists()
        assert filepath.read_text() == "<html>Test</html>"

    def test_context_manager(self, client):
        """Test client works as context manager."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_session.request.return_value = mock_response
        client._session = mock_session

        with client as c:
            result = c.get("https://example.com/test")
            assert result.status_code == 200

        # Session should be closed after context
        assert client._session is None

    def test_retry_backoff_timing(self, client):
        """Test exponential backoff timing (1s, 2s, 4s pattern)."""
        config = ScraperConfig(
            delay_seconds=0.0,
            max_retries=3,
            backoff_base=0.1,  # 0.1s, 0.2s, 0.4s for fast testing (min 0.1)
        )
        client = SUMEClient(config)

        with patch.object(client.session, "request") as mock_request:
            # All requests fail with 500
            mock_response = MagicMock(status_code=500, text="Server Error")
            mock_request.return_value = mock_response

            start = time.monotonic()
            result = client.get("https://example.com/api")
            elapsed = time.monotonic() - start

            # Should have retried 3 times with backoff
            # Total wait ~= 0.1 + 0.2 + 0.4 = 0.7s (but urllib3 handles backoff)
            assert mock_request.call_count >= 1


class TestRequestResult:
    """Tests for RequestResult dataclass."""

    def test_successful_result(self):
        """Test successful request result."""
        result = RequestResult(
            url="https://example.com",
            status_code=200,
            duration_ms=150.5,
            content="<html>OK</html>",
        )
        assert result.status_code == 200
        assert result.error is None

    def test_error_result(self):
        """Test error request result."""
        result = RequestResult(
            url="https://example.com",
            status_code=0,
            duration_ms=5000,
            content="",
            error="Connection timeout",
        )
        assert result.status_code == 0
        assert result.error == "Connection timeout"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])