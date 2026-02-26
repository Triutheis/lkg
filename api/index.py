from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
import aiohttp
import json
import re
import time
import asyncio
import os

# Import cấu hình
try:
    from app.config import TOKEN_SETS
except ImportError:
    TOKEN_SETS = []

app = FastAPI()

HEADERS_TEMPLATE = {
    'Host': 'api.revenuecat.com',
    'Authorization': 'Bearer appl_JngFETzdodyLmCREOlwTUtXdQik',
    'Content-Type': 'application/json',
    'X-Platform': 'iOS',
    'X-Platform-Version': 'Version 26.2 (Build 23C55)',
    'X-Platform-Device': 'iPhone15,3',
    'X-Platform-Flavor': 'native',
    'X-Version': '5.41.0',
    'X-Client-Version': '2.32.2',
    'X-Client-Bundle-ID': 'com.locket.Locket',
    'X-StoreKit2-Enabled': 'true',
    'X-StoreKit-Version': '2',
    'X-Is-Sandbox': 'true',
    'User-Agent': 'Locket/3 CFNetwork/3860.300.31 Darwin/25.2.0',
}

async def resolve_uid(username):
    url = f"https://locket.cam/{username}"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)", "Accept": "text/html"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as res:
                html = await res.text()
                redirect_url = str(res.url)
                
                def extract(text):
                    m = re.search(r'/invites/([A-Za-z0-9]{28})', text)
                    if m: return m.group(1)
                    lp = re.search(r'link=([^\s"\'>]+)', text)
                    if lp:
                        d = lp.group(1).replace('%3A', ':').replace('%2F', '/')
                        dm = re.search(r'/invites/([A-Za-z0-9]{28})', d)
                        if dm: return dm.group(1)
                    return None
                return extract(redirect_url) or extract(html)
    except: return None

async def check_status(uid):
    url = f"https://api.revenuecat.com/v1/subscribers/{uid}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS_TEMPLATE, timeout=10) as res:
                if res.status == 200:
                    data = await res.json()
                    entitlements = data.get('subscriber', {}).get('entitlements', {}).get('Gold', {})
                    return {"active": bool(entitlements)}
                return {"active": False}
    except: return None

@app.get("/api/inject")
async def inject(username: str):
    uid = await resolve_uid(username)
    if not uid:
        return {"success": False, "message": "Không tìm thấy User ID."}

    if not TOKEN_SETS:
        return {"success": False, "message": "Chưa cấu hình TOKEN_SETS."}

    token_config = TOKEN_SETS[0]
    url = "https://api.revenuecat.com/v1/receipts"
    
    body = {
        "product_id": "locket_199_1m",
        "fetch_token": token_config['fetch_token'],
        "app_transaction": token_config['app_transaction'],
        "app_user_id": uid,
        "is_restore": True,
        "store_country": "VNM",
        "currency": "USD",
        "price": "1.99",
        "normal_duration": "P1M",
        "subscription_group_id": "21419447",
        "observer_mode": False,
        "initiation_source": "restore",
        "attributes": {"$attConsentStatus": {"updated_at_ms": int(time.time() * 1000), "value": "notDetermined"}}
    }

    current_headers = HEADERS_TEMPLATE.copy()
    current_headers['X-Is-Sandbox'] = str(token_config['is_sandbox']).lower()
    
    async with aiohttp.ClientSession() as session:
        # Thử tối đa 2 lần để tránh timeout trên Vercel
        for _ in range(2):
            try:
                async with session.post(url, headers=current_headers, json=body, timeout=15) as res:
                    if res.status == 200:
                        status = await check_status(uid)
                        if status and status['active']:
                            return {"success": True, "message": "Buff Gold thành công!"}
                    elif res.status == 529:
                        await asyncio.sleep(1)
                        continue
            except: pass
    
    return {"success": False, "message": "Thất bại hoặc hết hạn receipt."}

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("public/index.html", "r", encoding="utf-8") as f:
        return f.read()