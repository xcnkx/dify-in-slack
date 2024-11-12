import logging
import time

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
            thread_ts=thread_ts,
            text="Hello there !",
        )
    except Exception as e:
        logger.error(f"Failed to respond to app mention: {e}")

        client.chat_postMessage(
            channel=context.channel_id,
            text="Sorry, I failed to respond to your message. Please try again later.",
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
        is_thread_for_this_app = False
        thread_ts = payload.get("thread_ts")
        if is_in_dm_with_bot is False and thread_ts is None:
            return

        messages_in_context = []
        if is_in_dm_with_bot is True and thread_ts is None:
            # In the DM with the bot; this is not within a thread
            past_messages = client.conversations_history(
                channel=context.channel_id,
                include_all_metadata=True,
                limit=100,
            ).get("messages", [])
            past_messages.reverse()
            # Remove old messages
            for message in past_messages:
                seconds = time.time() - float(message.get("ts"))
                if seconds < 86400:  # less than 1 day
                    messages_in_context.append(message)
            is_thread_for_this_app = True
        else:
            # Within a thread
            messages_in_context = client.conversations_replies(
                channel=context.channel_id,
                ts=thread_ts,
                include_all_metadata=True,
                limit=1000,
            ).get("messages", [])
            if is_in_dm_with_bot is True:
                # In the DM with this bot
                is_thread_for_this_app = True
            else:
                # In a channel
                the_parent_message_found = False
                for message in messages_in_context:
                    if message.get("ts") == thread_ts:
                        the_parent_message_found = True
                        is_thread_for_this_app = is_this_app_mentioned(context, message)
                        break
                if the_parent_message_found is False:
                    parent_message = find_parent_message(
                        client, context.channel_id, thread_ts
                    )
                    if parent_message is not None:
                        is_thread_for_this_app = is_this_app_mentioned(
                            context, parent_message
                        )

        if is_thread_for_this_app is False:
            return

        client.chat_postMessage(
            channel=context.channel_id,
            thread_ts=thread_ts,
            text="Hello there !",
        )

    except Exception as e:
        logger.error(f"Failed to respond to app mention: {e}")

        client.chat_postMessage(
            channel=context.channel_id,
            text="Sorry, I failed to respond to your message. Please try again later.",
        )


def register_listeners(app):
    # Chat with the bot
    app.event("app_mention")(ack=just_ack, lazy=[respond_to_app_mention])
    app.event("message")(ack=just_ack, lazy=[respond_to_new_message])
