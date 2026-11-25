import json, os, random, glob, datetime, urllib.request

API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-flash-latest"

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

url = "https://generativelanguage.googleapis.com/v1beta/models/" + MODEL + ":generateContent"
body = {
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {"responseMimeType": "application/json"},
}
req = urllib.request.Request(
    url,
    data=json.dumps(body).encode("utf-8"),
    headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY},
)
with urllib.request.urlopen(req, timeout=120) as r:
    data = json.load(r)

story = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
if len(story["scenes"]) != 6:
    raise SystemExit("Story did not have 6 scenes")

name = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d-%H%M")
with open("stories/" + name + ".json", "w", encoding="utf-8") as out:
    json.dump(story, out, ensure_ascii=False, indent=2)
print("Saved story:", story["title"])
