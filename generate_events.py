import os
import requests
import uuid
import json
from openai import OpenAI

# Initialize OpenAI client (new SDK format)
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

prompt = """
Give me 5 upcoming cultural events happening worldwide between today and July 2026.
For each event, return a JSON object with the fields:
name, location, start_date, end_date, image_url, category, and description.
"""

# Call OpenAI using new SDK syntax
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.7
)

content = response.choices[0].message.content

try:
    events = json.loads(content)
except Exception as e:
    print("❌ Failed to parse GPT output:", e)
    print("Raw content was:", content)
    exit(1)

headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

inserted = 0
for event in events:
    # Check for existing event by name + start_date
    query = f"{SUPABASE_URL}/rest/v1/events?select=id&name=eq.{event['name']}&start_date=eq.{event['start_date']}"
    check = requests.get(query, headers=headers)
    if check.status_code == 200 and check.json():
        print(f"⚠️ Skipping duplicate: {event['name']} ({event['start_date']})")
        continue

    event['id'] = str(uuid.uuid4())
    res = requests.post(f"{SUPABASE_URL}/rest/v1/events", headers=headers, json=event)
    if res.status_code in [200, 201]:
        inserted += 1
        print(f"✅ Inserted: {event['name']}")
    else:
        print(f"❌ Failed to insert: {event['name']} —", res.text)

print(f"🏁 Done. Inserted {inserted} new events.")
