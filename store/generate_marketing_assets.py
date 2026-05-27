"""
Build #16 marketing campaign — generates Satoshi Cloud Miner App Store assets
using Gemini Nano Banana via the Emergent LLM key.

Outputs to /app/store/marketing/:
  - icon-1024.png           (App Store app icon, 1024x1024)
  - banner-hero.png         (App Store "Featured Today" wide banner)
  - banner-feature-mine.png (slideshow frame — mining feature)
  - banner-feature-yield.png(slideshow frame — yield feature)
  - banner-feature-support.png (slideshow frame — premium support)
  - banner-cta.png          (closing slide — download CTA)

Honest copy — we intentionally avoid earnings claims per Apple guidelines
4.3.0 and FTC.
"""
import asyncio
import base64
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load backend .env so we get EMERGENT_LLM_KEY
load_dotenv("/app/backend/.env")
from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: E402

OUT_DIR = Path("/app/store/marketing")
OUT_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("EMERGENT_LLM_KEY")
if not API_KEY:
    print("ERROR: EMERGENT_LLM_KEY missing from /app/backend/.env")
    sys.exit(1)


ASSETS = [
    {
        "filename": "icon-1024.png",
        "session": "scm-icon-v3",
        "prompt": (
            "Design a clean, premium iOS App Store icon, 1024x1024 px, perfectly square, "
            "no transparency, no rounded corners (Apple adds those). Solid dark navy background "
            "(#0B0E14). Center motif: a stylized Bitcoin ₿ symbol fused with a circuit "
            "board pattern, glowing emerald green (#10B981) with subtle neon teal accents. "
            "Tiny lightning bolt detail in the lower right. Flat modern minimal style, "
            "high contrast, NO TEXT, NO LETTERS, NO NUMBERS. Apple-grade polish."
        ),
    },
    {
        "filename": "banner-hero.png",
        "session": "scm-hero-v3",
        "prompt": (
            "App Store promotional hero banner, 16:9 widescreen ratio. Dark navy background "
            "(#0B0E14) with a faint hex-grid pattern. Center: a sleek modern iPhone 15 Pro "
            "mockup tilted slightly, screen showing a Bitcoin mining dashboard with a glowing "
            "₿ logo, line charts, and a green hashrate counter. Around the phone: emerald and "
            "teal light particles floating like data packets. Top-right small text only: "
            "'SATOSHI CLOUD MINER' in white sans-serif. Lower-left small text: "
            "'Bitcoin mining performance, simplified.' Minimal, premium, fintech aesthetic."
        ),
    },
    {
        "filename": "banner-feature-mine.png",
        "session": "scm-feat-mine-v3",
        "prompt": (
            "Promotional slide, 16:9. Dark background. Left half: iPhone mockup showing a "
            "'Mine' tab with hashrate cards. Right half: white headline text 'AI-OPTIMIZED MINING "
            "PLANS' in bold sans-serif, subtext 'Pick a hashrate that matches your goals.' "
            "Emerald green accent line. No earnings figures, no dollar amounts."
        ),
    },
    {
        "filename": "banner-feature-yield.png",
        "session": "scm-feat-yield-v3",
        "prompt": (
            "Promotional slide, 16:9. Dark background. Left half: iPhone mockup showing a "
            "Lightning Network withdrawal screen with a BOLT11 invoice QR code on screen. "
            "Right half: white headline text 'INSTANT LIGHTNING WITHDRAWALS' in bold sans-serif, "
            "subtext 'Cash out to any Lightning wallet, anytime.' Teal accent. No earnings "
            "claims, no specific amounts shown."
        ),
    },
    {
        "filename": "banner-feature-support.png",
        "session": "scm-feat-supp-v3",
        "prompt": (
            "Promotional slide, 16:9. Dark navy background. Left half: iPhone mockup showing a "
            "chat-style support conversation with green and gray message bubbles. Right half: "
            "white headline 'PREMIUM SUPPORT INSIDE THE APP' in bold sans-serif, subtext "
            "'Get a response from our operator team within 48 hours.' Emerald accent line."
        ),
    },
    {
        "filename": "banner-cta.png",
        "session": "scm-cta-v3",
        "prompt": (
            "Closing promo slide, 16:9. Dark navy background (#0B0E14) with subtle radial "
            "glow in emerald. Center: large stylized ₿ logo with circuit accents. Below: bold "
            "white text 'SATOSHI CLOUD MINER' and underneath in lighter weight 'Download free "
            "on the App Store today.' Clean, premium, no specific earning claims."
        ),
    },
]


async def generate_one(item: dict) -> bool:
    print(f"  → Generating {item['filename']} …")
    chat = LlmChat(
        api_key=API_KEY,
        session_id=item["session"],
        system_message="You are an expert App Store marketing designer.",
    ).with_model("gemini", "gemini-3.1-flash-image-preview").with_params(
        modalities=["image", "text"]
    )
    try:
        text, images = await chat.send_message_multimodal_response(
            UserMessage(text=item["prompt"])
        )
    except Exception as e:
        print(f"    ✖ FAILED {item['filename']}: {e}")
        return False
    if not images:
        print(f"    ✖ No image returned for {item['filename']} (text: {text[:80]})")
        return False
    out_path = OUT_DIR / item["filename"]
    image_bytes = base64.b64decode(images[0]["data"])
    # Gemini Nano Banana sometimes returns JPEG bytes even when prompted for
    # PNG. EAS expo-doctor enforces magic-byte ↔ extension matching and will
    # fail the build (icon field is .png but bytes are jpg). Round-trip
    # through Pillow so the on-disk file is always a real PNG.
    from io import BytesIO
    from PIL import Image as _PILImage
    img = _PILImage.open(BytesIO(image_bytes)).convert("RGBA")
    img.save(out_path, format="PNG", optimize=True)
    size_kb = out_path.stat().st_size / 1024
    print(f"    ✓ Saved {out_path}  ({size_kb:.1f} KB, real PNG)")
    return True


async def main() -> int:
    print(f"Generating {len(ASSETS)} marketing assets via Gemini Nano Banana …")
    results = await asyncio.gather(*[generate_one(a) for a in ASSETS])
    success = sum(1 for r in results if r)
    print(f"\nDone. {success}/{len(ASSETS)} succeeded.")
    return 0 if success == len(ASSETS) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
