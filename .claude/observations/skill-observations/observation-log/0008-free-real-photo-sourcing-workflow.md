---
id: 8
title: "Sourcing real, license-safe photos for an ad is a reusable workflow"
status: open
type: open-source
skill: []
proposes_skill: [free-photo-sourcing]
target_file: []
siblings_checked: "none — proposed new skill, no family yet"
area: "Media sourcing for ads"
date: 2026-10-21
session_context: "Enoryx installations ad needed real HVAC/cold-room/generator photos"
parked_until:
resolved:
resolution:
reference: "videos/enoryx-installations/CREDITS.md"
commands_verified: "run: Commons REST search (api.wikimedia.org/core/v1/commons/search/page) with a User-Agent → 200; run: action API imageinfo extmetadata → license and author; run: thumbnail 2560px → HTTP 400, 1920px → OK"
---

**Issue:** Getting real photos took many probes: Openverse timed out, Unsplash and Pexels refused, Commons needed a User-Agent, throttling (429, Retry-After), standard thumbnail sizes only, and license sorting (avoid BY-SA in ads, credit CC BY).

**Suggested improvement:** A small skill: query Commons REST search with a User-Agent, read license and author through imageinfo extmetadata, keep public domain, CC0 and CC BY, fetch the 1920 px standard thumbnail with paced retries, write a credits file and an on-screen credit line.

**Principle:** Licence and author are fetched with the image and written into the project at the same time, never reconstructed later.
