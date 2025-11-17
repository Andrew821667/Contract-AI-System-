# ⚡ Quick Start - 5 минут до запуска!

## Минимальные требования
- Ubuntu 22.04
- 1 GB RAM + **3 GB Swap** (критично!)
- 20 GB SSD
- Docker + Docker Compose

---

## 🚀 5 шагов до запуска

### 1. Установите Docker
```bash
curl -fsSL https://get.docker.com | sh
apt install docker-compose -y
```

### 2. Настройте Swap (ВАЖНО!)
```bash
sudo ./setup-swap.sh
```

### 3. Настройте .env
```bash
cp .env.production .env.production

# Измените:
nano .env.production
# - SECRET_KEY (сгенерируйте: openssl rand -hex 32)
# - POSTGRES_PASSWORD
# - OPENAI_API_KEY=sk-...
# - ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Запустите деплой
```bash
./deploy.sh
# Выберите: 1) Deploy
```

### 5. Откройте в браузере
```
http://your-server-ip
```

---

## 📚 Детальная документация
Смотрите [DEPLOYMENT.md](DEPLOYMENT.md) для подробных инструкций

---

## 🐛 Проблемы?

### Out of Memory
```bash
free -h  # Проверьте swap
sudo ./setup-swap.sh  # Создайте swap
```

### Backend не запускается
```bash
docker-compose -f docker-compose.production.yml logs backend
# Проверьте API ключи в .env.production
```

### Не работает сеть
```bash
# Откройте порты
ufw allow 80/tcp
ufw allow 443/tcp
```

---

## ✅ Checklist
- [ ] Docker установлен
- [ ] Swap 3GB настроен
- [ ] .env.production заполнен
- [ ] Порты 80/443 открыты
- [ ] deploy.sh выполнен

**Готово!** 🎉
