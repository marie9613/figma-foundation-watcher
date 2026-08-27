#!/usr/bin/env python3
"""Canonical hashing method for Foundations sub-page state.

This module does not run standalone: it has no network or Figma API access
of its own. It documents the exact, reproducible procedure an agent with
Figma MCP tool access must follow to compute each sub-page's content hash
for state.json, so that repeated runs are comparable:

  1. Call the Figma MCP tool `get_metadata` with fileKey=FILE_KEY and
     nodeId=<page node id from PAGES below>.
  2. Take the XML text of the response.
  3. Strip the trailing boilerplate the tool appends
     ("IMPORTANT: After you call this tool...").
  4. Strip leading/trailing whitespace.
  5. Encode as UTF-8 and take the sha256 hex digest (normalize_hash below).

Do not use the Figma REST API (`api.figma.com`) to compute these hashes:
its /v1/files/*/nodes response shape does not match get_metadata's XML and
produces hashes that cannot be compared against this baseline.
"""
import hashlib

FILE_KEY = "4EZqcDA8pAD4CVfPR9f9Gh"

PAGES = {
    "Colors": "37:2",
    "Typography": "37:3",
    "Spatial": "24109:2951",
    "Grids": "30396:77272",
    "Effects": "24123:50",
    "Image": "24243:6889",
    "Assets": "24243:6892",
}

BOILERPLATE_MARKER = "IMPORTANT: After you call this tool"


def normalize_hash(xml_text):
    idx = xml_text.find(BOILERPLATE_MARKER)
    if idx != -1:
        xml_text = xml_text[:idx]
    xml_text = xml_text.strip()
    return hashlib.sha256(xml_text.encode("utf-8")).hexdigest()
