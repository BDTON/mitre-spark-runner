#!/usr/bin/env python3
"""Fetch OpenRouter model pricing for astra/gpt-6 models."""
import json
import urllib.request

url = "https://openrouter.ai/api/v1/models"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=15) as resp:
    d = json.load(resp)

for m in d["data"]:
    mid = m["id"]
    if "astra" in mid.lower() or "gpt-6" in mid.lower():
        pricing = m.get("pricing", {})
        print(f"{mid}: prompt=${pricing.get('prompt', 0)}/tok, completion=${pricing.get('completion', 0)}/tok, context={m.get('context_length', '?')}")
