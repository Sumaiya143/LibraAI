"""Validate and canonicalize the public HTTPS origin used in payment callbacks."""
import ipaddress
import re
from urllib.parse import urlsplit

from payment_providers import GatewayError

_DNS_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
# Special-use names are not suitable as public payment callback origins.
_RESERVED_SUFFIXES = (
    ".test", ".invalid", ".example", ".localhost", ".local",
    ".internal", ".onion", ".home.arpa", ".lan",
)
_RESERVED_HOSTS = {"test", "invalid", "example", "localhost", "local", "internal", "onion", "lan"}


def _public_hostname(host: str) -> str:
    """Return a canonical public host, rejecting local/reserved address literals."""
    if not host or host.endswith(".") or "%" in host:
        raise GatewayError("Public URL must use a canonical public hostname")

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None:
        if not address.is_global:
            raise GatewayError("Payment callbacks cannot use a non-public IP address")
        return f"[{address.compressed}]" if address.version == 6 else str(address)

    try:
        ascii_host = host.encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError) as exc:
        raise GatewayError("Invalid public hostname") from exc
    if len(ascii_host) > 253:
        raise GatewayError("Invalid public hostname")
    labels = ascii_host.split(".")
    if ascii_host in _RESERVED_HOSTS or any(
        ascii_host.endswith(suffix) for suffix in _RESERVED_SUFFIXES
    ):
        raise GatewayError("Payment callbacks cannot use a reserved or internal hostname")
    if len(labels) < 2 or any(
        len(label) > 63 or not _DNS_LABEL.fullmatch(label) for label in labels
    ):
        raise GatewayError("Public URL must use a valid fully-qualified hostname")
    if all(label.isdigit() for label in labels):
        raise GatewayError("Invalid numeric hostname")
    if ascii_host in ("localhost", "localhost.localdomain"):
        raise GatewayError("Payment callbacks cannot use a local hostname")
    return ascii_host


def validate_public_origin(value):
    """Accept only a canonical HTTPS origin suitable for payment callback URLs.

    Paths, credentials, query strings, fragments, non-default ports, malformed DNS
    names, and non-public IP literals are rejected before any gateway request starts.
    """
    if not isinstance(value, str) or not value or value != value.strip() or "\\" in value:
        raise GatewayError("Public URL must be a canonical HTTPS origin")
    try:
        parsed = urlsplit(value)
        port = parsed.port  # Invalid ports raise ValueError.
    except ValueError as exc:
        raise GatewayError("Invalid public URL") from exc

    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or (port is not None and port != 443)
    ):
        raise GatewayError("Public URL must be a public HTTPS origin")

    host = _public_hostname(parsed.hostname)
    return "https://" + host
