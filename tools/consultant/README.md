# Инструменты выгрузки из КонсультантПлюс

Скачивают кодексы, федеральные законы, указы и судебную практику в
`~/consultant-data` — оттуда их забирает в граф и векторы еженедельный
`scripts/kb_update.sh`. Перенесены сюда 23.10.2026 из отдельного репозитория
`OpenClaw_consultant-tools` (последний коммит там — aee7ae4): к агенту
OpenClaw они отношения не имеют, это часть базы знаний Contract AI.

Вход в К+ и сессия — вне репозитория: логин и пароль в
`~/.config/consultant/.env`, куки — в `~/consultant-data/session.json`.

Окружение — своё (`tools/consultant/.venv`, создаёт
`scripts/deploy_prod_macmini.sh`): Playwright бэкенду не нужен.

**Новые редакции кодексов** ловит `modules/kodeksy.py --refresh`: в К+ новая
редакция кодекса приходит под тем же номером документа, поэтому кодекс
перекачивается и текст сравнивается с сохранённым. Прежний
`modules/edition_check.py` (сверка даты в облачном интерфейсе К+) ослеп после
смены вёрстки К+ и удалён. Посмотреть, что изменилось, ничего не записывая:
`modules/kodeksy.py --refresh --dry-run`.

## Модули

| Модуль | Описание | Статус |
|--------|----------|--------|
| `modules/kodeksy.py` | Загрузка всех Кодексов РФ (23 документа) | ✅ |
| `modules/hotdocs.py` | Еженедельные горячие НПА | ✅ |
| `modules/federal_laws.py` | Федеральные законы (ФЗ + ФКЗ) | ✅ |
| `modules/gov_decrees.py` | Постановления Правительства | 🔄 |
| `modules/court_practice.py` | Судебная практика (КС РФ, ВС РФ) | 🔄 |

## Установка

```bash
pip install -r requirements.txt
playwright install chromium
```

## Использование

```bash
# Кодексы
python3 modules/kodeksy.py
python3 modules/kodeksy.py --force

# Горячие НПА  
python3 modules/hotdocs.py

# Федеральные законы (ФЗ + ФКЗ, автодискавер из карточки поиска К+)
python3 modules/federal_laws.py --smoke 10        # тест: первые 10
python3 modules/federal_laws.py --smoke 5 --only fz   # только ФЗ
python3 modules/federal_laws.py --smoke 5 --only fkz  # только ФКЗ
python3 modules/federal_laws.py --check           # что уже скачано
python3 modules/federal_laws.py --all             # все ~12K (долго!)

# Обновить сессию К+
python3 auth/session.py
```

Файлы складываются в `~/consultant-data/federal-laws/{fz,fkz}/converted-md/`.

## Интеграция с OpenClaw

Модули подключаются как tools к агенту `legal` через `tools/openclaw_tool.py`.
