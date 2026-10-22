"""Quick Pixabay API connectivity check — no file download."""
import os, requests
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("PIXABAY_API_KEY", "").strip()
print(f"Key loaded: {key[:8]}...{key[-4:]}")

url = (
    "https://pixabay.com/api/videos/"
    f"?key={key}"
    "&q=sunrise+worship+nature"
    "&video_type=film"
    "&category=nature"
    "&min_duration=30"
    "&per_page=3"
    "&safesearch=true"
)

resp = requests.get(url, timeout=15)
data = resp.json()
hits  = data.get("hits", [])
total = data.get("totalHits", 0)

print(f"HTTP {resp.status_code} | Total hits: {total} | Returned: {len(hits)}")
for i, h in enumerate(hits):
    dur = h.get("duration", "?")
    med = h.get("videos", {}).get("medium", {}).get("url", "N/A")[:60]
    print(f"  [{i+1}] {dur}s  {med}...")
print("DONE")
