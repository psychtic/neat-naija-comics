import json, os, random, glob, datetime, time, urllib.request, urllib.error

API_KEY = os.environ["GEMINI_API_KEY"]
BASE = "https://generativelanguage.googleapis.com/v1beta/"

# Preferred models first. The robot also asks Google which flash models exist today,
# so old names being retired will not break it.
PREFERRED = ["gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash-lite", "gemini-flash-lite-latest"]
SKIP_WORDS = ("tts", "image", "live", "audio", "embedding", "robotics", "computer", "thinking-exp")


def find_models():
    models = list(PREFERRED)
    try:
        req = urllib.request.Request(BASE + "models?pageSize=200", headers={"x-goog-api-key": API_KEY})
        with urllib.request.urlopen(req, timeout=60) as r:
            listing = json.load(r)
        for m in listing.get("models", []):
            name = m["name"].replace("models/", "")
            if "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            if "flash" not in name or any(w in name for w in SKIP_WORDS):
                continue
            if name not in models:
                models.append(name)
    except Exception as e:
        print("Could not list models:", e)
    print("Models to try:", models)
    return models


CAST = (
    "Chidi: young Nigerian man in his late 20s, short black hair, casual t-shirt. "
    "Aunty Ngozi: middle-aged Nigerian woman, colourful wrapper and blouse, gele headwrap. "
    "Neat Naija attendant: professional Nigerian person in a neat green uniform and glasses."
)
AUDIENCES = ["single men", "single ladies", "married couples", "busy workers", "students", "parents"]
ENDING = "Laundry, house, office, sofa and carpet cleaning. DM to book."

os.makedirs("stories", exist_ok=True)
old_titles = []
for f in glob.glob("stories/*.json"):
    try:
        with open(f, encoding="utf-8") as fh:
            old_titles.append(json.load(fh)["title"])
    except Exception:
        pass

audience = random.choice(AUDIENCES)
prompt = (
    "You write funny comic stories for Neatnaija, a Nigerian laundry and cleaning business. "
    "Write a 6-scene comic storyboard in light Nigerian Pidgin. "
    "The audience is: " + audience + ". "
    "Characters you may use: " + CAST + " "
    "Scenes 1 to 5 show a funny cleaning or laundry disaster that gets worse. "
    "Scene 6: the Neat Naija attendant saves the day. "
    "The caption of scene 6 must end with: " + ENDING + " "
    "Do not repeat these old titles: " + ", ".join(old_titles) + ". "
    "Return JSON with keys: title (string), audience (string), "
    "scenes (a list of exactly 6 items, each with keys picture, dialogue, caption). "
    "picture describes what we see, in English, for an image drawing tool. "
    "dialogue is short speech in Pidgin. caption is one funny line."
)

body = json.dumps({
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {"responseMimeType": "application/json"},
}).encode("utf-8")

models = find_models()
dead = set()  # models that do not exist for us (404/400/403): never try them again
story = None

for round_number in range(5):
    for model in models:
        if model in dead:
            continue
        try:
            req = urllib.request.Request(
                BASE + "models/" + model + ":generateContent",
                data=body,
                headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY},
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
            candidate = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
            if len(candidate["scenes"]) == 6:
                story = candidate
                print("Used model:", model)
                break
            print(model, "gave", len(candidate["scenes"]), "scenes, moving on")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:200].replace("\n", " ")
            print(model, "failed with", e.code, detail)
            if e.code not in (429, 500, 502, 503, 504):
                dead.add(model)
        except Exception as e:
            print(model, "problem:", e)
    if story:
        break
    print("Round", round_number + 1, "failed. Waiting before trying again.")
    time.sleep(20 * (round_number + 1))

if not story:
    raise SystemExit("All models failed. Try again later.")

name = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d-%H%M")
with open("stories/" + name + ".json", "w", encoding="utf-8") as out:
    json.dump(story, out, ensure_ascii=False, indent=2)
print("Saved story:", story["title"])
