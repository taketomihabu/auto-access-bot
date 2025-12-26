import time
import random
import configparser
import datetime
import json
import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# --- 二重起動防止のチェック ---
# GitHub Actionsの環境ではプロセスが分離されていることがあるため、
# ファイルの存在でチェックします。
LOCK_FILE = "running.lock"

if os.path.exists(LOCK_FILE):
    # 前回の実行が異常終了してファイルが残っている可能性も考慮し、
    # ファイルの作成日時が3時間以上前なら無視して進む（念のため）
    file_time = datetime.datetime.fromtimestamp(os.path.getmtime(LOCK_FILE))
    if datetime.datetime.now() - file_time < datetime.timedelta(hours=3):
        print(f"[{datetime.datetime.now()}] 他のプロセスが実行中のため、終了します。")
        sys.exit(0)

# ロックファイルを作成
with open(LOCK_FILE, "w") as f:
    f.write(str(os.getpid()))

def remove_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
# ----------------------------

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
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    # サーバーの応答（パフォーマンスログ）を取得する設定
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    if user_agent:
        options.add_argument(f'user-agent={user_agent}')
    if proxy_addr:
        options.add_argument(f'--proxy-server={proxy_addr}')
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def check_http_status(driver):
    """ブラウザのログからHTTPステータスコードを解析する"""
    try:
        logs = driver.get_log('performance')
        for entry in logs:
            log = json.loads(entry['message'])['message']
            if log['method'] == 'Network.responseReceived':
                status = log['params']['response']['status']
                # 200(成功) か 302/301(転送) があれば通信成功とみなす
                if status in [200, 301, 302]:
                    return status
    except:
        pass
    return None

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

write_log(f"=== システム起動 (ログ: {log_filename}) ===")

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
        write_log(f"--- サイクル{c} スケジュール公開 ---")
        for idx, t in enumerate(schedule_times, 1):
            write_log(f"  [{idx}回目] 実行予定: {t.strftime('%H:%M:%S')}")

        for i, target_time in enumerate(schedule_times, 1):
            while datetime.datetime.now() < target_time:
                time.sleep(1)
            
            success = False
            # 全プロキシをシャッフルして順番に試す
            test_proxies = random.sample(original_proxies, len(original_proxies))
            
            # 成功するまでプロキシを替えながらループ
            for p_idx, current_proxy in enumerate(test_proxies, 1):
                driver = None
                try:
                    write_log(f"  [試行] {i}回目 (Proxy {p_idx}/{len(test_proxies)}): {current_proxy}")
                    driver = create_driver(current_proxy, USER_AGENT)
                    driver.set_page_load_timeout(40)
                    
                    driver.get(URL)
                    time.sleep(10) # 転送処理を待つ
                    
                    status = check_http_status(driver)
                    current_url = driver.current_url
                    
                    # 厳格な成功判定：
                    # 1. HTTPステータスが200/300系であること
                    # 2. 現在のURLが、元のURLから変化している（転送された）こと
                    if status and current_url != URL:
                        write_log(f"  [成功] 応答:{status} / URL遷移確認完了")
                        success = True
                        break
                    else:
                        write_log(f"  [失敗] 応答:{status} / URL遷移なし")
                except Exception as e:
                    write_log(f"  [エラー] 通信切断: {str(e)[:40]}")
                finally:
                    if driver: driver.quit()
                
                if success: break

            # プロキシ全滅時の最終手段（生IP）
            if not success:
                write_log(f"  [警告] 全プロキシ失敗。生IPで最終試行します。")
                driver = None
                try:
                    driver = create_driver(None, USER_AGENT)
                    driver.get(URL)
                    time.sleep(12)
                    write_log(f"  [完了] 生IPでアクセス実行")
                    success = True
                except Exception as e:
                    write_log(f"  [断念] 生IPアクセス失敗: {e}")
                finally:
                    if driver: driver.quit()

        while datetime.datetime.now() < start_time + datetime.timedelta(seconds=total_seconds):
            time.sleep(1)

except Exception as e:
    write_log(f"システムエラー: {e}")
finally:
    # 終了時に必ずロックファイルを削除
    remove_lock()
    write_log("=== 全工程終了 ===")
