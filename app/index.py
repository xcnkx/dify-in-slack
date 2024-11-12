import os

from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler

slack_app_token = slack_bot_token = os.environ["SLACK_APP_TOKEN"]
slack_signing_token = os.environ["SLACK_SIGNING_SECRET"]

app = App(
    process_before_response=True,
    token=slack_bot_token,
    signing_secret=slack_signing_token,
)


def lambda_handler(event, context):
    slack_handler = SlackRequestHandler(app=app)
    return slack_handler.handle(event, context)


if __name__ == "__main__":
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    SocketModeHandler(app, slack_app_token).start()
