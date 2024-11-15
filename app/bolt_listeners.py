import logging
import re

from dify_client import ChatClient
from slack_bolt import Ack, BoltContext, BoltResponse
from slack_bolt.request.payload_utils import is_event
from slack_sdk import WebClient

from app.dify_ops import (
    format_dify_message_content,
    get_answer_from_streaming_response,
    get_last_conversation_id,
)
from app.env import TRANSLATE_MARKDOWN
from app.markdown_conversion import slack_to_markdown
from app.slack_ops import (
    find_parent_message,
    is_this_app_mentioned,
    post_wip_message,
    update_wip_message,
)


def just_ack(ack: Ack):
    ack()


def get_user_message(payload: dict, bot_user_id: str) -> str:
    return re.sub(f"<@{bot_user_id}>\\s*", "", payload["text"])


def handle_response_error(
    logger: logging.Logger,
    client: WebClient,
    channel_id: str,
    thread_ts: str,
    user_id: str,
    error: Exception,
):
    logger.error(f"Failed to respond to app mention: {error}")
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text=f"<@{user_id}>\n申し訳ありませんが、エラーが発生しました。後ほどお試しください。",
    )


def respond_to_app_mention(
    context: BoltContext,
    payload: dict,
    client: WebClient,
    logger: logging.Logger,
):
    thread_ts = payload.get("thread_ts")
    if thread_ts:
        parent_message = find_parent_message(client, context.channel_id, thread_ts)
        if parent_message and is_this_app_mentioned(context, parent_message):
            return

    try:
        user_id = context.actor_user_id or context.user_id
        dify_client = ChatClient(context["DIFY_APP_API_KEY"])
        user_message = get_user_message(payload, context.bot_user_id)
        user_message = format_dify_message_content(user_message, TRANSLATE_MARKDOWN)

        if thread_ts:
            wip_reply = post_wip_message(
                client=client, channel=context.channel_id, thread_ts=thread_ts
            )
            latest_conversation_id = get_last_conversation_id(dify_client, thread_ts)
            messages_history = client.conversations_replies(
                channel=context.channel_id,
                ts=thread_ts,
                include_all_metadata=True,
                limit=1000,
            ).get("messages", [])

            if latest_conversation_id:
                response = dify_client.create_chat_message(
                    inputs={"slack_user_id": user_id},
                    query=user_message,
                    conversation_id=latest_conversation_id,
                    user=thread_ts.replace(".", "-"),
                    response_mode="streaming",
                )
            else:
                messages_fmt = "\n".join(
                    slack_to_markdown(msg["text"]) for msg in messages_history
                )
                query = f"{messages_fmt}\n{user_message}"
                response = dify_client.create_chat_message(
                    inputs={"slack_user_id": user_id},
                    query=query,
                    user=thread_ts.replace(".", "-"),
                    response_mode="streaming",
                )
        else:
            wip_reply = post_wip_message(
                client=client, channel=context.channel_id, thread_ts=payload.get("ts")
            )
            response = dify_client.create_chat_message(
                inputs={"slack_user_id": user_id},
                query=user_message,
                user=payload.get("ts").replace(".", "-"),
                response_mode="streaming",
            )

        response.raise_for_status()
        reply_message = get_answer_from_streaming_response(response)
        update_wip_message(
            client, context.channel_id, wip_reply["message"]["ts"], reply_message
        )

    except Exception as e:
        handle_response_error(
            logger, client, context.channel_id, payload.get("ts"), user_id, e
        )


def respond_to_new_message(
    context: BoltContext,
    payload: dict,
    client: WebClient,
    logger: logging.Logger,
):
    if payload.get("bot_id") and payload.get("bot_id") != context.bot_id:
        return

    try:
        is_in_dm_with_bot = payload.get("channel_type") == "im"
        thread_ts = payload.get("thread_ts")
        dify_client = ChatClient(context["DIFY_APP_API_KEY"])
        user_id = context.actor_user_id or context.user_id

        if not is_in_dm_with_bot and not thread_ts:
            return

        user_message = get_user_message(payload, context.bot_user_id)

        if is_in_dm_with_bot and not thread_ts:
            wip_reply = post_wip_message(
                client=client, channel=context.channel_id, thread_ts=payload.get("ts")
            )
            response = dify_client.create_chat_message(
                inputs={"slack_user_id": user_id},
                query=user_message,
                user=payload.get("ts").replace(".", "-"),
                response_mode="streaming",
            )
        else:
            wip_reply = post_wip_message(
                client=client, channel=context.channel_id, thread_ts=thread_ts
            )
            messages_in_context = client.conversations_replies(
                channel=context.channel_id,
                ts=thread_ts,
                include_all_metadata=True,
                limit=1000,
            ).get("messages", [])

            is_thread_for_this_app = any(
                message.get("ts") == thread_ts
                and is_this_app_mentioned(context, message)
                for message in messages_in_context
            )
            if not is_thread_for_this_app:
                return

            latest_conversation_id = get_last_conversation_id(dify_client, thread_ts)
            user_message = format_dify_message_content(user_message, TRANSLATE_MARKDOWN)

            if latest_conversation_id:
                response = dify_client.create_chat_message(
                    inputs={"slack_user_id": user_id},
                    query=user_message,
                    conversation_id=latest_conversation_id,
                    user=thread_ts.replace(".", "-"),
                    response_mode="streaming",
                )
            else:
                response = dify_client.create_chat_message(
                    inputs={"slack_user_id": user_id},
                    query=user_message,
                    user=thread_ts.replace(".", "-"),
                    response_mode="streaming",
                )

        response.raise_for_status()
        reply_message = get_answer_from_streaming_response(response)
        update_wip_message(
            client, context.channel_id, wip_reply["message"]["ts"], reply_message
        )

    except Exception as e:
        handle_response_error(
            logger, client, context.channel_id, payload.get("ts"), user_id, e
        )


def register_listeners(app):
    app.event("app_mention")(ack=just_ack, lazy=[respond_to_app_mention])
    app.event("message")(ack=just_ack, lazy=[respond_to_new_message])


MESSAGE_SUBTYPES_TO_SKIP = ["message_changed", "message_deleted"]


# To reduce unnecessary workload in this app,
# this before_authorize function skips message changed/deleted events.
# Especially, "message_changed" events can be triggered many times when the app rapidly updates its reply.
def before_authorize(
    body: dict,
    payload: dict,
    logger: logging.Logger,
    next_,
):
    if (
        is_event(body)
        and payload.get("type") == "message"
        and payload.get("subtype") in MESSAGE_SUBTYPES_TO_SKIP
    ):
        logger.debug(
            "Skipped the following middleware and listeners "
            f"for this message event (subtype: {payload.get('subtype')})"
        )
        return BoltResponse(status=200, body="")
    next_()
