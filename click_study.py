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

# 日本時間のタイムスタンプ
jst_now = datetime.datetime.now()
log_filename = f"log_{jst_now.strftime('%Y%m%d_%H%M%S')}.txt"

def write_log(message):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{now}] {message}"
    print(log_msg, flush=True)
    with open(log_filename, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

def create_driver(proxy_addr, user_agent):
    """
    proxy_addr: "123.456.78.90:8080" 形式、または None
    """
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--remote-debugging-port=9222')
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
# プロキシの順番を毎回シャッフルして、全プロキシを試せるようにする
original_proxies = [p.strip() for p in raw_proxy_list.split(',') if p.strip()]

write_log(f"=== プログラム開始 (ログファイル: {log_filename}) ===")

try:
    for c in range(1, X_CYCLES + 1):
        total_seconds = M_MIN * 60
        start_time = datetime.datetime.now()
        
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
            # 今回試すプロキシたちのリスト（ランダムに入れ替え）
            test_proxies = random.sample(original_proxies, len(original_proxies))
            
            # --- 手順1: プロキシを一つずつ試す ---
            for p_idx, current_proxy in enumerate(test_proxies, 1):
                driver = None
                try:
                    write_log(f"  [実行] {i}回目(プロキシ試行{p_idx}): {current_proxy}")
                    driver = create_driver(current_proxy, USER_AGENT)
                    driver.set_page_load_timeout(35)
                    driver.get(URL)
                    
                    # 成功判定（タイトルが空でない、かつエラー画面っぽくないこと）
                    if driver.title and len(driver.title) > 3:
                        write_log(f"  [成功] Title: {driver.title[:20]}...")
                        success = True
                        break
                    else:
                        write_log(f"  [失敗] 無効なページタイトルです。")
                except Exception as e:
                    write_log(f"  [エラー] 接続失敗: {str(e)[:40]}")
                finally:
                    if driver: driver.quit()
                
                if success: break

            # --- 手順2: 全プロキシ失敗なら「プロキシなし」で最終試行 ---
            if not success:
                write_log(f"  [最終手段] 全プロキシ失敗のため、プロキシなしで接続します。")
                driver = None
                try:
                    driver = create_driver(None, USER_AGENT)
                    driver.set_page_load_timeout(30)
                    driver.get(URL)
                    write_log(f"  [成功] プロキシなしでアクセス完了: {driver.title[:20]}...")
                    success = True
                except Exception as e:
                    write_log(f"  [断念] プロキシなしでも失敗しました: {str(e)[:40]}")
                finally:
                    if driver: driver.quit()

            if success:
                time.sleep(random.uniform(2, 5))

        cycle_end_time = start_time + datetime.timedelta(seconds=total_seconds)
        while datetime.datetime.now() < cycle_end_time:
            time.sleep(1)

    write_log("=== 全サイクル終了 ===")

except Exception as e:
    write_log(f"致命的エラー: {e}")
