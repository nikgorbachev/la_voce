from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import io
import re
import os
import asyncio
import threading
import httpx 
import base64
from dotenv import load_dotenv
import torch
from TTS.utils.synthesizer import Synthesizer
import soundfile as sf

load_dotenv()

try:
    from num2words import num2words
    HAS_NUM2WORDS = True
except Exception:
    HAS_NUM2WORDS = False

app = FastAPI()

ABBREV = {
    r'\bprof\.?\b': 'professore',
    r'\bdott\.?\b': 'dottore',
    r'\bsig\.?\b': 'signore',
    r'\bsigra\.?\b': 'signora',
}

def _expand_number(match):
    s = match.group(0)
    if HAS_NUM2WORDS:
        try:
            return num2words(int(s), lang='it')
        except Exception:
            return s
    return s

def normalize_text(text: str) -> str:
    if not text: return ""
    t = text.strip().lower()
    
    for pat, repl in ABBREV.items():
        t = re.sub(pat, repl, t)
    t = re.sub(r'\d+', _expand_number, t)
    t = re.sub(r'\s+', ' ', t)
    t = t.replace(" ,", ",").replace(": ", ", ")
    
    t = re.sub(r"cha", "cia", t)
    t = re.sub(r"cho", "cio", t)
    t = re.sub(r"chu", "ciu", t)
    return t

# --- LOCAL TTS SETUP (Coqui VITS) ---
model_checkpoint_path = "models/best_model.pth"
config_path = "models/config.json"
device = "cuda" if torch.cuda.is_available() else "cpu"

try:
    print(f"Starting Local TTS on device: {device}")
    synthesizer = Synthesizer(
        tts_checkpoint=model_checkpoint_path,
        tts_config_path=config_path,
        use_cuda=torch.cuda.is_available(),
    )
    SAMPLE_RATE = synthesizer.output_sample_rate
    synth_lock = threading.Lock()
    LOCAL_TTS_READY = True
except Exception as e:
    print(f"Local TTS could not be loaded: {e}")
    LOCAL_TTS_READY = False

async def synthesize_local(normalized_text: str) -> io.BytesIO:
    if not LOCAL_TTS_READY:
        raise HTTPException(status_code=500, detail="Local TTS model is not available.")
    def _do_synth(text_in):
        with synth_lock:
            wav = synthesizer.tts(text=text_in, language_name='it')
        buf = io.BytesIO()
        sf.write(buf, wav, SAMPLE_RATE, format='WAV')
        buf.seek(0)
        return buf
    return await asyncio.to_thread(_do_synth, normalized_text)


async def synthesize_voxtral(text: str, voice_id: str) -> io.BytesIO:
    api_key = os.getenv("MISTRAL_API_KEY") 
    if not api_key:
        raise HTTPException(status_code=500, detail="MISTRAL_API_KEY environment variable not set")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.mistral.ai/v1/audio/speech",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "voxtral-mini-tts-2603",
                "input": text,
                "voice_id": voice_id,       
                "response_format": "wav" 
            },
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"Mistral API Error: {response.text}")
            
        # Mistral returns JSON containing a base64 encoded audio string
        data = response.json()
        audio_b64 = data.get("audio_data", "")
        
        # Decode the string back into actual binary audio bytes
        audio_bytes = base64.b64decode(audio_b64)
        return io.BytesIO(audio_bytes)
    


# --- ENDPOINTS ---
@app.post("/normalize")
async def normalize_endpoint(request: Request):
    data = await request.json()
    text = data.get("text", "")
    return JSONResponse({"original": text, "normalized": normalize_text(text)})

@app.post("/tts")
async def tts_endpoint(request: Request):
    data = await request.json()
    text = data.get("text", "")
    provider = data.get("provider", "local") 
    voice_id = data.get("voice_id", "c6fdbd50-6da9-45d4-8954-cb5b7b49eca1") 
    
    if not text.strip():
        raise HTTPException(status_code=400, detail="No text provided")

    normalized = normalize_text(text)

    if provider == "voxtral":
        wav_buf = await synthesize_voxtral(normalized, voice_id)
    else:
        wav_buf = await synthesize_local(normalized)

    return StreamingResponse(
        wav_buf,
        media_type="audio/wav",
        headers={"Content-Disposition": "inline; filename=output.wav"}
    )

# app.mount("/", StaticFiles(directory="static", html=True), name="static")