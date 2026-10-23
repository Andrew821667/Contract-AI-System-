"""Logs into КонсультантПлюс via Playwright and saves cookies to session.json.

Используется всеми modules/*.py для аутентифицированной выкачки.

Проверка успеха обновлена: К+ больше не редиректит на cloud.consultant.ru/cloud/
сразу после login.consultant.ru/. Признак успеха — title страницы становится
«Стартовая страница - КонсультантПлюс» (а не «КонсультантПлюс Авторизация»),
и в DOM появляются ссылки на cloud.consultant.ru с параметром ?rnd=…

Если К+ показывает модалку «Ограничение доступа: учётная запись используется на
других компьютерах» — нажимаем «Попробовать ещё раз», чтобы вытеснить
предыдущую сессию.
"""
import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ENV_PATH = Path.home() / '.config' / 'consultant' / '.env'
SESSION_PATH = Path.home() / 'consultant-data' / 'session.json'
OUTPUT_DIR = Path.home() / 'consultant-recon' / 'output'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')


def _js_click_popbrovat(frame) -> int:
    """JS-side click на любой элемент с текстом 'Попробовать ещё раз'."""
    try:
        return frame.evaluate(
            """() => {
                const all = document.querySelectorAll('*');
                let count = 0;
                for (const el of all) {
                    if (!el.offsetWidth && !el.offsetHeight) continue;
                    const t = (el.innerText || '').trim();
                    if (t === 'Попробовать ещё раз' || t === 'Попробовать еще раз' || t === 'Попробовать') {
                        el.click(); count++;
                    }
                }
                return count;
            }"""
        ) or 0
    except Exception:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
        return 0


def _dump_modal_dom(page) -> None:
    """В отладке — скриншот и DOM-дамп всех элементов содержащих 'Попроб'."""
    debug_dir = Path.home() / 'consultant-data' / '_debug'
    debug_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    try:
        page.screenshot(path=str(debug_dir / f'restriction_{ts}.png'), full_page=True)
    except Exception:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
        pass
    for fr in page.frames:
        try:
            els = fr.evaluate(
                """() => {
                    const out = [];
                    function walk(root) {
                        const all = root.querySelectorAll('*');
                        for (const el of all) {
                            const t = (el.innerText || el.textContent || '').trim();
                            if (t.includes('Попроб') || t.includes('Ограничение')) {
                                out.push({
                                    tag: el.tagName,
                                    id: el.id || null,
                                    cls: (el.className||'').toString().slice(0,120),
                                    text: t.slice(0, 120),
                                    role: el.getAttribute('role'),
                                    visible: !!(el.offsetWidth || el.offsetHeight),
                                    has_shadow: !!el.shadowRoot
                                });
                            }
                            if (el.shadowRoot) walk(el.shadowRoot);
                        }
                    }
                    walk(document);
                    return out;
                }"""
            )
            if els:
                print(f'    Frame {fr.url[:80]}:')
                for e in els[:10]:
                    print(f'      {e}')
        except Exception as e:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
            print(f'    frame err: {e}')


def click_exit_in_restriction(page) -> bool:
    """Нажать «Выйти из системы» в модалке Ограничение доступа.

    Это освобождает лицензию К+. После этого нужна повторная авторизация.
    """
    for sel in (
        '.popupButtons button:has-text("Выйти из системы")',
        'button:has-text("Выйти из системы")',
        '.x-popup-access-limitation button:not(.x-button--primary)',
    ):
        try:
            for el in page.locator(sel).all():
                if el.is_visible():
                    el.click(timeout=3000, force=True)
                    print(f'    [Выйти из системы] clicked via {sel!r}')
                    return True
        except Exception:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
            continue
    # JS fallback
    for fr in page.frames:
        try:
            n = fr.evaluate(
                """() => {
                    let count = 0;
                    for (const b of document.querySelectorAll('button')) {
                        if ((b.innerText||'').trim() === 'Выйти из системы') {
                            b.click(); count++;
                        }
                    }
                    return count;
                }"""
            ) or 0
            if n:
                print(f'    [Выйти из системы] JS-clicked: {n}')
                return True
        except Exception:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
            pass
    return False


def kill_restriction(page, max_tries: int = 3) -> bool:
    """Закрыть модалку «Ограничение доступа», если она появилась.

    Сначала пробуем «Попробовать ещё раз» — это нормальный способ забрать
    сессию. Если за N попыток не помогло (лицензия занята другим клиентом
    К+), возвращаем False — вызывающий должен сделать full logout+re-login.
    """
    for attempt in range(max_tries):
        try:
            body = page.inner_text('body')
        except Exception:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
            body = ''
        if 'Ограничение доступа' not in body and 'используется на других' not in body:
            return True
        print(f'  [Ограничение доступа: попытка {attempt + 1}/{max_tries}]')

        if attempt == 0:
            _dump_modal_dom(page)

        # Strategy 1: Playwright Locator click — точные селекторы по DOM-дампу
        # Структура модалки: .popupButtons > button.x-button.x-button--primary "Попробовать еще раз"
        clicked = False
        for sel in (
            'button.x-button--primary:has-text("Попробовать")',
            '.popupButtons button:has-text("Попробовать")',
            'button:has-text("Попробовать еще раз")',
            'button:has-text("Попробовать ещё раз")',
            'button:has-text("Попробовать")',
            '.x-popup-access-limitation button.x-button--primary',
        ):
            try:
                for el in page.locator(sel).all():
                    if el.is_visible():
                        el.click(timeout=3000, force=True)
                        clicked = True
                        print(f'    clicked via {sel!r}')
                        break
            except Exception:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
                continue
            if clicked:
                break

        # Strategy 2: JS click directly on .popupButtons button (primary one)
        if not clicked:
            for fr in page.frames:
                try:
                    n = fr.evaluate(
                        """() => {
                            let count = 0;
                            // Primary button in popup
                            const btns = document.querySelectorAll(
                                '.popupButtons button.x-button--primary, .popupButtons button.default, .x-popup-access-limitation button.x-button--primary'
                            );
                            for (const b of btns) { b.click(); count++; }
                            // Fallback: any button containing 'Попробовать'
                            if (!count) {
                                for (const b of document.querySelectorAll('button')) {
                                    const t = (b.innerText||b.textContent||'').trim();
                                    if (t.startsWith('Попробовать')) { b.click(); count++; }
                                }
                            }
                            return count;
                        }"""
                    ) or 0
                    if n:
                        print(f'    JS-clicked: {n}')
                        clicked = True
                        break
                except Exception:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
                    pass

        # Strategy 3: keyboard (modal button is often focused by default)
        if not clicked:
            try:
                page.keyboard.press('Enter')
                print('    keyboard Enter')
                clicked = True
            except Exception:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
                pass

        # Strategy 4: reload
        if attempt >= max_tries - 2:
            print('    fallback: page.reload()')
            try:
                page.reload(wait_until='domcontentloaded', timeout=20000)
            except Exception:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
                pass

        # Дать К+ серверу время на смену сессии (он не моментально проверяет)
        time.sleep(8)
        try:
            page.wait_for_load_state('networkidle', timeout=15000)
        except Exception:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
            pass

    try:
        body = page.inner_text('body')
        return 'Ограничение доступа' not in body
    except Exception:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
        return False


def main() -> None:
    load_dotenv(ENV_PATH)
    USERNAME = os.getenv('CONSULTANT_USERNAME', '')
    PASSWORD = os.getenv('CONSULTANT_PASSWORD', '')
    print(f'Логин: {USERNAME[:3]}***')
    if not USERNAME or not PASSWORD:
        raise SystemExit(f'CONSULTANT_USERNAME/PASSWORD не заданы в {ENV_PATH}')

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = browser.new_context(
            viewport={'width': 1366, 'height': 900},
            user_agent=UA,
            locale='ru-RU',
        )
        page = ctx.new_page()

        # Шаг 1: Авторизация
        print('Шаг 1: Авторизация на login.consultant.ru...')
        page.goto('https://login.consultant.ru/', wait_until='networkidle', timeout=30000)
        page.locator('input[name="LoginForm[login]"]').fill(USERNAME)
        time.sleep(0.3)
        page.locator('input[name="LoginForm[password]"]').fill(PASSWORD)
        time.sleep(0.3)
        page.locator('#buttonLogin').click()
        try:
            page.wait_for_load_state('networkidle', timeout=20000)
        except Exception:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
            pass
        time.sleep(3)

        kill_restriction(page)

        title = page.title()
        login_form_present = page.locator('input[name="LoginForm[login]"]').count() > 0
        login_ok = ('Авторизация' not in title) and (not login_form_present)
        print(f'  Title: {title}')
        print(f'  Авторизация: {"OK" if login_ok else "ОШИБКА"}')

        # Шаг 2: Извлечение rnd из ссылок дашборда (нужно для всех модулей)
        rnd = None
        for fr in page.frames:
            try:
                hrefs = fr.eval_on_selector_all('a', 'els => els.map(e => e.href)') or []
            except Exception:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
                continue
            for h in hrefs:
                m = re.search(r'[?&]rnd=([^&]+)', h or '')
                if m:
                    rnd = m.group(1)
                    break
            if rnd:
                break
        if not rnd:
            for fr in page.frames:
                m = re.search(r'[?&]rnd=([^&]+)', fr.url)
                if m:
                    rnd = m.group(1)
                    break
        print(f'  rnd={rnd}')

        # Шаг 3: Smoke-проверка платного доступа на Воздушном кодексе
        print('Шаг 3: Проверка доступа к платному документу (Воздушный кодекс)...')
        page.goto('https://www.consultant.ru/document/cons_doc_LAW_19912/',
                  wait_until='networkidle', timeout=30000)
        text = page.inner_text('body')
        if 'доступен по расписанию' in text:
            print('  ⚠ некоммерческая версия — платный доступ НЕ работает')
        elif 'У вас есть доступ к системе' in text and len(text) < 3000:
            print('  ⚠ www.consultant.ru без логина (cookies не пробросились)')
        elif len(text) > 1000:
            print(f'  OK: платный доступ работает (текст {len(text)} симв)')
        else:
            print(f'  ? непонятный ответ ({len(text)} симв): {text[:200]}')

        # Шаг 4: Сохраняем cookies
        cookies = ctx.cookies()
        SESSION_PATH.write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        print(f'\nCookies сохранены: {len(cookies)} шт. → {SESSION_PATH}')
        domains = sorted({c.get('domain', '') for c in cookies})
        for d in domains:
            cnt = sum(1 for c in cookies if c.get('domain', '') == d)
            print(f'  {d}: {cnt}')

        ctx.close()
        browser.close()


if __name__ == '__main__':
    main()
