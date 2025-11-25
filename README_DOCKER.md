# ChromaDB Docker Setup

## Быстрый старт

### 1. Запустить ChromaDB в Docker

```bash
docker-compose up -d chromadb
```

Проверить статус:
```bash
docker-compose ps
```

### 2. Проверить работу ChromaDB

```bash
# Health check
curl http://localhost:8001/api/v1/heartbeat

# Должен вернуть: {"nanosecond heartbeat": <timestamp>}
```

### 3. Настроить подключение

В `.env` файле:
```bash
# ChromaDB Configuration
CHROMA_HOST=localhost
CHROMA_PORT=8001
CHROMA_MODE=http  # 'http' для Docker, 'local' для локального
```

### 4. Использование в коде

```python
from chromadb import HttpClient

# Подключение к ChromaDB в Docker
client = HttpClient(host='localhost', port=8001)

# Создать коллекцию
collection = client.get_or_create_collection("test")

# Добавить документ с OpenAI embeddings
import openai
text = "Пример текста"
response = openai.embeddings.create(
    model="text-embedding-3-small",
    input=text
)
embedding = response.data[0].embedding

collection.add(
    embeddings=[embedding],
    documents=[text],
    ids=["doc1"]
)

# Поиск
results = collection.query(
    query_embeddings=[embedding],
    n_results=5
)
```

## Управление

### Остановить ChromaDB
```bash
docker-compose stop chromadb
```

### Перезапустить ChromaDB
```bash
docker-compose restart chromadb
```

### Просмотр логов
```bash
docker-compose logs -f chromadb
```

### Полная очистка (удалить все данные)
```bash
docker-compose down -v
rm -rf chroma_data
```

## Продакшн конфигурация

Для продакшна рекомендуется:

1. **Использовать внешний volume**:
```yaml
volumes:
  chroma_data:
    external: true
```

2. **Добавить аутентификацию**:
```yaml
environment:
  - CHROMA_SERVER_AUTH_CREDENTIALS=your-token-here
  - CHROMA_SERVER_AUTH_PROVIDER=token
```

3. **Настроить ресурсы**:
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 4G
    reservations:
      cpus: '1.0'
      memory: 2G
```

4. **Backup данных**:
```bash
# Создать backup
docker run --rm -v contract-ai-chroma_data:/data -v $(pwd):/backup alpine tar czf /backup/chroma-backup-$(date +%Y%m%d).tar.gz -C /data .

# Восстановить backup
docker run --rm -v contract-ai-chroma_data:/data -v $(pwd):/backup alpine sh -c "cd /data && tar xzf /backup/chroma-backup-YYYYMMDD.tar.gz"
```

## Архитектура

```
┌─────────────────┐         HTTP API         ┌──────────────────┐
│   FastAPI App   │────────(port 8001)───────│  ChromaDB Docker │
│  (Port 8000)    │                           │   (Port 8001)    │
└─────────────────┘                           └──────────────────┘
        │                                              │
        │                                              │
        │                                              ▼
        │                                      ┌──────────────┐
        │                                      │   Volume:    │
        │                                      │ chroma_data  │
        ▼                                      └──────────────┘
┌─────────────────┐
│  OpenAI API     │
│  (Embeddings)   │
└─────────────────┘
```

## Мониторинг

### Проверка использования ресурсов
```bash
docker stats contract-ai-chromadb
```

### Проверка размера данных
```bash
du -sh ./chroma_data
```

### Количество коллекций
```bash
curl http://localhost:8001/api/v1/collections | jq
```
