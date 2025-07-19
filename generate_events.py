from openai import OpenAI
import requests
import uuid
import json
from dateutil.parser import parse as parse_date
from datetime import datetime, timezone
import os

client = OpenAI()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

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
Respond ONLY with a raw JSON array, without markdown or formatting.
Each event must have:
- name (string)
- location (string, format: City, Country)
- start_date (ISO8601)
- end_date (ISO8601)
- image_url (string)
- category (one of: Culture, Seasonal, Music, Arts, Iconic, Nature, Sports)
- description (1–2 sentence summary of the event)"""

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

# Step 3: Validate & de-duplicate
headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

def is_valid_date(date_str):
    try:
        parse_date(date_str)
        return True
    except:
        return False

required_fields = {"name", "location", "start_date", "end_date", "image_url", "category", "description"}
inserted = 0
for event in events:
    if not required_fields.issubset(event.keys()):
        print("⚠️ Skipping incomplete event:", event)
        continue
    if not is_valid_date(event["start_date"]) or not is_valid_date(event["end_date"]):
        print("⚠️ Invalid date format, skipping:", event)
        continue

    # Check for duplicate
    query = f"{SUPABASE_URL}/rest/v1/events?select=id&name=eq.{event['name']}&start_date=eq.{event['start_date']}"
    check = requests.get(query, headers=headers)
    if check.status_code == 200 and check.json():
        print(f"⏩ Skipping duplicate: {event['name']}")
        continue

    # Assign UUID and insert
    event['id'] = str(uuid.uuid4())
    res = requests.post(f"{SUPABASE_URL}/rest/v1/events", headers=headers, json=event)
    if res.status_code in [200, 201]:
        inserted += 1
        print(f"✅ Inserted: {event['name']}")
    else:
        print(f"❌ Failed to insert: {event['name']} →", res.status_code, res.text)

print(f"🎉 Weekly update done. {inserted} new events inserted.")
