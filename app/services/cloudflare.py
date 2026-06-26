"""Async Cloudflare API client for Email Routing.

Only the minimum surface is used:
  * list zones (domains)
  * read email-routing status of a zone
  * list / create / delete routing rules
  * list verified destination addresses

Security: the API token is sent only in the Authorization header; it is never
logged, never echoed, never placed in callbacks. Errors raised here carry a
user-safe message (no tokens, no raw stack traces).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.utils.logger import get_logger

logger = get_logger(__name__)

CF_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareError(Exception):
    """Raised on a failed / unexpected Cloudflare API response."""

    def __init__(self, message: str, *, status: Optional[int] = None):
        super().__init__(message)
        self.user_message = message
        self.status = status


class CloudflareUnknownResult(CloudflareError):
    """Raised when a create/delete may or may not have applied (e.g. timeout).

    The caller must verify the real state via a fresh list before retrying.
    """


@dataclass
class Zone:
    id: str
    name: str
    status: str


@dataclass
class RoutingRule:
    id: str
    email: str  # the 'to' literal matcher value (lowercased)
    destination: Optional[str]
    enabled: bool
    name: Optional[str] = None


class CloudflareClient:
    def __init__(
        self,
        api_token: str,
        account_id: str = "",
        *,
        timeout: float = 25.0,
        max_retries: int = 3,
    ) -> None:
        self._token = api_token
        self._account_id = account_id
        self._timeout = httpx.Timeout(timeout, connect=10.0)
        self._max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    # -- lifecycle -----------------------------------------------------------
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=CF_BASE,
                timeout=self._timeout,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    # -- low level -----------------------------------------------------------
    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
        retry_safe: bool = True,
    ) -> dict[str, Any]:
        client = await self._get_client()
        last_exc: Optional[Exception] = None
        attempts = self._max_retries if retry_safe else 1

        for attempt in range(1, attempts + 1):
            try:
                response = await client.request(method, path, params=params, json=json)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                # connection never established -> safe to retry any method
                last_exc = exc
                await asyncio.sleep(min(2 ** attempt, 8) * 0.5)
                continue
            except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as exc:
                # request may have been applied server-side
                if retry_safe:
                    last_exc = exc
                    await asyncio.sleep(min(2 ** attempt, 8) * 0.5)
                    continue
                raise CloudflareUnknownResult(
                    "Request to Cloudflare timed out. Status unknown."
                ) from exc
            except httpx.HTTPError as exc:
                last_exc = exc
                break

            # retry transient server errors / rate limit for idempotent calls
            if response.status_code in (429, 500, 502, 503, 504) and retry_safe:
                await asyncio.sleep(min(2 ** attempt, 8) * 0.5)
                last_exc = CloudflareError(
                    f"Cloudflare temporarily unavailable ({response.status_code}).",
                    status=response.status_code,
                )
                continue

            return self._parse(response)

        if isinstance(last_exc, CloudflareError):
            raise last_exc
        raise CloudflareError(
            "Could not connect to Cloudflare. Check connection / API token."
        ) from last_exc

    def _parse(self, response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except Exception:
            data = {}

        if response.status_code == 401 or response.status_code == 403:
            raise CloudflareError(
                "Cloudflare token rejected (401/403). The token needs "
                "'Zone > Email Routing Rules > Edit' (Edit, not just Read).",
                status=response.status_code,
            )

        if not isinstance(data, dict):
            raise CloudflareError(
                f"Invalid Cloudflare response (HTTP {response.status_code}).",
                status=response.status_code,
            )

        if not data.get("success", False):
            msg = self._first_error(data) or f"Cloudflare error (HTTP {response.status_code})."
            raise CloudflareError(msg, status=response.status_code)
        return data

    @staticmethod
    def _first_error(data: dict[str, Any]) -> str:
        errors = data.get("errors") or []
        if errors and isinstance(errors, list):
            first = errors[0]
            if isinstance(first, dict):
                code = first.get("code")
                message = first.get("message", "")
                return f"{message} (code {code})" if code else str(message)
        return ""

    # -- public API ----------------------------------------------------------
    async def verify(self) -> bool:
        """Lightweight connectivity check used by the dashboard status."""
        try:
            await self._request("GET", "/zones", params={"per_page": 1, "page": 1})
            return True
        except CloudflareError:
            return False

    async def list_zones(self) -> list[Zone]:
        zones: list[Zone] = []
        page = 1
        while True:
            data = await self._request(
                "GET", "/zones", params={"per_page": 50, "page": page}
            )
            for item in data.get("result", []) or []:
                zones.append(
                    Zone(
                        id=item.get("id", ""),
                        name=item.get("name", ""),
                        status=item.get("status", "unknown"),
                    )
                )
            info = data.get("result_info") or {}
            total_pages = info.get("total_pages", 1) or 1
            if page >= total_pages:
                break
            page += 1
        zones.sort(key=lambda z: z.name.lower())
        return zones

    async def get_email_routing_status(self, zone_id: str) -> dict[str, Any]:
        data = await self._request("GET", f"/zones/{zone_id}/email/routing")
        return data.get("result") or {}

    async def list_routing_rules(self, zone_id: str) -> list[RoutingRule]:
        rules: list[RoutingRule] = []
        page = 1
        while True:
            data = await self._request(
                "GET",
                f"/zones/{zone_id}/email/routing/rules",
                params={"per_page": 50, "page": page},
            )
            for item in data.get("result", []) or []:
                rule = self._parse_rule(item)
                if rule is not None:
                    rules.append(rule)
            info = data.get("result_info") or {}
            total_pages = info.get("total_pages", 1) or 1
            if page >= total_pages:
                break
            page += 1
        rules.sort(key=lambda r: r.email)
        return rules

    @staticmethod
    def _parse_rule(item: dict[str, Any]) -> Optional[RoutingRule]:
        matchers = item.get("matchers") or []
        to_value = None
        for matcher in matchers:
            if (
                isinstance(matcher, dict)
                and matcher.get("type") == "literal"
                and matcher.get("field") == "to"
            ):
                to_value = (matcher.get("value") or "").lower()
                break
        if not to_value:
            return None  # skip catch-all / non-literal rules
        destination = None
        for action in item.get("actions") or []:
            if isinstance(action, dict) and action.get("type") == "forward":
                values = action.get("value") or []
                if values:
                    destination = values[0]
                break
        return RoutingRule(
            id=item.get("id", ""),
            email=to_value,
            destination=destination,
            enabled=bool(item.get("enabled", True)),
            name=item.get("name"),
        )

    async def find_rule_by_email(
        self, zone_id: str, email: str
    ) -> Optional[RoutingRule]:
        email = email.lower()
        for rule in await self.list_routing_rules(zone_id):
            if rule.email == email:
                return rule
        return None

    async def create_routing_rule(
        self, zone_id: str, email: str, destination: str
    ) -> RoutingRule:
        email = email.lower()
        body = {
            "actions": [{"type": "forward", "value": [destination]}],
            "matchers": [{"type": "literal", "field": "to", "value": email}],
            "enabled": True,
            "name": f"bot:{email}",
        }
        # not auto-retried on read-timeout: caller verifies via list afterwards
        data = await self._request(
            "POST",
            f"/zones/{zone_id}/email/routing/rules",
            json=body,
            retry_safe=False,
        )
        result = data.get("result") or {}
        rule = self._parse_rule(result)
        if rule is None:
            rule = RoutingRule(
                id=result.get("id", ""),
                email=email,
                destination=destination,
                enabled=True,
            )
        return rule

    async def delete_routing_rule(self, zone_id: str, rule_id: str) -> None:
        await self._request(
            "DELETE",
            f"/zones/{zone_id}/email/routing/rules/{rule_id}",
            retry_safe=False,
        )

    async def list_destination_addresses(self) -> list[str]:
        if not self._account_id:
            return []
        try:
            data = await self._request(
                "GET", f"/accounts/{self._account_id}/email/routing/addresses"
            )
        except CloudflareError:
            return []
        addresses: list[str] = []
        for item in data.get("result", []) or []:
            email = item.get("email")
            verified = item.get("verified")
            if email and verified:
                addresses.append(email.lower())
        return addresses
