# -*- coding: utf-8 -*-
"""Dependency-free HTML text extractor for exported/public HTML files."""
import os
from html.parser import HTMLParser
from pathlib import Path

class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.in_script=0; self.in_style=0; self.time_text=[]; self.times=[]
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): setattr(self, 'in_'+tag, 1)
        if tag=='time': self.time_text=[]
    def handle_endtag(self, tag):
        if tag in ('script','style'): setattr(self, 'in_'+tag, 0)
        if tag=='time' and self.time_text: self.times.append(' '.join(self.time_text).strip())
    def handle_data(self, data):
        if self.in_script or self.in_style: return
        text=' '.join(data.split())
        if text: self.parts.append(text); self.time_text.append(text)

def parse_facebook_posts(html_file_path):
    path=Path(html_file_path)
    if not path.exists(): return []
    parser=_Parser(); parser.feed(path.read_text(encoding='utf-8', errors='replace'))
    # This is intentionally conservative: an export's exact DOM differs by version.
    text=' '.join(parser.parts)
    if not text: return []
    chunks=[x.strip() for x in text.split('  ') if len(x.strip())>15]
    seen=set(); posts=[]
    for chunk in chunks:
        if chunk in seen: continue
        seen.add(chunk); posts.append({"content":chunk,"timestamp":parser.times[len(posts)] if len(posts)<len(parser.times) else ""})
    return posts[:10000]
