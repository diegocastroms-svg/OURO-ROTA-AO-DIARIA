# main.py — OURO TENDÊNCIAS MULTITEMPO (4H, 1D, 1W)
# Mostra apenas as moedas em tendência de alta confirmada por EMA9 > MA20 (+0.15%)
# Separado em blocos por timeframe: 4h, 1d e 1w
# Relatório limpo e direto para Telegram

import os, asyncio, aiohttp, time
from datetime import datetime, timedelta
from flask import Flask

# ---------------- CONFIG ----------------
BINANCE_HTTP = "https://api.binance.com"
TOP_N = 120
REQ_TIMEOUT = 10
VERSION = "OURO TENDÊNCIAS MULTITEMPO (4H, 1D, 1W)"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()

# ---------------- FLASK ----------------
app = Flask(__name__)
@app.route("/")
def home():
    return f"{VERSION} — relatório gerado automaticamente no deploy", 200

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

# ---------------- MÉDIAS ----------------
def ema_series(values, period):
    ema = []
    k = 2 / (period + 1)
    for i, v in enumerate(values):
        if i == 0:
            ema.append(v)
        else:
            ema.append(v * k + ema[-1] * (1 - k))
    return ema

def ma_series(values, period):
    ma = []
    for i in range(len(values)):
        if i < period:
            ma.append(sum(values[:i+1]) / (i+1))
        else:
            ma.append(sum(values[i-period+1:i+1]) / period)
    return ma

# ---------------- FUNÇÃO DE TENDÊNCIA ----------------
def tendencia_alta(candles):
    try:
        closes = [float(k[4]) for k in candles if len(k) >= 5]
        if len(closes) < 50:
            return False

        ema9 = ema_series(closes, 9)
        ma20 = ma_series(closes, 20)

        e9_prev2, e9_prev, e9_now = ema9[-3], ema9[-2], ema9[-1]
        m20_prev2, m20_prev, m20_now = ma20[-3], ma20[-2], ma20[-1]

        cruzamento = (e9_prev2 < m20_prev2) and (e9_prev > m20_prev) and (e9_now > m20_now)
        diferenca = (e9_now - m20_now) / m20_now

        return cruzamento and diferenca > 0.0015
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

            if tendencia_alta(kl_4h):
                tendencia_4h.append(s)
            if tendencia_alta(kl_1d):
                tendencia_1d.append(s)
            if tendencia_alta(kl_1w):
                tendencia_1w.append(s)

        tempo = round(time.time() - inicio, 1)
        texto = (
            f"<b>📊 OURO TENDÊNCIAS MULTITEMPO</b>\n"
            f"⏰ {now_br()} BR\n\n"
            f"🟢 Critério: EMA9 > MA20 com +0.15% de confirmação\n"
            f"📈 Total analisado: {len(pares)} pares\n\n"
        )

        texto += "━━━━━━━━━━━━━━━\n📉 <b>TENDÊNCIA 4H</b>\n━━━━━━━━━━━━━━━\n"
        texto += ", ".join(tendencia_4h) if tendencia_4h else "Nenhuma moeda em tendência no 4h."

        texto += "\n\n━━━━━━━━━━━━━━━\n📊 <b>TENDÊNCIA 1D</b>\n━━━━━━━━━━━━━━━\n"
        texto += ", ".join(tendencia_1d) if tendencia_1d else "Nenhuma moeda em tendência no 1D."

        texto += "\n\n━━━━━━━━━━━━━━━\n🕒 <b>TENDÊNCIA SEMANAL</b>\n━━━━━━━━━━━━━━━\n"
        texto += ", ".join(tendencia_1w) if tendencia_1w else "Nenhuma moeda em tendência semanal."

        texto += f"\n\n⏱️ Tempo de análise: {tempo}s\n🟢 Relatório gerado automaticamente no deploy"

        await tg(session, texto)
        print(f"[{now_br()}] RELATÓRIO ENVIADO COM SUCESSO ({tempo}s)")

# ---------------- EXECUÇÃO ----------------
async def agendar_execucao():
    print(f"[{now_br()}] OURO TENDÊNCIAS MULTITEMPO ATIVO — Gerando relatório imediato.")
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
