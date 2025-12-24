import time
import random
import configparser
import datetime
import sys
import os # 追加
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# 日本時間のタイムスタンプを取得してファイル名を作成
# プログラム起動時の時刻をファイル名に使う
jst_now = datetime.datetime.now()
log_filename = f"log_{jst_now.strftime('%Y%m%d_%H%M%S')}.txt"

def write_log(message):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{now}] {message}"
    # flush=True を追加することで、GitHubの画面に即座に表示されるようになります
    print(log_msg, flush=True)
    with open(log_filename, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

# --- 以下、前回のロジックを維持 ---
# (create_driver 関数などはそのまま)

def create_driver(proxy_list, user_agent):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--remote-debugging-port=9222')
    if user_agent:
        options.add_argument(f'user-agent={user_agent}')
    
    chosen_proxy = "None"
    if proxy_list:
        chosen_proxy = random.choice(proxy_list)
        options.add_argument(f'--proxy-server={chosen_proxy}')
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options), chosen_proxy

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
proxies = [p.strip() for p in raw_proxy_list.split(',') if p.strip()]

write_log(f"=== プログラム開始 (ログファイル: {log_filename}) ===")

# (以降のループ処理もそのまま。write_logを呼び出しているのでリアルタイム化されます)
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
            max_retries = 3
            
            for attempt in range(1, max_retries + 1):
                driver, used_proxy = create_driver(proxies, USER_AGENT)
                driver.set_page_load_timeout(40)

                try:
                    write_log(f"  [実行] {i}回目(試行{attempt}): {used_proxy}")
                    driver.get(URL)
                    
                    if driver.title and "not available" not in driver.title.lower():
                        write_log(f"  [成功] Title: {driver.title[:15]}...")
                        success = True
                        time.sleep(random.uniform(3, 5))
                        break
                    else:
                        write_log(f"  [失敗] ページ内容が取得できませんでした。")
                except Exception as e:
                    write_log(f"  [エラー] 接続失敗: {str(e)[:40]}")
                finally:
                    driver.quit()
                
                if attempt < max_retries:
                    write_log("  [リトライ] 別のプロキシで再試行します...")
                    time.sleep(2)
            
            if not success:
                write_log(f"  [断念] {i}回目は規定回数試行しましたが失敗しました。")

        cycle_end_time = start_time + datetime.timedelta(seconds=total_seconds)
        while datetime.datetime.now() < cycle_end_time:
            time.sleep(1)

    write_log("=== 全サイクル終了 ===")

except Exception as e:
    write_log(f"致命的エラー: {e}")
