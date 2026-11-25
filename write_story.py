import json, os, random, glob, datetime, time, urllib.request, urllib.error

API_KEY = os.environ["GEMINI_API_KEY"]
# The robot tries these models in order. If one is busy it waits, retries, then moves to the next.
MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite"]

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

story = None
for model in MODELS:
    url = "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent"
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY},
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
            candidate = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
            if len(candidate["scenes"]) == 6:
                story = candidate
                break
            print("Model", model, "gave", len(candidate["scenes"]), "scenes, trying again")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:300]
            print("Model", model, "attempt", attempt + 1, "failed with", e.code, detail)
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(15 * (attempt + 1))
                continue
            break  # a different kind of error: skip to the next model
        except Exception as e:
            print("Model", model, "attempt", attempt + 1, "problem:", e)
            time.sleep(5)
    if story:
        print("Used model:", model)
        break

if not story:
    raise SystemExit("All models failed. Try again later.")

name = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d-%H%M")
with open("stories/" + name + ".json", "w", encoding="utf-8") as out:
    json.dump(story, out, ensure_ascii=False, indent=2)
print("Saved story:", story["title"])
