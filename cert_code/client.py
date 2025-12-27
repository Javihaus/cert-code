"""
CERT API client for submitting code traces.

Handles:
- Authentication
- Trace submission
- Async batch submission
- Retry logic
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from cert_code.config import CertCodeConfig
from cert_code.models import CodeTrace

logger = logging.getLogger(__name__)


class CertAPIError(Exception):
    """Error from CERT API."""

    def __init__(self, status_code: int, message: str, details: dict[str, Any] | None = None):
        self.status_code = status_code
        self.message = message
        self.details = details or {}
        super().__init__(f"CERT API Error ({status_code}): {message}")


@dataclass
class SubmitResult:
    """Result of trace submission."""

    success: bool
    trace_id: str | None = None
    error: str | None = None
    evaluation: dict[str, Any] | None = None


class CertClient:
    """
    Client for CERT API.

    Usage:
        client = CertClient(config)
        result = client.submit(trace)

        # Or async
        async with CertAsyncClient(config) as client:
            result = await client.submit(trace)
    """

    def __init__(self, config: CertCodeConfig):
        self.config = config
        self._validate_config()

        self._client = httpx.Client(
            base_url=config.api_url,
            headers=self._build_headers(),
            timeout=30.0,
        )

    def _validate_config(self) -> None:
        """Validate required configuration."""
        if not self.config.api_key:
            raise ValueError(
                "CERT API key is required. "
                "Set CERT_CODE_API_KEY environment variable or configure in .cert-code.toml"
            )

    def _build_headers(self) -> dict[str, str]:
        """Build request headers."""
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "cert-code/0.1.0",
        }

    def submit(self, trace: CodeTrace) -> SubmitResult:
        """
        Submit a code trace to CERT.

        Args:
            trace: CodeTrace to submit

        Returns:
            SubmitResult with trace ID or error
        """
        # Apply project from config if not set
        if not trace.project_id and self.config.project_id:
            trace.project_id = self.config.project_id

        payload = trace.to_cert_trace()

        try:
            response = self._client.post("/traces", json=payload)

            if response.status_code == 401:
                raise CertAPIError(401, "Invalid API key")

            if response.status_code == 403:
                raise CertAPIError(403, "Access denied to project")

            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise CertAPIError(
                    response.status_code,
                    error_data.get("error", "Unknown error"),
                    error_data,
                )

            data = response.json()

            return SubmitResult(
                success=True,
                trace_id=data.get("id") or data.get("trace_id"),
                evaluation=data.get("evaluation"),
            )

        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}")
            return SubmitResult(
                success=False,
                error=f"Request failed: {e}",
            )
        except CertAPIError as e:
            logger.error(f"API error: {e}")
            return SubmitResult(
                success=False,
                error=str(e),
            )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> CertClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class CertAsyncClient:
    """Async version of CERT client."""

    def __init__(self, config: CertCodeConfig):
        self.config = config
        self._validate_config()

        self._client = httpx.AsyncClient(
            base_url=config.api_url,
            headers=self._build_headers(),
            timeout=30.0,
        )

    def _validate_config(self) -> None:
        if not self.config.api_key:
            raise ValueError(
                "CERT API key is required. "
                "Set CERT_CODE_API_KEY environment variable or configure in .cert-code.toml"
            )

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "cert-code/0.1.0",
        }

    async def submit(self, trace: CodeTrace) -> SubmitResult:
        """Submit a code trace asynchronously."""
        if not trace.project_id and self.config.project_id:
            trace.project_id = self.config.project_id

        payload = trace.to_cert_trace()

        try:
            response = await self._client.post("/traces", json=payload)

            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise CertAPIError(
                    response.status_code,
                    error_data.get("error", "Unknown error"),
                    error_data,
                )

            data = response.json()

            return SubmitResult(
                success=True,
                trace_id=data.get("id") or data.get("trace_id"),
                evaluation=data.get("evaluation"),
            )

        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}")
            return SubmitResult(success=False, error=f"Request failed: {e}")
        except CertAPIError as e:
            logger.error(f"API error: {e}")
            return SubmitResult(success=False, error=str(e))

    async def submit_batch(
        self,
        traces: list[CodeTrace],
        concurrency: int = 5,
    ) -> list[SubmitResult]:
        """Submit multiple traces with controlled concurrency."""
        semaphore = asyncio.Semaphore(concurrency)

        async def submit_with_semaphore(trace: CodeTrace) -> SubmitResult:
            async with semaphore:
                return await self.submit(trace)

        return await asyncio.gather(*[submit_with_semaphore(t) for t in traces])

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> CertAsyncClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
