from app.services.ai_service import parse_json_content, resolve_endpoint, text_from_response, usage_tokens


def test_azure_full_responses_url():
    url, style = resolve_endpoint("https://aws-talk11.services.ai.azure.com/openai/v1/responses")
    assert style == "responses"
    assert url.endswith("/responses")


def test_openai_chat_style():
    url, style = resolve_endpoint("https://api.openai.com/v1")
    assert style == "chat"
    assert url.endswith("/chat/completions")


def test_parse_responses_output():
    body = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": '{"vendor":"Uber"}'}],
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    assert text_from_response(body) == '{"vendor":"Uber"}'
    assert usage_tokens(body) == 15


def test_parse_fenced_json():
    data = parse_json_content('```json\n{"vendor": "ABC Hotel", "amount": 1}\n```')
    assert data["vendor"] == "ABC Hotel"
