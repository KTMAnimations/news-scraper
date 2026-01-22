"""Proxy pool manager for rotating proxies."""

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class ProxyConfig:
    """Configuration for a single proxy."""

    url: str
    username: str = ""
    password: str = ""
    protocol: str = "http"

    # Health tracking
    is_healthy: bool = True
    last_used: datetime | None = None
    fail_count: int = 0
    success_count: int = 0
    avg_response_time: float = 0.0

    @property
    def full_url(self) -> str:
        """Get full proxy URL with auth."""
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.url}"
        return f"{self.protocol}://{self.url}"


@dataclass
class ProxyPool:
    """Pool of proxy configurations."""

    proxies: list[ProxyConfig] = field(default_factory=list)
    current_index: int = 0
    rotation_mode: str = "round_robin"  # round_robin, random, weighted


class ProxyManager:
    """Manager for proxy rotation and health checking."""

    # Max consecutive failures before marking unhealthy
    MAX_FAILURES = 5

    # Test URL for health checks
    TEST_URL = "https://httpbin.org/ip"

    def __init__(
        self,
        proxies: list[dict[str, str]] | None = None,
        rotation_mode: str = "round_robin",
        enable_health_check: bool = True,
    ):
        """Initialize proxy manager.

        Args:
            proxies: List of proxy configurations
            rotation_mode: How to select proxies (round_robin, random, weighted)
            enable_health_check: Whether to run health checks
        """
        self.pool = ProxyPool(rotation_mode=rotation_mode)
        self.enable_health_check = enable_health_check
        self._health_check_task: asyncio.Task | None = None

        # Initialize proxies
        if proxies:
            for proxy in proxies:
                self.add_proxy(**proxy)
        elif settings.proxy_enabled and settings.proxy_url:
            # Add default proxy from settings
            self.add_proxy(
                url=settings.proxy_url,
                username=settings.proxy_username,
                password=settings.proxy_password,
            )

    def add_proxy(
        self,
        url: str,
        username: str = "",
        password: str = "",
        protocol: str = "http",
    ) -> None:
        """Add a proxy to the pool.

        Args:
            url: Proxy URL (host:port)
            username: Proxy username
            password: Proxy password
            protocol: Protocol (http, https, socks5)
        """
        proxy = ProxyConfig(
            url=url,
            username=username,
            password=password,
            protocol=protocol,
        )
        self.pool.proxies.append(proxy)
        logger.info("Added proxy to pool", proxy=url, pool_size=len(self.pool.proxies))

    def remove_proxy(self, url: str) -> bool:
        """Remove a proxy from the pool.

        Args:
            url: Proxy URL to remove

        Returns:
            True if proxy was removed
        """
        for proxy in self.pool.proxies:
            if proxy.url == url:
                self.pool.proxies.remove(proxy)
                logger.info("Removed proxy from pool", proxy=url)
                return True
        return False

    def get_next_proxy(self) -> ProxyConfig | None:
        """Get the next available proxy.

        Returns:
            ProxyConfig or None if no healthy proxies
        """
        healthy_proxies = [p for p in self.pool.proxies if p.is_healthy]

        if not healthy_proxies:
            logger.warning("No healthy proxies available")
            return None

        if self.pool.rotation_mode == "random":
            proxy = random.choice(healthy_proxies)
        elif self.pool.rotation_mode == "weighted":
            # Weight by success rate
            weights = []
            for p in healthy_proxies:
                total = p.success_count + p.fail_count
                success_rate = p.success_count / total if total > 0 else 0.5
                weights.append(success_rate)

            proxy = random.choices(healthy_proxies, weights=weights)[0]
        else:
            # Round robin
            self.pool.current_index = (self.pool.current_index + 1) % len(healthy_proxies)
            proxy = healthy_proxies[self.pool.current_index]

        proxy.last_used = datetime.now(timezone.utc)
        return proxy

    def get_proxy_url(self) -> str | None:
        """Get the next proxy URL for httpx.

        Returns:
            Proxy URL string or None
        """
        proxy = self.get_next_proxy()
        return proxy.full_url if proxy else None

    def report_success(self, proxy_url: str, response_time: float = 0.0) -> None:
        """Report successful use of a proxy.

        Args:
            proxy_url: Proxy URL that was used
            response_time: Response time in seconds
        """
        for proxy in self.pool.proxies:
            if proxy.url == proxy_url or proxy.full_url == proxy_url:
                proxy.success_count += 1
                proxy.fail_count = 0  # Reset fail count
                proxy.is_healthy = True

                # Update average response time
                if proxy.avg_response_time > 0:
                    proxy.avg_response_time = (proxy.avg_response_time + response_time) / 2
                else:
                    proxy.avg_response_time = response_time

                break

    def report_failure(self, proxy_url: str, error: str = "") -> None:
        """Report failed use of a proxy.

        Args:
            proxy_url: Proxy URL that failed
            error: Error description
        """
        for proxy in self.pool.proxies:
            if proxy.url == proxy_url or proxy.full_url == proxy_url:
                proxy.fail_count += 1

                if proxy.fail_count >= self.MAX_FAILURES:
                    proxy.is_healthy = False
                    logger.warning(
                        "Proxy marked unhealthy",
                        proxy=proxy.url,
                        fail_count=proxy.fail_count,
                        error=error,
                    )

                break

    async def health_check(self, proxy: ProxyConfig) -> bool:
        """Check if a proxy is healthy.

        Args:
            proxy: ProxyConfig to check

        Returns:
            True if healthy
        """
        try:
            async with httpx.AsyncClient(proxy=proxy.full_url, timeout=10.0) as client:
                response = await client.get(self.TEST_URL)
                response.raise_for_status()

                proxy.is_healthy = True
                proxy.fail_count = 0
                return True

        except Exception as e:
            logger.warning("Proxy health check failed", proxy=proxy.url, error=str(e))
            proxy.fail_count += 1

            if proxy.fail_count >= self.MAX_FAILURES:
                proxy.is_healthy = False

            return False

    async def run_health_checks(self) -> dict[str, Any]:
        """Run health checks on all proxies.

        Returns:
            Health check results
        """
        results = {"healthy": 0, "unhealthy": 0, "proxies": []}

        for proxy in self.pool.proxies:
            is_healthy = await self.health_check(proxy)

            results["proxies"].append({
                "url": proxy.url,
                "healthy": is_healthy,
                "success_count": proxy.success_count,
                "fail_count": proxy.fail_count,
                "avg_response_time": proxy.avg_response_time,
            })

            if is_healthy:
                results["healthy"] += 1
            else:
                results["unhealthy"] += 1

        return results

    async def start_health_monitor(self, interval: float = 300.0) -> None:
        """Start background health monitoring.

        Args:
            interval: Seconds between health checks
        """
        if not self.enable_health_check:
            return

        async def monitor():
            while True:
                await self.run_health_checks()
                await asyncio.sleep(interval)

        self._health_check_task = asyncio.create_task(monitor())
        logger.info("Started proxy health monitor", interval=interval)

    def stop_health_monitor(self) -> None:
        """Stop background health monitoring."""
        if self._health_check_task:
            self._health_check_task.cancel()
            self._health_check_task = None
            logger.info("Stopped proxy health monitor")

    def get_pool_stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Pool stats dictionary
        """
        healthy = sum(1 for p in self.pool.proxies if p.is_healthy)
        total = len(self.pool.proxies)

        return {
            "total_proxies": total,
            "healthy_proxies": healthy,
            "unhealthy_proxies": total - healthy,
            "rotation_mode": self.pool.rotation_mode,
            "health_check_enabled": self.enable_health_check,
        }


# Global proxy manager instance
_proxy_manager: ProxyManager | None = None


def get_proxy_manager() -> ProxyManager:
    """Get or create global proxy manager."""
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager()
    return _proxy_manager
