"""User agent string rotation for web scraping."""

import random
from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# Common desktop browser user agents (updated regularly)
DESKTOP_USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",

    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",

    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",

    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",

    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",

    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",

    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

# Mobile browser user agents
MOBILE_USER_AGENTS = [
    # Chrome on Android
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.43 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.43 Mobile Safari/537.36",

    # Safari on iOS
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
]

# Bot user agents (for APIs that require identification)
BOT_USER_AGENTS = [
    "NewsScraperBot/1.0 (+https://example.com/bot)",
    "FinanceDataBot/1.0 (contact@example.com)",
]


class UserAgentRotator:
    """Rotates user agent strings for web requests."""

    def __init__(
        self,
        include_desktop: bool = True,
        include_mobile: bool = False,
        include_bot: bool = False,
        custom_agents: list[str] | None = None,
    ):
        """Initialize user agent rotator.

        Args:
            include_desktop: Include desktop browser agents
            include_mobile: Include mobile browser agents
            include_bot: Include bot identification agents
            custom_agents: Additional custom user agents
        """
        self.agents: list[str] = []

        if include_desktop:
            self.agents.extend(DESKTOP_USER_AGENTS)
        if include_mobile:
            self.agents.extend(MOBILE_USER_AGENTS)
        if include_bot:
            self.agents.extend(BOT_USER_AGENTS)
        if custom_agents:
            self.agents.extend(custom_agents)

        if not self.agents:
            self.agents = DESKTOP_USER_AGENTS.copy()

        self._use_counts: dict[str, int] = {ua: 0 for ua in self.agents}
        self._last_used: str = ""

    def get_random(self) -> str:
        """Get a random user agent.

        Returns:
            User agent string
        """
        agent = random.choice(self.agents)
        self._use_counts[agent] = self._use_counts.get(agent, 0) + 1
        self._last_used = agent
        return agent

    def get_least_used(self) -> str:
        """Get the least recently used user agent.

        Returns:
            User agent string
        """
        min_count = min(self._use_counts.values())
        least_used = [ua for ua, count in self._use_counts.items() if count == min_count]
        agent = random.choice(least_used)
        self._use_counts[agent] += 1
        self._last_used = agent
        return agent

    def get_next(self, avoid_last: bool = True) -> str:
        """Get next user agent, optionally avoiding the last one.

        Args:
            avoid_last: Whether to avoid returning the same agent twice in a row

        Returns:
            User agent string
        """
        available = self.agents.copy()

        if avoid_last and self._last_used and len(available) > 1:
            available = [ua for ua in available if ua != self._last_used]

        return self.get_random() if not avoid_last else random.choice(available)

    def get_for_domain(self, domain: str) -> str:
        """Get appropriate user agent for a domain.

        Some domains may require specific user agents.

        Args:
            domain: Target domain

        Returns:
            User agent string
        """
        domain_lower = domain.lower()

        # SEC requires identification
        if "sec.gov" in domain_lower:
            return BOT_USER_AGENTS[0] if BOT_USER_AGENTS else self.get_random()

        # Most sites prefer desktop browsers
        return self.get_random()

    def add_agent(self, user_agent: str) -> None:
        """Add a custom user agent.

        Args:
            user_agent: User agent string to add
        """
        if user_agent not in self.agents:
            self.agents.append(user_agent)
            self._use_counts[user_agent] = 0

    def remove_agent(self, user_agent: str) -> bool:
        """Remove a user agent.

        Args:
            user_agent: User agent string to remove

        Returns:
            True if removed
        """
        if user_agent in self.agents:
            self.agents.remove(user_agent)
            self._use_counts.pop(user_agent, None)
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get usage statistics.

        Returns:
            Stats dictionary
        """
        return {
            "total_agents": len(self.agents),
            "total_uses": sum(self._use_counts.values()),
            "usage_distribution": dict(sorted(
                self._use_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5]),  # Top 5
        }


# Global user agent rotator instance
_ua_rotator: UserAgentRotator | None = None


def get_user_agent_rotator() -> UserAgentRotator:
    """Get or create global user agent rotator."""
    global _ua_rotator
    if _ua_rotator is None:
        _ua_rotator = UserAgentRotator()
    return _ua_rotator


def get_random_user_agent() -> str:
    """Get a random user agent string.

    Convenience function for quick access.

    Returns:
        User agent string
    """
    return get_user_agent_rotator().get_random()
