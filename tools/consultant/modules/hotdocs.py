import os,re,json,time,logging,requests,html2text
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv

BASE_DIR=Path.home()/'consultant-data'
SESSION_PATH=BASE_DIR/'session.json'

def load_session():
    import json
    if not SESSION_PATH.exists(): return {}
    cookies_list=json.loads(SESSION_PATH.read_text(encoding='utf-8'))
    return {c['name']:c['value'] for c in cookies_list}

RAW_DIR=BASE_DIR/'raw-html'
MD_DIR=BASE_DIR/'converted-md'
MANIFEST_PATH=BASE_DIR/'manifest.json'
LOG_PATH=BASE_DIR/'scraper.log'
BASE_URL='https://www.consultant.ru'
HOTDOCS_URL=BASE_URL+'/law/hotdocs/'
HEADERS={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36','Accept-Language':'ru-RU,ru;q=0.9'}
BASE_DIR.mkdir(parents=True,exist_ok=True)
logging.basicConfig(level=logging.INFO,format='%(asctime)s [%(levelname)s] %(message)s',handlers=[logging.FileHandler(str(LOG_PATH),encoding='utf-8'),logging.StreamHandler()])
log=logging.getLogger(__name__)

def clean_title(t):
    t=re.sub(r'\s*\(\s*см\.\s*аннотацию\s*\)\s*$','',t).strip()
    m=re.match(r'^(.*?"[^"]*")\s+[А-ЯA-Z].+$',t,re.DOTALL)
    if m: t=m.group(1).strip()
    return t

def safe_fn(t):
    t=re.sub(r'[^\w\s-]','',t.lower())
    return re.sub(r'[\s]+','_',t.strip())[:80]

def load_m():
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH,encoding='utf-8') as f: return json.load(f)
    return []

def save_m(m):
    with open(MANIFEST_PATH,'w',encoding='utf-8') as f: json.dump(m,f,ensure_ascii=False,indent=2)

def downloaded(url,m): return any(i['source_url']==url for i in m)

def fetch(url,retries=3,delay=5):
    cookies=load_session()
    for a in range(retries):
        try:
            r=requests.get(url,headers=HEADERS,cookies=cookies,timeout=20); r.raise_for_status(); return r
        except requests.RequestException as e:
            log.warning(f'  Попытка {a+1}/{retries}: {e}')
            if a<retries-1: time.sleep(delay)
    log.error(f'  Не удалось: {url}'); return None

def get_docs():
    log.info(f'Загружаем {HOTDOCS_URL}')
    resp=fetch(HOTDOCS_URL)
    if not resp: return []
    soup=BeautifulSoup(resp.text,'html.parser')
    docs=[]; seen=set()
    items=soup.find_all('div',class_=lambda c: c and 'hot-docs-list__item' in c)
    log.info(f'Блоков найдено: {len(items)}')
    for item in items:
        # Первая ссылка = сам документ (cons_doc_LAW или document)
        links=item.find_all('a',href=True)
        if not links: continue
        doc_link=links[0]
        url=doc_link['href']
        if not url.startswith('http'): url=BASE_URL+url
        if url in seen: continue
        seen.add(url)
        # Заголовок — текст блока минус дата
        full=item.get_text(separator=' ',strip=True)
        title=re.sub(r'^\d{1,2}\s+\w+\s+\d{4}\s*','',full).strip()
        title=clean_title(title)
        if not title or len(title)<5: continue
        date_m=re.match(r'^(\d{1,2}\s+\w+\s+\d{4})',full)
        date=date_m.group(1) if date_m else datetime.now().strftime('%d.%m.%Y')
        docs.append({'title':title,'url':url,'date':date})
    log.info(f'Итого документов: {len(docs)}')
    return docs

def process(doc):
    title=doc['title']; url=doc['url']
    log.info(f'  Скачиваем: {title[:70]}')
    resp=fetch(url)
    if not resp: return None
    html=resp.text
    soup=BeautifulSoup(html,'html.parser')
    ct=soup.find('div',class_=lambda c: c and any(x in ' '.join(c) for x in ['document','doc-content','text','content'])) or soup.find('body') or soup
    for tag in ct.find_all(['nav','header','footer','script','style']): tag.decompose()
    h2=html2text.HTML2Text(); h2.ignore_links=False; h2.ignore_images=True; h2.body_width=0
    md=h2.handle(str(ct))
    md=re.sub(r'\[Вход в систему\]\([^)]+\)\s*','',md)
    md=re.sub(r'\*\s*\[Главная\]\([^)]+\)\s*','',md)
    md=re.sub(r'\*\s*\[Документы\]\([^)]+\)\s*','',md)
    md=re.sub(r'Открыть полный текст документа\s*','',md)
    md=re.sub(r'\* \* \*.*$','',md,flags=re.DOTALL)
    md=md.strip()
    dd=datetime.now().isoformat()
    slug=safe_fn(title); dt=datetime.now().strftime('%Y%m%d')
    hfn=f'{slug}_{dt}.html'; mfn=f'{slug}_{dt}.md'
    RAW_DIR.mkdir(parents=True,exist_ok=True); MD_DIR.mkdir(parents=True,exist_ok=True)
    (RAW_DIR/hfn).write_text(html,encoding='utf-8')
    (MD_DIR/mfn).write_text(f'---\ntitle: {title}\nsource_url: {url}\ndate_downloaded: {dd}\ndocument_date: {doc["date"]}\n---\n\n# {title}\n\n'+md.strip(),encoding='utf-8')
    log.info(f'    OK: {mfn}')
    return {'title':title,'source_url':url,'date_downloaded':dd,'document_date':doc['date'],'raw_html':f'raw-html/{hfn}','converted_md':f'converted-md/{mfn}'}

def send_tg(saved,errors):
    load_dotenv(Path.home()/'.config'/'consultant'/'.env')
    token=os.getenv('TELEGRAM_BOT_TOKEN','')
    chat_id=os.getenv('TELEGRAM_CHAT_ID','321681061')
    if not token: log.info('TELEGRAM_BOT_TOKEN не задан'); return
    text=f'OK {len(saved)} НПА скачано' if saved else 'Новых НПА нет'
    if errors: text+=f', ошибок: {errors}'
    try: requests.post(f'https://api.telegram.org/bot{token}/sendMessage',json={'chat_id':chat_id,'text':text},timeout=10)
    except Exception as e: log.warning(f'Telegram: {e}')

def main():
    log.info('='*60); log.info('Consultant+ Scraper'); log.info('='*60)
    m=load_m(); docs=get_docs(); saved=[]; errors=0
    for doc in docs:
        if downloaded(doc['url'],m): log.info(f'  Пропуск (есть): {doc["title"][:50]}'); continue
        r=process(doc)
        if r: m.append(r); saved.append(r); save_m(m)
        else: errors+=1
        time.sleep(1)
    log.info(f'Готово: скачано {len(saved)}, ошибок {errors}')
    send_tg(saved,errors)

if __name__=='__main__': main()
