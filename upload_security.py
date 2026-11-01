"""Upload safety checks with optional ClamAV INSTREAM scanning.

This module is intentionally dependency-free. Configure LIBRAAI_CLAMAV_HOST and
LIBRAAI_CLAMAV_PORT to use a local/private ClamAV daemon. Set
LIBRAAI_REQUIRE_MALWARE_SCAN=1 to reject uploads whenever the scanner is not
available; the default remains compatible with local development and reports
that content was not scanned rather than claiming it was clean.
"""
from __future__ import annotations

import os
import socket
import struct

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
CHUNK_SIZE = 64 * 1024


def _magic_ok(filename: str, payload: bytes) -> bool:
    ext = os.path.splitext(filename.replace('\\', '/').rsplit('/', 1)[-1])[1].lower()
    if not payload:
        return False
    checks = {
        '.pdf': lambda b: b.startswith(b'%PDF-'),
        '.png': lambda b: b.startswith(b'\x89PNG\r\n\x1a\n'),
        '.jpg': lambda b: b.startswith(b'\xff\xd8\xff'),
        '.jpeg': lambda b: b.startswith(b'\xff\xd8\xff'),
        '.webp': lambda b: len(b) >= 12 and b[:4] == b'RIFF' and b[8:12] == b'WEBP',
        '.epub': lambda b: b.startswith(b'PK\x03\x04'),
        '.cbz': lambda b: b.startswith((b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08')),
        '.mp3': lambda b: b.startswith(b'ID3') or (len(b) >= 2 and b[0] == 0xff and (b[1] & 0xe0) == 0xe0),
        '.wav': lambda b: len(b) >= 12 and b[:4] == b'RIFF' and b[8:12] == b'WAVE',
        '.ogg': lambda b: b.startswith(b'OggS'),
        '.oga': lambda b: b.startswith(b'OggS'),
        '.opus': lambda b: b.startswith(b'OggS'),
        '.flac': lambda b: b.startswith(b'fLaC'),
        '.m4a': lambda b: len(b) >= 12 and b[4:8] == b'ftyp',
        '.aac': lambda b: len(b) >= 2 and b[0] == 0xff and (b[1] & 0xf6) == 0xf0,
        '.webm': lambda b: b.startswith(b'\x1aE\xdf\xa3'),
    }
    check = checks.get(ext)
    return check(payload) if check else True


def _clamav_scan(payload: bytes) -> tuple[str, str]:
    host = os.getenv('LIBRAAI_CLAMAV_HOST', '').strip()
    if not host:
        return 'unavailable', 'ClamAV is not configured.'
    try:
        port = int(os.getenv('LIBRAAI_CLAMAV_PORT', '3310'))
        timeout = max(0.2, min(10.0, float(os.getenv('LIBRAAI_CLAMAV_TIMEOUT', '3'))))
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(b'zINSTREAM\0')
            for offset in range(0, len(payload), CHUNK_SIZE):
                chunk = payload[offset:offset + CHUNK_SIZE]
                sock.sendall(struct.pack('!I', len(chunk)) + chunk)
            sock.sendall(struct.pack('!I', 0))
            response = bytearray()
            while len(response) < 4096:
                part = sock.recv(1024)
                if not part:
                    break
                response.extend(part)
                if b'\0' in part or b'\n' in part:
                    break
        message = response.decode('utf-8', 'replace').strip('\0\r\n ')
        if 'FOUND' in message:
            return 'infected', message[:300]
        if 'OK' in message:
            return 'clean', message[:300]
        return 'unavailable', 'ClamAV returned an unrecognized response.'
    except (OSError, ValueError) as exc:
        return 'unavailable', f'ClamAV scan failed: {type(exc).__name__}.'


def inspect_upload(filename: str, payload: bytes) -> tuple[bool, str, str]:
    """Return (accepted, scan_status, message); callers must not store rejected bytes."""
    if not payload:
        return False, 'rejected', 'The uploaded file is empty.'
    if EICAR in payload:
        return False, 'infected', 'Known antivirus test signature detected.'
    if not _magic_ok(filename, payload):
        return False, 'invalid', 'File content does not match its filename extension.'
    status, message = _clamav_scan(payload)
    if status == 'infected':
        return False, status, 'Malware detected; upload rejected.'
    if status == 'unavailable' and os.getenv('LIBRAAI_REQUIRE_MALWARE_SCAN', '0').strip().lower() in ('1', 'true', 'yes', 'on'):
        return False, status, 'Malware scanner is required but unavailable; upload rejected.'
    if status == 'unavailable':
        return True, 'not_scanned', message
    return True, 'clean', 'ClamAV scan passed.'
