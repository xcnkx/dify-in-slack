import logging

from slack_bolt import Ack, BoltContext
from slack_sdk import WebClient

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
        client.chat_postMessage(
            channel=context.channel_id,
            text="Hello there!",
        )
    except Exception as e:
        logger.error(f"Failed to respond to app mention: {e}")

        client.chat_postMessage(
            channel=context.channel_id,
            text="Sorry, I failed to respond to your message. Please try again later.",
        )
