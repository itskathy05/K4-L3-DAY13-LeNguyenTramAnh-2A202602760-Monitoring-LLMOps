"""Create and exercise the Day 13 managed-prompt lifecycle in the configured project."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
from langfuse import get_client

from app.cli import configure_utf8_stdio

PROMPT_NAME = "day13-chat"
V1 = "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}"
V2 = V1 + "\nAnswer briefly and cite the relevant document when possible."


def _get_version(client, version: int):
    try:
        return client.get_prompt(
            PROMPT_NAME, version=version, type="text", cache_ttl_seconds=0,
            fetch_timeout_seconds=10, max_retries=0,
        )
    except Exception as exc:
        if getattr(exc, "status_code", None) == 404:
            return None
        raise


def _summary(client) -> None:
    for version in (1, 2):
        prompt = _get_version(client, version)
        if prompt is None:
            print(f"version={version} missing")
        else:
            print(f"version={version} exists labels={getattr(prompt, 'labels', [])}")
    for label in ("baseline", "candidate", "production"):
        try:
            prompt = client.get_prompt(
                PROMPT_NAME, label=label, type="text", cache_ttl_seconds=0,
                fetch_timeout_seconds=10, max_retries=0,
            )
            print(f"label={label} version={prompt.version}")
        except Exception as exc:
            if getattr(exc, "status_code", None) == 404:
                print(f"label={label} missing")
            else:
                raise


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["status", "bootstrap", "promote", "rollback"])
    args = parser.parse_args()
    load_dotenv(REPO_ROOT / ".env")
    client = get_client()
    if not client.auth_check():
        print("Langfuse credentials are invalid")
        return 1
    if args.action == "bootstrap":
        first = _get_version(client, 1)
        second = _get_version(client, 2)
        if first is not None or second is not None:
            print("Existing prompt versions found; bootstrap does not overwrite them.")
            _summary(client)
            return 1
        client.create_prompt(name=PROMPT_NAME, type="text", prompt=V1, labels=["baseline", "production"])
        client.create_prompt(name=PROMPT_NAME, type="text", prompt=V2, labels=["candidate"])
    elif args.action in {"promote", "rollback"}:
        target = 2 if args.action == "promote" else 1
        if _get_version(client, target) is None:
            print(f"Version {target} is missing; run bootstrap first.")
            return 1
        labels = ["candidate", "production"] if target == 2 else ["baseline", "production"]
        client.update_prompt(name=PROMPT_NAME, version=target, new_labels=labels)
    _summary(client)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
