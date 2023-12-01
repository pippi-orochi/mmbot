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
SPREAD_ENTRY = 0.0002  # 実効スプレッド(100%=1,1%=0.01)がこの値を上回ったらエントリー
SPREAD_CANCEL = 0.00005 # 実効スプレッド(100%=1,1%=0.01)がこの値を下回ったら指値更新を停止

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
            time.sleep(1)
    return value

# JPY証拠金を参照する関数
def get_colla():

    while True:
        try:
            value = bitbank.privateGetGetcollateral()
            break
        except Exception as e:
            logger.info(e)
            time.sleep(1)
    return value

# 板情報から実効Ask/Bid(=指値を入れる基準値)を計算する関数
def get_effective_tick(size_thru, rate_ask, size_ask, rate_bid, size_bid):

    while True:
        try:
            value = bitbank.fetchOrderBook('ETH/JPY')
            break
        except Exception as e:
            logger.info(e)
            time.sleep(1)

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

    time.sleep(0.5)
    return {'bid': value['bids'][i-1][0], 'ask': value['asks'][j-1][0]}

# 成行注文する関数
def market(side, size):

    while True:
        try:
            value = bitbank.create_order(PAIR, type = 'market', side = side, amount = size)
            break
        except Exception as e:
            logger.info(e)
            time.sleep(1)

    time.sleep(0.5)
    return value

# 指値注文する関数
def limit(side, size, price):

    while True:
        try:
            value = bitbank.create_order('ETH/JPY', type = 'limit', side = side, amount = size, price = price)
            break
        except Exception as e:
            logger.info(e)
            time.sleep(1)

    time.sleep(0.5)
    return value

# 注文をキャンセルする関数
def cancel(id):

    try:
        value = bitbank.cancel_order(symbol = 'ETH/JPY', id = id)
        logger.info(value)
        logger.info('cancel確定')
    except Exception as e:
        logger.info(e)

        # 指値が約定していた(=キャンセルが通らなかった)場合、
        # 注文情報を更新(約定済み)して返す
        value = get_status(id)
        logger.info(value)
        logger.info('未cancel約定')

    time.sleep(0.5)
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
            time.sleep(1)

    for order in values:
        if order['id'] == id:
            status = order['status']
            remaining = order['remaining']
            executed_size = float(order['amount']) - float(remaining)
            size = order['amount']
            price = order['price']

    time.sleep(0.3)
    return {'id': id, 'status': status, 'filled': executed_size, 'remaining': remaining, 'amount': size, 'price': price}

#------------------------------------------------------------------------------#

# 未約定量が存在することを示すフラグ
remaining_ask_flag = 0
remaining_bid_flag = 0

# 指値の有無を示す変数
pos = 'none'

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

    # 自分の指値が存在しないとき実行する
    if pos == 'none':

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

            # 実効Ask/Bidからdelta離れた位置に指値を入れる
            trade_ask = limit('sell', amount_int_ask, ask - DELTA)
            trade_bid = limit('buy', amount_int_bid, bid + DELTA)
            trade_ask['status'] = 'open'
            trade_bid['status'] = 'open'
            pos = 'entry'

            logger.info('--------------------------')
            logger.info('entry')

            time.sleep(1)

    # 自分の指値が存在するとき実行する
    if pos == 'entry':

        # 注文ステータス取得
        if trade_ask['status'] != 'closed':
            logger.info('AAA')
            trade_ask = get_status(trade_ask['id'])
        if trade_bid['status'] != 'closed':
            logger.info('BBB')
            trade_bid = get_status(trade_bid['id'])
        time.sleep(1)


        # 板情報を取得、実効Ask/Bid(指値を入れる基準値)を決定する
        logger.info(trade_ask['amount'])
        if trade_ask['amount'] == None:
            trade_ask['status'] = 'closed'
            logger.info(trade_ask['id'])
            logger.info('上記trade_ask orderクローズ')
        logger.info(trade_bid['amount'])
        if trade_bid['amount'] == None:
            trade_bid['status'] = 'closed'
            logger.info(trade_bid['id'])
            logger.info('上記trade_bid orderクローズ')
        tick = get_effective_tick(size_thru=AMOUNT_THRU, rate_ask=trade_ask['price'], size_ask=trade_ask['amount'], rate_bid=trade_bid['price'], size_bid=trade_bid['amount'])
        ask = float(tick['ask'])
        bid = float(tick['bid'])
        spread = (ask - bid) / bid

        logger.info('--------------------------')
        logger.info('ask:{0}, bid:{1}, spread:{2}%'.format(int(ask * 100) / 100, int(bid * 100) / 100, float(spread * 10000) / 100))
        logger.info('ask status:{0}, filled:{1}/{2}, price:{3}'.format(trade_ask['status'], trade_ask['filled'], trade_ask['amount'], trade_ask['price']))
        logger.info('bid status:{0}, filled:{1}/{2}, price:{3}'.format(trade_bid['status'], trade_bid['filled'], trade_bid['amount'], trade_bid['price']))

        # Ask未約定量が最小注文量を下回るとき実行
        if trade_ask['status'] == 'open' and trade_ask['remaining'] <= AMOUNT_MIN:

            # 注文をキャンセル
            cancel_ask = cancel(trade_ask['id'])
            logger.info(cancel_ask)

            # ステータスをCLOSEDに書き換える
            trade_ask['status'] = 'closed'

            # 未約定量を記録、次サイクルで未約定量を加えるフラグを立てる
            remaining_ask = float(trade_ask['remaining'])
            remaining_ask_flag = 1

            logger.info('--------------------------')
            logger.info('ask almost filled.')

        # Bid未約定量が最小注文量を下回るとき実行
        if trade_bid['status'] == 'open' and trade_bid['remaining'] <= AMOUNT_MIN:

            # 注文をキャンセル
            cancel_bid = cancel(trade_bid['id'])
            logger.info(cancel_bid)

            # ステータスをCLOSEDに書き換える
            trade_bid['status'] = 'closed'

            # 未約定量を記録、次サイクルで未約定量を加えるフラグを立てる
            remaining_bid = float(trade_bid['remaining'])
            remaining_bid_flag = 1

            logger.info('--------------------------')
            logger.info('bid almost filled.')

        # 片方約定の場合は放置して新規注文に移る
        if trade_ask['amount'] != None or trade_bid['amount'] != None:
            #スプレッドが閾値以上のときに実行する
            if spread > SPREAD_CANCEL:
                logger.info('CCC')

                # Ask指値が最良位置に存在しないとき、指値を更新する
                if trade_ask['status'] == 'open' and trade_ask['price'] != ask - DELTA:
                    logger.info('CCC-A')

                    # 指値を一旦キャンセル
                    cancel_ask = cancel(trade_ask['id'])
                    # キャンセル処理中に約定してる場合がある
                    if cancel_ask['status'] != None:
                        # 注文数が最小注文数より大きいとき、指値を更新する
                        if trade_ask['remaining'] >= AMOUNT_MIN:
                            trade_ask = limit('sell', trade_ask['remaining'], ask - DELTA)
                            logger.info('CCC-A-limit-open')
                            trade_ask['status'] = 'open'
                        # 注文数が最小注文数より小さく0でないとき、未約定量を記録してCLOSEDとする
                        elif AMOUNT_MIN > trade_ask['remaining'] > 0:
                            trade_ask['status'] = 'closed'
                            remaining_ask = float(trade_ask['remaining'])
                            remaining_ask_flag = 1
                            logger.info('CCC-A-limit-closed')
                        # 注文数が最小注文数より小さく0のとき、CLOSEDとする
                        else:
                            trade_ask['status'] = 'closed'
                            logger.info('CCC-A-closed')
                    else:
                        trade_ask['status'] = 'closed'
                        logger.info('CCC-A-status-None')


                # Bid指値が最良位置に存在しないとき、指値を更新する
                if trade_bid['status'] == 'open' and trade_bid['price'] != bid + DELTA:
                    logger.info('CCC-B')

                    # 指値を一旦キャンセル
                    cancel_bid = cancel(trade_bid['id'])
                    # キャンセル処理中に約定してる場合がある
                    if cancel_bid['status'] != None:
                        # 注文数が最小注文数より大きいとき、指値を更新する
                        if trade_bid['remaining'] >= AMOUNT_MIN:
                            trade_bid = limit('buy', trade_bid['remaining'], bid + DELTA)
                            logger.info('CCC-B-limit-open')
                            trade_bid['status'] = 'open'
                        # 注文数が最小注文数より小さく0でないとき、未約定量を記録してCLOSEDとする
                        elif AMOUNT_MIN > trade_bid['remaining'] > 0:
                            trade_bid['status'] = 'closed'
                            remaining_bid = float(trade_bid['remaining'])
                            remaining_bid_flag = 1
                            logger.info('CCC-B-limit-closed')
                        # 注文数が最小注文数より小さく0のとき、CLOSEDとする
                        else:
                            trade_bid['status'] = 'closed'
                            logger.info('CCC-B-closed')
                    else:
                        trade_ask['status'] = 'closed'
                        logger.info('CCC-B-status-None')
            else:
                trade_ask['status'] = 'closed'
                trade_bid['status'] = 'closed'

        # Ask/Bid両方の指値が約定したとき、1サイクル終了、最初の処理に戻る
        if trade_ask['status'] == 'closed' and trade_bid['status'] == 'closed':
            pos = 'none'
            logger.info('DDD')

            logger.info('--------------------------')
            logger.info('completed.')

    time.sleep(1)


