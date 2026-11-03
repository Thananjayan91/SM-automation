"""Security service — SSRF protection, URL validation, and media upload checks."""
import ipaddress
import socket
from urllib.parse import urlparse
from typing import Optional

from PIL import Image

# Blocked private and reserved network ranges
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
ALLOWED_IMAGE_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB
MAX_IMAGE_DIMENSION = 8192


def validate_url_safe(url: str) -> tuple[bool, Optional[str]]:
    """Validate that a URL is well-formed and does not target internal or private networks (SSRF defense).

    Returns (is_safe, error_message).
    """
    if not url or not isinstance(url, str):
        return False, "URL is required."

    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Malformed URL."

    if parsed.scheme not in ("http", "https"):
        return False, "Only HTTP and HTTPS URLs are permitted."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL must include a valid hostname."

    # Prevent localhost aliases
    if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return False, "Access to localhost or loopback addresses is blocked."

    # Resolve IP addresses
    try:
        resolved_ips = socket.getaddrinfo(hostname, parsed.port or 80, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False, f"Could not resolve host '{hostname}'."
    except Exception as exc:
        return False, f"Failed resolving hostname: {exc}"

    for entry in resolved_ips:
        sockaddr = entry[4]
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            for net in _BLOCKED_NETWORKS:
                if ip_obj in net:
                    return False, f"Access to IP address {ip_str} ({net}) is blocked for security."
        except ValueError:
            return False, f"Invalid resolved IP: {ip_str}"

    return True, None


def validate_uploaded_image(file_storage) -> tuple[bool, Optional[str], Optional[dict]]:
    """Validate an uploaded image file for extension, MIME, size, and integrity.

    Returns (is_valid, error_message, metadata_dict).
    """
    if not file_storage or not file_storage.filename:
        return False, "No file provided.", None

    filename = file_storage.filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return False, f"File format '.{ext}' is not supported. Use JPG, PNG, WEBP, or GIF.", None

    # Check content length if available
    file_storage.seek(0, 2)
    size_bytes = file_storage.tell()
    file_storage.seek(0)

    if size_bytes == 0:
        return False, "The uploaded file is empty.", None

    if size_bytes > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        return False, f"File exceeds the maximum allowed size of {max_mb} MB.", None

    # Verify image integrity with Pillow
    try:
        with Image.open(file_storage) as img:
            img.verify()
            width, height = img.size
            img_format = (img.format or "JPEG").lower()
    except Exception:
        return False, "The uploaded file is not a valid or readable image.", None

    # Rewind stream after verify
    file_storage.seek(0)

    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        return False, f"Image dimensions ({width}x{height}) exceed maximum allowed ({MAX_IMAGE_DIMENSION}px).", None

    # Re-detect MIME
    mime = file_storage.mimetype
    if mime not in ALLOWED_IMAGE_MIMES:
        mime = f"image/{img_format}"

    metadata = {
        "filename": filename,
        "extension": ext,
        "mime_type": mime,
        "size_bytes": size_bytes,
        "width": width,
        "height": height,
    }
    return True, None, metadata


def get_credential_fernet():
    """Derive a consistent 32-byte Fernet key from configuration."""
    import base64
    import hashlib
    from cryptography.fernet import Fernet
    from flask import current_app

    raw_key = "default-dev-encryption-key-for-credentials"
    if current_app:
        raw_key = (
            current_app.config.get("CREDENTIAL_ENCRYPTION_KEY")
            or current_app.config.get("SECRET_KEY")
            or raw_key
        )
    derived = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode("utf-8")).digest())
    return Fernet(derived)


def encrypt_credential(plain_text: Optional[str]) -> Optional[str]:
    """Encrypt sensitive tokens at rest using AES-128-CBC authenticated encryption."""
    if not plain_text:
        return None
    fernet = get_credential_fernet()
    return fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_credential(cipher_text: Optional[str]) -> Optional[str]:
    """Decrypt sensitive access tokens."""
    if not cipher_text:
        return None
    try:
        fernet = get_credential_fernet()
        return fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except Exception:
        return None

