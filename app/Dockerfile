FROM public.ecr.aws/lambda/python:3.12 as base

WORKDIR ${LAMBDA_TASK_ROOT}

FROM base as builder

# 依存解決
RUN pip install uv==0.4.15
COPY pyproject.toml uv.lock ./
RUN uv pip install --requirement pyproject.toml --system --target "${LAMBDA_TASK_ROOT}" --link-mode copy

COPY . ${LAMBDA_TASK_ROOT}

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