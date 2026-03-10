# Market Gap Scanner

Инструмент для поиска рыночных ниш на основе трёх источников данных:

- **Яндекс.Вордстат** — объём поисковых запросов через API Яндекс.Директа
- **Reddit** — сигналы рынка из обсуждений (жалобы, запросы, поиск альтернатив)
- **LLM** — AI-анализ собранных данных и генерация рекомендаций (YandexGPT / OpenAI)

## Возможности

| Модуль | Источник | Что делает |
|--------|----------|------------|
| `wordstat.py` | Yandex Direct API v4 | Получает объёмы поисковых запросов, батч-обработка до 10 фраз |
| `reddit.py` | Reddit API (PRAW) | Собирает сигналы: `unmet_demand`, `pain_point`, `feature_request` |
| `analyzer.py` | — | Gap-scoring: demand / supply ratio |
| `llm.py` | YandexGPT / OpenAI | AI-рекомендации по нишам на основе собранных данных |

## Установка

```bash
pip install -e .
```

## Быстрый старт

### CLI

```bash
# Только Wordstat
market-gap-scanner "crm для фрилансеров" "автоматизация бизнеса" \
    --token YOUR_YANDEX_TOKEN

# Wordstat + Reddit
market-gap-scanner "crm для фрилансеров" \
    --token YOUR_YANDEX_TOKEN \
    --reddit-id YOUR_CLIENT_ID \
    --reddit-secret YOUR_CLIENT_SECRET

# Полный пайплайн: Wordstat + Reddit + LLM
market-gap-scanner "crm для фрилансеров" \
    --token YOUR_YANDEX_TOKEN \
    --reddit-id YOUR_CLIENT_ID \
    --reddit-secret YOUR_CLIENT_SECRET \
    --llm
```

### Python API

```python
import asyncio
from market_gap_scanner.wordstat import WordstatClient
from market_gap_scanner.reddit import RedditCollector
from market_gap_scanner.analyzer import analyze_gaps
from market_gap_scanner.llm import LLMAnalyzer, format_recommendations

async def full_scan():
    # 1. Keyword volumes from Wordstat
    async with WordstatClient(token="YOUR_TOKEN") as ws:
        keyword_data = await ws.get_keyword_stats(["crm freelancer", "task automation"])

    # 2. Reddit signals
    reddit = RedditCollector(client_id="...", client_secret="...")
    signals = reddit.collect_signals(keywords=["crm", "automation"])

    # 3. Gap analysis
    gaps = analyze_gaps(keyword_data)

    # 4. LLM recommendations
    analyzer = LLMAnalyzer()  # auto-detects provider from env
    recs = analyzer.analyze(gaps=gaps, signals=signals)
    print(format_recommendations(recs))

asyncio.run(full_scan())
```

## Получение API-ключей

### Яндекс Wordstat

1. Зарегистрируйте приложение: [OAuth Яндекса](https://oauth.yandex.ru/)
2. Подайте заявку на доступ к API Директа
3. Получите OAuth-токен

### Reddit

1. Создайте приложение: [Reddit Apps](https://www.reddit.com/prefs/apps)
2. Тип: `script`
3. Скопируйте `client_id` и `client_secret`

### LLM-провайдеры

**YandexGPT** (приоритет по умолчанию):
```bash
export YC_API_KEY="AQVNxxx..."
export YC_FOLDER_ID="b1g..."
```

**OpenAI и совместимые** (OpenRouter, Ollama, vLLM):
```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://openrouter.ai/api/v1"  # опционально
export LLM_MODEL="gpt-4o-mini"  # опционально
```

Провайдер определяется автоматически: если задан `YC_API_KEY` → YandexGPT, иначе `OPENAI_API_KEY` → OpenAI.

Можно задать явно:

```python
from market_gap_scanner.llm import LLMAnalyzer, YandexGPTProvider, OpenAIProvider

# YandexGPT
analyzer = LLMAnalyzer(provider=YandexGPTProvider(
    folder_id="b1g...", api_key="AQV...", model="yandexgpt-lite",
))

# OpenAI
analyzer = LLMAnalyzer(provider=OpenAIProvider(api_key="sk-..."))

# Ollama (local)
analyzer = LLMAnalyzer(provider=OpenAIProvider(
    api_key="ollama", base_url="http://localhost:11434/v1", model="llama3",
))
```

## Архитектура

```
┌─────────────────┐     ┌──────────────────┐
│  Yandex Wordstat│     │   Reddit API     │
│  (Direct API v4)│     │   (PRAW)         │
└────────┬────────┘     └────────┬─────────┘
         │                       │
         ▼                       ▼
   Keyword volumes         Market signals
   (shows/month)        (discussions, complaints)
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
              Gap Analyzer
         (score = demand / supply)
                     │
                     ▼
              ┌──────────────┐
              │  LLM Engine  │
              │ (YandexGPT / │
              │   OpenAI)    │
              └──────┬───────┘
                     │
                     ▼
           Niche Recommendations
```

## Пример вывода

```
============================================================
MARKET GAP ANALYSIS REPORT
============================================================

  1. crm для фрилансеров
     Monthly searches: 2,450
     Gap score: 122.5
     Related: учет клиентов фрилансер, crm бесплатно

Total opportunities found: 1

============================================================
REDDIT MARKET SIGNALS REPORT
============================================================

  1. [unmet_demand] r/SaaS
     Looking for a simple CRM that works for solo freelancers
     Score: 142 | Comments: 67
     Keywords: looking for, crm

Total signals: 15

============================================================
AI NICHE RECOMMENDATIONS
============================================================

1. CRM для фрилансеров [high demand, 85% confidence]
   Высокий спрос (2,450 запросов/мес) при отсутствии специализированного решения
   Product idea: Легковесный CRM с треком проектов, инвойсингом и простым UI
   Evidence:
     - 2,450 поисковых запросов/мес по "crm для фрилансеров"
     - Reddit: активный поиск альтернатив в r/SaaS и r/Entrepreneur
```

## Лицензия

MIT — см. [LICENSE](LICENSE).

## Благодарности

- [Yandex.Wordstat-parser](https://github.com/ne-coding/Yandex.Wordstat-parser) (MIT) — паттерн работы с Direct API
- [PRAW](https://praw.readthedocs.io/) — Python Reddit API Wrapper
- [OpenAI Python SDK](https://github.com/openai/openai-python) — LLM integration
