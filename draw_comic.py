import base64, glob, hashlib, io, json, os, shutil, time
import urllib.error, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageOps

API_KEY = os.environ.get("GEMINI_API_KEY", "")
BASE = "https://generativelanguage.googleapis.com/v1beta/"
UA = {"User-Agent": "Mozilla/5.0 (neatnaija-robot)"}
KEEP_COMICS = 14  # only the newest comics keep their pictures, so the repo stays small

STYLE = (
    "Colourful comic book illustration, bold clean outlines, flat vibrant colours, "
    "funny expressive faces, everyday Nigerian setting, square panel. "
    "Absolutely no text, no letters, no words and no speech bubbles in the picture."
)
CAST = {
    "chidi": "Chidi is a young Nigerian man in his late 20s with short black hair, wearing a casual t-shirt.",
    "ngozi": "Aunty Ngozi is a middle-aged Nigerian woman in a colourful wrapper and blouse with a gele headwrap.",
    "attendant": "The Neat Naija attendant is a professional Nigerian person in a neat green uniform and glasses.",
}

GREEN = "#1b8a3a"
W, IMG_H, CAP_H = 1080, 1080, 320


# ---------- getting pictures ----------
def fetch(url, data=None, headers=None, timeout=150):
    req = urllib.request.Request(url, data=data, headers=headers or UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", "")


def from_pollinations(prompt, seed):
    q = urllib.parse.quote(prompt)
    urls = [
        "https://image.pollinations.ai/prompt/" + q + "?width=1024&height=1024&seed=" + str(seed) + "&model=flux&nologo=true",
        "https://gen.pollinations.ai/image/" + q + "?width=1024&height=1024&seed=" + str(seed) + "&model=flux&nologo=true",
    ]
    for u in urls:
        host = u.split("/")[2]
        try:
            raw, ctype = fetch(u)
            if ctype.startswith("image/") and len(raw) > 5000:
                return Image.open(io.BytesIO(raw)).convert("RGB")
            print(host, "answered but it was not a picture:", ctype, len(raw))
        except urllib.error.HTTPError as e:
            print(host, "failed with", e.code, e.read()[:150])
        except Exception as e:
            print(host, "problem:", e)
    return None


def gemini_image_models():
    if not API_KEY:
        return []
    try:
        raw, _ = fetch(BASE + "models?pageSize=200", headers={"x-goog-api-key": API_KEY}, timeout=60)
        out = []
        for m in json.loads(raw).get("models", []):
            name = m["name"].replace("models/", "")
            if "image" in name and "generateContent" in m.get("supportedGenerationMethods", []):
                out.append(name)
        return out
    except Exception as e:
        print("Could not list Gemini image models:", e)
        return []


def from_gemini(prompt, models):
    for m in models:
        try:
            body = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
            }).encode("utf-8")
            raw, _ = fetch(
                BASE + "models/" + m + ":generateContent",
                data=body,
                headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY},
            )
            for part in json.loads(raw)["candidates"][0]["content"]["parts"]:
                inline = part.get("inlineData") or part.get("inline_data")
                if inline:
                    return Image.open(io.BytesIO(base64.b64decode(inline["data"]))).convert("RGB")
        except urllib.error.HTTPError as e:
            print("Gemini", m, "failed with", e.code, e.read()[:150])
        except Exception as e:
            print("Gemini", m, "problem:", e)
    return None


def get_picture(prompt, seed, gemini_models):
    for attempt in range(3):
        img = from_pollinations(prompt, seed)
        if img:
            return img
        img = from_gemini(prompt, gemini_models)
        if img:
            return img
        print("No picture on attempt", attempt + 1, "- waiting")
        time.sleep(20 * (attempt + 1))
    return None


def build_prompt(scene):
    picture = scene["picture"]
    low = picture.lower()
    who = []
    if "chidi" in low:
        who.append(CAST["chidi"])
    if "ngozi" in low:
        who.append(CAST["ngozi"])
    if "attendant" in low or "neat naija" in low or "neatnaija" in low:
        who.append(CAST["attendant"])
    return STYLE + " Scene: " + picture + " " + " ".join(who)


# ---------- drawing the comic ----------
def load_font(size):
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        test = (cur + " " + word).strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def make_panel(img, dialogue, caption, number):
    canvas = Image.new("RGB", (W, IMG_H + CAP_H), "white")
    canvas.paste(ImageOps.fit(img, (W, IMG_H)), (0, 0))
    d = ImageDraw.Draw(canvas)

    if dialogue:
        f = load_font(40)
        lines = wrap(d, dialogue, f, W - 200)[:4]
        h = len(lines) * 50 + 40
        d.rounded_rectangle((50, 40, W - 50, 40 + h), radius=30, fill="white", outline="black", width=5)
        for i, line in enumerate(lines):
            d.text((80, 60 + i * 50), line, font=f, fill="black")

    d.ellipse((W - 120, IMG_H - 120, W - 40, IMG_H - 40), fill=GREEN, outline="white", width=4)
    d.text((W - 80, IMG_H - 80), str(number), font=load_font(48), fill="white", anchor="mm")

    f2 = load_font(44)
    lines = wrap(d, caption, f2, W - 100)[:4]
    for i, line in enumerate(lines):
        d.text((50, IMG_H + 25 + i * 54), line, font=f2, fill="black")
    d.text((50, IMG_H + CAP_H - 55), "NEATNAIJA", font=load_font(34), fill=GREEN)
    return canvas


def make_comic(panels, title):
    cols, rows = 3, 2
    tw, th = W // 2, (IMG_H + CAP_H) // 2
    head = 170
    gap = 12
    comic = Image.new("RGB", (cols * tw + (cols + 1) * gap, head + rows * th + (rows + 1) * gap), "white")
    d = ImageDraw.Draw(comic)
    d.rectangle((0, 0, comic.width, head - 20), fill=GREEN)
    d.text((comic.width // 2, 55), title, font=load_font(64), fill="white", anchor="mm")
    d.text((comic.width // 2, 125), "Neatnaija saves the day!", font=load_font(38), fill="white", anchor="mm")
    for i, p in enumerate(panels):
        r, c = divmod(i, cols)
        comic.paste(p.resize((tw, th)), (gap + c * (tw + gap), head + gap + r * (th + gap)))
    return comic


# ---------- main ----------
stories = sorted(glob.glob("stories/*.json"))
todo = []
for s in stories:
    name = os.path.basename(s)[:-5]
    if not os.path.exists("comics/" + name + "/comic.jpg"):
        todo.append(s)
todo = todo[-1:]  # one comic per run keeps things fast

if not todo:
    print("Every story already has its comic.")
    raise SystemExit(0)

gemini_models = gemini_image_models()
print("Gemini image models found:", gemini_models)

for path in todo:
    name = os.path.basename(path)[:-5]
    with open(path, encoding="utf-8") as fh:
        story = json.load(fh)
    seed = int(hashlib.md5(name.encode()).hexdigest()[:6], 16)
    out_dir = "comics/" + name
    os.makedirs(out_dir, exist_ok=True)
    print("Drawing:", story["title"])

    panels = []
    for i, scene in enumerate(story["scenes"], 1):
        img = get_picture(build_prompt(scene), seed, gemini_models)
        if img is None:
            shutil.rmtree(out_dir, ignore_errors=True)
            raise SystemExit("Could not draw scene " + str(i) + ". Try again later.")
        panel = make_panel(img, scene.get("dialogue", ""), scene.get("caption", ""), i)
        panel.save(out_dir + "/panel-" + str(i) + ".jpg", quality=88)
        panels.append(panel)
        print("Scene", i, "done")
        time.sleep(4)

    make_comic(panels, story["title"]).save(out_dir + "/comic.jpg", quality=88)
    print("Comic saved in", out_dir)

# keep the repo small: only the newest comics keep their pictures
folders = sorted(d for d in glob.glob("comics/*") if os.path.isdir(d))
for old in folders[:-KEEP_COMICS]:
    shutil.rmtree(old, ignore_errors=True)
    print("Removed old pictures:", old)
