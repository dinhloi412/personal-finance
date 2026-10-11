"""One place that knows how to open an HTTPS connection.

Three of this app's four feeds are plain `urllib` requests, and they need
different things from a TLS stack — which was discovered the hard way:

- Yahoo (through `yfinance`) and Fmarket and the FX feed verify happily against
  the system trust store.
- **BTMC, the Vietnamese gold shop, does not.** Its server does not send the
  intermediate certificate, so verification against the system store fails with
  `unable to get local issuer certificate` while `curl` — which fills the chain
  in from its own cache — succeeds. The same URL verifies against the `certifi`
  bundle, which is the Mozilla store and complete.

So every request goes through `open_url`, which prefers `certifi` when it is
installed and falls back to the platform default when it is not. The point is
that no caller has to know this: a new feed added later gets the working
behaviour by default rather than by remembering.
"""

from __future__ import annotations

import ssl
import urllib.request

#: Identifies the caller. Some of these are commercial services and a bare
#: `Python-urllib/3.13` in their logs helps nobody, including the operator
#: trying to work out what is hitting them.
USER_AGENT = "SoTaiSan/0.1 (personal asset tracker)"


def ssl_context() -> ssl.SSLContext | None:
    """The strictest context this machine can actually verify with.

    `certifi` first because it is complete; the platform bundle second because
    it is better than nothing; `None` last, which makes `urlopen` build its own
    default. None is not a fallback to "no verification" — it is the same
    verification the standard library would have done anyway.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001 — a missing bundle is not an error here
        return None


def open_url(request: urllib.request.Request, *, timeout: float):
    """`urllib.request.urlopen` with a working trust store and a user agent.

    Accepts either a URL string or a prepared `Request`; a plain string gets
    the user agent attached, and a prepared request keeps whatever headers its
    caller set.
    """
    if isinstance(request, str):
        request = urllib.request.Request(
            request, headers={"User-Agent": USER_AGENT}
        )
    elif not request.has_header("User-agent"):
        request.add_header("User-Agent", USER_AGENT)

    return urllib.request.urlopen(request, timeout=timeout, context=ssl_context())
