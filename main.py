# main.py — OURO ROTAÇÃO DIÁRIA
# Identifica moedas que sobem forte em um dia e corrigem no outro
# Baseado em variação diária e volume de 24h
# Relatório direto no console (sem Telegram por enquanto)

import asyncio
import aiohttp
from datetime import datetime, timedelta

BINANCE_HTTP = "https://api.binance.com"
REQ_TIMEOUT = 10
TOP_N = 50

def now_br():
    return (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S") + " BR"

async def get_tickers(session):
    url = f"{BINANCE_HTTP}/api/v3/ticker/24hr"
    try:
        async with session.get(url, timeout=REQ_TIMEOUT) as r:
            data = await r.json()
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[ERRO TICKERS] {e}")
        return []

async def analisar_rotacao():
    async with aiohttp.ClientSession() as session:
        dados = await get_tickers(session)
        if not dados:
            print("Nenhum dado recebido da Binance.")
            return
        
        pares = []
        for d in dados:
            if not d.get("symbol", "").endswith("USDT"):
                continue
            vol = float(d.get("quoteVolume", 0))
            if vol < 20_000_000:
                continue
            var = float(d.get("priceChangePercent", 0))
            pares.append((d["symbol"], var, vol))
        
        pares.sort(key=lambda x: x[1], reverse=True)
        top = pares[:TOP_N]
        worst = sorted(pares, key=lambda x: x[1])[:TOP_N]

        print(f"\n🟢 {now_br()} — TOP {TOP_N} EM ALTA:")
        for s, v, vol in top:
            print(f"{s:<12} {v:>6.2f}% | Vol: {vol/1_000_000:.1f}M USDT")

        print(f"\n🔴 {now_br()} — TOP {TOP_N} EM QUEDA:")
        for s, v, vol in worst:
            print(f"{s:<12} {v:>6.2f}% | Vol: {vol/1_000_000:.1f}M USDT")

        # 🔁 Análise de reversão (alta ontem, queda hoje)
        reversoes = []
        for s, v, vol in top:
            if v < 0:
                reversoes.append((s, v, vol))

        if reversoes:
            print("\n⚠️ Possíveis reversões detectadas:")
            for s, v, vol in reversoes:
                print(f"{s:<12} {v:>6.2f}% | Vol: {vol/1_000_000:.1f}M USDT")
        else:
            print("\nNenhuma reversão forte detectada hoje.")

asyncio.run(analisar_rotacao())
