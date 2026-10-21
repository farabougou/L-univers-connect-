---
id: 7
title: "STUDIO.split reads textContent and drops inline emphasis markup"
status: open
type: open-source
skill: [studio-motion-system]
proposes_skill: []
target_file: [videos/_studio/studio.js]
siblings_checked: "studio: studio-motion-system added (documents split); studio-quality excluded — references the helper only (assumed); studio-polish-pass excluded (assumed)"
area: "Text helpers / split"
date: 2026-10-21
session_context: "Enoryx and motion reel headlines with a colored <em> word"
parked_until:
resolved:
resolution:
reference:
commands_verified: none
---

**Issue:** Headlines with a coloured <em> word cannot go through split() (it rebuilds from textContent). Each project pre-builds .st-mask spans by hand; a naive pre-build split the <em> tag itself and produced a 1 200 px overflowing line.

**Suggested improvement:** Let split() walk child nodes and keep each word's enclosing inline element (class and tag), or document the pre-built markup pattern with a tag-aware word splitter.

**Principle:** A text-splitting helper must preserve inline styling, or every styled headline bypasses it.
