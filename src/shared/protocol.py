import json

def encode_message(msg: dict) -> bytes:
    """Zakóduje správu do JSONu a pridá newline separátor."""
    return (json.dumps(msg) + "\n").encode("utf-8")

def decode_messages(buffer: bytes) -> tuple[list[dict], bytes]:
    """Dekóduje správy z bufferu. Vráti (zoznam správ, zvyšok bufferu)."""
    messages = []
    while b"\n" in buffer:
        line, buffer = buffer.split(b"\n", 1)
        if line.strip():  # Ignoruj prázdne riadky
            try:
                messages.append(json.loads(line.decode("utf-8")))
            except json.JSONDecodeError:
                print("Chyba pri dekódovaní JSONu:", line)
    return messages, buffer
