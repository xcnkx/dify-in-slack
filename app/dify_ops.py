from typing import Optional

from dify_client import ChatClient

from app.markdown_conversion import slack_to_markdown

# ----------------------------
# Internal functions
# ----------------------------


# Format message from Slack to send to OpenAI
def format_dify_message_content(
    content: str, translate_markdown: bool
) -> Optional[str]:
    if content is None:
        return None

    # Unescape &, < and >, since Slack replaces these with their HTML equivalents
    # See also: https://api.slack.com/reference/surfaces/formatting#escaping
    content = content.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

    # Convert from Slack mrkdwn to markdown format
    if translate_markdown:
        content = slack_to_markdown(content)

    return content


def get_last_conversation_id(client: ChatClient, thread_ts: str) -> Optional[str]:
    res = client.get_conversations(thread_ts.replace(".", "-"))
    res.raise_for_status()
    conversation_history = res.json()
    if conversation_history is None:
        return None
    return conversation_history["data"][-1]["id"]
