# 🚀 Contract AI System - Deployment Guide

Полное руководство по развёртыванию системы на production сервере с Ubuntu 22.04

---

## 📋 Требования к серверу

### Минимальная конфигурация
- **OS**: Ubuntu 22.04 LTS
- **CPU**: 1 vCPU (минимум)
- **RAM**: 1 GB
- **Swap**: 3 GB (**критично важно!**)
- **Disk**: 20 GB SSD (минимум 12 GB свободно)
- **Network**: Статический IP или домен

### Рекомендуемая конфигурация
- **CPU**: 2+ vCPU
- **RAM**: 2+ GB
- **Swap**: 3-4 GB
- **Disk**: 40+ GB SSD

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────┐
│             Nginx (Port 80/443)         │
│         Reverse Proxy + SSL             │
└──────────┬──────────────────────────────┘
           │
     ┌─────┴─────┐
     │           │
┌────▼────┐  ┌──▼──────────┐
│ Frontend│  │   Backend   │
│ Next.js │  │   FastAPI   │
│ (3000)  │  │   (8000)    │
└─────────┘  └──┬──────┬───┘
                │      │
        ┌───────┘      └────────┐
        │                       │
   ┌────▼─────┐          ┌──────▼───────┐
   │PostgreSQL│          │    Redis     │
   │  (5432)  │          │    (6379)    │
   └──────────┘          └──────────────┘
```

---

## 📦 Что включено

### Services
- **Backend**: FastAPI + LangGraph + ChromaDB + ML
- **Frontend**: Next.js 14 (React)
- **Database**: PostgreSQL 14
- **Cache**: Redis 7
- **Proxy**: Nginx

### Features
✅ Полный AI stack (OpenAI, Claude, YandexGPT, etc.)
✅ Vector search (ChromaDB + sentence-transformers)
✅ ML risk prediction
✅ Real-time WebSocket support
✅ JWT authentication
✅ Auto-backup scripts
✅ Health monitoring
✅ SSL ready

---

## 🚀 Быстрый старт (5 минут)

### 1. Подключитесь к серверу
```bash
ssh root@your-server-ip
```

### 2. Установите Docker
```bash
# Update packages
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install docker-compose -y

# Verify installation
docker --version
docker-compose --version
```

### 3. Клонируйте репозиторий
```bash
cd /opt
git clone https://github.com/your-username/Contract-AI-System.git
cd Contract-AI-System
```

### 4. Настройте Swap (КРИТИЧНО!)
```bash
sudo ./setup-swap.sh
```

Это создаст 3GB swap файл. **Без swap система не запустится!**

### 5. Настройте окружение
```bash
# Скопируйте пример
cp .env.production .env.production

# Отредактируйте конфигурацию
nano .env.production
```

**Обязательно измените:**
```bash
# Security
SECRET_KEY=<сгенерируйте: openssl rand -hex 32>
JWT_SECRET_KEY=<сгенерируйте: openssl rand -hex 32>
POSTGRES_PASSWORD=<придумайте сложный пароль>

# LLM API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Domain (если есть)
DOMAIN=your-domain.com
```

### 6. Запустите деплой
```bash
./deploy.sh
```

Выберите **опцию 1: Deploy (First time setup)**

### 7. Проверьте статус
```bash
# Через deploy.sh
./deploy.sh
# Выбрать: 7) Show status

# Или вручную
docker-compose -f docker-compose.production.yml ps
```

### 8. Доступ к системе

- **Frontend**: http://your-server-ip
- **Backend API**: http://your-server-ip/api
- **API Docs**: http://your-server-ip/api/docs
- **API Redoc**: http://your-server-ip/api/redoc

---

## 🔧 Детальная установка

### Шаг 1: Подготовка сервера

#### 1.1 Обновление системы
```bash
apt update && apt upgrade -y
apt install curl wget git nano htop -y
```

#### 1.2 Настройка файрвола
```bash
# Установка UFW
apt install ufw -y

# Разрешить SSH
ufw allow 22/tcp

# Разрешить HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Включить файрвол
ufw enable
ufw status
```

#### 1.3 Создание swap файла
```bash
# Проверка текущего swap
free -h

# Автоматическая настройка
sudo ./setup-swap.sh

# Или вручную:
fallocate -l 3G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Оптимизация
sysctl vm.swappiness=10
echo "vm.swappiness=10" >> /etc/sysctl.conf
```

### Шаг 2: Установка Docker

```bash
# Удалить старые версии (если есть)
apt remove docker docker-engine docker.io containerd runc

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Запуск Docker при загрузке
systemctl enable docker
systemctl start docker

# Установка Docker Compose
apt install docker-compose -y

# Проверка
docker --version
docker-compose --version
```

### Шаг 3: Клонирование и настройка

```bash
# Создание директории
mkdir -p /opt/apps
cd /opt/apps

# Клонирование
git clone https://github.com/your-username/Contract-AI-System.git
cd Contract-AI-System

# Права доступа
chmod +x *.sh
```

### Шаг 4: Конфигурация

#### 4.1 Создание .env.production
```bash
cp .env.production .env.production.example
nano .env.production
```

#### 4.2 Генерация секретных ключей
```bash
# SECRET_KEY
openssl rand -hex 32

# JWT_SECRET_KEY
openssl rand -hex 32

# POSTGRES_PASSWORD
openssl rand -base64 32
```

#### 4.3 API ключи

Получите API ключи от провайдеров:
- **OpenAI**: https://platform.openai.com/api-keys
- **Anthropic (Claude)**: https://console.anthropic.com/
- **Yandex**: https://cloud.yandex.ru/docs/iam/concepts/authorization/api-key

### Шаг 5: Первый запуск

```bash
# Интерактивный деплой
./deploy.sh

# Или вручную:
docker-compose -f docker-compose.production.yml build
docker-compose -f docker-compose.production.yml up -d
docker-compose -f docker-compose.production.yml exec backend alembic upgrade head
```

### Шаг 6: Проверка работы

```bash
# Логи всех сервисов
docker-compose -f docker-compose.production.yml logs -f

# Только backend
docker-compose -f docker-compose.production.yml logs -f backend

# Статус контейнеров
docker-compose -f docker-compose.production.yml ps

# Health check
curl http://localhost/health
curl http://localhost:8000/health
```

---

## 🔐 Настройка SSL (HTTPS)

### Вариант 1: Let's Encrypt (Certbot)

```bash
# Установка Certbot
apt install certbot -y

# Получение сертификата
certbot certonly --standalone -d your-domain.com

# Сертификаты будут в:
# /etc/letsencrypt/live/your-domain.com/fullchain.pem
# /etc/letsencrypt/live/your-domain.com/privkey.pem

# Копируем в проект
mkdir -p nginx/ssl
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/
cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/

# Включаем HTTPS в nginx/conf.d/contract-ai.conf
# (раскомментируйте секцию # HTTPS Server)
```

### Вариант 2: Самоподписанный сертификат (для тестов)

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem \
  -out nginx/ssl/fullchain.pem \
  -subj "/C=RU/ST=Moscow/L=Moscow/O=ContractAI/CN=your-domain.com"
```

### Автообновление сертификатов

```bash
# Cron job для обновления
crontab -e

# Добавить:
0 0 * * * certbot renew --quiet && docker-compose -f /opt/apps/Contract-AI-System/docker-compose.production.yml restart nginx
```

---

## 📊 Мониторинг

### Проверка ресурсов

```bash
# Использование ресурсов контейнерами
docker stats

# Дисковое пространство
df -h

# Память и swap
free -h

# CPU и процессы
htop
```

### Логи

```bash
# Все логи
./deploy.sh
# Выбрать: 6) Show logs

# Или вручную:
docker-compose -f docker-compose.production.yml logs -f --tail=100

# Конкретный сервис
docker-compose -f docker-compose.production.yml logs -f backend
```

### Health Check

```bash
# Через скрипт
./deploy.sh
# Выбрать: 9) Health check

# Вручную
curl http://localhost/health
curl http://localhost:8000/health
curl http://localhost:3000
```

---

## 💾 Резервное копирование

### Автоматический бэкап

```bash
# Создать бэкап
./backup.sh backup

# Список бэкапов
./backup.sh list

# Восстановление
./backup.sh restore 20250117_120000
```

### Настройка автобэкапа через Cron

```bash
crontab -e

# Ежедневный бэкап в 3:00
0 3 * * * /opt/apps/Contract-AI-System/backup.sh backup

# Еженедельный в воскресенье в 4:00
0 4 * * 0 /opt/apps/Contract-AI-System/backup.sh backup
```

### Что бэкапится

- ✅ PostgreSQL database
- ✅ Uploaded files (data/)
- ✅ ChromaDB vector store
- ✅ Configuration files
- ✅ Manifest с checksums

Бэкапы хранятся в `/backup/contract-ai/`

---

## 🔄 Обновление системы

### Обновление кода

```bash
# Через скрипт
./deploy.sh
# Выбрать: 2) Update

# Или вручную:
git pull origin main
docker-compose -f docker-compose.production.yml build
docker-compose -f docker-compose.production.yml up -d
```

### Обновление зависимостей

```bash
# Пересобрать образы без кэша
docker-compose -f docker-compose.production.yml build --no-cache

# Рестарт
docker-compose -f docker-compose.production.yml up -d
```

---

## 🐛 Troubleshooting

### Проблема: Out of Memory

**Решение:**
```bash
# Проверить swap
free -h

# Если swap отсутствует
sudo ./setup-swap.sh

# Увеличить лимиты памяти в docker-compose
# Отредактировать deploy.resources.limits.memory
```

### Проблема: Backend не запускается

**Проверка:**
```bash
# Логи
docker-compose -f docker-compose.production.yml logs backend

# Войти в контейнер
docker-compose -f docker-compose.production.yml exec backend bash

# Проверить переменные окружения
docker-compose -f docker-compose.production.yml exec backend env | grep API_KEY
```

**Частые причины:**
- ❌ Отсутствует API ключ (OpenAI/Anthropic)
- ❌ Неправильный DATABASE_URL
- ❌ Не хватает памяти

### Проблема: PostgreSQL не стартует

```bash
# Проверить логи
docker-compose -f docker-compose.production.yml logs postgres

# Удалить volume и пересоздать
docker-compose -f docker-compose.production.yml down -v
docker-compose -f docker-compose.production.yml up -d postgres
```

### Проблема: Nginx 502 Bad Gateway

```bash
# Проверить, запущены ли backend и frontend
docker-compose -f docker-compose.production.yml ps

# Проверить логи nginx
docker-compose -f docker-compose.production.yml logs nginx

# Перезапустить
docker-compose -f docker-compose.production.yml restart nginx
```

### Проблема: Медленная работа

```bash
# Проверить CPU и память
docker stats

# Проверить swap
free -h

# Уменьшить workers в backend
# Отредактировать Dockerfile.backend:
# --workers 1 (по умолчанию уже 1)

# Отключить неиспользуемые сервисы
# Закомментировать в docker-compose.production.yml
```

---

## 📈 Оптимизация производительности

### 1. Оптимизация PostgreSQL

```bash
# Войти в контейнер
docker-compose -f docker-compose.production.yml exec postgres bash

# Настроить параметры
psql -U contract_user -d contract_ai

# Выполнить:
ALTER SYSTEM SET shared_buffers = '128MB';
ALTER SYSTEM SET effective_cache_size = '256MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '4MB';
ALTER SYSTEM SET default_statistics_target = 100;

# Рестарт
docker-compose -f docker-compose.production.yml restart postgres
```

### 2. Оптимизация Redis

```bash
# Уже настроено в docker-compose:
# - maxmemory 64mb
# - maxmemory-policy allkeys-lru
```

### 3. Настройка Linux для Docker

```bash
# Увеличить лимиты
echo "fs.file-max = 65536" >> /etc/sysctl.conf
sysctl -p

# Настроить swappiness
sysctl vm.swappiness=10
echo "vm.swappiness=10" >> /etc/sysctl.conf
```

---

## 🔒 Безопасность

### 1. Файрвол

```bash
# Разрешить только необходимые порты
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw enable
```

### 2. Автообновления

```bash
apt install unattended-upgrades -y
dpkg-reconfigure --priority=low unattended-upgrades
```

### 3. Fail2Ban (защита от брутфорса)

```bash
apt install fail2ban -y
systemctl enable fail2ban
systemctl start fail2ban
```

### 4. Регулярные обновления

```bash
# Еженедельно
apt update && apt upgrade -y

# Обновление Docker образов
docker-compose -f docker-compose.production.yml pull
docker-compose -f docker-compose.production.yml up -d
```

---

## 📞 Поддержка

### Логи приложения
- Backend: `/opt/apps/Contract-AI-System/logs/api.log`
- Docker: `docker-compose logs`

### Полезные команды
```bash
# Остановить всё
docker-compose -f docker-compose.production.yml down

# Удалить всё включая volumes
docker-compose -f docker-compose.production.yml down -v

# Очистить неиспользуемые образы
docker system prune -a

# Посмотреть потребление места
docker system df
```

### Контакты
- Issues: https://github.com/your-username/Contract-AI-System/issues
- Email: support@your-domain.com

---

## ✅ Checklist для продакшена

- [ ] Swap 3GB настроен
- [ ] Docker установлен
- [ ] .env.production заполнен
- [ ] Секретные ключи сгенерированы
- [ ] API ключи добавлены
- [ ] Файрвол настроен
- [ ] SSL сертификат установлен
- [ ] Автобэкап настроен (cron)
- [ ] Мониторинг работает
- [ ] Домен привязан
- [ ] DNS настроен
- [ ] Health checks проходят

---

## 🎉 Готово!

Ваша система Contract AI успешно развёрнута!

**Доступ:**
- Frontend: http://your-domain.com
- API: http://your-domain.com/api/docs

**Следующие шаги:**
1. Создайте первого администратора через API
2. Загрузите шаблоны договоров
3. Настройте интеграции с внешними системами
4. Обучите команду работе с системой

**Удачи! 🚀**
