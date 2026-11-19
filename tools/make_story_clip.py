"""Record the scroll story as a short clip (run locally; needs Playwright + Chrome + ffmpeg).

  python tools/make_story_clip.py http://localhost:8000/index.html

Writes:
  media/story.mp4      ~30 s screen recording, desktop layout (for LinkedIn / the site)
  media/story_sq.mp4   1:1 crop of the map only (for social feeds)
  media/story.gif      lighter GIF of the map, for the README
"""
import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "media"
URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/index.html"
W, H = 1280, 800
HOLD = [3.5, 3.2, 7.5, 4.5, 4.5]  # seconds to linger on each step (step 3 = the invisible riders)


async def main():
    MEDIA.mkdir(exist_ok=True)
    tmp = MEDIA / "_rec"
    shutil.rmtree(tmp, ignore_errors=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome")
        ctx = await b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(tmp),
                                  record_video_size={"width": W, "height": H})
        pg = await ctx.new_page()
        await pg.goto(URL)
        await pg.wait_for_timeout(3000)
        # hide chrome that isn't part of the story
        await pg.add_style_tag(content="#rail,#prog{display:none!important}")
        tops = await pg.evaluate("""() => [...document.querySelectorAll('.step')].map(s => {
            const r = s.getBoundingClientRect(); return r.top + scrollY + r.height/2 - innerHeight/2; })""")
        await pg.evaluate(f"() => scrollTo(0, {tops[0]})")
        await pg.wait_for_timeout(1200)
        mark = await pg.evaluate("() => performance.now()")
        for i, y in enumerate(tops):
            if i:
                # eased scroll from previous step to this one over ~1.1 s
                await pg.evaluate(f"""() => new Promise(res => {{ const y0 = scrollY, y1 = {y}, t0 = performance.now();
                    (function f(t) {{ const p = Math.min(1, (t - t0) / 1100), e = p < .5 ? 2*p*p : 1 - Math.pow(-2*p + 2, 2)/2;
                      scrollTo(0, y0 + (y1 - y0) * e); p < 1 ? requestAnimationFrame(f) : res(); }})(t0); }})""")
            await pg.wait_for_timeout(int(HOLD[i] * 1000))
        box = await pg.evaluate("() => { const r = document.getElementById('stmap').getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }")
        lead = (await pg.evaluate("() => performance.now()") - mark) / 1000
        await ctx.close()
        await b.close()
    raw = next(tmp.glob("*.webm"))
    # rough start offset: total recording minus the timed section
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(raw)]).decode().strip())
    ss = max(0, dur - lead - 0.2)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{ss:.2f}", "-i", str(raw), "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(MEDIA / "story.mp4")], check=True)
    x, y, w, h = [int(v) for v in box]
    s = min(w, h) // 2 * 2
    crop = f"crop={s}:{s}:{x + (w - s)//2}:{y + (h - s)//2}"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(MEDIA / "story.mp4"), "-vf", crop, "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(MEDIA / "story_sq.mp4")], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(MEDIA / "story.mp4"), "-vf",
                    "fps=12,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
                    str(MEDIA / "story.gif")], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print("written:", [(f.name, f.stat().st_size // 1024) for f in MEDIA.glob("story*")])


asyncio.run(main())
