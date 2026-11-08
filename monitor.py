import asyncio
import json
import os
import sys
from pathlib import Path

from TikTokLive import TikTokLiveClient
from TikTokLive.client.errors import UserNotFoundError

USERNAME = "Kenny_ctmd"
STATE_FILE = Path("live_state.json")
LIVE_URL = f"https://www.tiktok.com/@{USERNAME}/live"


def send_botghost_notification() -> None:
    webhook_url = os.environ.get("BOTGHOST_WEBHOOK")
    api_key = os.environ.get("BOTGHOST_API_KEY")

    if not webhook_url or not api_key:
        raise RuntimeError("Missing BOTGHOST_WEBHOOK or BOTGHOST_API_KEY GitHub secret.")

    message = (
        f"🔴 **Kenny is LIVE on TikTok!**\n"
        f"{LIVE_URL}"
    )

    response = requests.post(
        webhook_url,
        headers={
            "Authorization": api_key,
            "Content-Type": "application/json",
        },
        json={
            "variables": [
                {
                    "name": "message",
                    "variable": "{event_message}",
                    "value": message,
                }
            ]
        },
        timeout=20,
    )

    if not response.ok:
        raise RuntimeError(
            f"BotGhost returned HTTP {response.status_code}: {response.text[:300]}"
        )

    print("BotGhost webhook accepted the LIVE notification.")


async def check_live_status(client: TikTokLiveClient) -> bool:
    """Check by username first, then resolve the public LIVE page to a room ID."""
    try:
        return await client.is_live()
    except UserNotFoundError as original_error:
        print(
            "TikTok's username status endpoint rejected this account. "
            "Trying TikTokLive's documented LIVE-page room-ID route."
        )
        try:
            room_id = await client.web.fetch_room_id_from_html(USERNAME)
            return await client.web.fetch_is_live(room_id=int(room_id))
        except Exception as fallback_error:
            raise RuntimeError(
                "Both TikTok LIVE checks failed. "
                f"Username check: {original_error}. "
                f"LIVE-page room-ID check: {fallback_error}"
            ) from fallback_error

async def main() -> None:
    client = TikTokLiveClient(unique_id=f"@{USERNAME}")

    try:
        is_live = await check_live_status(client)
    except Exception as exc:
        raise RuntimeError(f"TikTok LIVE status check failed: {exc}") from exc
    finally:
        await client.web.close()

    previous_state = None
    if STATE_FILE.exists():
        try:
            previous_state = json.loads(STATE_FILE.read_text(encoding="utf-8")).get("state")
        except (json.JSONDecodeError, OSError):
            print("Previous state file was unreadable; treating this as the first check.")

    current_state = "live" if is_live else "offline"
    print(f"@{USERNAME} is currently {current_state}.")

    # Notify only when transitioning from offline to live.
    # On the first successful run, notify if the creator is already live.
    if is_live and previous_state != "live":
        send_botghost_notification()

    STATE_FILE.write_text(
        json.dumps({"state": current_state}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
