import uuid
from typing import Optional

import requests
from slack_bolt import BoltContext
from slack_sdk.errors import SlackApiError
from slack_sdk.web import SlackResponse, WebClient

from app.env import IMAGE_FILE_ACCESS_ENABLED
from app.markdown_conversion import markdown_to_slack, slack_to_markdown

# ----------------------------
# Messages
# ----------------------------

DEFAULT_LOADING_TEXT = ":hourglass_flowing_sand: しばらくお待ちください..."


# ----------------------------
# General operations in a channel
# ----------------------------


def find_parent_message(
    client: WebClient, channel_id: Optional[str], thread_ts: Optional[str]
) -> Optional[dict]:
    if channel_id is None or thread_ts is None:
        return None

    messages = client.conversations_history(
        channel=channel_id,
        latest=thread_ts,
        limit=1,
        inclusive=True,
    ).get("messages", [])

    return messages[0] if len(messages) > 0 else None


def is_this_app_mentioned(context: BoltContext, parent_message: dict) -> bool:
    parent_message_text = parent_message.get("text", "")
    return f"<@{context.bot_user_id}>" in parent_message_text


def build_thread_replies_as_combined_text(
    *,
    context: BoltContext,
    client: WebClient,
    channel: str,
    thread_ts: str,
) -> str:
    thread_content = ""
    for page in client.conversations_replies(
        channel=channel,
        ts=thread_ts,
        limit=1000,
    ):
        for reply in page.get("messages", []):
            user = reply.get("user")
            if user == context.bot_user_id:  # Skip replies by this app
                continue
            if user is None:
                bot_response = client.bots_info(bot=reply.get("bot_id"))
                user = bot_response.get("bot", {}).get("user_id")
                if user is None or user == context.bot_user_id:
                    continue
            text = slack_to_markdown("".join(reply["text"].splitlines()))
            thread_content += f"<@{user}>: {text}\n"
    return thread_content


# ----------------------------
# WIP reply message stuff
# ----------------------------


def post_wip_message(
    *,
    client: WebClient,
    channel: str,
    thread_ts: str,
    loading_text: str = DEFAULT_LOADING_TEXT,
) -> SlackResponse:
    return client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=markdown_to_slack(loading_text),
    )


def update_wip_message(
    client: WebClient,
    channel: str,
    ts: str,
    text: str,
) -> SlackResponse:
    return client.chat_update(
        channel=channel,
        ts=ts,
        text=markdown_to_slack(text),
    )


# ----------------------------
# Modals
# ----------------------------


def extract_state_value(payload: dict, block_id: str, action_id: str = "input") -> dict:
    state_values = payload["state"]["values"]
    return state_values[block_id][action_id]


# ----------------------------
# Files
# ----------------------------


def can_send_image_url_to_openai(context: BoltContext) -> bool:
    if IMAGE_FILE_ACCESS_ENABLED is False:
        return False
    bot_scopes = context.authorize_result.bot_scopes or []
    can_access_files = context and "files:read" in bot_scopes
    if can_access_files is False:
        return False

    openai_model = context.get("OPENAI_MODEL")
    # More supported models will come. This logic will need to be updated then.
    can_send_image_url = openai_model is not None and openai_model.startswith("gpt-4o")
    return can_send_image_url


def download_slack_image_content(
    image_url: str, image_name: str, bot_token: str
) -> str:
    response = requests.get(
        image_url,
        headers={"Authorization": f"Bearer {bot_token}"},
    )
    if response.status_code != 200:
        error = f"Request to {image_url} failed with status code {response.status_code}"
        raise SlackApiError(error, response)

    content_type = response.headers["content-type"]
    if content_type.startswith("text/html"):
        error = f"You don't have the permission to download this file: {image_url}"
        raise SlackApiError(error, response)

    if not content_type.startswith("image/"):
        error = f"The responded content-type is not for image data: {content_type}"
        raise SlackApiError(error, response)

    temp_path = f"/tmp/{uuid.uuid4()}-{image_name}"
    with open(temp_path, "wb") as f:
        f.write(response.content)

    return temp_path
