"""Victim-context browser profiles.

Cloakers (Keitaro/TDS, kit A) decide per visit whether to show the offer or a decoy, based on UA
(mobile + in-app browser tokens), language, referrer (facebook link shim), the original click params
(fbclid, utm_*, ad ids) and IP reputation/geo. We emulate the *victim's context*; we do not defeat
challenges: a captcha / Turnstile / "Just a moment" page is recorded as cloak_verdict=blocked and the
capture stops there.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Profile:
    name: str
    user_agent: str
    viewport: tuple[int, int]
    device_scale_factor: float = 1.0
    is_mobile: bool = False
    has_touch: bool = False
    locale: str = "pl-PL"
    timezone: str = "Europe/Warsaw"
    referer: str | None = None
    accept_language: str = "pl-PL,pl;q=0.9,en-US;q=0.6,en;q=0.5"
    extra_headers: dict = field(default_factory=dict)


PROFILES: dict[str, Profile] = {
    # Facebook in-app browser on Android (where most PL scam-ad clicks happen)
    "fb_inapp_android_pl": Profile(
        name="fb_inapp_android_pl",
        user_agent=("Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/AP2A.240805.005; wv) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36 "
                    "[FB_IAB/FB4A;FBAV/489.0.0.53.111;]"),
        viewport=(412, 915), device_scale_factor=2.625, is_mobile=True, has_touch=True,
        referer="https://l.facebook.com/", extra_headers={"X-Requested-With": "com.facebook.katana"}),
    # Instagram in-app browser on iPhone (UA only — engine stays Chromium)
    "ig_inapp_ios_pl": Profile(
        name="ig_inapp_ios_pl",
        user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Mobile/22B83 Instagram 357.0.0.25.101 (iPhone15,2; iOS 18_1; pl_PL; pl; scale=3.00; 1179x2556; 655563285)"),
        viewport=(393, 852), device_scale_factor=3.0, is_mobile=True, has_touch=True,
        referer="https://l.instagram.com/"),
    "desktop_chrome_pl": Profile(
        name="desktop_chrome_pl",
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"),
        viewport=(1366, 768), referer="https://www.facebook.com/"),
    # deliberately bot-looking: capture it next to a victim profile to *measure* cloaking (content delta)
    "plain_headless": Profile(
        name="plain_headless", user_agent="", viewport=(1280, 800), locale="en-US", timezone="UTC",
        accept_language="en-US,en;q=0.9"),
}

# Minimal hygiene only (no fingerprint forgery): hide the automation flag that every cloaker checks first.
INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
"""

# Never fetch these (sandbox policy): executables / archives / installers.
BLOCKED_EXT = (".exe", ".msi", ".apk", ".dmg", ".pkg", ".scr", ".bat", ".cmd", ".ps1", ".vbs", ".jar",
               ".zip", ".rar", ".7z", ".iso", ".img")
