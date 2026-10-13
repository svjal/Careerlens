import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict


PASSWORD_HASH_ITERATIONS = 600_000


def _encode_part(value: Dict[str, Any]) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode_part(value: str) -> Dict[str, Any]:
    padded = value + "=" * (-len(value) % 4)
    decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
    result = json.loads(decoded.decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("Invalid token data")
    return result


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS
    )
    salt_text = base64.urlsafe_b64encode(salt).decode("ascii")
    digest_text = base64.urlsafe_b64encode(digest).decode("ascii")
    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_HASH_ITERATIONS, salt_text, digest_text
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iteration_text, salt_text, expected_text = encoded_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iteration_text)
        if iterations < 1 or iterations > 2_000_000:
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(expected_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, UnicodeError):
        return False


def create_access_token(user_id: int, secret: str, expires_minutes: int) -> str:
    now = int(time.time())
    header = _encode_part({"alg": "HS256", "typ": "JWT"})
    payload = _encode_part({"sub": str(user_id), "iat": now, "exp": now + expires_minutes * 60})
    signed_value = header + "." + payload
    signature = hmac.new(secret.encode("utf-8"), signed_value.encode("ascii"), hashlib.sha256).digest()
    signature_text = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return signed_value + "." + signature_text


def read_access_token(token: str, secret: str) -> int:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token")
    header = _decode_part(parts[0])
    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        raise ValueError("Unsupported token")

    signed_value = parts[0] + "." + parts[1]
    expected = hmac.new(secret.encode("utf-8"), signed_value.encode("ascii"), hashlib.sha256).digest()
    expected_text = base64.urlsafe_b64encode(expected).rstrip(b"=").decode("ascii")
    if not hmac.compare_digest(expected_text, parts[2]):
        raise ValueError("Invalid signature")

    payload = _decode_part(parts[1])
    if int(payload["exp"]) <= int(time.time()):
        raise ValueError("Expired token")
    user_id = int(payload["sub"])
    if user_id < 1:
        raise ValueError("Invalid user")
    return user_id
