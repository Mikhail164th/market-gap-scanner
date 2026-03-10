# Market Gap Scanner

Инструмент для анализа рыночных ниш с использованием данных [Яндекс.Вордстат](https://wordstat.yandex.ru/) через API Яндекс.Директа.

Сканирует поисковые запросы, оценивает объём спроса и находит незанятые ниши — ключевые слова с высоким спросом, но низкой конкуренцией.

## Возможности

- **Сбор данных** — получение статистики показов по ключевым словам через Yandex Direct API v4
- **Анализ ниш** — автоматическое выявление рыночных пробелов (gap score)
- **Батч-обработка** — до 10 фраз за запрос с автоматическим разбиением
- **Геотаргетинг** — фильтрация по регионам
- **CLI** — запуск из командной строки

## Установка

```bash
pip install -e .
```

## Использование

```bash
# Базовый анализ
market-gap-scanner "crm для фрилансеров" "автоматизация бизнеса" --token YOUR_TOKEN

# С фильтрацией по Москве (geo=1) и минимум 500 показов
market-gap-scanner "онлайн курсы" --token YOUR_TOKEN --geo 1 --min-shows 500

# Подробный вывод
market-gap-scanner "доставка еды" --token YOUR_TOKEN -v
```

## Как получить токен

1. Зарегистрируйте приложение на [OAuth Яндекса](https://oauth.yandex.ru/)
2. Получите доступ к API Директа (полный или тестовый)
3. Получите OAuth-токен для приложения

Подробнее: [документация Яндекс.Директ API](https://yandex.ru/dev/direct/doc/start/auth.html)

## Схема работы с API

```
CreateNewWordstatReport (фразы, регион)
        │
        ▼
GetWordstatReportList (poll каждые 3 сек)
        │
        ▼
GetWordstatReport (получение данных)
        │
        ▼
DeleteWordstatReport (очистка)
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

  2. автоматизация малого бизнеса
     Monthly searches: 1,820
     Gap score: 91.0
     Related: автоматизация продаж, crm система

Total opportunities found: 2
```

## Лицензия

MIT — см. [LICENSE](LICENSE).

## Благодарности

Вдохновлено [Yandex.Wordstat-parser](https://github.com/ne-coding/Yandex.Wordstat-parser) от ne-coding.
