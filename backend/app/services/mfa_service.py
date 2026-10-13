import time
import base64
import secrets
import struct
import hmac
import hashlib
from typing import Optional, List, Tuple
from urllib.parse import quote

class MFAService:
    """
    Standard RFC 6238 Time-Based One-Time Password (TOTP) and Recovery Code service.
    Engineered with zero external pip dependencies using Python standard library (hmac, hashlib, secrets).
    Compatible with Google Authenticator, Microsoft Authenticator, 1Password, and Authy.
    """

    @staticmethod
    def generate_mfa_secret() -> str:
        """Generate a cryptographically secure 160-bit (20 byte) Base32 secret."""
        raw = secrets.token_bytes(20)
        return base64.b32encode(raw).decode("utf-8").replace("=", "").strip()

    @staticmethod
    def get_totp_uri(secret: str, email: str, issuer: str = "NEXORA AI") -> str:
        """Construct standard otpauth:// URI for QR code generation."""
        clean_email = email.strip()
        encoded_issuer = quote(issuer)
        encoded_account = quote(f"{issuer}:{clean_email}")
        return f"otpauth://totp/{encoded_account}?secret={secret.upper()}&issuer={encoded_issuer}&algorithm=SHA1&digits=6&period=30"

    @classmethod
    def generate_totp_code(cls, secret: str, time_step: int = 30, for_time: Optional[float] = None) -> str:
        """Generate 6-digit TOTP code for the specified time (default: current time)."""
        if for_time is None:
            for_time = time.time()
        secret_cleaned = secret.upper().replace(" ", "")
        padding = "=" * ((8 - len(secret_cleaned) % 8) % 8)
        key = base64.b32decode(secret_cleaned + padding)
        counter = int(for_time // time_step)
        msg = struct.pack(">Q", counter)
        digest = hmac.new(key, msg, hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1000000
        return f"{code:06d}"

    @classmethod
    def verify_totp_code(cls, secret: str, code: str, time_step: int = 30, window: int = 1) -> bool:
        """
        Verify a 6-digit TOTP code against a secret with +/- window intervals tolerance (clock drift).
        Uses constant-time comparison to prevent timing attacks.
        """
        if not secret or not code:
            return False
        clean_code = code.strip().replace(" ", "").replace("-", "")
        if len(clean_code) != 6 or not clean_code.isdigit():
            return False
        
        now = time.time()
        for offset in range(-window, window + 1):
            expected = cls.generate_totp_code(secret, time_step=time_step, for_time=now + (offset * time_step))
            if hmac.compare_digest(expected, clean_code):
                return True
        return False

    @staticmethod
    def _hash_code(code: str) -> str:
        clean = code.strip().upper().replace(" ", "")
        return hashlib.sha256(clean.encode("utf-8")).hexdigest()

    @classmethod
    def generate_recovery_codes(cls, count: int = 8) -> Tuple[List[str], List[str]]:
        """
        Generate high-entropy, human-readable single-use backup recovery codes.
        Returns: (plaintext_codes_for_user, sha256_hashed_codes_for_database)
        """
        plain = []
        hashed = []
        chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ" # Exclude ambiguous characters (0, O, 1, I)
        for _ in range(count):
            part1 = "".join(secrets.choice(chars) for _ in range(4))
            part2 = "".join(secrets.choice(chars) for _ in range(4))
            code = f"{part1}-{part2}"
            plain.append(code)
            hashed.append(cls._hash_code(code))
        return plain, hashed

    @classmethod
    def verify_and_consume_recovery_code(cls, stored_hashes: List[str], submitted_code: str) -> Tuple[bool, List[str]]:
        """
        Verify submitted recovery code against stored hashes.
        If matched, consumes (removes) the code so it cannot be used again.
        Returns: (is_valid, remaining_hashes)
        """
        if not stored_hashes or not submitted_code:
            return False, stored_hashes
        
        target_hash = cls._hash_code(submitted_code)
        remaining = []
        matched = False
        for h in stored_hashes:
            if hmac.compare_digest(h, target_hash) and not matched:
                matched = True
            else:
                remaining.append(h)
        return matched, remaining

mfa_service = MFAService()
