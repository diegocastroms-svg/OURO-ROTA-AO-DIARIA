# main.py — OURO ROTA DIÁRIA v2.1
# Previsão de Alta e Queda — Análise 1h + 4h + 1D
# Probabilidade 0–1 com base na confluência de tendência
# Envia alerta apenas quando há forte sinal de alta ou queda

import os, asyncio, aiohttp, time, threading
from datetime import datetime, timedelta
from flask import Flask

# ---------------- CONFIG ----------------
BINANCE_HTTP = "https://api.binance.com"
TOP_N = 60
REQ_TIMEOUT = 10
COOLDOWN_SEC = 30 * 60  # 30 min
VOL_MIN_USDT = 20_000_000

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()

# ---------------- FLASK ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "OURO ROTA DIÁRIA v2.1 — Previsão de Alta e Queda", 200

# ---------------- UTILS ----------------
def now_br():
    return (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S") + " BR"

def ema(seq, span):
    if not seq: return []
    alpha = 2 / (span + 1)
    e = seq[0]
    out = [e]
    for x in seq[1:]:
        e = alpha * x + (1 - alpha) * e
        out.append(e)
    return out

def macd_hist(seq):
    if len(seq) < 35: return 0.0
    ema_fast = ema(seq, 12)
    ema_slow = ema(seq, 26)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal = ema(macd_line, 9)
    return macd_line[-1] - signal[-1] if signal else 0.0

def calc_rsi(seq, period=14):
    if len(seq) < period + 1: return 50
    gains, losses = [], []
    for i in range(1, len(seq)):
        diff = seq[i] - seq[i-1]
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    rs = avg_gain / (avg_loss + 1e-12)
    return 100 - (100 / (1 + rs))

async def tg(session, text: str):
    if not (TELEGRAM_TOKEN and CHAT_ID): return
    try:
        await session.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except: pass

# ---------------- BINANCE ----------------
async def get_klines(session, symbol, interval, limit=150):
    try:
        async with session.get(f"{BINANCE_HTTP}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}", timeout=REQ_TIMEOUT) as r:
            return await r.json()
    except:
        return []

async def get_top_usdt_symbols(session):
    try:
        async with session.get(f"{BINANCE_HTTP}/api/v3/ticker/24hr", timeout=REQ_TIMEOUT) as r:
            data = await r.json()
        pares = []
        for d in data:
            s = d.get("symbol", "")
            qv = float(d.get("quoteVolume", "0") or 0.0)
            if s.endswith("USDT") and qv >= VOL_MIN_USDT:
                pares.append((s, qv))
        pares.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in pares[:TOP_N]]
    except:
        return []

# ---------------- COOLDOWN ----------------
last_alert = {}
def can_alert(symbol):
    now = time.time()
    last = last_alert.get(symbol, 0)
    if now - last > COOLDOWN_SEC:
        last_alert[symbol] = now
        return True
    return False

# ---------------- WORKER ----------------
async def scan_symbol(session, symbol):
    try:
        k1h = await get_klines(session, symbol, "1h", 100)
        k4h = await get_klines(session, symbol, "4h", 100)
        k1d = await get_klines(session, symbol, "1d", 100)
        if not (k1h and k4h and k1d): return

        c1h = [float(x[4]) for x in k1h]
        c4h = [float(x[4]) for x in k4h]
        c1d = [float(x[4]) for x in k1d]

        # Indicadores
        macd1h, macd4h, macd1d = macd_hist(c1h), macd_hist(c4h), macd_hist(c1d)
        rsi1h, rsi4h, rsi1d = calc_rsi(c1h), calc_rsi(c4h), calc_rsi(c1d)

        # Probabilidade de alta (baseada em confluência)
        sinais_verde = sum([
            macd1h > 0,
            macd4h > 0,
            macd1d > 0,
            45 < rsi1h < 70,
            45 < rsi4h < 70,
            45 < rsi1d < 70
        ])
        prob_alta = sinais_verde / 6

        # Direção e força
        if prob_alta >= 0.8:
            direcao = "⬆️ ALTA FORTE"
        elif prob_alta <= 0.2:
            direcao = "⬇️ QUEDA FORTE"
        else:
            return

        if can_alert(symbol):
            preco = c1h[-1]
            msg = (
                f"<b>{symbol}</b>\n"
                f"🎯 {direcao}\n"
                f"Probabilidade: {prob_alta:.2f}\n"
                f"Preço atual: ${preco:.6f}\n"
                f"RSI(1h/4h/1D): {rsi1h:.1f}/{rsi4h:.1f}/{rsi1d:.1f}\n"
                f"MACD(1h/4h/1D): {macd1h:.4f}/{macd4h:.4f}/{macd1d:.4f}\n"
                f"{now_br()}\n"
                "━━━━━━━━━━━━━━━"
            )
            await tg(session, msg)
            print(f"[ALERTA] {symbol} {direcao} | {prob_alta:.2f}")

    except Exception as e:
        print(f"[ERRO] {symbol}: {e}")

# ---------------- MAIN ----------------
async def main_loop():
    async with aiohttp.ClientSession() as session:
        pares = await get_top_usdt_symbols(session)
        print(f"[{now_br()}] Monitorando {len(pares)} pares USDT.")
        await tg(session, f"🤖 OURO ROTA DIÁRIA v2.1 INICIADO\nMonitorando {len(pares)} pares.\n{now_br()}")
        while True:
            await asyncio.gather(*[scan_symbol(session, s) for s in pares])
            await asyncio.sleep(300)  # 5 min entre ciclos

def start():
    while True:
        try:
            asyncio.run(main_loop())
        except Exception as e:
            print(f"[ERRO FATAL] {e}")
            time.sleep(5)

threading.Thread(target=start, daemon=True).start()
app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
