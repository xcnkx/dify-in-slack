import logging
import re
import time

from dify_client import ChatClient
from slack_bolt import Ack, BoltContext
from slack_sdk import WebClient

from app.dify_ops import format_dify_message_content, get_last_conversation_id
from app.env import TRANSLATE_MARKDOWN
from app.markdown_conversion import markdown_to_slack
from app.slack_ops import find_parent_message, is_this_app_mentioned


def just_ack(ack: Ack):
    ack()


def respond_to_app_mention(
    context: BoltContext,
    payload: dict,
    client: WebClient,
    logger: logging.Logger,
):
    thread_ts = payload.get("thread_ts")
    if thread_ts is not None:
        parent_message = find_parent_message(client, context.channel_id, thread_ts)
        if parent_message is not None and is_this_app_mentioned(
            context, parent_message
        ):
            # The message event handler will reply to this
            return

    try:
        user_id = context.actor_user_id or context.user_id
        # Mentioning the bot user in a thread
        dify_client = ChatClient(context["DIFY_APP_API_KEY"])
        if thread_ts is not None:
            latest_conversation_id = get_last_conversation_id(dify_client, thread_ts)

            user_message = re.sub(f"<@{context.bot_user_id}>\\s*", "", payload["text"])
            user_message = format_dify_message_content(
                payload.get("text"), TRANSLATE_MARKDOWN
            )

            if latest_conversation_id is not None:
                response = dify_client.create_chat_message(
                    inputs={"slack_user_id": user_id},
                    query=user_message,
                    conversation_id=latest_conversation_id,
                    user=thread_ts.replace(".", "-"),
                )
                response.raise_for_status()

            else:
                response = dify_client.create_chat_message(
                    inputs={"slack_user_id": user_id},
                    query=user_message,
                    user=thread_ts.replace(".", "-"),
                )
                response.raise_for_status()

            reply_message = response.json()["answer"]
            client.chat_postMessage(
                channel=context.channel_id,
                thread_ts=thread_ts,
                text=markdown_to_slack(reply_message),
            )
        else:
            user_message = re.sub(f"<@{context.bot_user_id}>\\s*", "", payload["text"])
            response = dify_client.create_chat_message(
                inputs={"slack_user_id": user_id},
                query=user_message,
                user=payload.get("ts").replace(".", "-"),
            )
            response.raise_for_status()

            reply_message = response.json()["answer"]
            client.chat_postMessage(
                channel=context.channel_id,
                thread_ts=payload.get("ts"),
                text=markdown_to_slack(reply_message),
            )
    except Exception as e:
        logger.error(f"Failed to respond to app mention: {e}")

        client.chat_postMessage(
            channel=context.channel_id,
            thread_ts=payload.get("ts"),
            text=f"<@{user_id}>\nSorry, I failed to respond to your message. Please try again later.",
        )


def respond_to_new_message(
    context: BoltContext,
    payload: dict,
    client: WebClient,
    logger: logging.Logger,
):
    if payload.get("bot_id") is not None and payload.get("bot_id") != context.bot_id:
        # Skip a new message by a different app
        return

    try:
        is_in_dm_with_bot = payload.get("channel_type") == "im"
        thread_ts = payload.get("thread_ts")
        dify_client = ChatClient(context["DIFY_APP_API_KEY"])
        user_id = context.actor_user_id or context.user_id

        if is_in_dm_with_bot is False and thread_ts is None:
            return

        user_message = payload.get("text")

        if is_in_dm_with_bot is True and thread_ts is None:
            # In the DM with the bot; this is not within a thread
            response = dify_client.create_chat_message(
                inputs={"slack_user_id": user_id},
                query=user_message,
                user=payload.get("ts").replace(".", "-"),
            )
            response.raise_for_status()

            reply_message = response.json()["answer"]

            client.chat_postMessage(
                channel=context.channel_id,
                thread_ts=payload.get("ts"),
                text=markdown_to_slack(reply_message),
            )
        else:
            # In a channel
            latest_conversation_id = get_last_conversation_id(dify_client, thread_ts)

            user_message = format_dify_message_content(
                payload.get("text"), TRANSLATE_MARKDOWN
            )

            if latest_conversation_id is not None:
                response = dify_client.create_chat_message(
                    inputs={"slack_user_id": user_id},
                    query=user_message,
                    conversation_id=latest_conversation_id,
                    user=thread_ts.replace(".", "-"),
                )
                response.raise_for_status()

            else:
                response = dify_client.create_chat_message(
                    inputs={"slack_user_id": user_id},
                    query=user_message,
                    user=thread_ts.replace(".", "-"),
                )
                response.raise_for_status()

        client.chat_postMessage(
            channel=context.channel_id,
            thread_ts=thread_ts,
            text=markdown_to_slack(response.json()["answer"]),
        )

    except Exception as e:
        logger.error(f"Failed to respond to app mention: {e}")

        client.chat_postMessage(
            channel=context.channel_id,
            thread_ts=payload.get("ts"),
            text="Sorry, I failed to respond to your message. Please try again later.",
        )


def register_listeners(app):
    # Chat with the bot
    app.event("app_mention")(ack=just_ack, lazy=[respond_to_app_mention])
    app.event("message")(ack=just_ack, lazy=[respond_to_new_message])
