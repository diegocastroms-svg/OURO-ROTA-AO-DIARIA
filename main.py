# main.py — OURO-ROTA-DIÁRIA
# Scanner diário de rotação de moedas com análise de volume e reversão

import os, asyncio, aiohttp, time
from datetime import datetime, timedelta

# ---------------- CONFIG ----------------
BINANCE_HTTP = "https://api.binance.com"
REQ_TIMEOUT = 10
VOL_MIN_USDT = 20_000_000
TOP_N = 50

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()

# ---------------- UTILS ----------------
def now_br():
    return (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S") + " BR"

async def tg(session, text: str):
    if not (TELEGRAM_TOKEN and CHAT_ID):
        print("[TG] Falha: token/chat_id ausente")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
        async with session.post(url, data=payload, timeout=REQ_TIMEOUT):
            pass
    except Exception as e:
        print(f"[TG ERRO] {e}")

# ---------------- BINANCE ----------------
async def get_tickers(session):
    try:
        async with session.get(f"{BINANCE_HTTP}/api/v3/ticker/24hr", timeout=REQ_TIMEOUT) as r:
            data = await r.json()
            return data if isinstance(data, list) else []
    except:
        return []

# ---------------- MAIN ----------------
async def main_loop():
    async with aiohttp.ClientSession() as session:
        print(f"[{now_br()}] Iniciando scanner diário...")
        await tg(session, f"🟢 <b>OURO ROTA DIÁRIA INICIADO</b>\n{now_br()}")

        while True:
            data = await get_tickers(session)
            if not data:
                print(f"[{now_br()}] Falha ao obter dados.")
                await asyncio.sleep(60)
                continue

            pares = []
            for d in data:
                s = d.get("symbol", "")
                if not s.endswith("USDT"): continue
                vol = float(d.get("quoteVolume", 0) or 0)
                if vol < VOL_MIN_USDT: continue
                p = float(d.get("priceChangePercent", 0))
                pares.append((s, p, vol))

            pares.sort(key=lambda x: x[1], reverse=True)
            top_alta = pares[:TOP_N]
            top_baixa = sorted(pares, key=lambda x: x[1])[:TOP_N]

            print(f"[{now_br()}] BR — TOP 50 EM ALTA:")
            for s, p, v in top_alta[:7]:
                print(f"{s:10} {p:+.2f}% | Vol: {v/1e6:.1f}M USDT")

            print(f"[{now_br()}] BR — TOP 50 EM QUEDA:")
            for s, p, v in top_baixa[:7]:
                print(f"{s:10} {p:+.2f}% | Vol: {v/1e6:.1f}M USDT")

            possiveis_reversoes = [p for p in top_alta if p[0] in [b[0] for b in top_baixa]]

            print(f"[{now_br()}] ⚠️ Possíveis reversões detectadas:")
            for s, p, v in possiveis_reversoes:
                print(f"{s:10} {p:+.2f}% | Vol: {v/1e6:.1f}M USDT")

            # 🔔 ALERTA TELEGRAM
            msg = (
                f"📊 <b>RELATÓRIO DIÁRIO OURO</b>\n"
                f"🟢 <b>Top 10 em Alta</b>\n{', '.join([p[0] for p in top_alta[:10]])}\n\n"
                f"🔴 <b>Top 10 em Queda</b>\n{', '.join([p[0] for p in top_baixa[:10]])}\n\n"
                f"⚠️ <b>Possíveis Reversões:</b>\n"
                f"{', '.join([p[0] for p in possiveis_reversoes]) or 'Nenhuma'}\n\n"
                f"{now_br()}"
            )
            await tg(session, msg)

            print(f"[{now_br()}] Relatório enviado ao Telegram.")
            await asyncio.sleep(3600 * 24)  # roda uma vez por dia

# ---------------- EXECUÇÃO ----------------
if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("Encerrado manualmente.")
