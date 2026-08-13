"""Diagnostic probe: figure out why the council portal returns 403 in CI.

Run via the 'Portal Diagnostic' workflow (manual dispatch only). Prints the
response status, key headers and a body snippet for several request
strategies so we can tell a WAF challenge apart from an IP-reputation block.
"""

import requests

ROOT = "https://wav-wrp.whitespacews.com/"
MOP = "https://wav-wrp.whitespacews.com/mop.php?serviceID=A&seq=1"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Connection": "keep-alive",
}

INTERESTING_HEADERS = [
    "server", "cf-ray", "cf-mitigated", "x-cache", "via", "x-iinfo",
    "x-cdn", "x-sucuri-id", "set-cookie", "content-type", "retry-after",
    "x-amz-cf-id", "x-akamai-request-id", "location",
]


def report(label: str, resp: requests.Response) -> None:
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
    print(f"status: {resp.status_code}  final-url: {resp.url}")
    for h in INTERESTING_HEADERS:
        if h in resp.headers:
            print(f"  {h}: {resp.headers[h][:200]}")
    body = resp.text[:800].replace("\n", " ")
    print(f"body[:800]: {body}")


def probe(label: str, fn) -> None:
    try:
        report(label, fn())
    except Exception as e:  # noqa: BLE001 - diagnostic, report anything
        print(f"\n{'=' * 70}\n{label}\n{'=' * 70}\n  EXCEPTION: {type(e).__name__}: {e}")


def main() -> None:
    # 1. Bare request, no headers at all - the original failing behaviour.
    probe("1. bare requests.get(mop.php)", lambda: requests.get(MOP, timeout=20))

    # 2. User-Agent only - the fix that did not work.
    probe(
        "2. User-Agent only (mop.php)",
        lambda: requests.get(
            MOP, headers={"User-Agent": BROWSER_HEADERS["User-Agent"]}, timeout=20
        ),
    )

    # 3. Full browser header set - is a partial fingerprint the problem?
    probe(
        "3. full browser headers (mop.php)",
        lambda: requests.get(MOP, headers=BROWSER_HEADERS, timeout=20),
    )

    # 4. Site root rather than mop.php - the path HACS uses.
    probe(
        "4. full browser headers (site root)",
        lambda: requests.get(ROOT, headers=BROWSER_HEADERS, timeout=20),
    )

    # 5. Session: visit root first to pick up cookies, then mop.php with Referer.
    def session_flow():
        s = requests.Session()
        s.headers.update(BROWSER_HEADERS)
        r1 = s.get(ROOT, timeout=20)
        print(f"  [session] root status: {r1.status_code}, cookies: {s.cookies.get_dict()}")
        return s.get(MOP, headers={"Referer": ROOT}, timeout=20)

    probe("5. session: root -> mop.php with cookies + Referer", session_flow)


if __name__ == "__main__":
    main()
