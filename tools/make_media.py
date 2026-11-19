"""Generate share/preview media from the built page (run locally; needs Playwright + Chrome + ffmpeg).

  python tools/make_media.py http://localhost:8000/index.html

Writes:
  media/og.png       1200x630 social preview (LinkedIn / X / Slack)
  media/demo.mp4     ~12 s hero animation (rush hour)
  media/demo.gif     lighter GIF of the same, for the README
"""
import asyncio
import subprocess
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "media"
URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/index.html"
CHROME = "/usr/bin/google-chrome"

OG_CSS = """
nav, #rail, #prog, .hero-num, .linechips, .byline, .mapnote, .ctrl, .eyebrow { display:none !important }
header { padding: 34px 0 0 !important }
header .wrap.hero { max-width: 1200px; padding: 0 48px; gap: 36px; grid-template-columns: 1fr 1.08fr }
header h1 { font-size: 74px !important; max-width: 9ch }
.dek { font-size: 23px !important; max-width: 26ch; margin-top: 18px }
.hud { margin-bottom: 6px }
.og-tag { font-family: var(--f-mono); font-size: 15px; letter-spacing: .05em; text-transform: uppercase; color: var(--muted); margin: 26px 0 0 }
"""


async def set_hour(pg, h):
    await pg.evaluate(f"() => {{ const s = document.getElementById('hour'); s.value = {h}; s.dispatchEvent(new Event('input')); }}")


async def main():
    MEDIA.mkdir(exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        # --- social preview ---
        pg = await b.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=2)
        await pg.goto(URL)
        await pg.wait_for_timeout(3500)
        await pg.add_style_tag(content=OG_CSS)
        await pg.evaluate("""() => { const d = document.querySelector('.dek');
            d.textContent = 'Two official MBTA ridership numbers disagree by up to 23%. Three datasets show where the missing riders are.';
            const t = document.createElement('p'); t.className = 'og-tag'; t.textContent = 'Shreyas Tayde · Data reconciliation · Boston'; d.after(t);
            document.getElementById('play').click(); }""")
        await set_hour(pg, 5.5)  # 8:30 AM
        await pg.wait_for_timeout(400)
        await pg.screenshot(path=str(MEDIA / "og.png"), clip={"x": 0, "y": 0, "width": 1200, "height": 630})
        await pg.close()

        # --- demo frames: map card only, 6:30 AM -> 10:30 AM ---
        pg = await b.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
        await pg.goto(URL)
        await pg.wait_for_timeout(3500)
        await pg.evaluate("() => document.getElementById('play').click()")
        frames = MEDIA / "frames"
        frames.mkdir(exist_ok=True)
        box = await pg.query_selector("header .hero > div:nth-child(2)")
        n = 300
        for i in range(n):
            await set_hour(pg, 3.5 + 4.0 * i / n)
            await box.screenshot(path=str(frames / f"f{i:04d}.png"))
        await b.close()

    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "25", "-i", str(frames / "f%04d.png"),
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
                    "-pix_fmt", "yuv420p", str(MEDIA / "demo.mp4")], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(MEDIA / "demo.mp4"), "-vf",
                    "fps=12,scale=520:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
                    str(MEDIA / "demo.gif")], check=True)
    for f in frames.glob("*.png"):
        f.unlink()
    frames.rmdir()
    print("media written:", [f.name for f in MEDIA.iterdir()])


if __name__ == "__main__":
    asyncio.run(main())
