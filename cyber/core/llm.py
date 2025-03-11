import json
from ..utils import calculate_price


def bedrock_anthropic(client, model, param, stream=False):
    body = json.dumps(param)
    if stream:
        return bedrock_anthropic_stream(client, model, body)
    message = client.invoke_model(body=body, modelId=model)

    message = json.loads(message.get("body").read())

    calculate_price(model, message["usage"])
    return message["content"][0]["text"]


def parse_stream(stream):
    for event in stream:
        chunk = event.get("chunk")
        if chunk:
            message = json.loads(chunk.get("bytes").decode())
            if message["type"] == "content_block_delta":
                yield message["delta"]["text"] or ""
            elif message["type"] == "message_stop":
                yield "\n"


def bedrock_anthropic_stream(client, model, body):
    message = client.invoke_model_with_response_stream(body=body, modelId=model)
    stream = message.get("body")
    return parse_stream(stream)


def interact_with_bedrock_anthropic(client, model, params, stream=False):
    return bedrock_anthropic(client, model, params, stream)


def print_stream(string_stream):
    for s in string_stream:
        print(s, end="", flush=True)


def main():
    import time

    start = time.time()
    stream = True
    s = interact_with_bedrock_anthropic(stream)
    if stream:
        print_stream(s)
    else:
        print(s)

    end = time.time()
    print(end - start)


if __name__ == "__main__":
    main()
