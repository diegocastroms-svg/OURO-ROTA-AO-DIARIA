# main.py — OURO TENDÊNCIAS REAIS (V23.5)
# Lista todas as moedas com tendência de alta (EMA9 > MA20) em 4H, 1D e 1W
# Mostra blocos separados e envia direto pro Telegram

import os, asyncio, aiohttp, time
from datetime import datetime, timedelta
from flask import Flask

# ---------------- CONFIG ----------------
BINANCE_HTTP = "https://api.binance.com"
TOP_N = 150
REQ_TIMEOUT = 10
VERSION = "OURO TENDÊNCIAS REAIS (4H, 1D, 1W)"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()

# ---------------- FLASK ----------------
app = Flask(__name__)
@app.route("/")
def home():
    return f"{VERSION} — relatório de tendências reais (EMA9>MA20)", 200

# ---------------- UTILS ----------------
def now_br():
    return (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")

async def tg(session, text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("[TG] Token ou Chat ID ausente.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        await session.post(
            url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=REQ_TIMEOUT
        )
    except Exception as e:
        print(f"[TG ERRO] {e}")

# ---------------- MÉDIAS ----------------
def ema_series(values, n):
    k = 2 / (n + 1)
    ema = []
    e = values[0]
    for v in values:
        e = v * k + e * (1 - k)
        ema.append(e)
    return ema

def ma_series(values, n):
    ma = []
    for i in range(len(values)):
        if i < n:
            ma.append(sum(values[:i+1]) / (i+1))
        else:
            ma.append(sum(values[i-n+1:i+1]) / n)
    return ma

# ---------------- TENDÊNCIA REAL ----------------
def em_tendencia_alta(candles):
    try:
        closes = [float(k[4]) for k in candles]
        if len(closes) < 50:
            return False

        ema9 = ema_series(closes, 9)
        ma20 = ma_series(closes, 20)

        # Confirmar que EMA9 > MA20 nas últimas 5 velas
        ult5 = [(ema9[-i] > ma20[-i]) for i in range(1, 6)]
        tendencia_alta = all(ult5)

        # Confirmar inclinação positiva (EMA9 subindo)
        inclinacao = ema9[-1] > ema9[-3]

        return tendencia_alta and inclinacao
    except:
        return False

# ---------------- BINANCE ----------------
async def get_klines(session, symbol, interval="4h", limit=200):
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
        if not s.endswith("USDT"):
            continue
        if any(x in s for x in blocked):
            continue
        qv = float(d.get("quoteVolume", 0) or 0)
        pares.append((s, qv))
    pares.sort(key=lambda x: x[1], reverse=True)
    return [p[0] for p in pares[:TOP_N]]

# ---------------- RELATÓRIO ----------------
async def gerar_relatorio():
    async with aiohttp.ClientSession() as session:
        inicio = time.time()
        pares = await get_top_usdt_symbols(session)

        tendencia_4h, tendencia_1d, tendencia_1w = [], [], []

        for s in pares:
            kl_4h = await get_klines(session, s, "4h", 200)
            kl_1d = await get_klines(session, s, "1d", 200)
            kl_1w = await get_klines(session, s, "1w", 200)

            if em_tendencia_alta(kl_4h):
                tendencia_4h.append(s)
            if em_tendencia_alta(kl_1d):
                tendencia_1d.append(s)
            if em_tendencia_alta(kl_1w):
                tendencia_1w.append(s)

        tempo = round(time.time() - inicio, 1)
        texto = (
            f"<b>📊 OURO TENDÊNCIAS REAIS</b>\n"
            f"⏰ {now_br()} BR\n"
            f"🟢 Critério: EMA9 acima da MA20 nas últimas 5 velas + inclinação positiva\n"
            f"📈 Total analisado: {len(pares)} pares\n\n"
        )

        texto += "━━━━━━━━━━━━━━━\n📉 <b>TENDÊNCIA 4H</b>\n━━━━━━━━━━━━━━━\n"
        texto += ", ".join(tendencia_4h) if tendencia_4h else "Nenhuma moeda em tendência no 4h."

        texto += "\n\n━━━━━━━━━━━━━━━\n📊 <b>TENDÊNCIA 1D</b>\n━━━━━━━━━━━━━━━\n"
        texto += ", ".join(tendencia_1d) if tendencia_1d else "Nenhuma moeda em tendência no 1D."

        texto += "\n\n━━━━━━━━━━━━━━━\n🕒 <b>TENDÊNCIA 1W (Semanal)</b>\n━━━━━━━━━━━━━━━\n"
        texto += ", ".join(tendencia_1w) if tendencia_1w else "Nenhuma moeda em tendência semanal."

        texto += f"\n\n⏱️ Tempo de análise: {tempo}s\n🟢 Relatório gerado automaticamente no deploy"

        await tg(session, texto)
        print(f"[{now_br()}] RELATÓRIO ENVIADO COM SUCESSO ({tempo}s)")

# ---------------- EXECUÇÃO ----------------
async def agendar_execucao():
    print(f"[{now_br()}] OURO TENDÊNCIAS REAIS ATIVO — Gerando relatório imediato.")
    await gerar_relatorio()
    while True:
        await asyncio.sleep(3600)

# ---------------- MAIN ----------------
def start_bot():
    asyncio.run(agendar_execucao())

if __name__ == "__main__":
    import threading
    threading.Thread(target=start_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
