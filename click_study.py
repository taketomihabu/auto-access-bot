import time
import random
import configparser
import datetime
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def write_log(message):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{now}] {message}"
    print(log_msg)
    with open("operation_log.txt", "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

def create_driver(proxy_list, user_agent):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--remote-debugging-port=9222')
    if user_agent:
        options.add_argument(f'user-agent={user_agent}')
    if proxy_list:
        chosen_proxy = random.choice(proxy_list)
        options.add_argument(f'--proxy-server={chosen_proxy}')
        # ログはアクセス直前に出すためここでは抑制
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options), chosen_proxy
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options), "None"

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

write_log("=== プログラム開始 ===")

try:
    for c in range(1, X_CYCLES + 1):
        total_seconds = M_MIN * 60
        start_time = datetime.datetime.now()
        
        # --- 改修：最初に全スケジュールを決定 ---
        if MODE == "fixed":
            offsets = [(total_seconds / N_TIMES) * i for i in range(N_TIMES)]
        else:
            offsets = sorted([random.uniform(0, total_seconds) for _ in range(N_TIMES)])
        
        schedule_times = [start_time + datetime.timedelta(seconds=o) for o in offsets]
        
        write_log(f"--- 第 {c} サイクル スケジュール公開 ---")
        for idx, t in enumerate(schedule_times, 1):
            write_log(f"  予定 {idx}回目: {t.strftime('%H:%M:%S')}")
        write_log("---------------------------------------")

        # --- 実行フェーズ ---
        for i, target_time in enumerate(schedule_times, 1):
            # 予定時刻まで待機
            while datetime.datetime.now() < target_time:
                time.sleep(1)
            
            # ブラウザ起動とプロキシ選択
            driver, used_proxy = create_driver(proxies, USER_AGENT)
            driver.set_page_load_timeout(60) # 応答が遅いプロキシのために長めに設定

            try:
                write_log(f"  [実行] {i}回目開始 (Proxy: {used_proxy})")
                driver.get(URL)
                # ページのタイトル等を表示して「アクセスできた感」を出す（デバッグ用）
                write_log(f"  [完了] ページタイトル: {driver.title[:20]}...")
                time.sleep(random.uniform(3, 5))
            except Exception as e:
                write_log(f"  [失敗] アクセスエラー: {str(e)[:50]}")
            finally:
                driver.quit()

        # サイクル終了までの残時間待機（渋滞防止用）
        cycle_end_time = start_time + datetime.timedelta(seconds=total_seconds)
        while datetime.datetime.now() < cycle_end_time:
            time.sleep(1)

    write_log("=== 全サイクル終了 ===")

except Exception as e:
    write_log(f"予期せぬエラー: {e}")
