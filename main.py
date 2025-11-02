# main.py — OURO ROTA DIÁRIA (20h)
# Relatório diário com as 10 maiores probabilidades de alta e queda

import os, asyncio, aiohttp, time
from datetime import datetime, timedelta
from flask import Flask

# ---------------- CONFIG ----------------
BINANCE_HTTP = "https://api.binance.com"
TOP_N = 100
REQ_TIMEOUT = 10
VERSION = "OURO ROTA DIÁRIA 20h"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()

# ---------------- FLASK ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return f"{VERSION} — Relatório diário de probabilidades às 20h (BR)", 200

# ---------------- UTILS ----------------
def now_br():
    return (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")

async def tg(session, text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("[TG] Token ou Chat ID ausente.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        await session.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=REQ_TIMEOUT)
    except Exception as e:
        print(f"[TG ERRO] {e}")

def calc_prob(candles):
    try:
        closes = [float(k[4]) for k in candles]
        if len(closes) < 2: return 0
        diffs = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        ups = sum(1 for d in diffs if d > 0)
        return ups / len(diffs)
    except:
        return 0

# ---------------- BINANCE ----------------
async def get_klines(session, symbol, interval="1h", limit=48):
    url = f"{BINANCE_HTTP}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        async with session.get(url, timeout=REQ_TIMEOUT) as r:
            return await r.json()
    except:
        return []

async def get_top_usdt_symbols(session):
    url = f"{BINANCE_HTTP}/api/v3/ticker/24hr"
    async with session.get(url, timeout=REQ_TIMEOUT) as r:
        data = await r.json()
    blocked = ("UP","DOWN","BULL","BEAR","BUSD","FDUSD","TUSD","USDC","EUR","BRL","PERP","TEST","USDE")
    pares = []
    for d in data:
        s = d.get("symbol", "")
        if not s.endswith("USDT"): continue
        if any(x in s for x in blocked): continue
        qv = float(d.get("quoteVolume", 0) or 0)
        pares.append((s, qv))
    pares.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in pares[:TOP_N]]

# ---------------- RELATÓRIO ----------------
async def gerar_relatorio():
    async with aiohttp.ClientSession() as session:
        symbols = await get_top_usdt_symbols(session)
        resultados = []

        for s in symbols:
            kl = await get_klines(session, s)
            prob = calc_prob(kl)
            resultados.append((s, prob))

        resultados.sort(key=lambda x: x[1], reverse=True)
        altas = resultados[:10]
        quedas = resultados[-10:]

        texto = "<b>📊 RELATÓRIO DIÁRIO — OURO ROTA DIÁRIA</b>\n"
        texto += f"⏰ {now_br()} BR\n\n"
        texto += "🔥 <b>Top 10 Probabilidades de Alta:</b>\n"
        for s, p in altas:
            texto += f"• {s}: {p*100:.1f}%\n"

        texto += "\n❄️ <b>Top 10 Probabilidades de Queda:</b>\n"
        for s, p in quedas:
            texto += f"• {s}: {p*100:.1f}%\n"

        texto += f"\nTotal analisado: {len(resultados)} pares\n"
        await tg(session, texto)
        print("[RELATÓRIO ENVIADO]")

# ---------------- AGENDAMENTO ----------------
async def agendar_execucao():
    while True:
        agora = datetime.utcnow() - timedelta(hours=3)
        if agora.hour == 20 and agora.minute == 0:
            await gerar_relatorio()
            await asyncio.sleep(60)
        await asyncio.sleep(30)

# ---------------- MAIN ----------------
def start_bot():
    asyncio.run(agendar_execucao())

if __name__ == "__main__":
    import threading
    threading.Thread(target=start_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
