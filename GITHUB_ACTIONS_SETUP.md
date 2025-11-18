# 🚀 GitHub Actions Setup - Инструкция

Автоматическая сборка Docker образов на серверах GitHub и деплой на VPS.

---

## ✅ Что уже готово:

- ✅ Workflow файл создан (`.github/workflows/build-and-deploy.yml`)
- ✅ `docker-compose.production.yml` настроен на использование готовых образов
- ✅ Dockerfiles оптимизированы

---

## 🔐 Шаг 1: Настройте SSH для деплоя (НА СЕРВЕРЕ)

```bash
# 1. Подключитесь к серверу
ssh root@84.19.3.240

# 2. Создайте пользователя для деплоя
sudo useradd -m -s /bin/bash deploy
sudo usermod -aG docker deploy

# 3. Создайте SSH ключ
sudo -u deploy ssh-keygen -t ed25519 -C "github-actions" -f /home/deploy/.ssh/github_actions -N ""

# 4. Добавьте ключ в authorized_keys
sudo -u deploy bash -c 'cat /home/deploy/.ssh/github_actions.pub >> /home/deploy/.ssh/authorized_keys'
sudo -u deploy chmod 600 /home/deploy/.ssh/authorized_keys

# 5. Скопируйте ПРИВАТНЫЙ ключ (нужен для GitHub)
sudo cat /home/deploy/.ssh/github_actions
```

**ВАЖНО:** Скопируйте весь вывод последней команды (начинается с `-----BEGIN OPENSSH PRIVATE KEY-----`)

```bash
# 6. Дайте права на проект
sudo chown -R deploy:deploy /opt/contract-ai-system

# 7. Перезагрузите Docker группу
sudo systemctl restart docker
```

---

## 🔑 Шаг 2: Добавьте Secrets в GitHub

1. Откройте: https://github.com/Andrew821667/Contract-AI-System-/settings/secrets/actions

2. Нажмите **New repository secret**

3. Добавьте следующие секреты:

### Секрет 1: `DEPLOY_HOST`
```
84.19.3.240
```

### Секрет 2: `DEPLOY_USER`
```
deploy
```

### Секрет 3: `DEPLOY_PATH`
```
/opt/contract-ai-system
```

### Секрет 4: `DEPLOY_SSH_KEY`
Вставьте приватный ключ из Шага 1 (пункт 5)

Должно выглядеть так:
```
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
...
(много строк)
...
-----END OPENSSH PRIVATE KEY-----
```

---

## 📦 Шаг 3: Сделайте образы публичными (чтобы сервер мог скачать)

### Вариант A: Публичные образы (рекомендуется для начала)

После первого успешного build:

1. Откройте: https://github.com/Andrew821667/Contract-AI-System-/pkgs/container/contract-ai-system-%2Fbackend
2. Нажмите **Package settings** (справа)
3. Прокрутите вниз до **Danger Zone**
4. Нажмите **Change visibility** → **Public**
5. Подтвердите

Повторите для frontend:
https://github.com/Andrew821667/Contract-AI-System-/pkgs/container/contract-ai-system-%2Ffrontend

### Вариант B: Приватные образы (более безопасно)

Если хотите оставить приватными, нужно на сервере:

```bash
# На сервере создайте Personal Access Token
# GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
# Scope: read:packages

# Залогиньтесь на сервере
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u Andrew821667 --password-stdin
```

---

## 🚀 Шаг 4: Первый запуск!

### Закоммитьте и запушьте изменения:

```bash
# На вашем компьютере (в папке проекта)
git add .github/workflows/build-and-deploy.yml
git add docker-compose.production.yml
git add GITHUB_ACTIONS_SETUP.md
git add requirements.txt
git add Dockerfile.backend

git commit -m "feat: Add GitHub Actions CI/CD with automatic Docker build

- Build images on GitHub servers (fast, 16 vCPU)
- Automatic deployment to VPS
- No local building required
- Solves 1 vCPU server limitation"

git push origin claude/deploy-web-interface-01A4fDJnCFJ2Tzqmpy2W2Xkg
```

### Проверьте процесс:

1. Откройте: https://github.com/Andrew821667/Contract-AI-System-/actions
2. Увидите запущенный workflow "Build and Deploy"
3. Кликните на него чтобы смотреть логи
4. Процесс займёт **5-10 минут**

---

## 📊 Что происходит:

```
1. GitHub Actions получает код ✅
   ↓
2. Собирает Backend образ (5 мин) 🏗️
   ↓
3. Собирает Frontend образ (3 мин) 🏗️
   ↓
4. Загружает в ghcr.io ✅
   ↓
5. Подключается к вашему серверу 🔐
   ↓
6. Скачивает готовые образы (1 мин) 📥
   ↓
7. Запускает контейнеры 🚀
   ↓
8. ✅ Готово!
```

---

## ✅ Проверка работы

После успешного деплоя:

```bash
# Подключитесь к серверу
ssh deploy@84.19.3.240

# Проверьте контейнеры
cd /opt/contract-ai-system
docker-compose -f docker-compose.production.yml ps

# Должны быть запущены:
# - postgres (Up)
# - redis (Up)
# - backend (Up)
# - frontend (Up)
# - nginx (Up)

# Проверьте здоровье
curl http://localhost/health

# Должно вернуть: {"status":"healthy",...}
```

---

## 🔄 Как теперь обновлять проект

**Больше ничего не нужно делать вручную!**

```bash
# Просто делайте изменения и пушьте:
git add .
git commit -m "feat: Add new feature"
git push

# GitHub Actions автоматически:
# 1. Соберёт новые образы
# 2. Задеплоит на сервер
# 3. Перезапустит контейнеры
```

---

## 🐛 Troubleshooting

### Проблема: Build failed на GitHub

Смотрите логи: https://github.com/Andrew821667/Contract-AI-System-/actions

Обычно это:
- ❌ Ошибка в коде
- ❌ Проблема с зависимостями
- ❌ Неправильный Dockerfile

### Проблема: Deploy failed

```bash
# Проверьте SSH ключ
ssh deploy@84.19.3.240

# Если не работает - проверьте:
cat /home/deploy/.ssh/authorized_keys

# Должен содержать публичный ключ
```

### Проблема: Container not found

```bash
# На сервере
docker login ghcr.io -u Andrew821667

# Введите GitHub Personal Access Token

# Попробуйте скачать вручную
docker pull ghcr.io/andrew821667/contract-ai-system-/backend:claude-deploy-web-interface-01a4fdjncfj2tzqmpy2w2xkg
```

---

## 📱 Опционально: Telegram уведомления

Добавьте в конец `.github/workflows/build-and-deploy.yml`:

```yaml
      - name: 📱 Send notification
        if: always()
        uses: appleboy/telegram-action@master
        with:
          to: ${{ secrets.TELEGRAM_CHAT_ID }}
          token: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          message: |
            🚀 Deploy ${{ job.status }}!
            Branch: ${{ github.ref_name }}
            Commit: ${{ github.sha }}
```

Добавьте secrets:
- `TELEGRAM_BOT_TOKEN`: Токен от @BotFather
- `TELEGRAM_CHAT_ID`: Ваш chat ID

---

## 🎉 Готово!

Теперь у вас полностью автоматизированный CI/CD:
- ✅ Сборка на мощных серверах GitHub
- ✅ Автоматический деплой
- ✅ Не нужен мощный сервер
- ✅ Работает навсегда

**При каждом push → автоматический деплой!** 🚀
