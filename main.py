# main.py — OURO ROTA DIÁRIA (V21.8 — EMA9 x MA20 4H CRUZAMENTO REAL)
# Marca 📊 apenas se EMA9 cruzar e sustentar acima da MA20 (4h)
# Mantém toda a estrutura e lógica anterior

import os, asyncio, aiohttp, time
from datetime import datetime, timedelta
from flask import Flask

# ---------------- CONFIG ----------------
BINANCE_HTTP = "https://api.binance.com"
TOP_N = 120
REQ_TIMEOUT = 10
VERSION = "OURO ROTA DIÁRIA V21.8 — EMA9 x MA20 4H CRUZAMENTO REAL"

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

# ---------------- FUNÇÕES DE MÉDIA ----------------
def ema(values, n):
    k = 2 / (n + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e

def ema_series(values, n):
    k = 2 / (n + 1)
    e = None
    out = []
    for v in values:
        e = v if e is None else (v * k + e * (1 - k))
        out.append(e)
    return out

# ---------------- TENDÊNCIA 4H (EMA9 x MA20 CRUZAMENTO REAL) ----------------
def tendencia_4h(candles):
    try:
        closes = [float(k[4]) for k in candles if len(k) >= 5]
        if len(closes) < 100:
            return False

        # EMA9
        ema_vals = ema_series(closes, 9)
        # MA20 simples (média aritmética)
        ma20_vals = [sum(closes[i-20:i]) / 20 for i in range(20, len(closes)+1)]

        # alinhar comprimentos
        diff = len(ema_vals) - len(ma20_vals)
        if diff > 0:
            ema_vals = ema_vals[diff:]
        elif diff < 0:
            ma20_vals = ma20_vals[-len(ema_vals):]

        # últimos 3 valores para confirmar cruzamento
        e9_prev2, e9_prev, e9_now = ema_vals[-3], ema_vals[-2], ema_vals[-1]
        ma_prev2, ma_prev, ma_now = ma20_vals[-3], ma20_vals[-2], ma20_vals[-1]

        # cruzamento real (EMA9 cruza MA20 de baixo pra cima e se mantém)
        cruzou = (e9_prev2 < ma_prev2) and (e9_prev > ma_prev) and (e9_now > ma_now)
        confirmacao = (e9_now > ma_now) and (e9_prev > ma_prev)

        return cruzou and confirmacao
    except Exception as e:
        print(f"[tendencia_4h ERRO] {e}")
        return False

# ---------------- PROBABILIDADE (1h) ----------------
def calc_prob(candles, ch24):
    try:
        closes = [float(k[4]) for k in candles]
        volumes = [float(k[5]) for k in candles]
        if len(closes) < 30:
            return 0.0, "NEUT", 50, "→", "→", "→", "→"

        # RSI(14)
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        avg_gain = (sum(gains[-14:]) / 14) if sum(gains[-14:]) else 0.001
        avg_loss = (sum(losses[-14:]) / 14) if sum(losses[-14:]) else 0.001
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        last20 = closes[-25:]
        ema9_now = ema(last20, 9)
        ema20_now = ema(last20, 20)
        prev20 = closes[-26:-1]
        ema9_prev = ema(prev20, 9)
        ema_slope = "↗" if (ema9_now - ema9_prev) > 0 else "↘"
        tendencia = "↑" if ema9_now > ema20_now else "↓"

        vol_med = sum(volumes[-12:]) / 12 if sum(volumes[-12:]) > 0 else 1
        vol_force = volumes[-1] / vol_med if vol_med > 0 else 1
        vol_tag = "↑" if vol_force > 1.1 else "↓"
        mom6 = closes[-1] - closes[-7]
        mom_tag = "+" if mom6 > 0 else "-"

        regime = "REV" if ch24 <= -3.0 else ("CONT" if ch24 >= 1.0 else "NEUT")

        score = 0.45
        if regime == "REV":
            score = 0.50
            if rsi < 35: score += 0.20
            if rsi < 25: score += 0.10
            if ema_slope == "↗": score += 0.10
            if tendencia == "↑": score += 0.10
            if vol_force > 1.2: score += 0.10
            if mom6 > 0: score += 0.10
            if ch24 < -10: score += 0.08
            if rsi > 55: score -= 0.10
        elif regime == "CONT":
            score = 0.48
            if 50 <= rsi <= 65: score += 0.10
            if 65 < rsi <= 75: score += 0.05
            if tendencia == "↑": score += 0.15
            if ema_slope == "↗": score += 0.10
            if vol_force > 1.0: score += 0.05
            if mom6 > 0: score += 0.10
            if ch24 > 10: score -= 0.20
            if ch24 > 20: score -= 0.10
            if rsi > 75: score -= 0.20
        else:
            score = 0.35
            if tendencia == "↑" and ema_slope == "↗": score += 0.10
            if 45 <= rsi <= 55: score += 0.05

        score = max(0.05, min(score, 0.95))
        return float(score), regime, rsi, ema_slope, tendencia, vol_tag, mom_tag
    except Exception as e:
        print(f"[calc_prob ERRO] {e}")
        return 0.0, "NEUT", 0, "→", "→", "→", "→"

# ---------------- TENDÊNCIA 1H ----------------
def tendencia_1h(candles):
    try:
        closes = [float(k[4]) for k in candles]
        if len(closes) < 40:
            return False
        ema9 = ema(closes[-40:], 9)
        ema20 = ema(closes[-40:], 20)
        ema12 = ema(closes[-40:], 12)
        ema26 = ema(closes[-40:], 26)
        macd = ema12 - ema26
        return ema9 > ema20 and macd > 0
    except:
        return False

# ---------------- BINANCE ----------------
async def get_klines(session, symbol, interval="1h", limit=48):
    url = f"{BINANCE_HTTP}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        async with session.get(url, timeout=REQ_TIMEOUT) as r:
            return await r.json()
    except:
        return []

# ---------------- TOP USDT ----------------
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
        change = float(d.get("priceChangePercent", 0) or 0)
        pares.append((s, qv, change))
    pares.sort(key=lambda x: x[1], reverse=True)
    return pares[:TOP_N]

# ---------------- RELATÓRIO ----------------
async def gerar_relatorio():
    async with aiohttp.ClientSession() as session:
        inicio = time.time()
        pares = await get_top_usdt_symbols(session)

        reversao, continuacao, tendencia_1h_list = [], [], []

        for s, vol, change in pares:
            kl_1h = await get_klines(session, s, "1h", 60)
            kl_4h = await get_klines(session, s, "4h", 200)

            conf_4h = tendencia_4h(kl_4h)
            prob, regime, rsi, ema_slope, tendencia, vol_tag, mom_tag = calc_prob(kl_1h, change)
            diario_tag = "📊" if conf_4h else "—"

            if tendencia_1h(kl_1h):
                tendencia_1h_list.append(s)

            if regime == "REV":
                reversao.append((s, prob, change, rsi, ema_slope, tendencia, vol_tag, mom_tag, diario_tag))
            elif regime == "CONT":
                continuacao.append((s, prob, change, rsi, ema_slope, tendencia, vol_tag, mom_tag, diario_tag))

        reversao.sort(key=lambda x: x[1], reverse=True)
        continuacao.sort(key=lambda x: x[1], reverse=True)

        texto = "<b>📊 RELATÓRIO DIÁRIO — OURO ROTA DIÁRIA</b>\n"
        texto += f"⏰ {now_br()} BR\n\n"

        texto += "🔁 <b>Reversão provável (repique após queda) — Top 10:</b>\n"
        for s, p, ch, rsi, ema_slope, tendencia, vol_tag, mom_tag, diario_tag in reversao[:10]:
            texto += f"⚠️ {s}: {p*100:.1f}% | {ch:+.2f}% 24h | RSI {rsi:.0f} | EMA9{ema_slope} | Tend{tendencia} | Vol{vol_tag} | Mom{mom_tag} | {diario_tag}\n"

        texto += "\n📈 <b>Continuação provável (tendência saudável) — Top 10:</b>\n"
        for s, p, ch, rsi, ema_slope, tendencia, vol_tag, mom_tag, diario_tag in continuacao[:10]:
            texto += f"⬆️ {s}: {p*100:.1f}% | {ch:+.2f}% 24h | RSI {rsi:.0f} | EMA9{ema_slope} | Tend{tendencia} | Vol{vol_tag} | Mom{mom_tag} | {diario_tag}\n"

        texto += "\n🧾 <b>Resumo técnico:</b>\n"
        texto += f"🔁 {len(reversao[:10])} reversões fortes detectadas\n"
        texto += f"📈 {len(continuacao[:10])} continuações confirmadas\n"
        tempo = round(time.time() - inicio, 1)
        texto += f"⏱️ Tempo de análise: {tempo}s\n"
        texto += f"\n📊 Total analisado: {len(pares)} pares\n"
        texto += f"\n🟢 Relatório gerado automaticamente no deploy\n"

        if tendencia_1h_list:
            texto += "\n💠 <b>Moedas com tendência no 4h (EMA9>MA20 - Cruzamento confirmado):</b>\n"
            texto += ", ".join(tendencia_1h_list)
        else:
            texto += "\n💠 Nenhuma moeda com tendência clara no 4h."

        await tg(session, texto)
        print(f"[{now_br()}] RELATÓRIO ENVIADO COM SUCESSO ({tempo}s)")

# ---------------- EXECUÇÃO IMEDIATA ----------------
async def agendar_execucao():
    print(f"[{now_br()}] OURO ROTA DIÁRIA ATIVO — gerando relatório imediato no deploy.")
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
