import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
import requests
import os
import json

# 配置参数
TOTAL_ASSETS = 1000000  # 建议修改为你真实的资产基数
STRATEGY = {
    "VOO": {"target": "UPRO", "tp_line": 0.10},
    "QQQ": {"target": "TQQQ", "tp_line": 0.08},
    "FNGS": {"target": "FNGU", "tp_line": 0.10}
}

def run_strategy():
    # 1. 授权 Google Sheets
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    # 从环境变量读取 Google 凭据
    creds_dict = json.loads(os.environ['GOOGLE_CREDS'])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(os.environ['SHEET_ID']).worksheet("Strategy_Monitor")

    # 2. 检查买入触发
    for trigger, cfg in STRATEGY.items():
        ticker = yf.Ticker(trigger)
        hist = ticker.history(period="2d")
        if len(hist) < 2: continue
        
        # 计算昨日到现在的跌幅
        change = (hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]
        
        if change <= -0.005:
            # 逻辑：每跌 1% 借 0.1% 总资产 -> 借款金额 = |跌幅| * 0.1 * 总资产
            borrow_amt = abs(change) * 0.1 * TOTAL_ASSETS
            target_symbol = cfg['target']
            target_price = yf.Ticker(target_symbol).history(period="1d")['Close'].iloc[-1]
            
            # 写入表格新行
            new_row = [trigger, target_symbol, "Open", str(hist.index[-1].date()), target_price, round(borrow_amt, 2)]
            sheet.append_row(new_row, value_input_option='USER_ENTERED')
            
            # 推送
            send_push(f"📉 {trigger}触发买入\n跌幅:{change:.2%}\n买入:{target_symbol}\n金额:${borrow_amt:.0f}")

    # 3. 检查止盈止损信号 (读取表格 K 列)
    records = sheet.get_all_records()
    for i, row in enumerate(records):
        if row['Status'] == "Open" and row['Signal'] in ["TP", "SL"]:
            msg = f"🔔 {row['Target_ETF']} 信号触发: {row['Signal']}\n当前净收益: {row['Net_Return']:.2%}\n请平仓还款！"
            send_push(msg)

def send_push(msg):
    requests.post("https://api.pushover.net/1/messages.json", data={
        "token": os.environ['PUSH_TOKEN'],
        "user": os.environ['PUSH_USER'],
        "message": msg
    })

if __name__ == "__main__":
    run_strategy()
