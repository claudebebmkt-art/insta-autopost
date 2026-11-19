#!/usr/bin/env python3
"""Renova o token de longa duração do Instagram (vale 60 dias) e imprime o novo."""
import json
import os
import urllib.parse
import urllib.request

q = urllib.parse.urlencode({"grant_type": "ig_refresh_token",
                            "access_token": os.environ["IG_ACCESS_TOKEN"]})
with urllib.request.urlopen(f"https://graph.instagram.com/refresh_access_token?{q}") as r:
    data = json.loads(r.read())
print(data["access_token"])
