from openai import OpenAI
import requests
import uuid
import json
import os
from dateutil.parser import parse as parse_date
from datetime import datetime, timezone
from difflib import get_close_matches
import random

client = OpenAI()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

CATEGORY_IMAGES = {
    "Culture": [
        "https://images.unsplash.com/photo-1533049022229-6e319a8abf8d",
        "https://images.unsplash.com/photo-1516637090014-cb1ab78511f5"
    ],
    "Seasonal": [
        "https://images.unsplash.com/photo-1608889175115-98140b67e126",
        "https://images.unsplash.com/photo-1483683804023-6ccdb62f86ef"
    ],
    "Music": [
        "https://images.unsplash.com/photo-1511376777868-611b54f68947",
        "https://images.unsplash.com/photo-1485579149621-3123dd979885"
    ],
    "Arts": [
        "https://images.unsplash.com/photo-1581091012184-e0fc0a29eab1",
        "https://images.unsplash.com/photo-1540503831541-329cd3a7b5f4"
    ],
    "Iconic": [
        "https://images.unsplash.com/photo-1587502537745-84f1c933ef1e",
        "https://images.unsplash.com/photo-1512453979798-5ea266f8880c"
    ],
    "Nature": [
        "https://images.unsplash.com/photo-1506744038136-46273834b3fb",
        "https://images.unsplash.com/photo-1470770841072-f978cf4d019e"
    ],
    "Sports": [
        "https://images.unsplash.com/photo-1605408499391-6368c219e4c3",
        "https://images.unsplash.com/photo-1521412644187-c49fa049e84d"
    ]
}

# Step 1: Delete expired events
today = datetime.now(timezone.utc).date().isoformat()
delete_url = f"{SUPABASE_URL}/rest/v1/events?end_date=lt.{today}"
delete_headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
}
delete_res = requests.delete(delete_url, headers=delete_headers)
print(f"🧹 Deleted past events → Status: {delete_res.status_code}")

# Step 2: Generate 10–15 new events
prompt = """Give me 12 upcoming global cultural, iconic, or seasonal events happening between now and July 2026.
Return only a raw JSON array. Each object must include:
- name
- location
- start_date
- end_date
- category (Culture, Seasonal, Music, Arts, Iconic, Nature, Sports)
- description (1–2 sentence summary)
Do not include an image_url."""

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.7
)

content = response.choices[0].message.content.strip()
if content.startswith("```json"):
    content = content.removeprefix("```json").removesuffix("```").strip()
elif content.startswith("```"):
    content = content.removeprefix("```").removesuffix("```").strip()

try:
    events = json.loads(content)
except Exception as e:
    print("❌ Failed to parse GPT output:", e)
    print("Raw content was:", content)
    exit(1)

# Step 3: Fetch all current events for fuzzy match
headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json"
}
existing_res = requests.get(f"{SUPABASE_URL}/rest/v1/events?select=name,start_date", headers=headers)
existing_events = existing_res.json() if existing_res.status_code == 200 else []
existing_lookup = [(e["name"], e["start_date"]) for e in existing_events]

def is_duplicate(name, start_date):
    matches = [e_name for e_name, e_date in existing_lookup if e_date == start_date]
    return bool(get_close_matches(name, matches, n=1, cutoff=0.8))

def assign_image(category):
    images = CATEGORY_IMAGES.get(category, [])
    return random.choice(images) if images else "https://source.unsplash.com/random/800x600?" + category.lower()

def is_valid_date(date_str):
    try:
        parse_date(date_str)
        return True
    except:
        return False

required_fields = {"name", "location", "start_date", "end_date", "category", "description"}
inserted = 0
for event in events:
    if not required_fields.issubset(event.keys()):
        print("⚠️ Skipping incomplete event:", event)
        continue
    if not is_valid_date(event["start_date"]) or not is_valid_date(event["end_date"]):
        print("⚠️ Invalid date format, skipping:", event)
        continue
    if is_duplicate(event["name"], event["start_date"]):
        print(f"⏩ Skipping fuzzy duplicate: {event['name']}")
        continue

    event["image_url"] = assign_image(event["category"])
    event["id"] = str(uuid.uuid4())

    res = requests.post(f"{SUPABASE_URL}/rest/v1/events", headers={**headers, "Prefer": "resolution=merge-duplicates"}, json=event)
    if res.status_code in [200, 201]:
        inserted += 1
        print(f"✅ Inserted: {event['name']}")
    else:
        print(f"❌ Failed to insert: {event['name']} →", res.status_code, res.text)

print(f"🎉 Weekly update done. {inserted} new events inserted.")
