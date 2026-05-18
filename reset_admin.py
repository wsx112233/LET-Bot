from __future__ import annotations

import argparse
import json
import secrets

from app_config import DATA_DIR

ADMIN_AUTH_PATH = DATA_DIR / "admin_auth.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset LET Bot admin credentials.")
    parser.add_argument("--username", default="admin", help="Admin username")
    parser.add_argument("--password", default="", help="Admin password. Auto-generated if omitted.")
    args = parser.parse_args()

    username = args.username.strip() or "admin"
    password = args.password.strip() or secrets.token_urlsafe(18)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ADMIN_AUTH_PATH.write_text(
        json.dumps({"username": username, "password": password}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        ADMIN_AUTH_PATH.chmod(0o600)
    except OSError:
        pass

    print(f"LET_ADMIN_USERNAME={username}")
    print(f"LET_ADMIN_PASSWORD={password}")
    print("Admin credentials reset. Restart let_bot_admin to reload them.")


if __name__ == "__main__":
    main()
