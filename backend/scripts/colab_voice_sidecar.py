"""Google Colab / Cloud GPU Voice Cloning Sidecar for Raghvi V2.

Powered by official AI4Bharat IndicF5 (11 Indian Languages, 1417h trained):
1. Runtime -> Change runtime type -> Select T4 GPU -> Save
2. In Colab cell 1, install official IndicF5:
   !pip install -q git+https://github.com/ai4bharat/IndicF5.git
   !pip install -q fastapi uvicorn pyngrok pydantic soundfile aiofiles anyio
3. Run the sidecar:
   !python colab_voice_sidecar.py --port 8000
"""

import argparse
import contextlib
import importlib
import io
import logging
import os
import re
import subprocess
from typing import Annotated, Any

import aiofiles
import uvicorn
from anyio import Path as AsyncPath
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("raghvi_indicf5_sidecar")

app = FastAPI(title="Raghvi Official IndicF5 Voice Cloning GPU Sidecar", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_REFERENCE_AUDIO = "reference_voice.wav"
DEFAULT_REFERENCE_TEXT = (
    "इंस्पेक्शन डिपार्टमेंट से आप वाईस प्रेसिडेंट ब्रेनन है न? "
    "आपको बहुत तकलीफ होगी लेकिन इजासत हो तो मैं आपकी सांसे छीनना चाहती हूँ बुरा मत मानियेगा."
)


def _resolve_reference_audio(custom_path: str | None = None) -> str:
    """Find reference audio candidate file if available."""
    if custom_path:
        return custom_path
    import os

    for candidate in [
        "reference_voice.wav",
        "yor-audio-raghvi-testing.mpeg",
        "reference_voice.mp3",
    ]:
        if os.path.exists(candidate):
            return candidate
    return DEFAULT_REFERENCE_AUDIO


def _get_torch() -> Any:
    """Safely resolve PyTorch module if installed in the host environment."""
    try:
        return importlib.import_module("torch")
    except ImportError:
        return None


def _get_soundfile() -> Any:
    """Safely resolve soundfile module if installed in the host environment."""
    try:
        return importlib.import_module("soundfile")
    except ImportError:
        return None


def _get_numpy() -> Any:
    """Safely resolve numpy module if installed in the host environment."""
    try:
        return importlib.import_module("numpy")
    except ImportError:
        return None


_torch = _get_torch()
device = "cuda" if _torch is not None and _torch.cuda.is_available() else "cpu"
logger.info(f"Initialized with device: {device}")
if device == "cpu":
    logger.warning("CUDA not detected! Running on CPU will be slow. Enable GPU in Colab Runtime.")

model_engine: str | None = None
indicf5_model: Any = None
xtts_model: Any = None
f5_model: Any = None


def load_model(hf_token: str | None = None) -> None:
    global model_engine, indicf5_model, xtts_model, f5_model
    token = hf_token or os.getenv("HF_TOKEN")

    # 1. Primary: Official AI4Bharat IndicF5 model (if user has token/access)
    try:
        transformers_mod = importlib.import_module("transformers")
        AutoModel = transformers_mod.AutoModel
        logger.info("Checking official AI4Bharat IndicF5 model on Hugging Face...")
        repo_id = "ai4bharat/IndicF5"
        indicf5_model = AutoModel.from_pretrained(
            repo_id,
            trust_remote_code=True,
            token=token,
        )
        if hasattr(indicf5_model, "to") and device == "cuda":
            indicf5_model = indicf5_model.to("cuda")
        model_engine = "indicf5"
        logger.info("Official AI4Bharat IndicF5 model loaded successfully on GPU!")
        return
    except Exception as e:
        logger.info(
            f"IndicF5 AutoModel requires token or gated access ({e}). "
            "Switching to open-weights IIT Madras F5-Hindi..."
        )

    # 2. Secondary: IIT Madras Indic F5 (SPRINGLab/F5-Hindi-24KHz - un-gated open weights)
    try:
        hf_hub = importlib.import_module("huggingface_hub")
        hf_hub_download = hf_hub.hf_hub_download

        logger.info("Downloading IIT Madras F5-Hindi-24KHz checkpoint & vocab (open weights)...")
        ckpt_path = hf_hub_download(
            repo_id="SPRINGLab/F5-Hindi-24KHz",
            filename="model_2500000.safetensors",
        )
        vocab_path = hf_hub_download(
            repo_id="SPRINGLab/F5-Hindi-24KHz",
            filename="vocab.txt",
        )
        logger.info(f"Loaded F5-Hindi checkpoint: {ckpt_path}")

        f5_infer = importlib.import_module("f5_tts.infer.utils_infer")
        f5_model_mod = importlib.import_module("f5_tts.model")
        f5_load_model = f5_infer.load_model
        load_vocoder = f5_infer.load_vocoder
        load_checkpoint = getattr(f5_infer, "load_checkpoint", None)
        DiT = f5_model_mod.DiT
        vocoder = load_vocoder(vocoder_name="vocos", is_local=False, device=device)

        model_cfg = dict(dim=768, depth=18, heads=12, ff_mult=2, text_dim=512, conv_layers=4)
        try:
            # IndicF5 variant (load_model creates architecture, load_checkpoint loads weights)
            model = f5_load_model(
                model_cls=DiT,
                model_cfg=model_cfg,
                vocab_file=vocab_path,
                mel_spec_type="vocos",
                device=device,
            )
            if load_checkpoint is not None:
                model = load_checkpoint(model, ckpt_path=ckpt_path, device=device, use_ema=True)
        except TypeError:
            # Upstream F5-TTS variant (single-step with ckpt_path)
            model = f5_load_model(
                model_cls=DiT,
                model_cfg=model_cfg,
                ckpt_path=ckpt_path,
                vocab_file=vocab_path,
                device=device,
            )

        f5_model = {"model": model, "vocoder": vocoder, "vocab_file": vocab_path}
        model_engine = "f5_hindi"
        logger.info("IIT Madras F5-Hindi small DiT loaded successfully onto GPU!")
        return
    except Exception as e:
        logger.warning(f"F5-Hindi load failed: {e}, checking alternatives...")

    # 3. Tertiary: Coqui XTTS v2
    try:
        tts_api = importlib.import_module("TTS.api")
        TTS = tts_api.TTS
        logger.info("Loading Coqui XTTS-v2 on GPU...")
        xtts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
        model_engine = "xtts"
        logger.info("Coqui XTTS-v2 loaded successfully on GPU!")
        return
    except Exception as e:
        logger.info(f"XTTS not loaded ({e}), checking base F5-TTS...")

    # 4. Quaternary: Standard F5-TTS
    try:
        f5_infer = importlib.import_module("f5_tts.infer.utils_infer")
        f5_model_mod = importlib.import_module("f5_tts.model")
        f5_load_model = f5_infer.load_model
        load_vocoder = f5_infer.load_vocoder
        load_checkpoint = getattr(f5_infer, "load_checkpoint", None)
        DiT = f5_model_mod.DiT

        logger.info("Loading F5-TTS model on GPU...")
        vocoder = load_vocoder(vocoder_name="vocos", is_local=False, device=device)

        hf_hub = importlib.import_module("huggingface_hub")
        hf_hub_download = hf_hub.hf_hub_download

        checkpoint_path = hf_hub_download(
            repo_id="SWivid/F5-TTS",
            filename="F5TTS_Base/model_1200000.safetensors",
        )
        saved_vocab = vocab_path if "vocab_path" in locals() and vocab_path else ""
        cfg_base = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
        try:
            model = f5_load_model(
                model_cls=DiT,
                model_cfg=cfg_base,
                vocab_file=saved_vocab,
                mel_spec_type="vocos",
                device=device,
            )
            if load_checkpoint is not None:
                model = load_checkpoint(
                    model, ckpt_path=checkpoint_path, device=device, use_ema=True
                )
        except TypeError:
            model = f5_load_model(
                model_cls=DiT,
                model_cfg=cfg_base,
                ckpt_path=checkpoint_path,
                vocab_file=saved_vocab,
                device=device,
            )
        f5_model = {"model": model, "vocoder": vocoder, "vocab_file": saved_vocab}
        model_engine = "f5"
        logger.info("F5-TTS model loaded successfully onto GPU!")
    except Exception as e:
        logger.warning(f"Voice model import failed: {e}. Operating in lightweight sidecar mode.")


class SynthesisRequest(BaseModel):
    text: str
    language: str | None = "en"
    voice_id: str | None = None
    reference_audio_path: str | None = None
    reference_text: str | None = None
    speed: float | None = 1.0


@app.get("/")
@app.get("/health")
@app.get("/wake")
async def health_check():
    """Health and wake-up ping endpoint."""
    torch_mod = _get_torch()
    gpu_name = (
        torch_mod.cuda.get_device_name(0)
        if torch_mod is not None and torch_mod.cuda.is_available()
        else "None"
    )
    audio_path = AsyncPath(_resolve_reference_audio())
    has_audio = await audio_path.exists()
    return {
        "status": "ready",
        "service": "raghvi-indicf5-sidecar",
        "device": device,
        "gpu": gpu_name,
        "engine": model_engine or "none",
        "model_loaded": model_engine is not None,
        "has_reference_audio": has_audio,
    }


@app.post("/upload_sample")
async def upload_reference_sample(
    audio_file: Annotated[UploadFile, File()],
    reference_text: str | None = None,
):
    """Upload reference audio (e.g. yor-audio-raghvi-testing.mpeg) for voice cloning."""
    global DEFAULT_REFERENCE_TEXT
    try:
        content = await audio_file.read()
        async with aiofiles.open(DEFAULT_REFERENCE_AUDIO, "wb") as buffer:
            await buffer.write(content)

        if reference_text:
            DEFAULT_REFERENCE_TEXT = reference_text

        logger.info(f"Registered new reference voice: {audio_file.filename}")
        return {
            "status": "success",
            "message": f"Reference audio saved ({audio_file.filename})",
            "reference_text": DEFAULT_REFERENCE_TEXT,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


_ROMAN_TO_DEVA: dict[str, str] = {
    "mai": "मैं",
    "main": "मैं",
    "me": "मैं",
    "mera": "मेरा",
    "meri": "मेरी",
    "mere": "मेरे",
    "mujhe": "मुझे",
    "mujhko": "मुझको",
    "mujhse": "मुझसे",
    "hum": "हम",
    "humara": "हमारा",
    "humari": "हमारी",
    "humare": "हमारे",
    "hume": "हमें",
    "humein": "हमें",
    "humse": "हमसे",
    "tum": "तुम",
    "tumhara": "तुम्हारा",
    "tumhari": "तुम्हारी",
    "tumhare": "तुम्हारे",
    "tumhe": "तुम्हें",
    "tumko": "तुमको",
    "tumse": "तुमसे",
    "aap": "आप",
    "aapka": "आपका",
    "aapki": "आपकी",
    "aapke": "आपके",
    "aapko": "आपको",
    "aapse": "आपसे",
    "yeh": "यह",
    "ye": "ये",
    "iska": "इसका",
    "iski": "इसकी",
    "iske": "इसके",
    "ise": "इसे",
    "isse": "इससे",
    "inhe": "इन्हें",
    "inse": "इनसे",
    "woh": "वह",
    "wo": "वो",
    "uska": "उसका",
    "uski": "उसकी",
    "uske": "उसके",
    "use": "उसे",
    "usse": "उससे",
    "unka": "उनका",
    "unki": "उनकी",
    "unke": "उनके",
    "unhe": "उन्हें",
    "unse": "उनसे",
    "apna": "अपना",
    "apni": "अपनी",
    "apne": "अपने",
    "khud": "खुद",
    "kya": "क्या",
    "kyun": "क्यों",
    "kyu": "क्यों",
    "kaise": "कैसे",
    "kaisa": "कैसा",
    "kaisi": "कैसी",
    "kese": "कैसे",
    "kesi": "कैसी",
    "kahan": "कहाँ",
    "kaha": "कहाँ",
    "kidhar": "किधर",
    "kab": "कब",
    "kaun": "कौन",
    "kon": "कौन",
    "kitna": "कितना",
    "kitne": "कितने",
    "kitni": "कितनी",
    "kis": "किस",
    "kisko": "किसको",
    "kisse": "किससे",
    "raghvi": "राघवी",
    "namaste": "नमस्ते",
    "namaskar": "नमस्कार",
    "pranam": "प्रणाम",
    "hello": "नमस्ते",
    "hi": "नमस्ते",
    "hii": "नमस्ते",
    "hey": "अरे सुनो",
    "bye": "अलविदा",
    "alvida": "अलविदा",
    "shukriya": "शुक्रिया",
    "dhanyavaad": "धन्यवाद",
    "dhanyawad": "धन्यवाद",
    "haan": "हाँ",
    "ha": "हाँ",
    "han": "हाँ",
    "nahi": "नहीं",
    "nahin": "नहीं",
    "na": "ना",
    "mat": "मत",
    "theek": "ठीक",
    "thik": "ठीक",
    "accha": "अच्छा",
    "achha": "अच्छा",
    "achhi": "अच्छी",
    "achi": "अच्छी",
    "achhe": "अच्छे",
    "ache": "अच्छे",
    "sahi": "सही",
    "galat": "गलत",
    "bilkul": "बिल्कुल",
    "zaroor": "ज़रूर",
    "zarur": "ज़रूर",
    "shayad": "शायद",
    "kripya": "कृपया",
    "please": "कृपया",
    "hai": "है",
    "hain": "हैं",
    "he": "है",
    "ho": "हो",
    "hoon": "हूँ",
    "hun": "हूँ",
    "tha": "था",
    "thi": "थी",
    "the": "थे",
    "hoga": "होगा",
    "hogi": "होगी",
    "hoge": "होंगे",
    "honge": "होंगे",
    "raha": "रहा",
    "rahe": "रहे",
    "rahi": "रही",
    "hua": "हुआ",
    "hue": "हुए",
    "hui": "हुई",
    "karo": "करो",
    "karna": "करना",
    "kare": "करें",
    "karein": "करें",
    "kar": "कर",
    "karta": "करता",
    "karti": "करती",
    "karte": "करते",
    "karunga": "करूँगा",
    "karungi": "करूँगी",
    "karoge": "करोगे",
    "karogi": "करोगी",
    "karni": "करनी",
    "karne": "करने",
    "batao": "बताओ",
    "batana": "बताना",
    "bolo": "बोलो",
    "bolna": "बोलना",
    "suno": "सुनो",
    "sunao": "सुनाओ",
    "dekho": "देखो",
    "dekh": "देख",
    "dekhna": "देखना",
    "samjho": "समझो",
    "samajh": "समझ",
    "samjha": "समझा",
    "samjhi": "समझी",
    "chalo": "चलो",
    "chal": "चल",
    "chalte": "चलते",
    "aao": "आओ",
    "aana": "आना",
    "jao": "जाओ",
    "jana": "जाना",
    "milte": "मिलते",
    "milo": "मिलो",
    "milna": "मिलना",
    "le": "ले",
    "lo": "लो",
    "lena": "लेना",
    "de": "दे",
    "do": "दो",
    "dena": "देना",
    "rakho": "रखो",
    "rakhna": "रखना",
    "baitho": "बैठो",
    "sona": "सोना",
    "so": "सो",
    "uth": "उठ",
    "utho": "उठो",
    "madad": "मदद",
    "sahayata": "सहायता",
    "baat": "बात",
    "baatein": "बातें",
    "sawal": "सवाल",
    "jawab": "जवाब",
    "naam": "नाम",
    "kaam": "काम",
    "dost": "दोस्त",
    "saath": "साथ",
    "paas": "पास",
    "pyar": "प्यार",
    "khushi": "खुशी",
    "khush": "खुश",
    "aaj": "आज",
    "kal": "कल",
    "parso": "परसों",
    "ab": "अब",
    "abhi": "अभी",
    "pehle": "पहले",
    "baad": "बाद",
    "din": "दिन",
    "raat": "रात",
    "subah": "सुबह",
    "shaam": "शाम",
    "ghar": "घर",
    "khana": "खाना",
    "pani": "पानी",
    "chahiye": "चाहिए",
    "chahie": "चाहिए",
    "pasand": "पसंद",
    "zindagi": "ज़िंदगी",
    "mausam": "मौसम",
    "waqt": "वक़्त",
    "samay": "समय",
    "naya": "नया",
    "nayi": "नयी",
    "naye": "नए",
    "purana": "पुराना",
    "bura": "बुरा",
    "buri": "बुरी",
    "bada": "बड़ा",
    "chota": "छोटा",
    "thoda": "थोड़ा",
    "zyada": "ज़्यादा",
    "jyada": "ज़्यादा",
    "bahut": "बहुत",
    "bohot": "बहुत",
    "kuch": "कुछ",
    "sab": "सब",
    "log": "लोग",
    "duniya": "दुनिया",
    "chai": "चाय",
    "coffee": "कॉफ़ी",
    "tea": "चाय",
    "ka": "का",
    "ki": "की",
    "ke": "के",
    "ko": "को",
    "se": "से",
    "mein": "में",
    "par": "पर",
    "aur": "और",
    "ya": "या",
    "lekin": "लेकिन",
    "magar": "मगर",
    "bhi": "भी",
}

_PHONETIC_DIGRAPHS = [
    ("chh", "छ"),
    ("shh", "ष"),
    ("kh", "ख"),
    ("gh", "घ"),
    ("ch", "च"),
    ("jh", "झ"),
    ("th", "थ"),
    ("dh", "ध"),
    ("ph", "फ"),
    ("bh", "भ"),
    ("sh", "श"),
    ("rh", "ढ़"),
    ("gy", "ज्ञ"),
    ("tr", "त्र"),
    ("ks", "क्ष"),
]

_PHONETIC_CONSONANTS = {
    "k": "क",
    "g": "ग",
    "c": "क",
    "j": "ज",
    "t": "त",
    "d": "द",
    "n": "न",
    "p": "प",
    "f": "फ",
    "b": "ब",
    "m": "म",
    "y": "य",
    "r": "र",
    "l": "ल",
    "v": "व",
    "w": "व",
    "s": "स",
    "h": "ह",
    "z": "ज़",
    "q": "क़",
    "x": "क्स",
}

_VOWEL_INDEP = {
    "aa": "आ",
    "a": "अ",
    "ee": "ई",
    "i": "इ",
    "oo": "ऊ",
    "u": "उ",
    "ai": "ऐ",
    "au": "औ",
    "e": "ए",
    "o": "ओ",
}

_VOWEL_MATRA = {
    "aa": "ा",
    "a": "",
    "ee": "ी",
    "i": "ि",
    "oo": "ू",
    "u": "ु",
    "ai": "ै",
    "au": "ौ",
    "e": "े",
    "o": "ो",
}


def _phonetic_word_to_devanagari(word: str) -> str:
    clean = word.lower()
    if clean in _ROMAN_TO_DEVA:
        return _ROMAN_TO_DEVA[clean]

    res: list[str] = []
    i = 0
    n = len(clean)
    prev_was_consonant = False

    while i < n:
        if i + 2 <= n and clean[i : i + 2] in _VOWEL_INDEP:
            v = clean[i : i + 2]
            res.append(_VOWEL_MATRA[v] if prev_was_consonant else _VOWEL_INDEP[v])
            prev_was_consonant = False
            i += 2
            continue

        if clean[i] in _VOWEL_INDEP:
            v = clean[i]
            if v == "i" and i == n - 1 and prev_was_consonant:
                res.append("ी")
            else:
                res.append(_VOWEL_MATRA[v] if prev_was_consonant else _VOWEL_INDEP[v])
            prev_was_consonant = False
            i += 1
            continue

        matched_dg = False
        for dg, de_char in _PHONETIC_DIGRAPHS:
            if clean[i:].startswith(dg):
                res.append(de_char)
                prev_was_consonant = True
                i += len(dg)
                matched_dg = True
                break
        if matched_dg:
            continue

        if clean[i] in _PHONETIC_CONSONANTS:
            res.append(_PHONETIC_CONSONANTS[clean[i]])
            prev_was_consonant = True
            i += 1
            continue

        res.append(clean[i])
        prev_was_consonant = False
        i += 1

    return "".join(res)


def _ensure_hindi_text(text: str) -> str:
    """Map Romanized Hinglish words to Devanagari using 2-layer dictionary + phonetics."""
    if not text:
        return ""

    def _replace_word(m: re.Match) -> str:
        w = m.group(0).lower()
        return _ROMAN_TO_DEVA.get(w) or _phonetic_word_to_devanagari(w)

    converted = re.sub(r"[a-zA-Z]+", _replace_word, text)
    has_deva = any(0x0900 <= ord(c) <= 0x097F for c in converted)
    return converted if has_deva else f"नमस्ते, {converted}"


@app.post("/synthesize")
async def synthesize_speech(request: SynthesisRequest):
    """Synthesize speech using zero-shot cloned voice on GPU."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    ref_audio = _resolve_reference_audio(request.reference_audio_path)
    ref_text = request.reference_text or DEFAULT_REFERENCE_TEXT

    logger.info(f"Synthesizing [{request.language}]: '{request.text[:40]}...'")

    sf_mod = _get_soundfile()

    if model_engine == "indicf5" and indicf5_model is not None:
        try:
            np_mod = _get_numpy()
            audio = indicf5_model(
                request.text,
                ref_audio_path=ref_audio,
                ref_text=ref_text,
            )
            if np_mod is not None:
                if getattr(audio, "dtype", None) == np_mod.int16:
                    audio = audio.astype(np_mod.float32) / 32768.0
                audio_arr = np_mod.array(audio, dtype=np_mod.float32)
            else:
                audio_arr = audio

            buffer = io.BytesIO()
            if sf_mod is not None:
                sf_mod.write(buffer, audio_arr, samplerate=24000, format="WAV")
            buffer.seek(0)
            return Response(content=buffer.read(), media_type="audio/wav")
        except Exception as e:
            logger.error(f"IndicF5 synthesis error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"IndicF5 error: {e}") from e

    elif model_engine == "xtts" and xtts_model is not None:
        try:
            import os
            import tempfile

            is_hindi = request.language == "hi" or any(ord(c) >= 0x0900 for c in request.text)
            lang = "hi" if is_hindi else (request.language or "en")

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_f:
                tmp_path = tmp_f.name

            xtts_model.tts_to_file(
                text=request.text,
                speaker_wav=ref_audio,
                language=lang,
                file_path=tmp_path,
                speed=request.speed or 1.0,
            )

            async with aiofiles.open(tmp_path, "rb") as af:
                wav_bytes = await af.read()

            with contextlib.suppress(OSError):
                os.remove(tmp_path)

            return Response(content=wav_bytes, media_type="audio/wav")
        except Exception as e:
            logger.error(f"XTTS inference error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"XTTS error: {e}") from e

    elif model_engine == "f5_hindi" and f5_model is not None:
        try:
            f5_infer = importlib.import_module("f5_tts.infer.utils_infer")
            infer_process = f5_infer.infer_process
            target_text = _ensure_hindi_text(request.text)
            wav, sr, _ = infer_process(
                ref_audio,
                ref_text,
                target_text,
                f5_model["model"],
                f5_model["vocoder"],
                device=device,
                speed=request.speed or 1.0,
            )
            buffer = io.BytesIO()
            if sf_mod is not None:
                sf_mod.write(buffer, wav, sr, format="WAV")
            buffer.seek(0)
            return Response(content=buffer.read(), media_type="audio/wav")
        except Exception as e:
            logger.error(f"F5-Hindi inference error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"F5-Hindi error: {e}") from e

    elif f5_model is not None:
        try:
            f5_infer = importlib.import_module("f5_tts.infer.utils_infer")
            infer_process = f5_infer.infer_process

            wav, sr, _ = infer_process(
                ref_audio,
                ref_text,
                request.text,
                f5_model["model"],
                f5_model["vocoder"],
                device=device,
                speed=request.speed or 1.0,
            )
            buffer = io.BytesIO()
            if sf_mod is not None:
                sf_mod.write(buffer, wav, sr, format="WAV")
            buffer.seek(0)
            return Response(content=buffer.read(), media_type="audio/wav")
        except Exception as e:
            logger.error(f"Inference error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Inference error: {e}") from e

    else:
        np_mod = _get_numpy()
        sr = 24000
        duration = min(max(len(request.text) * 0.06, 0.5), 10.0)
        buf = io.BytesIO()
        if np_mod is not None and sf_mod is not None:
            t = np_mod.linspace(0, duration, int(sr * duration), False)
            sine = 0.2 * np_mod.sin(2 * np_mod.pi * 440 * t)
            sf_mod.write(buf, sine.astype(np_mod.float32), sr, format="WAV")
        buf.seek(0)
        return Response(content=buf.read(), media_type="audio/wav")


def start_tunnel(port: int, ngrok_token: str | None = None) -> str | None:
    """Expose local port to public internet via ngrok, cloudflared, or localtunnel."""
    if ngrok_token:
        try:
            pyngrok_mod = importlib.import_module("pyngrok")
            ngrok = pyngrok_mod.ngrok
            ngrok.set_auth_token(ngrok_token)
            tunnel = ngrok.connect(port)
            public_url = tunnel.public_url
            logger.info("=" * 60)
            logger.info(f"🚀 NGROK PUBLIC URL: {public_url}")
            logger.info(f"📋 Put this in backend/.env: INDICF5_SIDECAR_URL={public_url}")
            logger.info("=" * 60)
            return public_url
        except ImportError:
            logger.warning("pyngrok is not installed. Falling back...")

    # Attempt Cloudflare Tunnel (completely free, zero-config, passwordless)
    try:
        import re
        import time

        cf_url = (
            "https://github.com/cloudflare/cloudflared/releases"
            "/latest/download/cloudflared-linux-amd64"
        )
        install_cmd = (
            f"curl -sL {cf_url} -o /usr/local/bin/cloudflared && "
            "chmod +x /usr/local/bin/cloudflared"
        )
        subprocess.run(
            install_cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cf_proc = subprocess.Popen(
            f"cloudflared tunnel --url http://127.0.0.1:{port}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for _ in range(15):
            time.sleep(1)
            line = cf_proc.stdout.readline() if cf_proc.stdout else ""
            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if match:
                url = match.group(0)
                logger.info("=" * 60)
                logger.info(f"🚀 CLOUDFLARE PUBLIC URL: {url}")
                logger.info(f"📋 Put this in backend/.env: INDICF5_SIDECAR_URL={url}")
                logger.info("=" * 60)
                return url
    except Exception as e:
        logger.debug(f"Cloudflare tunnel note: {e}")

    # Fallback to localtunnel
    logger.info("Starting localtunnel (fallback)...")
    cmd = f"npx -y localtunnel --port {port}"
    subprocess.Popen(cmd, shell=True)
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Raghvi Voice Cloning GPU Sidecar")
    parser.add_argument("--port", type=int, default=8000, help="Local port to bind")
    parser.add_argument("--ngrok-token", type=str, default=None, help="Optional ngrok auth token")
    parser.add_argument("--hf-token", type=str, default=None, help="Optional Hugging Face token")
    args = parser.parse_args()

    load_model(hf_token=args.hf_token)
    start_tunnel(args.port, args.ngrok_token)
    uvicorn.run(app, host="0.0.0.0", port=args.port)
