#!/usr/bin/python3
# coding: utf-8

import datetime
import time
import csv
import settings
from datetime import datetime, timedelta

api_key = settings.AK
secret_key = settings.SK

import ccxt
bitbank = ccxt.bitbank({
'apiKey': api_key,
'secret': secret_key,
})

now = datetime.now()
hour_ago = now - timedelta(hours=1)
# fetchMyTrades()関数に渡すためのミリ秒単位の時刻に変換
start_timestamp = int(hour_ago.timestamp() * 1000)
# fetchMyTrades()関数で当日のトレードを取得
trade_info = bitbank.fetchMyTrades('BTC/JPY', since=start_timestamp)

sell_total = 0
sell_amount = 0
buy_total = 0
buy_amount = 0

for trade in trade_info:
    if trade['side'] == 'sell':
        sell_total += trade['price'] * trade['amount']
        sell_amount += trade['amount']
        utc_date = datetime.strptime(trade['datetime'], "%Y-%m-%dT%H:%M:%S.%fZ")
        local_date = utc_date + timedelta(hours=9)  # 日本の場合、9時間を加算
        print("現地時間（日本の場合）:", local_date)
    elif trade['side'] == 'buy':
        buy_total += trade['price'] * trade['amount']
        buy_amount += trade['amount']
        utc_date = datetime.strptime(trade['datetime'], "%Y-%m-%dT%H:%M:%S.%fZ")
        local_date = utc_date + timedelta(hours=9)  # 日本の場合、9時間を加算
        print("現地時間（日本の場合）:", local_date)

difference = sell_total - buy_total
print(f"Sell Side Total: {int(sell_total)}")
print(f"Sell Side Total: {float(sell_amount)}")
print(f"Buy Side Total: {int(buy_total)}")
print(f"Buy Side Total: {float(buy_amount)}")
print(f"Difference (Sell Total - Buy Total): {int(difference)}")

# # 指定した列だけを抽出
# selected_data = [{
#     'datetime': d['datetime'],
#     'side': d['side'],
#     'price': d['price'],
#     'amount': d['amount']
# } for d in trade_info]

# # CSVファイルに書き込む
# csv_file = 'trade_data.csv'
# with open(csv_file, 'w', newline='') as file:
#     writer = csv.DictWriter(file, fieldnames=['datetime', 'side', 'price', 'amount'])
#     writer.writeheader()
#     writer.writerows(selected_data)

# print(f"CSVファイル '{csv_file}' にデータを書き込みました。")