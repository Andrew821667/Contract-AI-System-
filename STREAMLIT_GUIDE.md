# 📖 РУКОВОДСТВО ПО STREAMLIT

## 🤔 Как работает Streamlit?

**Streamlit = это веб-сервер**, который работает **постоянно** в фоне, как любой веб-сайт.

### Аналогия с веб-сайтом:

| Обычный сайт | Streamlit |
|--------------|-----------|
| Nginx/Apache работает 24/7 | Streamlit работает постоянно |
| Вы открываете google.com | Вы открываете localhost:8501 |
| Google отдаёт страницу | Streamlit отдаёт страницу |
| Вы закрываете браузер | Вы закрываете браузер |
| Google продолжает работать | Streamlit продолжает работать |

---

## 🔄 Жизненный цикл:

```
1. ЗАПУСК (один раз)
   ↓
   streamlit run app.py
   ↓
2. РАБОТА (постоянно)
   ↓
   Streamlit слушает порт 8501
   Ждёт подключений
   ↓
3. ПОДКЛЮЧЕНИЕ (когда вы открываете браузер)
   ↓
   http://localhost:8501
   ↓
   Streamlit отдаёт HTML
   Вы видите UI
   ↓
4. ЗАКРЫТИЕ браузера
   ↓
   Streamlit ПРОДОЛЖАЕТ работать
   (не останавливается!)
```

---

## ✅ ТЕКУЩИЙ СТАТУС

**Streamlit УЖЕ работает!**

```bash
Процесс ID: 25531
Порт: 8501
Статус: РАБОТАЕТ В ФОНЕ
URL: http://localhost:8501
```

Вы можете:
- Открыть браузер → увидите UI
- Закрыть браузер → Streamlit продолжит работать
- Открыть снова → UI снова появится

---

## 🛠️ УПРАВЛЕНИЕ STREAMLIT

### Проверить статус:
```bash
ps aux | grep streamlit | grep -v grep
```

Если видите строку → **Streamlit работает** ✅
Если пусто → **Streamlit НЕ работает** ❌

### Запустить:
```bash
cd /Users/andrew/Contract-AI-System-
./start_streamlit.sh
```

Или вручную:
```bash
cd /Users/andrew/Contract-AI-System-
/Users/andrew/Library/Python/3.13/bin/streamlit run app.py
```

### Остановить:
```bash
cd /Users/andrew/Contract-AI-System-
./stop_streamlit.sh
```

Или вручную:
```bash
pkill -f "streamlit run app.py"
```

### Перезапустить:
```bash
cd /Users/andrew/Contract-AI-System-
./stop_streamlit.sh
./start_streamlit.sh
```

---

## 📊 ЛОГИ

Логи сохраняются в файл:
```bash
tail -f /Users/andrew/Contract-AI-System-/streamlit.log
```

Для просмотра в реальном времени:
```bash
cd /Users/andrew/Contract-AI-System-
tail -f streamlit.log
```

---

## 🚀 АВТОЗАПУСК ПРИ ВКЛЮЧЕНИИ MAC

Если хотите, чтобы Streamlit запускался **автоматически** при включении компьютера:

### Шаг 1: Создать файл автозапуска
```bash
nano ~/Library/LaunchAgents/com.contractai.streamlit.plist
```

### Шаг 2: Вставить содержимое:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.contractai.streamlit</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/andrew/Contract-AI-System-/start_streamlit.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/andrew/Contract-AI-System-/streamlit.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/andrew/Contract-AI-System-/streamlit_error.log</string>
</dict>
</plist>
```

### Шаг 3: Активировать
```bash
launchctl load ~/Library/LaunchAgents/com.contractai.streamlit.plist
```

Теперь Streamlit будет запускаться автоматически при включении Mac!

---

## 🌐 ДОСТУП К UI

### Локально (с этого Mac):
```
http://localhost:8501
```

### В локальной сети (с других устройств):
```
http://10.8.0.3:8501
```

### Из интернета (если настроен роутер):
```
http://84.19.3.240:8501
```

---

## 🔧 РЕЖИМЫ ЗАПУСКА

### 1. В терминале (с выводом логов):
```bash
streamlit run app.py
```
- Видны все логи
- Останавливается при закрытии терминала
- Нельзя закрыть терминал

### 2. В фоне (без терминала):
```bash
streamlit run app.py --server.headless=true &
```
- Работает в фоне
- Можно закрыть терминал
- Логи в файл

### 3. Через скрипт (рекомендуется):
```bash
./start_streamlit.sh
```
- Автоматическая проверка
- Логи в файл
- Управление простое

---

## ❓ ЧАСТЫЕ ВОПРОСЫ

### Q: Streamlit запускается при открытии браузера?
**A:** НЕТ! Streamlit должен быть запущен ЗАРАНЕЕ. Браузер только подключается к уже работающему серверу.

### Q: Если я закрою браузер, Streamlit остановится?
**A:** НЕТ! Streamlit продолжит работать в фоне. Вы можете открыть браузер снова.

### Q: Как узнать, работает ли Streamlit?
**A:** Выполните команду:
```bash
ps aux | grep streamlit | grep -v grep
```
Если видите процесс → работает ✅

### Q: Нужно ли запускать Streamlit каждый раз?
**A:** Нет, если настроен автозапуск. Иначе - запускайте вручную при необходимости.

### Q: Можно ли использовать одновременно с нескольких браузеров?
**A:** ДА! Один Streamlit сервер может обслуживать множество браузеров одновременно.

### Q: Почему порт 8501?
**A:** Это стандартный порт Streamlit. Можно изменить через параметр `--server.port`.

---

## 🎯 РЕКОМЕНДАЦИИ

### Для разработки:
```bash
# Запустить в терминале
streamlit run app.py
```
- Видны все логи
- Удобно отлаживать

### Для постоянной работы:
```bash
# Запустить в фоне
./start_streamlit.sh
```
- Работает постоянно
- Не мешает работе
- Логи в файл

### Для продакшена:
- Настроить автозапуск через LaunchAgent
- Использовать reverse proxy (nginx)
- Настроить HTTPS

---

## 📞 КОНТАКТЫ

- **URL:** http://localhost:8501
- **Логи:** /Users/andrew/Contract-AI-System-/streamlit.log
- **Скрипт запуска:** ./start_streamlit.sh
- **Скрипт остановки:** ./stop_streamlit.sh

---

**Streamlit - это постоянно работающий веб-сервер!**
**Не путайте его с программами, которые открываются при клике.**

🚀 Приятной работы!
