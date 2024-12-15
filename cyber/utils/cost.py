import anthropic

PROCES = {
    "gpt-4o-2024-08-06": {"input": 0.0000025, "output": 0.00001},
    "claude-3-5-sonnet-20241022": {"input": 0.000003, "output": 0.000015},
    "us.anthropic.claude-3-5-sonnet-20241022-v2:0": {
        "input": 0.000003,
        "output": 0.000015,
    },
}


def calculate_token():
    client = anthropic.Anthropic(
        api_key="",
    )
    response = client.beta.messages.count_tokens(
        betas=["token-counting-2024-11-01"],
        model="claude-3-5-sonnet-20241022",
        system="You are a scientist",
        messages=[{"role": "user", "content": "Hello, Claude"}],
    )
    print(response)


def calculate_price(model, usage):
    org = which_org(model)
    match org:
        case "OpenAI":
            price = (
                PROCES[model]["input"] * usage.prompt_tokens
                + PROCES[model]["output"] * usage.completion_tokens
            )
            print(
                f"Input : {usage.prompt_tokens} * {PROCES[model]["input"]} + Output : {usage.completion_tokens} * {PROCES[model]["output"]} = $ {price}"
            )
        case "Anthropic":
            price = (
                PROCES[model]["input"] * usage.input_tokens
                + PROCES[model]["output"] * usage.output_tokens
            )
            print(
                f"Input : {usage.input_tokens} * {PROCES[model]['input']} + Output : {usage.output_tokens} * {PROCES[model]['output']} = $ {price}"
            )
        case "Bedrock_Anthropic":
            price = (
                PROCES[model]["input"] * usage["input_tokens"]
                + PROCES[model]["output"] * usage["output_tokens"]
            )
            print(
                f"Input : {usage["input_tokens"]} * {PROCES[model]['input']} + Output : {usage["output_tokens"]} * {PROCES[model]['output']} = $ {price}"
            )

    return price


def which_org(model):
    if model == "gpt-4o-2024-08-06":
        return "OpenAI"
    elif model == "claude-3-5-sonnet-20241022":
        return "Anthropic"
    elif model == "us.anthropic.claude-3-5-sonnet-20241022-v2:0":
        return "Bedrock_Anthropic"
    else:
        return "Custom"


# calculate_token()
