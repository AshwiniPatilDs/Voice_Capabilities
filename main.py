import asyncio
import base64
import json
import os
import struct
from datetime import datetime

import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.websockets import WebSocketDisconnect
from pydantic import BaseModel
from twilio.rest import Client
from twilio.twiml.voice_response import Connect, VoiceResponse

from pathlib import Path
from customer_lookup import format_local_customer_db_for_prompt

""" Added the import statement for lookup_customer function from customer_lookup.py 
# to fetch the local customer database context for the system prompt
# and testing if AI Assistant can access the local customer database 
# for lookups. also created the customer_lookup.py file to 
# handle customer lookups and normalization of lookup keys."""

from customer_lookup import (
    lookup_customer_details,
    normalize_lookup_key,
    format_local_customer_db_for_prompt,
)
load_dotenv()


def log(msg, *args):
    """Helper for timestamped debug logging."""
    print(f"[{datetime.now().isoformat()}] {msg}", *args)


def load_prompt(file_name: str) -> str:
    """Load system prompt from file."""
    dir_path = os.path.dirname(os.path.realpath(__file__))
    prompt_path = os.path.join(dir_path, "prompts", f"{file_name}.txt")
    try:
        with open(prompt_path, "r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError:
        log(f"Could not find file: {prompt_path}")
        raise

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

GEMINI_SERVICE = os.getenv(
    "GEMINI_SERVICE",
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent",
)
GEMINI_LIVE_URL = os.getenv(
    "GEMINI_LIVE_URL",
    f"wss://generativelanguage.googleapis.com/ws/{GEMINI_SERVICE}",
)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
NGROK_URL = os.getenv("NGROK_URL", "").rstrip("/")


SYSTEM_PROMPT_PATH = Path(
    r"C:\Users\ashwi\OneDrive\Desktop\voice_ai_barge\prompts\system_prompt.txt"
)

SYSTEM_MESSAGE = (
    SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    .replace(
        "{LOCAL_CUSTOMER_DATABASE}",
        format_local_customer_db_for_prompt(),
    )
)

# 



# 
# BASE_SYSTEM_MESSAGE = load_prompt("system_prompt")
# 
# CUSTOMER_LOOKUP_EXTRA_INSTRUCTIONS = os.getenv("CUSTOMER_LOOKUP_EXTRA_INSTRUCTIONS", "")
# CUSTOMER_LOOKUP_PREFERRED_KEYS = os.getenv("CUSTOMER_LOOKUP_PREFERRED_KEYS", "")
# PREFERRED_LOOKUP_KEYS = (
#     [key.strip() for key in CUSTOMER_LOOKUP_PREFERRED_KEYS.split(",") if key.strip()]
#     if CUSTOMER_LOOKUP_PREFERRED_KEYS
#     else None
# )
# SYSTEM_MESSAGE = build_customer_lookup_system_message(
#     # base_system_message=BASE_SYSTEM_MESSAGE,
#     # extra_instructions=CUSTOMER_LOOKUP_EXTRA_INSTRUCTIONS,
#     # preferred_keys=PREFERRED_LOOKUP_KEYS,
# )

#

GEMINI_INPUT_SAMPLE_RATE = 16000
GEMINI_OUTPUT_SAMPLE_RATE = 24000
TWILIO_SAMPLE_RATE = 8000

app = FastAPI()

for name in ("GEMINI_API_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER", "NGROK_URL"):
    value = locals()[name]
    if not value:
        log(f"Missing configuration value: {name}")


@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "AI Voice Assistant is running!"}


class CallRequest(BaseModel):
    to_phone_number: str


@app.post("/make-call")
async def make_call(request: CallRequest):
    if not request.to_phone_number:
        raise HTTPException(status_code=400, detail="Phone number is required")
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        call = client.calls.create(
            url=f"{NGROK_URL}/outgoing-call",
            to=request.to_phone_number,
            from_=TWILIO_PHONE_NUMBER,
        )
        log(f"Call initiated with SID: {call.sid}")
        return {"call_sid": call.sid, "status": "success"}
    except Exception as exc:
        log(f"Error initiating call: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.api_route("/outgoing-call", methods=["GET", "POST"])
async def handle_outgoing_call(request: Request):
    response = VoiceResponse()
    response.say("Hello. You are being connected to an AI assistant.")
    with response.connect() as connect:
        connect.stream(url=f"wss://{request.url.hostname}/media-stream")
    return HTMLResponse(content=str(response), media_type="application/xml")


def _pcm16_to_mulaw_byte(sample: int) -> int:
    sign = 0x80 if sample < 0 else 0
    if sample < 0:
        sample = -sample
    sample = min(sample, 32635) + 0x84

    exponent = 7
    mask = 0x4000
    while exponent > 0 and not sample & mask:
        exponent -= 1
        mask >>= 1

    mantissa = (sample >> (exponent + 3)) & 0x0F
    return ~(sign | (exponent << 4) | mantissa) & 0xFF


def _mulaw_byte_to_pcm16(sample: int) -> int:
    value = ~sample & 0xFF
    sign = value & 0x80
    exponent = (value >> 4) & 0x07
    mantissa = value & 0x0F
    pcm_value = ((mantissa << 3) + 0x84) << exponent
    pcm_value -= 0x84
    return -pcm_value if sign else pcm_value


def _resample_pcm16_bytes(data: bytes, in_rate: int, out_rate: int) -> bytes:
    if not data:
        return b""
    if len(data) % 2 != 0:
        data = data[:-1]
    if not data:
        return b""

    samples = list(struct.unpack(f"<{len(data) // 2}h", data))
    if in_rate == out_rate:
        return data

    out_len = max(1, int(len(samples) * out_rate / in_rate))
    step = in_rate / out_rate
    resampled = []

    for index in range(out_len):
        source_index = index * step
        lower = int(source_index)
        upper = min(len(samples) - 1, lower + 1)
        if lower >= len(samples):
            resampled.append(samples[-1])
            continue
        fraction = source_index - lower
        if upper == lower:
            resampled.append(samples[lower])
            continue
        sample = samples[lower] + int((samples[upper] - samples[lower]) * fraction)
        resampled.append(max(-32768, min(32767, sample)))

    return struct.pack(f"<{len(resampled)}h", *resampled)


def twilio_mulaw_to_gemini_pcm16(payload: str) -> str:
    mulaw_bytes = base64.b64decode(payload)
    pcm_samples = [_mulaw_byte_to_pcm16(byte) for byte in mulaw_bytes]
    pcm_bytes = struct.pack(f"<{len(pcm_samples)}h", *pcm_samples)
    pcm_16khz = _resample_pcm16_bytes(pcm_bytes, TWILIO_SAMPLE_RATE, GEMINI_INPUT_SAMPLE_RATE)
    return base64.b64encode(pcm_16khz).decode("utf-8")


def gemini_pcm_to_twilio_mulaw(payload: str) -> str:
    pcm_bytes = base64.b64decode(payload)
    pcm_8khz = _resample_pcm16_bytes(pcm_bytes, GEMINI_OUTPUT_SAMPLE_RATE, TWILIO_SAMPLE_RATE)
    pcm_samples = list(struct.unpack(f"<{len(pcm_8khz) // 2}h", pcm_8khz))
    mulaw_bytes = bytes(_pcm16_to_mulaw_byte(sample) for sample in pcm_samples)
    return base64.b64encode(mulaw_bytes).decode("utf-8")


@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    log("Client connected to /media-stream")
    await websocket.accept()

    try:
        async with websockets.connect(
            GEMINI_LIVE_URL,
            additional_headers={"x-goog-api-key": GEMINI_API_KEY},
        ) as gemini_ws:
            log("Connected to Gemini Live API successfully.")
            stream_sid = None

            model_name = GEMINI_MODEL if GEMINI_MODEL.startswith("models/") else f"models/{GEMINI_MODEL}"
            initial_config = {
                "setup": {
                    "model": model_name,
                    "systemInstruction": {"parts": [{"text": SYSTEM_MESSAGE}]},
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                    },
                }
            }
            await gemini_ws.send(json.dumps(initial_config))
            log("Sent initial setup message to Gemini.")

            async def receive_from_twilio():
                nonlocal stream_sid
                try:
                    async for message in websocket.iter_text():
                        data = json.loads(message)
                        event = data.get("event")

                        if event == "media":
                            payload = twilio_mulaw_to_gemini_pcm16(data["media"]["payload"])
                            await gemini_ws.send(
                                json.dumps(
                                    {
                                        "realtimeInput": {
                                            "audio": {
                                                "data": payload,
                                                "mimeType": f"audio/pcm;rate={GEMINI_INPUT_SAMPLE_RATE}",
                                            }
                                        }
                                    }
                                )
                            )
                        elif event == "start":
                            stream_sid = data["start"]["streamSid"]
                            log(f"Incoming stream started with SID: {stream_sid}")
                            await gemini_ws.send(
                                json.dumps(
                                    {
                                        "realtimeInput": {
                                            "text": "Greet the caller briefly and ask how you can help."
                                        }
                                    }
                                )
                            )
                        elif event == "stop":
                            await gemini_ws.close()
                except WebSocketDisconnect:
                    log("Twilio WebSocket disconnected.")
                except Exception as exc:
                    log(f"Error in receive_from_twilio: {exc}")

            async def send_to_twilio():
                nonlocal stream_sid
                try:
                    async for gemini_message in gemini_ws:
                        response = json.loads(gemini_message)
                        server_content = response.get("serverContent", {})
                        parts = server_content.get("modelTurn", {}).get("parts", [])

                        for part in parts:
                            inline_data = part.get("inlineData") or part.get("inline_data")
                            if not inline_data or not stream_sid:
                                continue

                            mime_type = inline_data.get("mimeType") or inline_data.get("mime_type", "")
                            if not mime_type.startswith("audio/pcm"):
                                continue

                            await websocket.send_json(
                                {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": gemini_pcm_to_twilio_mulaw(inline_data["data"])},
                                }
                            )

                        if server_content.get("interrupted") and stream_sid:
                            await websocket.send_json({"event": "clear", "streamSid": stream_sid})
                except Exception as exc:
                    log(f"Exception in send_to_twilio: {exc}")

            await asyncio.gather(receive_from_twilio(), send_to_twilio())

    except Exception as exc:
        log(f"An unexpected error occurred during WebSocket handling: {exc}")
    finally:
        log("Closing main Twilio WebSocket connection.")
        await websocket.close()



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )