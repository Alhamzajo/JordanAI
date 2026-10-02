# -*- coding: utf-8 -*-
"""Optional public RSS reader. Failure is reported honestly; no synthetic fallback news."""
import urllib.request
import xml.etree.ElementTree as ET

DEFAULT_SOURCES = [
    {"name":"بترا", "url":"https://www.petra.gov.jo/Rss/ar/1"},
]


def fetch_latest_jordan_news(sources=None, limit=5, timeout=8):
    results=[]; errors=[]
    for source in (sources or DEFAULT_SOURCES):
        try:
            req=urllib.request.Request(source["url"], headers={"User-Agent":"Jordan-AI-Local/2.0"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                xml_data=response.read()
            root=ET.fromstring(xml_data)
            items=root.findall('.//item')[:max(1,int(limit))]
            for item in items:
                title=(item.findtext('title') or 'بدون عنوان').strip()
                link=(item.findtext('link') or '').strip()
                summary=(item.findtext('description') or '').strip()
                results.append({"source":source["name"],"title":title,"link":link,"summary":summary})
            if results:
                break
        except Exception as exc:
            errors.append({"source":source["name"],"error":str(exc)})
    return {"items":results,"errors":errors,"fresh":bool(results)}

if __name__ == '__main__':
    print(fetch_latest_jordan_news())
