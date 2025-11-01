# main.py — RELATÓRIO OURO DIÁRIO
# Analisa moedas com variação alta e envia resumo diário no Telegram

import os, asyncio, aiohttp
from datetime import datetime, timedelta

BINANCE_HTTP = "https://api.binance.com"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()
REQ_TIMEOUT = 10

def now_br():
    return (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M:%S")

async def tg(session, text):
    if not (TELEGRAM_TOKEN and CHAT_ID):
        print("[TG] Token ou Chat ID não configurado")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        await session.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=REQ_TIMEOUT)
    except Exception as e:
        print(f"[TG ERRO] {e}")

async def get_tickers(session):
    try:
        url = f"{BINANCE_HTTP}/api/v3/ticker/24hr"
        async with session.get(url, timeout=REQ_TIMEOUT) as r:
            return await r.json()
    except:
        return []

async def gerar_relatorio():
    async with aiohttp.ClientSession() as session:
        data = await get_tickers(session)
        if not data:
            await tg(session, "⚠️ Erro ao coletar dados da Binance.")
            return

        # filtra apenas pares com USDT e volume alto
        moedas = []
        for d in data:
            s = d.get("symbol", "")
            if not s.endswith("USDT"): 
                continue
            vol = float(d.get("quoteVolume", 0) or 0)
            if vol < 20_000_000:
                continue
            p = float(d.get("priceChangePercent", 0) or 0)
            moedas.append((s, p, vol))

        # ordena por variação
        moedas.sort(key=lambda x: x[1], reverse=True)
        top5 = moedas[:5]
        bot5 = moedas[-5:]

        # monta mensagem
        msg = f"📊 <b>RELATÓRIO OURO — {now_br()}</b>\n\n"
        msg += "🔥 <b>MAIORES ALTAS:</b>\n"
        for s, p, v in top5:
            msg += f"• {s:<10} {p:+.2f}%\n"

        msg += "\n💧 <b>MAIORES QUEDAS:</b>\n"
        for s, p, v in bot5:
            msg += f"• {s:<10} {p:+.2f}%\n"

        msg += "\n🕒 Atualizado em tempo real via Binance\n"
        await tg(session, msg)
        print("[OK] Relatório enviado com sucesso.")

if __name__ == "__main__":
    asyncio.run(gerar_relatorio())
