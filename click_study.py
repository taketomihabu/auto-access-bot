import time
import random
import configparser
import datetime
import sys
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException

jst_now = datetime.datetime.now()
log_filename = f"log_{jst_now.strftime('%Y%m%d_%H%M%S')}.txt"

def write_log(message):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{now}] {message}"
    print(log_msg, flush=True)
    with open(log_filename, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

def create_driver(proxy_addr, user_agent):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--remote-debugging-port=9222')
    # 言語設定を日本語に（海外IPからのアクセスでも日本語ブラウザとして振る舞う）
    options.add_argument('--lang=ja-JP')
    
    if user_agent:
        options.add_argument(f'user-agent={user_agent}')
    
    if proxy_addr:
        options.add_argument(f'--proxy-server={proxy_addr}')
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

# 1. 設定読み込み
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')
conf = config['SETTINGS']

URL = conf['URL']
M_MIN = int(conf['M_MINUTES'])
N_TIMES = int(conf['N_TIMES'])
X_CYCLES = int(conf['X_CYCLES'])
MODE = conf['MODE']
USER_AGENT = conf['USER_AGENT']
raw_proxy_list = conf.get('PROXY_LIST', '')
original_proxies = [p.strip() for p in raw_proxy_list.split(',') if p.strip()]

write_log(f"=== プログラム開始 (ログファイル: {log_filename}) ===")

try:
    for c in range(1, X_CYCLES + 1):
        total_seconds = M_MIN * 60
        start_time = datetime.datetime.now()
        
        # スケジュール決定
        if MODE == "fixed":
            offsets = [(total_seconds / N_TIMES) * i for i in range(N_TIMES)]
        else:
            offsets = sorted([random.uniform(0, total_seconds) for _ in range(N_TIMES)])
        
        schedule_times = [start_time + datetime.timedelta(seconds=o) for o in offsets]
        
        write_log(f"--- 第 {c} サイクル スケジュール ---")
        for idx, t in enumerate(schedule_times, 1):
            write_log(f"  予定 {idx}回目: {t.strftime('%H:%M:%S')}")
        write_log("---------------------------------------")

        for i, target_time in enumerate(schedule_times, 1):
            while datetime.datetime.now() < target_time:
                time.sleep(1)
            
            success = False
            test_proxies = random.sample(original_proxies, len(original_proxies))
            
            # 各試行でのプロキシループ
            for p_idx, current_proxy in enumerate(test_proxies, 1):
                driver = None
                try:
                    write_log(f"  [実行] {i}回目(プロキシ試行{p_idx}): {current_proxy}")
                    driver = create_driver(current_proxy, USER_AGENT)
                    # 読み込み待ち時間をしっかり確保
                    driver.set_page_load_timeout(45)
                    
                    # 1. アクセス開始
                    driver.get(URL)
                    
                    # 2. 転送待ち（リダイレクトを考慮して少し待機）
                    time.sleep(8) 
                    
                    current_url = driver.current_url
                    current_title = driver.title
                    
                    # 3. 成功判定：URLが取得できているか、エラーページでないか
                    if current_url and "http" in current_url:
                        # プロキシのエラーページ（403, 502, 接続不可）をタイトルで弾く
                        if any(x in current_title.lower() for x in ["error", "forbidden", "not found", "unavailable"]):
                            write_log(f"  [失敗] エラーページ検出: {current_title[:20]}")
                        else:
                            write_log(f"  [成功] Title: {current_title[:15]}... / URL: {current_url[:30]}...")
                            success = True
                            # ログを確実に残すためのダメ押し滞在
                            time.sleep(5)
                            break
                    else:
                        write_log(f"  [失敗] URL取得不可")
                        
                except Exception as e:
                    write_log(f"  [エラー] 接続失敗: {str(e)[:40]}")
                finally:
                    if driver: driver.quit()
                
                if success: break

            # 全プロキシ失敗時の最終手段
            if not success:
                write_log(f"  [最終手段] プロキシなしで実行")
                driver = None
                try:
                    driver = create_driver(None, USER_AGENT)
                    driver.set_page_load_timeout(30)
                    driver.get(URL)
                    time.sleep(10) # 生IPこそ確実に
                    write_log(f"  [成功] プロキシなし完了: {driver.title[:15]}...")
                    success = True
                except Exception as e:
                    write_log(f"  [断念] 最終手段も失敗: {str(e)[:40]}")
                finally:
                    if driver: driver.quit()

        cycle_end_time = start_time + datetime.timedelta(seconds=total_seconds)
        while datetime.datetime.now() < cycle_end_time:
            time.sleep(1)

    write_log("=== 全サイクル終了 ===")

except Exception as e:
    write_log(f"致命的エラー: {e}")
