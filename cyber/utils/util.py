build_user_message = lambda text: {
    "role": "user",
    "content": [{"type": "text", "text": text}],
}
build_assistant_message = lambda text: {
    "role": "assistant",
    "content": [{"type": "text", "text": text}],
}
build_system_message = lambda text: {
    "role": "system",
    "content": [{"type": "text", "text": text}],
}
