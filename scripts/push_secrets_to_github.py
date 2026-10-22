"""
HymnFlow — Auto-push .env secrets to GitHub Actions
Reads your local .env and uploads every key as a GitHub Actions secret.
No clicking required.

Run with: python scripts/push_secrets_to_github.py
"""

import os
import sys
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
GITHUB_TOKEN  = os.getenv("GITHUB_PAT", "")
REPO_OWNER    = "Oko300"
REPO_NAME     = "HymnFlow"
API_BASE      = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept":        "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# ── Secrets to upload (name → value from .env) ────────────────────────────────
SECRETS = {
    "GEMINI_API_KEYS":    os.getenv("GEMINI_API_KEYS",    ""),
    "SUPABASE_URL":       os.getenv("SUPABASE_URL",       ""),
    "SUPABASE_KEY":       os.getenv("SUPABASE_KEY",       ""),
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "TELEGRAM_CHAT_ID":   os.getenv("TELEGRAM_CHAT_ID",   ""),
    "PIXABAY_API_KEY":    os.getenv("PIXABAY_API_KEY",    ""),
    "PEXELS_API_KEY":     os.getenv("PEXELS_API_KEY",     ""),
    "FLASK_SECRET_KEY":   os.getenv("FLASK_SECRET_KEY",   "hymnflow-prod-secret-2026"),
    "TTS_VOICE_NAME":     os.getenv("TTS_VOICE_NAME",     "en-US-MichelleNeural"),
    "TTS_SPEAKING_RATE":  os.getenv("TTS_SPEAKING_RATE",  "+0%"),
    "TTS_PITCH":          os.getenv("TTS_PITCH",          "-2Hz"),
}


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """Encrypt secret using the repo's RSA public key (libsodium sealed box)."""
    from nacl import encoding, public as nacl_public
    pk = nacl_public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed = nacl_public.SealedBox(pk)
    encrypted = sealed.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def get_repo_public_key():
    """Fetch the repo's Actions public key for secret encryption."""
    resp = requests.get(f"{API_BASE}/actions/secrets/public-key", headers=HEADERS)
    if resp.status_code != 200:
        print(f"  FAIL: Could not get public key — HTTP {resp.status_code}")
        print(f"  {resp.text[:200]}")
        sys.exit(1)
    data = resp.json()
    return data["key_id"], data["key"]


def set_secret(name: str, value: str, key_id: str, public_key: str):
    """Create or update a single GitHub Actions secret."""
    if not value:
        print(f"  SKIP: {name} (empty — not in .env)")
        return False

    encrypted = encrypt_secret(public_key, value)
    payload = {
        "encrypted_value": encrypted,
        "key_id":          key_id,
    }
    url  = f"{API_BASE}/actions/secrets/{name}"
    resp = requests.put(url, headers=HEADERS, json=payload)

    if resp.status_code in (201, 204):
        preview = value[:6] + "..." if len(value) > 6 else value
        print(f"  [OK] {name}  ({preview})")
        return True
    else:
        print(f"  [FAIL] {name}  -- HTTP {resp.status_code}: {resp.text[:120]}")
        return False


if __name__ == "__main__":
    print("=" * 55)
    print("  HymnFlow — GitHub Actions Secret Uploader")
    print(f"  Repo: {REPO_OWNER}/{REPO_NAME}")
    print("=" * 55)

    print("\nFetching repo encryption key...")
    key_id, public_key = get_repo_public_key()
    print(f"  Got key_id: {key_id[:12]}...")

    print("\nUploading secrets:")
    ok = 0
    for name, value in SECRETS.items():
        if set_secret(name, value, key_id, public_key):
            ok += 1

    print(f"\n{'='*55}")
    print(f"  {ok}/{len(SECRETS)} secrets uploaded to GitHub Actions")
    if ok == len([v for v in SECRETS.values() if v]):
        print("\n  DONE! Your pipeline is ready to run.")
        print(f"  Check: https://github.com/{REPO_OWNER}/{REPO_NAME}/settings/secrets/actions")
    print("=" * 55)
