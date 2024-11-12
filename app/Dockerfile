FROM public.ecr.aws/lambda/python:3.12 as base

WORKDIR ${LAMBDA_TASK_ROOT}

# 環境変数の設定
ARG SLACK_APP_TOKEN
ARG SLACK_SIGNING_SECRET
ENV SLACK_APP_TOKEN=${SLACK_APP_TOKEN}
ENV SLACK_SIGNING_SECRET=${SLACK_SIGNING_SECRET}

FROM base as builder

# 依存解決
RUN pip install uv==0.4.15
COPY . ${LAMBDA_TASK_ROOT}/
COPY app ${LAMBDA_TASK_ROOT}/app
RUN uv pip install --requirement pyproject.toml --system --target "${LAMBDA_TASK_ROOT}" --link-mode copy


## dev
FROM builder as dev

EXPOSE 3000

ENV \
    # 開発環境ではログをリアルタイムに確認したいため、バッファリングを無効化
    PYTHONUNBUFFERED=1

ENTRYPOINT ["python"]
CMD ["index.py"]

## prod
FROM base as prod

COPY --from=builder ${LAMBDA_TASK_ROOT} ${LAMBDA_TASK_ROOT}

CMD [ "index.lambda_handler" ]