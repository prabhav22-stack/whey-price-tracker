
"""
amazon.py - Version 2.1

Adds:
- Multi-source price extraction
- Consensus voting
- Diagnostic output
"""

from __future__ import annotations
import re
from collections import Counter
from typing import Optional

from bs4 import BeautifulSoup
from curl_cffi import requests

BROWSER = "chrome136"
HEADERS = {
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://www.amazon.in/",
}

PRICE_SELECTORS = {
    "priceToPay": "#priceToPay .a-offscreen",
    "corePriceDisplay": "#corePriceDisplay_desktop_feature_div .a-offscreen",
    "corePrice": "#corePrice_feature_div .a-offscreen",
    "desktop_buybox": "#desktop_buybox .a-offscreen",
    "apexPrice": ".apex-pricetopay-value .a-offscreen",
}

def extract_asin(url:str)->Optional[str]:
    for p in (r"/dp/([A-Z0-9]{10})", r"/gp/product/([A-Z0-9]{10})"):
        m=re.search(p,url)
        if m: return m.group(1)
    return None

def download_page(url:str):
    r=requests.get(url,impersonate=BROWSER,headers=HEADERS,timeout=60,allow_redirects=True)
    r.raise_for_status()
    return r

def make_soup(html:str):
    try:
        return BeautifulSoup(html,"lxml")
    except Exception:
        return BeautifulSoup(html,"html.parser")

def extract_title(soup):
    for sel in ["#productTitle","#title span","#title","h1 span","title"]:
        n=soup.select_one(sel)
        if n:
            t=n.get_text(" ",strip=True)
            return t.replace(": Amazon.in","").strip()
    return None

def parse_price(text:str):
    m=re.search(r"₹\s*([\d,]+(?:\.\d{2})?)",text)
    if not m:
        return None
    return float(m.group(1).replace(",",""))

def extract_price_candidates(soup):
    c=[]
    for name,sel in PRICE_SELECTORS.items():
        node=soup.select_one(sel)
        if not node: continue
        p=parse_price(node.get_text(" ",strip=True))
        if p:
            c.append({"price":p,"source":name})
    return c

def choose_best_price(candidates):
    if not candidates:
        return None,None
    counts=Counter(x["price"] for x in candidates)
    winner,_=counts.most_common(1)[0]
    src=[c["source"] for c in candidates if c["price"]==winner]
    return winner,src

def print_price_diagnostics(candidates):
    print("\n"+"="*50)
    print("PRICE CANDIDATES")
    print("="*50)
    if not candidates:
        print("No candidates found.")
        return
    for c in candidates:
        print(f'{c["source"]:<20} ₹{c["price"]:,.2f}')
    winner,sources=choose_best_price(candidates)
    print("-"*50)
    print(f"Winner      : ₹{winner:,.2f}")
    print(f"Agreement   : {len(sources)} source(s)")
    print(f"Sources     : {', '.join(sources)}")

def check_price(url:str)->dict:
    asin=extract_asin(url)
    if not asin:
        return {"success":False,"error":"Could not extract ASIN."}
    try:
        resp=download_page(url)
    except Exception as e:
        return {"success":False,"error":str(e)}
    soup=make_soup(resp.text)
    title=extract_title(soup)
    candidates=extract_price_candidates(soup)
    price,sources=choose_best_price(candidates)
    return {
        "success":True,
        "source":"amazon",
        "asin":asin,
        "title":title,
        "price":price,
        "price_sources":sources or [],
        "status_code":resp.status_code,
        "url":resp.url,
        "html_length":len(resp.text),
        "_diagnostics":candidates,
    }

if __name__=="__main__":
    URL=("https://www.amazon.in/Platinum-Protein-Isolate-Digestive-Supplement/"
         "dp/B07WZM3714/ref=sr_1_1_in_f3_wg_fs?almBrandId=ctnow")
    result=check_price(URL)
    print("="*50)
    print("Amazon Checker V2.1")
    print("="*50)
    if not result["success"]:
        print(result["error"])
    else:
        print("Title :",result["title"])
        print("Price :",result["price"])
        print("ASIN  :",result["asin"])
        print_price_diagnostics(result["_diagnostics"])
