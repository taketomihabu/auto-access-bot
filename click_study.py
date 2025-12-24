import time
import random
import configparser
import datetime
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

# --- ブラウザを起動する関数 ---
def create_driver(proxy_list, user_agent):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')              # GPUを無効化（エラー対策）
    options.add_argument('--disable-extensions')      # 拡張機能を無効化
    options.add_argument('--remote-debugging-port=9222') # ポート衝突を避ける
    
    # タイムアウト対策
    options.page_load_strategy = 'normal' 

    if user_agent:
        options.add_argument(f'user-agent={user_agent}')
    
    if proxy_list:
        chosen_proxy = random.choice(proxy_list)
        options.add_argument(f'--proxy-server={chosen_proxy}')
        write_log(f"  [接続設定] プロキシを使用: {chosen_proxy}")
    else:
        write_log("  [接続設定] プロキシなし（通常IP）で接続します")
    
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
proxies = [p.strip() for p in raw_proxy_list.split(',') if p.strip()]

write_log("=== プログラム開始 ===")

try:
    for c in range(1, X_CYCLES + 1):
        write_log(f"--- 第 {c} サイクル開始 ---")
        total_seconds = M_MIN * 60
        
        if MODE == "fixed":
            timings = [ (total_seconds / N_TIMES) * i for i in range(N_TIMES) ]
        else:
            timings = sorted([random.uniform(0, total_seconds) for _ in range(N_TIMES)])
        
        last_time = 0
        for i, current_timing in enumerate(timings, 1):
            wait_duration = current_timing - last_time
            if wait_duration > 0:
                next_time = (datetime.datetime.now() + datetime.timedelta(seconds=wait_duration)).strftime('%H:%M:%S')
                write_log(f"  次まで {round(wait_duration, 1)}秒 待機 [予定 {next_time}]")
                time.sleep(wait_duration)
            
            # --- ブラウザ生成 ---
            try:
                driver = create_driver(proxies, USER_AGENT)
                driver.set_page_load_timeout(45) # 少し長めに待つ

                write_log(f"  [サイクル{c}] {i}回目アクセス実行: {URL}")
                driver.get(URL)
                time.sleep(random.uniform(2, 4))
                
            except Exception as e:
                write_log(f"  警告: アクセス中にエラーが発生しました: {e}")
            finally:
                # 確実にブラウザを閉じる
                if 'driver' in locals():
                    driver.quit()
            
            last_time = current_timing
            
        final_wait = total_seconds - last_time
        if final_wait > 0:
            time.sleep(final_wait)

    write_log("=== 全サイクル終了 ===")

except KeyboardInterrupt:
    write_log("中断されました。")
