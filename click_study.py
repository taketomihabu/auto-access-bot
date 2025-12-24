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

# プロキシ設定を読み込む
raw_proxy_list = conf.get('PROXY_LIST', '') # 空ならプロキシなし
proxies = [p.strip() for p in raw_proxy_list.split(',') if p.strip()]

# 2. ブラウザ設定
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

# プロキシが設定されていれば、ランダムに1つ選んで適用
if proxies:
    chosen_proxy = random.choice(proxies)
    options.add_argument(f'--proxy-server={chosen_proxy}')
    write_log(f"使用プロキシ: {chosen_proxy}")

if USER_AGENT:
    options.add_argument(f'user-agent={USER_AGENT}')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

write_log("=== プログラム開始 ===")

try:
    for c in range(1, X_CYCLES + 1):
        write_log(f"--- 第 {c} サイクル開始 ({M_MIN}分間に {N_TIMES}回アクセス) ---")
        
        total_seconds = M_MIN * 60
        
        if MODE == "fixed":
            interval = total_seconds / N_TIMES
            for i in range(1, N_TIMES + 1):
                write_log(f"  [サイクル{c}] {i}回目アクセス実行")
                driver.get(URL)
                if i < N_TIMES:
                    next_time = (datetime.datetime.now() + datetime.timedelta(seconds=interval)).strftime('%H:%M:%S')
                    write_log(f"  次まで {round(interval, 1)}秒 待機(定時) [次回予定 {next_time}]")
                    time.sleep(interval)
        
        else:
            # ランダムなタイミングを生成
            timings = sorted([random.uniform(0, total_seconds) for _ in range(N_TIMES)])
            
            last_time = 0
            for i, current_timing in enumerate(timings, 1):
                wait_duration = current_timing - last_time
                
                # 次回の予定時刻を計算
                next_time = (datetime.datetime.now() + datetime.timedelta(seconds=wait_duration)).strftime('%H:%M:%S')
                
                write_log(f"  次のアクセス地点まで {round(wait_duration, 1)}秒 待機(ランダム) [次回予定 {next_time}]")
                time.sleep(wait_duration)
                
                write_log(f"  [サイクル{c}] {i}回目アクセス実行 (地点: {round(current_timing, 1)}秒)")
                driver.get(URL)
                last_time = current_timing
            
            # サイクルの残り時間を消化
            final_wait = total_seconds - last_time
            if final_wait > 0:
                next_cycle_time = (datetime.datetime.now() + datetime.timedelta(seconds=final_wait)).strftime('%H:%M:%S')
                write_log(f"  サイクル残時間 {round(final_wait, 1)}秒 待機して終了 [次サイクル開始予定 {next_cycle_time}]")
                time.sleep(final_wait)

    write_log("=== 全サイクル終了 ===")

except KeyboardInterrupt:
    write_log("中断されました。")
finally:
    driver.quit()
