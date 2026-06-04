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

def encode_udp(msg: dict) -> bytes:
    """Zakóduje správu pre UDP – bez newline, kompaktný JSON."""
    return json.dumps(msg, separators=(',', ':')).encode("utf-8")

def decode_udp(data: bytes) -> dict | None:
    """Dekóduje jeden UDP datagram."""
    try:
        return json.loads(data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

# === UDP správy (real-time, strata paketu OK) ===
C2S_PLAYER_INPUT = "player_input"       # klient → server: input stav
S2C_GAME_STATE   = "game_state"          # server → klient: pozície všetkých hráčov

# === TCP správy (spoľahlivé, garantované doručenie) ===
C2S_PLAYER_REQUEST = "player_request"    # klient → server: špeciálna akcia (napr. vent)
S2C_VENT_UPDATE    = "vent_update"        # server → klient: zmena stavu ventu
S2C_ROLE_ASSIGN    = "role_assign"        # server → klient: pridelenie role
C2S_UDP_REGISTER   = "udp_register"       # klient → server (TCP): registrácia UDP portu
