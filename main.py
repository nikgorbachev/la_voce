
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import io
import re
import asyncio
import threading


import torch
from TTS.utils.synthesizer import Synthesizer
import soundfile as sf


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
    
    if text is None:
        return ""
    t = text.strip()
    if t == "":
        return t
    
    # add leading comma+space if not present (user request)
    # if not t.startswith(", "):
    #     t = ", " + t

    # lowercase
    t = t.lower()
    # expand simple abbreviations
    for pat, repl in ABBREV.items():
        t = re.sub(pat, repl, t)
    # expand integers
    t = re.sub(r'\d+', _expand_number, t)
    # normalize whitespace
    t = re.sub(r'\s+', ' ', t)
    # small punctuation fixes
    t = t.replace(" ,", ",")
    t = t.replace(": ", ", ")
    

    # a bit of hardcoded english spelling parsing
    t = re.sub(r"cha", "cia", t)
    t = re.sub(r"cho", "cio", t)
    t = re.sub(r"chu", "ciu", t)
    return t


model_checkpoint_path = "best_model.pth"
config_path = "config.json"

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Starting TTS on device: {device}")

synthesizer = Synthesizer(
    tts_checkpoint=model_checkpoint_path,
    tts_config_path=config_path,
    use_cuda=torch.cuda.is_available(),
)

SAMPLE_RATE = synthesizer.output_sample_rate

synth_lock = threading.Lock()

async def synthesize_wav_bytes(normalized_text: str) -> io.BytesIO:
    """Run blocking synthesizer in a thread and return a BytesIO WAV buffer."""
    def _do_synth(text_in):
        with synth_lock:
            wav = synthesizer.tts(text=text_in, language_name='it')
        buf = io.BytesIO()
        sf.write(buf, wav, SAMPLE_RATE, format='WAV')
        buf.seek(0)
        return buf

    buf = await asyncio.to_thread(_do_synth, normalized_text)
    return buf


@app.post("/normalize")
async def normalize_endpoint(request: Request):
    data = await request.json()
    text = data.get("text", "")
    normalized = normalize_text(text)
    return JSONResponse({"original": text, "normalized": normalized})

@app.post("/tts")
async def tts_endpoint(request: Request):
    data = await request.json()
    text = data.get("text", "")
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="No text provided")

    # 1) normalize first (use same function as /normalize)
    normalized = normalize_text(text)

    # 2) synthesize normalized text (offloaded to thread)
    wav_buf = await synthesize_wav_bytes(normalized)

    return StreamingResponse(
        wav_buf,
        media_type="audio/wav",
        headers={"Content-Disposition": "inline; filename=output.wav"}
    )

app.mount("/", StaticFiles(directory="static", html=True), name="static")
