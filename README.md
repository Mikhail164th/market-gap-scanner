# Market Gap Scanner

Инструмент для анализа рыночных ниш с использованием нескольких источников данных:

- **Яндекс.Вордстат** — объём поисковых запросов через API Яндекс.Директа
- **Reddit** — сигналы рынка из обсуждений (жалобы, запросы, поиск альтернатив)

Сканирует спрос, находит незанятые ниши и выявляет рыночные пробелы.

## Возможности

### Wordstat (Яндекс)
- Получение статистики показов по ключевым словам через Yandex Direct API v4
- Автоматический gap-scoring: спрос vs конкуренция
- Батч-обработка (до 10 фраз за запрос), геотаргетинг

### Reddit
- Сбор сигналов из тематических сабреддитов через Reddit API (PRAW)
- Классификация: `unmet_demand`, `pain_point`, `competitor_dissatisfaction`, `feature_request`
- Фильтрация по ключевым словам ("looking for", "alternative to", "frustrated with" и др.)

## Установка

```bash
pip install -e .
```

## Использование

### Анализ ключевых слов (Wordstat)

```bash
market-gap-scanner "crm для фрилансеров" "автоматизация бизнеса" --token YOUR_YANDEX_TOKEN
```

### Сбор Reddit-сигналов

```python
from market_gap_scanner.reddit import RedditCollector, format_signals

collector = RedditCollector(
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
)

signals = collector.collect_signals(
    subreddits=["SaaS", "startups", "Entrepreneur"],
    time_filter="week",
)

print(format_signals(signals))
```

### Комбинированный анализ

```python
import asyncio
from market_gap_scanner.wordstat import WordstatClient
from market_gap_scanner.reddit import RedditCollector
from market_gap_scanner.analyzer import analyze_gaps

async def full_scan():
    # 1. Get keyword volumes from Wordstat
    async with WordstatClient(token="YOUR_TOKEN") as ws:
        keyword_data = await ws.get_keyword_stats(["crm freelancer", "task automation"])

    # 2. Collect Reddit signals
    reddit = RedditCollector(client_id="...", client_secret="...")
    signals = reddit.collect_signals(keywords=["crm", "automation", "freelancer"])

    # 3. Analyze gaps
    gaps = analyze_gaps(keyword_data)
    print(f"Found {len(gaps)} market gaps and {len(signals)} Reddit signals")

asyncio.run(full_scan())
```

## Получение API-ключей

### Яндекс Wordstat
1. Зарегистрируйте приложение: [OAuth Яндекса](https://oauth.yandex.ru/)
2. Получите доступ к API Директа
3. Получите OAuth-токен

### Reddit
1. Создайте приложение: [Reddit Apps](https://www.reddit.com/prefs/apps)
2. Тип: `script`
3. Скопируйте `client_id` и `client_secret`

## Схема работы

```
┌─────────────────┐     ┌──────────────────┐
│  Yandex Wordstat│     │     Reddit API   │
│  (Direct API v4)│     │     (PRAW)       │
└────────┬────────┘     └────────┬─────────┘
         │                       │
         ▼                       ▼
   Keyword volumes         Market signals
   (shows/month)        (discussions, complaints)
         │                       │
         └───────────┬───────────┘
                     ▼
              Gap Analyzer
         (score = demand / supply)
                     │
                     ▼
              Market Gaps Report
```

## Пример вывода

### Wordstat
```
============================================================
MARKET GAP ANALYSIS REPORT
============================================================

  1. crm для фрилансеров
     Monthly searches: 2,450
     Gap score: 122.5
     Related: учет клиентов фрилансер, crm бесплатно

Total opportunities found: 1
```

### Reddit
```
============================================================
REDDIT MARKET SIGNALS REPORT
============================================================

  1. [unmet_demand] r/SaaS
     Looking for a simple CRM that works for solo freelancers
     Score: 142 | Comments: 67
     Keywords: looking for, crm

Total signals: 15
```

## Лицензия

MIT — см. [LICENSE](LICENSE).

## Благодарности

- [Yandex.Wordstat-parser](https://github.com/ne-coding/Yandex.Wordstat-parser) (MIT) — за базовый паттерн работы с API
- [PRAW](https://praw.readthedocs.io/) — Python Reddit API Wrapper
