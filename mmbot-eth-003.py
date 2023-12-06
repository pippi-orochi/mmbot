#!/usr/bin/python3
# coding: utf-8

import datetime
import time
import settings

api_key = settings.AK
secret_key = settings.SK

import ccxt
bitbank = ccxt.bitbank({
'apiKey': api_key,
'secret': secret_key,
})

# 取引する通貨、シンボルを設定
COIN = 'ETH'
PAIR = 'JPY'

# ロット(単位はETH)
LOT = 0.002

# 最小注文数(取引所の仕様に応じて設定)
# BitbankのETHの場合
AMOUNT_MIN = 0.0001

# スプレッド閾値
SPREAD_ENTRY = 0.00150  # 実効スプレッド(100%=1,1%=0.01)がこの値を上回ったらエントリー
SPREAD_CANCEL = 0.0010 # 実効スプレッド(100%=1,1%=0.01)がこの値を下回ったら指値更新を停止

# 数量X(この数量よりも下に指値をおく)
AMOUNT_THRU = 0.01

# 実効Ask/BidからDELTA離れた位置に指値をおく
DELTA = 1

#------------------------------------------------------------------------------#
#log設定
import logging
logger = logging.getLogger('LoggingTest')
logger.setLevel(10)
fh = logging.FileHandler('log_mm_bf_' + datetime.datetime.now().strftime('%Y%m%d') + '_' + datetime.datetime.now().strftime('%H%M%S') + '.log')
logger.addHandler(fh)
sh = logging.StreamHandler()
logger.addHandler(sh)
formatter = logging.Formatter('%(asctime)s: %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
fh.setFormatter(formatter)
sh.setFormatter(formatter)

#------------------------------------------------------------------------------#

# JPY残高を参照する関数
def get_asset():

    while True:
        try:
            value = bitbank.fetch_balance()
            break
        except Exception as e:
            logger.info(e)
            time.sleep(0.1)
    return value

# JPY証拠金を参照する関数
def get_colla():

    while True:
        try:
            value = bitbank.privateGetGetcollateral()
            break
        except Exception as e:
            logger.info(e)
            time.sleep(0.1)
    return value

# 板情報から実効Ask/Bid(=指値を入れる基準値)を計算する関数
def get_effective_tick(size_thru, rate_ask, size_ask, rate_bid, size_bid):

    while True:
        try:
            value = bitbank.fetchOrderBook('ETH/JPY')
            break
        except Exception as e:
            logger.info(e)
            time.sleep(0.1)

    i = 0
    s = 0
    while s <= size_thru:
        if value['bids'][i][0] == rate_bid:
            s += value['bids'][i][1] - size_bid
        else:
            s += value['bids'][i][1]
        i += 1

    j = 0
    t = 0
    while t <= size_thru:
        if value['asks'][j][0] == rate_ask:
            t += value['asks'][j][1] - size_ask
        else:
            t += value['asks'][j][1]
        j += 1

    time.sleep(0.1)
    return {'bid': value['bids'][i-1][0], 'ask': value['asks'][j-1][0]}

# 成行注文する関数
def market(side, size):

    while True:
        try:
            value = bitbank.create_order(PAIR, type = 'market', side = side, amount = size)
            break
        except Exception as e:
            logger.info(e)
            time.sleep(0.1)

    time.sleep(0.1)
    return value

# 指値注文する関数
def limit(side, size, price, param):
    if param is True:
        params = {'post_only': True}
    else:
        params = {'post_only': False}

    while True:
        try:
            value = bitbank.create_order('ETH/JPY', type = 'limit', side = side, amount = size, price = price, params = params)
            break
        except Exception as e:
            logger.info(e)
            time.sleep(0.1)

    time.sleep(2)
    return value

# 注文をキャンセルする関数
def cancel(id):

    try:
        value = bitbank.cancel_order(symbol = 'ETH/JPY', id = id)
    except Exception as e:
        logger.info(e)
        # 指値が約定していた(=キャンセルが通らなかった)場合、
        # 注文情報を更新(約定済み)して返す
        value = get_status(id)

    time.sleep(0.1)
    return value

# 指定した注文idのステータスを参照する関数
def get_status(id):
    status = None
    remaining = None
    executed_size = None
    size = None
    price = None

    if PAIR == 'ETH/JPY':
        PRODUCT = 'ETH_JPY'
    else:
        PRODUCT = PAIR

    while True:
        try:
            values = bitbank.fetch_open_orders(symbol = 'ETH/JPY')
            break
        except Exception as e:
            logger.info(e)
            time.sleep(0.1)

    for order in values:
        if order['id'] == id:
            status = order['status']
            remaining = order['remaining']
            executed_size = float(order['amount']) - float(remaining)
            size = order['amount']
            price = order['price']

    time.sleep(0.1)
    return {'id': id, 'status': status, 'filled': executed_size, 'remaining': remaining, 'amount': size, 'price': price}

#------------------------------------------------------------------------------#

# 未約定量が存在することを示すフラグ
remaining_ask_flag = 0
remaining_bid_flag = 0

# 指値の有無を示す変数
pos = 'none'

# 直近の板情報を保持するための変数
prev_tick = None
# 片方約定時の条件時に使用
trade_ask_status = 'none'
trade_bid_status = 'none'

#------------------------------------------------------------------------------#

logger.info('--------TradeStart--------')
logger.info('BOT TYPE      : MarketMaker @ bitbank')
logger.info('SYMBOL        : {0}'.format(PAIR))
logger.info('LOT           : {0} {1}'.format(LOT, COIN))
logger.info('SPREAD ENTRY  : {0} %'.format(SPREAD_ENTRY * 100))
logger.info('SPREAD CANCEL : {0} %'.format(SPREAD_CANCEL * 100))

# メインループ
while True:

    # 未約定量の繰越がなければリセット
    if remaining_ask_flag == 0:
        remaining_ask = 0
    if remaining_bid_flag == 0:
        remaining_bid = 0

    # フラグリセット
    remaining_ask_flag = 0
    remaining_bid_flag = 0

    # 一つ前の板情報がある場合、それを保持
    if prev_tick:
        prev_ask = prev_tick['ask']
        prev_bid = prev_tick['bid']
    else:                                        
        prev_ask = 0
        prev_bid = 0

    # 板情報を取得、実効ask/bid(指値を入れる基準値)を決定する
    tick = get_effective_tick(size_thru=AMOUNT_THRU, rate_ask=0, size_ask=0, rate_bid=0, size_bid=0)
    ask = float(tick['ask'])
    bid = float(tick['bid'])
    # 実効スプレッドを計算する
    spread = (ask - bid) / bid

    logger.info('--------------------------')
    logger.info('ask:{0}, bid:{1}, spread:{2}%'.format(int(ask * 100) / 100, int(bid * 100) / 100, float(spread * 10000) / 100))    

    # 実効スプレッドが閾値を超えた場合に実行する
    if spread > SPREAD_ENTRY:
        # 前回のサイクルにて未約定量が存在すれば今回の注文数に加える
        amount_int_ask = LOT + remaining_bid
        amount_int_bid = LOT + remaining_ask            
        # 一つ前の板情報と比較して売り買いどちらが優先か判断
        if abs(ask - prev_ask) > abs(bid - prev_bid):
            trade_bid = limit('buy', amount_int_bid, bid + DELTA, True)
            trade_bid_status = 'open'
            pos = 'entry'
            logger.info('--------------------------')
            logger.info(bid + DELTA)
            logger.info('firstEntry Buy pos=entry')
        else:
            trade_ask = limit('sell', amount_int_ask, ask - DELTA, True)
            trade_ask_status = 'open'
            pos = 'entry'
            logger.info('--------------------------')
            logger.info(ask - DELTA)
            logger.info('firstEntry Sell pos=entry')

    if trade_bid_status == 'open':
        trade_bid = get_status(trade_bid['id'])
        pos = 'none'
        d = bitbank.parse8601('2023-08-24T00:00:00Z')
        fetchTrades = bitbank.fetchMyTrades('ETH/JPY', d, 1, {
            'order': 'desc',
        })
        if trade_bid['id'] == fetchTrades[0]['order']:
            trade_ask = limit('sell', amount_int_ask, ask - DELTA, False)
            trade_bid_status = 'none'
            logger.info('--------------------------')
            logger.info(ask - DELTA)
            logger.info('finalEntry Sell')
        else:
            cancel_bid = cancel(trade_bid['id'])
            trade_bid_status = 'none'

    if trade_ask_status == 'open':
        trade_ask = get_status(trade_ask['id'])
        pos = 'none'
        d = bitbank.parse8601('2023-08-24T00:00:00Z')
        fetchTrades = bitbank.fetchMyTrades('ETH/JPY', d, 1, {
            'order': 'desc',
        })
        if trade_ask['id'] == fetchTrades[0]['order']:
            trade_bid = limit('buy', amount_int_bid, bid + DELTA, False)
            trade_ask_status = 'none'
            logger.info('--------------------------')
            logger.info(bid + DELTA)
            logger.info('finalEntry Buy')
        else:
            cancel_ask = cancel(trade_ask['id'])
            trade_ask_status = 'none'

    time.sleep(0.1)
    # 現在の板情報を保存しておく
    prev_tick = tick

