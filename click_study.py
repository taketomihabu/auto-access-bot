import time
import random
import configparser
import datetime
import json
import os
import sys
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# ==========================================================
# 二重起動防止のチェック（GitHubのconcurrency設定に移行したため無効化）
# ==========================================================
# LOCK_FILE = "running.lock"
# if os.path.exists(LOCK_FILE):
#     file_time = datetime.datetime.fromtimestamp(os.path.getmtime(LOCK_FILE))
#     if datetime.datetime.now() - file_time < datetime.timedelta(hours=3):
#         print(f"[{datetime.datetime.now()}] 他のプロセスが実行中のため、終了します。")
#         sys.exit(0)
# with open(LOCK_FILE, "w") as f:
#     f.write(str(os.getpid()))
# def remove_lock():
#     if os.path.exists(LOCK_FILE):
#         os.remove(LOCK_FILE)
# ==========================================================

jst_now = datetime.datetime.now()
log_filename = f"log_{jst_now.strftime('%Y%m%d_%H%M%S')}.txt"

def write_log(message):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{now}] {message}"
    print(log_msg, flush=True)
    with open(log_filename, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

def create_driver(proxy, user_agent):
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(f'user-agent={user_agent}')
    if proxy:
        chrome_options.add_argument(f'--proxy-server={proxy}')
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def check_http_status(driver):
    try:
        performance_log = driver.get_log('performance')
        for entry in performance_log:
            msg = json.loads(entry['message'])['message']
            if msg['method'] == 'Network.responseReceived':
                return msg['params']['response']['status']
    except:
        pass
    return None

# 設定読み込み
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')
conf = config['SETTINGS']

URL = conf['URL']
M_MIN = int(conf['M_MINUTES'])
N_TIMES = int(conf['N_TIMES'])
X_CYCLES = int(conf['X_CYCLES'])
USER_AGENT = conf['USER_AGENT']
TOTAL_GOAL = N_TIMES * X_CYCLES

raw_proxy_list = conf.get('PROXY_LIST', '')
original_proxies = [p.strip() for p in raw_proxy_list.split(',') if p.strip()]

def main_process():
    current_total_success = 0
    write_log(f"=== システム起動 (目標合計アクセス: {TOTAL_GOAL}回) ===")

    for c in range(1, X_CYCLES + 1):
        total_seconds = M_MIN * 60
        cycle_start_time = datetime.datetime.now()
        
        # スケジュール決定
        if conf['MODE'] == "fixed":
            offsets = [(total_seconds / N_TIMES) * i for i in range(N_TIMES)]
        else:
            offsets = sorted([random.uniform(0, total_seconds) for _ in range(N_TIMES)])
        
        schedule_times = [cycle_start_time + datetime.timedelta(seconds=o) for o in offsets]
        
        write_log(f"--- サイクル {c}/{X_CYCLES} 開始 ---")

        for i, target_time in enumerate(schedule_times, 1):
            # 予定時刻まで待機
            while datetime.datetime.now() < target_time:
                time.sleep(1)
            
            success = False
            test_proxies = random.sample(original_proxies, len(original_proxies))
            
            for p_idx, current_proxy in enumerate(test_proxies, 1):
                driver = None
                try:
                    write_log(f"  [試行] 通算{current_total_success + 1}回目 (Proxy {p_idx}/{len(test_proxies)}): {current_proxy}")
                    driver = create_driver(current_proxy, USER_AGENT)
                    driver.set_page_load_timeout(40)
                    driver.get(URL)
                    time.sleep(10) 
                    
                    status = check_http_status(driver)
                    if status and driver.current_url != URL:
                        write_log(f"  [成功] 応答:{status} / 遷移確認完了")
                        success = True
                        current_total_success += 1
                        break
                    else:
                        write_log(f"  [失敗] 応答:{status} / 遷移なし")
                except Exception as e:
                    write_log(f"  [エラー] {str(e)[:50]}")
                finally:
                    if driver: driver.quit()
                
                if success: break

            if not success:
                write_log(f"  [最終手段] 生IPで実行")
                driver = None
                try:
                    driver = create_driver(None, USER_AGENT)
                    driver.get(URL)
                    time.sleep(12)
                    write_log(f"  [完了] 生IPアクセス実行")
                    current_total_success += 1
                except Exception as e:
                    write_log(f"  [断念] 生IP失敗: {e}")
                finally:
                    if driver: driver.quit()

            # 目標達成チェック
            if current_total_success >= TOTAL_GOAL:
                write_log(f"== 目標数({TOTAL_GOAL}回)に達したため、早期終了します ==")
                return

    write_log("=== 全サイクル予定終了 ===")

if __name__ == "__main__":
    try:
        main_process()
    except Exception as e:
        write_log(f"システムエラー: {e}")
    finally:
        # remove_lock() # ロックファイルを使用しないためコメントアウト
        write_log("=== 全工程終了 ===")
