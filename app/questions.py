import random

QUESTIONS = [
    "What are the top volume movers on Base in the last 24 hours and what's driving the flow?",
    "Break down the current bid-ask spread and liquidity depth for major Base DEX pairs.",
    "What macro catalysts are driving crypto markets this week — rates, CPI, Fed signals?",
    "Which tokens on Base are showing unusual whale accumulation or distribution patterns?",
    "What does the on-chain order flow and trade size distribution look like on Base DEXs right now?",
    "How is global risk sentiment affecting crypto — DXY, yields, equity correlation?",
    "Which Base tokens have the highest realized volatility vs implied volatility skew right now?",
    "What are the biggest net inflows and outflows across Base bridges in the last 48 hours?",
    "What's the current funding rate and open interest landscape for tokens with Base exposure?",
    "Which sectors are rotating — DeFi, AI, memes, RWA — and what's the relative strength data?",
]


def get_random_question():
    return random.choice(QUESTIONS)
