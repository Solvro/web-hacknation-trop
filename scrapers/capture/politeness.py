"""Per-registrable-domain politeness budget (token bucket in domain_budgets) + circuit breaker.

Defaults: 6 captures/hour/eTLD+1, at most one in flight per eTLD+1 (worker-level lock), and after
3 consecutive failures a cooldown of 1 h doubling up to 24 h. Scam hosts are short-lived and
rate-limit or ban aggressive visitors (and burn the cloaker's 'good visitor' decision), so being
gentle also keeps captures representative.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def acquire(conn, etld1: str, cost: float = 1.0) -> tuple[bool, float]:
    """-> (allowed, seconds_to_wait)."""
    with conn.transaction():
        conn.execute("INSERT INTO domain_budgets (etld1) VALUES (%s) ON CONFLICT DO NOTHING", (etld1,))
        max_h, tokens, refilled, cooldown = conn.execute(
            "SELECT max_per_hour, tokens, refilled_at, cooldown_until FROM domain_budgets WHERE etld1 = %s FOR UPDATE",
            (etld1,)).fetchone()
        now = datetime.now(timezone.utc)
        if cooldown and cooldown > now:
            return False, (cooldown - now).total_seconds()
        tokens = min(float(max_h), tokens + (now - refilled).total_seconds() / 3600.0 * max_h)
        if tokens >= cost:
            conn.execute("UPDATE domain_budgets SET tokens = %s, refilled_at = %s, last_capture_at = %s WHERE etld1 = %s",
                         (tokens - cost, now, now, etld1))
            return True, 0.0
        conn.execute("UPDATE domain_budgets SET tokens = %s, refilled_at = %s WHERE etld1 = %s", (tokens, now, etld1))
        return False, (cost - tokens) / max_h * 3600.0


def report(conn, etld1: str, ok: bool) -> None:
    with conn.transaction():
        if ok:
            conn.execute("UPDATE domain_budgets SET consecutive_errors = 0, cooldown_until = NULL WHERE etld1 = %s", (etld1,))
            return
        n = conn.execute(
            "UPDATE domain_budgets SET consecutive_errors = consecutive_errors + 1 WHERE etld1 = %s RETURNING consecutive_errors",
            (etld1,)).fetchone()[0]
        if n >= 3:
            hours = min(24, 2 ** (n - 3))
            conn.execute("UPDATE domain_budgets SET cooldown_until = %s WHERE etld1 = %s",
                         (datetime.now(timezone.utc) + timedelta(hours=hours), etld1))
