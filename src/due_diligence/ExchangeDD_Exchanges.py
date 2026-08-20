"""
Functions
"""

# Import of all required packages
from pathlib import Path
import time
import pandas as pd
import requests
import json
import krakenex
from pykrakenapi import KrakenAPI
from binance.client import Client as BneClient
from binance.exceptions import BinanceAPIException
from gate_api.api_client import ApiClient as GateClient
from gate_api.exceptions import ApiException, GateApiException
from gate_api import Configuration as GateConf
from gate_api import SpotApi as GateAPI
from pybit import unified_trading as bbAPI
#from kucoin.client import Market as KcAPI


def pull_data_kraken(ccy_pair, granul, pull_date='2026-06-30'):
    """
    function to pull data from kraken
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    kraken_pull_date_start = (pd.to_datetime(pull_date) + pd.Timedelta('1 day')
                              - pd.Timedelta(granul * 720,
                                             'h')).value // 10 ** 9
    api = krakenex.API()
    k = KrakenAPI(api)
    ccy_pair_list = ccy_pair.split(':')
    if ccy_pair_list[0] == "BTC":
        kraken_ccy_pair = "XBT" + ccy_pair_list[1]
    elif ccy_pair_list[0] == 'DOGE':
        kraken_ccy_pair = 'XDG' + ccy_pair_list[1]
    else:
        kraken_ccy_pair = ccy_pair.replace(':', '')
    traded_pairs = k.get_tradable_asset_pairs()
    if traded_pairs[traded_pairs['altname'] == kraken_ccy_pair].shape[0] == 1:
        data_kraken = k.get_ohlc_data(kraken_ccy_pair, interval=60 * granul,
                                      since=kraken_pull_date_start)[
            0]  # 1440 for daily
        data_kraken = data_kraken.drop(['vwap', 'count'], axis=1)
        # merge to updated and sorted dataframe
        # data_kraken = data_kraken[data_kraken['volume'] > 0]
        data_kraken = data_kraken.sort_index(ascending=True)
    else:
        data_kraken = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])

    data_kraken.insert(0, 'Currencypair', ccy_pair)

    return data_kraken


def pull_data_coinbase(ccy_pair, granul, pull_date):
    """
    function to pull data from coinbase
    :param ccy_pair:
    :param granul:
    :param pull_date:
    :return:
    """

    coinbase_pull_date_end = pd.to_datetime(pull_date) + pd.Timedelta('1 day')
    coinbase_pull_date_start = coinbase_pull_date_end - pd.to_timedelta(
        199 * granul, 'h')
    coinbase_ccy_pair = ccy_pair.replace(':', '-')
    url = (
        f'https://api.exchange.coinbase.com/products/{coinbase_ccy_pair}'
        f'/candles?granularity={granul * 3600}&'
        f'start={coinbase_pull_date_start.strftime("%Y-%m-%dT%H:%M:%SZ")}&'
        f'end={coinbase_pull_date_end.strftime("%Y-%m-%dT%H:%M:%SZ")}')
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        data_coinbase = pd.DataFrame(
            data, columns=['time', 'low', 'high', 'open', 'close', 'volume'])
        data_coinbase['dtime'] = pd.to_datetime(
            data_coinbase['time'].astype('int64'), unit='s')
        data_coinbase.set_index('dtime', inplace=True)
        # merge to updated and sorted dataframe
        data_coinbase = data_coinbase.sort_index(ascending=True)
    except (
            KeyError, ValueError, requests.exceptions, json.JSONDecodeError
    ) as e:
        print(e)
        data_coinbase = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        data_coinbase.insert(0, 'Currencypair', ccy_pair)
    return data_coinbase


def pull_data_bitfinex(ccy_pair, granul, pull_date):
    """
    function to pull data from bitfinex
    :param ccy_pair:
    :param granul:
    :param pull_date:
    :return:
    """
    longnames_dict = {'USDT': 'UST', 'USDC': 'UDC', 'DASH': 'DSH'}
    bitfinex_pull_date_end = (pd.to_datetime(pull_date) + pd.Timedelta(
        '1 day')).value // 10 ** 6
    if granul == 1:
        tf = '1h'
    elif granul == 24:
        tf = '1D'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')

    ccy_pair_list = ccy_pair.split(':')
    for ind in [0, 1]:
        if ccy_pair_list[ind] in longnames_dict.keys():
            ccy_pair_list[ind] = longnames_dict[ccy_pair_list[ind]]
    if len(ccy_pair_list[0]) > 3:
        bitfinex_ccy_pair = ':'.join(ccy_pair_list)
    else:
        bitfinex_ccy_pair = ''.join(ccy_pair_list)
    try:
        bitfinex_pull_date_start = pd.to_datetime(pull_date) - pd.Timedelta(
            value=200, unit=tf[1])
        bitfinex_pull_date_start = bitfinex_pull_date_start.value // 10 ** 6
        url = (
                f"https://api.bitfinex.com/v2/candles/trade:{tf}"
                f":t{bitfinex_ccy_pair}/hist" +
                f"?start={bitfinex_pull_date_start}&end={bitfinex_pull_date_end}")
        print(url)
        r = requests.get(url, timeout=5)
        data = r.json()
        data_bitfinex = pd.DataFrame(data,
                                     columns=['time', 'open', 'close', 'high',
                                              'low', 'volume'])
        data_bitfinex['dtime'] = pd.to_datetime(
            data_bitfinex['time'].astype('int64'), unit='ms')
        data_bitfinex.set_index('dtime', inplace=True)
        data_bitfinex['time'] //= 1000
        data_bitfinex = data_bitfinex[
            ['time', 'open', 'high', 'low', 'close', 'volume']]
        data_bitfinex = data_bitfinex.sort_index(ascending=True)
    except Exception as e:
        print(e)
        data_bitfinex = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        data_bitfinex.insert(0, 'Currencypair', ccy_pair)
    return data_bitfinex


def pull_data_bitstamp(ccy_pair, granul, pull_date):
    """

    :param ccy_pair:
    :param granul:
    :param pull_date:
    :return:
    """
    bitstamp_ccy_pair = ccy_pair.replace(':', '').lower()
    bitstamp_pull_date_end = (pd.to_datetime(pull_date) + pd.Timedelta(
        '1 day')).value // 10 ** 9
    try:
        step = 3600 * granul
        if granul not in (1, 24):
            raise KeyError('invalid granul value, must be either 1 or 24')
        url = (f'https://www.bitstamp.net/api/v2/ohlc/{bitstamp_ccy_pair}'
               f'/?limit=1000&step={step}&end={bitstamp_pull_date_end}')
        if url != '':
            print(url)
            response = requests.get(url, timeout=5)
            # ld = response.json()['data']['ohlc']
            data_bitstamp = pd.DataFrame(response.json()['data']['ohlc'])
            data_bitstamp['dtime'] = pd.to_datetime(
                data_bitstamp['timestamp'].astype('int64'),
                unit='s')
            data_bitstamp.set_index('dtime', inplace=True)
            data_bitstamp = data_bitstamp.rename(columns={'timestamp': 'time'})
            data_bitstamp = data_bitstamp.sort_index(ascending=True)
            # data_bitstamp = data_bitstamp.astype(float).fillna(0.0)
            # data_bitstamp['time'] = data_bitstamp['time'].astype('int64')
            # merge to updated and sorted dataframe
    except (json.decoder.JSONDecodeError, ValueError, KeyError) as e:
        print(e)
        data_bitstamp = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        data_bitstamp.insert(0, 'Currencypair', ccy_pair)

    return data_bitstamp


def pull_data_binance(ccy_pair, granul, pull_date):
    """
    function to pull data from binance
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    client = BneClient()
    binance_pull_date_start = (pd.to_datetime(pull_date) - pd.Timedelta(
        '30 days')).value // 10 ** 6
    interval = str(granul) + 'h'
    binance_ccy_pair = ccy_pair.replace(':', '')
    try:
        data_binance = pd.DataFrame(
            client.get_historical_klines(symbol=binance_ccy_pair,
                                         interval=interval,
                                         start_str=binance_pull_date_start))
        data_binance.columns = ['time', 'open', 'high', 'low', 'close',
                                'volume', 'close_time', 'qav', 'num_trades',
                                'taker_base_vol', 'taker_quote_vol',
                                'is_best_match']
        data_binance['time'] = data_binance['time'] / 1000
        data_binance['dtime'] = pd.to_datetime(
            data_binance['time'].astype('int64'), unit='s')
        data_binance.set_index('dtime', inplace=True)
        data_binance = data_binance[
            ['time', 'open', 'high', 'low', 'close', 'volume']]
        # data_binance = data_binance.astype(float)
        # merge to updated and sorted dataframe
        data_binance.sort_index(ascending=True, inplace=True)
    except (BinanceAPIException, ValueError, KeyError) as e:
        print(e)
        data_binance = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        data_binance.insert(0, 'Currencypair', ccy_pair)

    return data_binance


def pull_data_binanceus(ccy_pair, granul, pull_date):
    """
    function to pull data from binance.us
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    client = BneClient(tld='us')
    binance_pull_date_start = (pd.to_datetime(pull_date) - pd.Timedelta(
        '30 days')).value // 10 ** 6
    interval = str(granul) + 'h'
    binance_ccy_pair = ccy_pair.replace(':', '')
    try:
        data_binance = pd.DataFrame(
            client.get_historical_klines(symbol=binance_ccy_pair,
                                         interval=interval,
                                         start_str=binance_pull_date_start))
        data_binance.columns = ['time', 'open', 'high', 'low', 'close',
                                'volume', 'close_time', 'qav', 'num_trades',
                                'taker_base_vol', 'taker_quote_vol',
                                'is_best_match']
        data_binance['time'] = data_binance['time'] / 1000
        data_binance['dtime'] = pd.to_datetime(
            data_binance['time'].astype('int64'), unit='s')
        data_binance.set_index('dtime', inplace=True)
        data_binance = data_binance[
            ['time', 'open', 'high', 'low', 'close', 'volume']]
        # data_binance = data_binance.astype(float)
        # merge to updated and sorted dataframe
        data_binance.sort_index(ascending=True, inplace=True)
    except (BinanceAPIException, ValueError, KeyError) as e:
        print(e)
        data_binance = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        data_binance.insert(0, 'Currencypair', ccy_pair)

    return data_binance


def pull_data_bittrex(ccy_pair, granul, pull_date='2026-06-30'):
    """
    Request candles from bittrex
    :param ccy_pair: 
    :param granul: 
    :param pull_date: which date should the candles be pulled. 
        Default to be 2026-06-30. Must be the previous month at the latest. 
        The API accepts only year or month internally depending on granul.
    :return: 
    """  #
    bittrex_ccy_pair = ccy_pair.replace(':', '-')
    dt = pull_date.split(sep='-')
    if granul == 1:
        candleinterval = 'HOUR_1'
        dt_url = dt[0] + '/' + dt[1]
    elif granul == 24:
        candleinterval = 'DAY_1'
        dt_url = dt[0]
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    url = (
        f'https://api.bittrex.com/v3/markets/{bittrex_ccy_pair}/candles/TRADE/'
        f'{candleinterval}/historical/{dt_url}')
    print(url)
    try:
        while True:
            r = requests.get(url, timeout=5)
            if r.status_code == 429:
                print(r.reason)
                time.sleep(60)
            if r.status_code in (200, 404):
                break
        bittrex_df = pd.DataFrame(r.json())
        bittrex_df.rename(columns={'startsAt': 'time'}, inplace=True)
        bittrex_df.drop('quoteVolume', axis=1, inplace=True)
        bittrex_df['dtime'] = pd.to_datetime(bittrex_df['time']).dt.tz_localize(
            None)
        bittrex_df.set_index('dtime', inplace=True)
        # bittrex_df = bittrex_df.astype(float)
        bittrex_df.sort_index(ascending=True, inplace=True)
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(e)
        bittrex_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        bittrex_df.insert(0, 'Currencypair', ccy_pair)

    return bittrex_df


def pull_data_bitbank(ccy_pair, granul, pull_date='2026-06-30'):
    """

    :param ccy_pair:
    :param granul:
    :param pull_date:
    :return:
    """
    bitbank_ccy_list = ccy_pair.split(':')
    if bitbank_ccy_list[0].lower() == 'bch':
        bitbank_ccy_list[0] = 'bcc'
    if bitbank_ccy_list[1].lower() == 'bch':
        bitbank_ccy_list[1] = 'bcc'
    bitbank_ccy_pair = '_'.join(bitbank_ccy_list).lower()
    if granul == 1:
        bitbank_granul = '1hour'
        bitbank_pull_date_end = pull_date.replace('-', '')
    elif granul == 24:
        bitbank_granul = '1day'
        bitbank_pull_date_end = pull_date[:4]
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    try:
        url = f'https://public.bitbank.cc/{bitbank_ccy_pair}/candlestick' \
              f'/{bitbank_granul}/{bitbank_pull_date_end}'
        print(url)
        r = requests.get(url, timeout=5)
        bitbank_df = pd.DataFrame(r.json()['data']['candlestick'][0]['ohlcv'],
                                  columns=['open', 'high', 'low', 'close',
                                           'volume', 'time'])
        bitbank_df['dtime'] = pd.to_datetime(
            bitbank_df['time'].astype('int64'), unit='ms').dt.tz_localize(None)
        bitbank_df.set_index('dtime', inplace=True)
        bitbank_df.sort_index(ascending=True, inplace=True)
    except (json.decoder.JSONDecodeError, ValueError, KeyError) as e:
        print(e)
        bitbank_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        bitbank_df.insert(0, 'Currencypair', ccy_pair)
    return bitbank_df


def pull_data_cexio(ccy_pair, granul, pull_date='2026-06-30'):
    """
    Pull data from cex.io using standard REST API.
    :param ccy_pair:
    :param granul: 
    :param pull_date: 
    :return: 
    """
    cexio_ccy_pair = ccy_pair.replace(':', '/')
    cexio_pull_date = pull_date.replace('-', '')
    if granul == 1:
        json_key = 'data1h'
    elif granul == 24:
        json_key = 'data1d'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    try:
        url = 'https://cex.io/api/ohlcv/hd/' + cexio_pull_date + '/' \
              + cexio_ccy_pair
        print(url)
        r = requests.get(url=url)
        cexio_df = pd.DataFrame(
            eval(r.json()[json_key]),
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        cexio_df['dtime'] = pd.to_datetime(
            cexio_df['time'].astype('int64'), unit='s').dt.tz_localize(None)
        cexio_df.set_index('dtime', inplace=True)
    except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
        print(e)
        cexio_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        cexio_df.insert(0, 'Currencypair', ccy_pair)
    return cexio_df


def pull_data_ftx(ccy_pair, granul, pull_date='2026-06-30'):
    """
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    ftx_ccy_pair = ccy_pair.replace(':', '/')
    ftx_granul = 3600 * granul
    ftx_pull_date_end = (pd.to_datetime(pull_date) + pd.Timedelta(
        '1 day')).value // 10 ** 9
    ftx_pull_date_start = ftx_pull_date_end - 200 * ftx_granul
    url = (f'https://ftx.com/api/markets/{ftx_ccy_pair}/candles?resolution=' +
           f'{ftx_granul}&start_time={ftx_pull_date_start}'
           f'&end_time={ftx_pull_date_end}')
    print(url)
    try:
        while True:
            r = requests.get(url, timeout=5)
            if r.status_code == 429:
                print(r.reason)
                time.sleep(5)
            if r.status_code in (200, 404):
                break
        ftx_df = pd.DataFrame(r.json()['result'])
        ftx_df.drop('time', axis=1, inplace=True)
        ftx_df.rename(columns={'startTime': 'time'}, inplace=True)
        ftx_df['dtime'] = pd.to_datetime(ftx_df['time']).dt.tz_localize(None)
        ftx_df.set_index('dtime', inplace=True)
        ftx_df.sort_index(inplace=True, ascending=True)
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(e)
        ftx_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        ftx_df.insert(0, 'Currencypair', ccy_pair)
    return ftx_df


def pull_data_gateio(ccy_pair, granul=1, pull_date='2022-06-30'):
    """

    :param ccy_pair:
    :param granul:
    :param pull_date:
    :return:
    """
    configuration = GateConf(host="https://api.gateio.ws/api/v4")
    api_client = GateClient(configuration)
    api_instance = GateAPI(api_client)
    if granul == 1:
        gateio_granul = '1h'
    elif granul == 24:
        gateio_granul = '1d'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    gateio_ccy_pair = ccy_pair.replace(':', '_')
    gateio_pull_date_end = (pd.to_datetime(pull_date) + pd.Timedelta(
        '1 day')).value // 10 ** 9
    try:
        # Market candlesticks
        api_response = api_instance.list_candlesticks(
            gateio_ccy_pair, limit=200, to=gateio_pull_date_end,interval=gateio_granul)
        gateio_df = pd.DataFrame(api_response,
                                 columns=['time', 'quotevolume', 'close',
                                          'high', 'low', 'open', 'volume',
                                          'status'])
        gateio_df.drop('quotevolume', axis=1, inplace=True)
        gateio_df['dtime'] = pd.to_datetime(
            gateio_df['time'].astype('int64'), unit='s').dt.tz_localize(None)
        gateio_df.set_index('dtime', inplace=True)
        gateio_df.sort_index(inplace=True, ascending=True)
    except (GateApiException, ApiException, ValueError) as e:
        print("Exception, label: %s, message: %s\n" % (e.label, e.message))
        gateio_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        gateio_df.insert(0, 'Currencypair', ccy_pair)
    return gateio_df


def pull_data_gemini(ccy_pair, granul=1, pull_date='2026-06-30'):
    """

    :param ccy_pair:
    :param granul:
    :param pull_date:
    :return:
    """
    if granul == 1:
        gemini_granul = '1hr'
    elif granul == 24:
        gemini_granul = '1day'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    gemini_ccy_pair = ccy_pair.replace(':', '').lower()
    url = f'https://api.gemini.com/v2/candles/{gemini_ccy_pair}/{gemini_granul}'
    try:
        # Market candlesticks
        r = requests.get(url, timeout=5)
        print(url)
        gemini_df = pd.DataFrame(r.json(),
                                 columns=['time', 'open', 'high', 'low',
                                          'close', 'volume'])
        gemini_df['dtime'] = pd.to_datetime(
            gemini_df['time'].astype('int64'), unit='ms').dt.tz_localize(None)
        gemini_df.set_index('dtime', inplace=True)
        gemini_df.sort_index(inplace=True, ascending=True)
    except (
            requests.exceptions.RequestException,
            requests.exceptions.JSONDecodeError,
            KeyError, ValueError) as e:
        print(e)
        gemini_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        gemini_df.insert(0, 'Currencypair', ccy_pair)
    return gemini_df


def pull_data_poloniex(ccy_pair, granul=1, pull_date='2026-07-31'):
    """

    :param ccy_pair:
    :param granul:
    :param pull_date:
    :return:
    """
    poloniex_ccy_list = ccy_pair.split(':')
    if poloniex_ccy_list[0] == '1INCH':
        poloniex_ccy_list[0] = 'ONEINCH'

    poloniex_ccy_pair = '_'.join(poloniex_ccy_list)
    if granul == 1:
        poloniex_granul = 'HOUR_1'
    elif granul == 24:
        poloniex_granul = 'DAY_1'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    poloniex_pull_date_start = pd.to_datetime(pull_date).value // 10 ** 6
    try:
        url = (f'https://api.poloniex.com/markets/{poloniex_ccy_pair}/candles?'
               f'interval={poloniex_granul}'
               f'&startTime={poloniex_pull_date_start}&limit=200')
        r = requests.get(url, timeout=5)
        print(url)
        poloniex_df = pd.DataFrame(r.json(),
                                   columns=['low', 'high', 'open', 'close',
                                            'baseamount', 'volume',
                                            'buyTakerAmount',
                                            'buyTakerQuantity', 'tradeCount',
                                            'elapsed',
                                            'weightedavg',
                                            'interval', 'time', 'closeTime'])
        poloniex_df.drop(
            columns=['baseamount', 'buyTakerAmount', 'buyTakerQuantity',
                     'tradeCount', 'elapsed', 'weightedavg',
                     'interval', 'closeTime'],
            inplace=True)
        # check if we use start or end time to align with coinmetrics
        poloniex_df['dtime'] = pd.to_datetime(
            poloniex_df['time'].astype('int64'), unit='ms')
        poloniex_df.set_index('dtime', inplace=True)
        poloniex_df.sort_index(ascending=True, inplace=True)
    except (json.decoder.JSONDecodeError, ValueError, KeyError) as e:
        print(e)
        poloniex_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        poloniex_df.insert(0, 'Currencypair', ccy_pair)
    return poloniex_df


def pull_data_bibox(ccy_pair, granul, pull_date='2026-06-30'):
    """

    :param ccy_pair:
    :param granul:
    :param pull_date:
    :return:
    """
    if granul == 1:
        bibox_granul = '1hour'
    elif granul == 24:
        bibox_granul = 'day'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    bibox_ccy_pair = ccy_pair.replace(':', '_')
    url = f'https://api.bibox.com/v3/mdata/kline?pair={bibox_ccy_pair}' \
          f'&period={bibox_granul}'
    print(url)
    try:
        r = requests.get(url, timeout=5)
        bibox_df = pd.DataFrame(r.json()['result'])
        bibox_df['dtime'] = pd.to_datetime(bibox_df['time'].astype('int64'),
                                           unit='ms')
        bibox_df.rename(columns={'vol': 'volume'}, inplace=True)
        bibox_df.set_index('dtime', inplace=True)
        bibox_df.sort_index(ascending=True, inplace=True)
    except (json.decoder.JSONDecodeError, ValueError, KeyError) as e:
        print(e)
        bibox_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        bibox_df.insert(0, 'Currencypair', ccy_pair)
    return bibox_df


def pull_data_ftxus(ccy_pair, granul, pull_date='2026-06-30'):
    """
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    ftxus_ccy_pair = ccy_pair.replace(':', '/')
    ftxus_granul = 3600 * granul
    ftxus_pull_date_end = (pd.to_datetime(pull_date) + pd.Timedelta(
        '1 day')).value // 10 ** 9
    ftxus_pull_date_start = ftxus_pull_date_end - 200 * ftxus_granul
    url = (f'https://ftx.us/api/markets/{ftxus_ccy_pair}/candles?resolution=' +
           f'{ftxus_granul}&start_time={ftxus_pull_date_start}'
           f'&end_time={ftxus_pull_date_end}')
    print(url)
    try:
        while True:
            r = requests.get(url, timeout=5)
            if r.status_code == 429:
                print(r.reason)
                time.sleep(5)
            if r.status_code in (200, 404):
                break
        ftxus_df = pd.DataFrame(r.json()['result'])
        ftxus_df.drop('time', axis=1, inplace=True)
        ftxus_df.rename(columns={'startTime': 'time'}, inplace=True)
        ftxus_df['dtime'] = pd.to_datetime(ftxus_df['time']).dt.tz_localize(
            None)
        ftxus_df.set_index('dtime', inplace=True)
        ftxus_df.sort_index(inplace=True, ascending=True)
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(e)
        ftxus_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        ftxus_df.insert(0, 'Currencypair', ccy_pair)
    return ftxus_df


def pull_data_bitmex(ccy_pair, granul, pull_date='2026-06-30'):
    """
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    if granul == 1:
        bitmex_granul = '1h'
    elif granul == 24:
        bitmex_granul = '1d'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    bitmex_ccy_pair = ccy_pair.replace(':', '').replace('BTC', 'XBT')
    bitmex_pull_date_emd = (
            pd.to_datetime(pull_date) + pd.Timedelta('1 day')).strftime(
        '%Y-%m-%d')
    url = (
        f'https://www.bitmex.com/api/v1/trade/bucketed?binSize={bitmex_granul}'
        f'&partial=false&symbol={bitmex_ccy_pair}'
        f'&count={200}&reverse=false&startTime={pull_date}'
        f'&endTime={bitmex_pull_date_emd}')
    print(url)
    try:
        r = requests.get(url, timeout=5)
        bitmex_df = pd.DataFrame(r.json())
        bitmex_df = bitmex_df[
            ['open', 'high', 'low', 'close', 'volume', 'timestamp']]
        bitmex_df['dtime'] = pd.to_datetime(
            bitmex_df['timestamp']).dt.tz_localize(None)
        bitmex_df.rename(columns={'timestamp': 'time'}, inplace=True)
        bitmex_df.set_index('dtime', inplace=True)
        bitmex_df.sort_index(ascending=True, inplace=True)
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(e)
        bitmex_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        bitmex_df.insert(0, 'Currencypair', ccy_pair)
    return bitmex_df


def pull_data_bybit(ccy_pair, granul, pull_date='2026-06-30'):
    """
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    if granul == 1:
        bybit_granul = 60
    elif granul == 24:
        bybit_granul = 'D'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    bybit_ccy_pair = ccy_pair.replace(':', '')
    bybit_pull_date_start = pd.to_datetime(pull_date).value // 10 ** 6
    bybit_pull_date_end = (pd.to_datetime(pull_date) + pd.Timedelta(
        '1 day')).value // 10 ** 6

    try:
        client = bbAPI.HTTP()
        r = client.get_kline(symbol=bybit_ccy_pair, interval=bybit_granul,
                             end=bybit_pull_date_end, category='spot',
                             start=bybit_pull_date_start)
        bybit_df = pd.DataFrame(r['result']['list'],
                                columns=['time', 'open', 'high', 'low', 'close',
                                         'volume', 'turnover'])
        bybit_df = bybit_df[['time', 'open', 'high', 'low', 'close', 'volume']]
        bybit_df['dtime'] = pd.to_datetime(bybit_df['time'].astype('int64'),
                                           unit='ms')
        bybit_df.set_index('dtime', inplace=True)
        bybit_df.sort_index(ascending=True)
    except Exception as e:
        print(e)
        bybit_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        bybit_df.insert(0, 'Currencypair', ccy_pair)

    return bybit_df


def pull_data_cryptocom(ccy_pair, granul, pull_date='2026-06-30'):
    """
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    if granul == 1:
        cryptocom_granul = '1h'
    elif granul == 1:
        cryptocom_granul = '1D'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    cryptocom_ccy_pair = ccy_pair.replace(':', '_')
    input_start_time = pd.to_datetime(pull_date).value // 10 ** 6
    input_end_time = (pd.to_datetime(pull_date) + pd.Timedelta(
        '1 day')).value // 10 ** 6
    url = (f'https://api.crypto.com/exchange/v1/public/get-candlestick?'
           f'timeframe={cryptocom_granul}&instrument_name={cryptocom_ccy_pair}'
           f'&start_ts={input_start_time}&end_ts={input_end_time}')
    print(url)
    try:
        r = requests.get(url, timeout=5)
        cryptocom_df = r.json()
        cryptocom_df = pd.DataFrame(r.json()['result']['data'])
        cryptocom_df.columns = ['open', 'high', 'low', 'close', 'volume',
                                'time']
        cryptocom_df['dtime'] = pd.to_datetime(
            cryptocom_df['time'].astype('int64'), unit='ms')
        cryptocom_df.set_index('dtime', inplace=True)
        cryptocom_df.sort_index(ascending=True, inplace=True)
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(e)
        cryptocom_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        cryptocom_df.insert(0, 'Currencypair', ccy_pair)
    return cryptocom_df


def pull_data_hitbtc(ccy_pair, granul, pull_date='2026-06-30'):
    """
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    if granul == 1:
        hitbtc_granul = 'H1'
    elif granul == 24:
        hitbtc_granul = 'D1'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    hitbtc_ccy_pair = ccy_pair.replace(':', '')
    hitbtc_pull_date_end = (
            pd.to_datetime(pull_date) + pd.Timedelta('1 day')).strftime(
        '%Y-%m-%d')
    url = (f'https://api.hitbtc.com/api/3/public/candles/'
           f'{hitbtc_ccy_pair}?sort=ASC&period={hitbtc_granul}&from={pull_date}'
           f'&till={hitbtc_pull_date_end}&offset=0')
    print(url)
    try:
        r = requests.get(url, timeout=5)
        hitbtc_df = pd.DataFrame(r.json())
        hitbtc_df.columns = ['time', 'open', 'close', 'low', 'high', 'volume',
                             'basevolume']
        hitbtc_df.drop('basevolume', axis=1, inplace=True)
        hitbtc_df['dtime'] = pd.to_datetime(hitbtc_df['time']).dt.tz_localize(
            None)
        hitbtc_df.set_index('dtime', inplace=True)
        hitbtc_df.sort_index(ascending=True, inplace=True)
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(e)
        hitbtc_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        hitbtc_df.insert(0, 'Currencypair', ccy_pair)
    return hitbtc_df


def pull_data_huobi(ccy_pair, granul, pull_date='2026-06-30'):
    """
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    if granul == 1:
        huobi_granul = '60min'
    elif granul == 24:
        huobi_granul = '1day'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    huobi_ccy_pair = ccy_pair.replace(':', '').lower()
    url = (f'https://api.huobi.pro/market/history/kline'
           f'?period={huobi_granul}&symbol={huobi_ccy_pair}&size=2000')
    print(url)
    try:
        r = requests.get(url, timeout=5)
        huobi_df = pd.DataFrame(r.json()['data'])
        huobi_df.drop(['vol', 'count'], axis=1, inplace=True)
        huobi_df.rename(columns={'amount': 'volume', 'id': 'time'},
                        inplace=True)
        huobi_df['dtime'] = pd.to_datetime(huobi_df['time'].astype('int64'),
                                           unit='s')
        huobi_df.set_index('dtime', inplace=True)
        huobi_df.sort_index(ascending=True, inplace=True)
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(e)
        huobi_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        huobi_df.insert(0, 'Currencypair', ccy_pair)

    return huobi_df


def pull_data_kucoin(ccy_pair, granul, pull_date='2026-06-30'):
    """
    Pull OHLC data directly from KuCoin REST API.
    """

    if granul == 1:
        kucoin_granul = '1hour'
    elif granul == 24:
        kucoin_granul = '1day'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')

    kucoin_ccy_pair = ccy_pair.replace(':', '-')

    kucoin_pull_date_start = int(
        pd.to_datetime(pull_date).timestamp()
    )

    kucoin_pull_date_end = int(
        (pd.to_datetime(pull_date) + pd.Timedelta('1 day')).timestamp()
    )

    url = "https://api.kucoin.com/api/v1/market/candles"

    params = {
        "symbol": kucoin_ccy_pair,
        "type": kucoin_granul,
        "startAt": kucoin_pull_date_start,
        "endAt": kucoin_pull_date_end
    }

    try:

        print(url)

        r = requests.get(
            url,
            params=params,
            timeout=10
        )

        r.raise_for_status()

        data = r.json()["data"]

        kucoin_df = pd.DataFrame(
            data,
            columns=[
                'time',
                'open',
                'close',
                'high',
                'low',
                'volume',
                'turnover'
                            ]
        )

        kucoin_df.drop(
            columns=['turnover'],
            inplace=True
        )

        kucoin_df['dtime'] = pd.to_datetime(
            kucoin_df['time'].astype('int64'),
            unit='s'
        )

        kucoin_df.set_index(
            'dtime',
            inplace=True
        )

        kucoin_df.sort_index(
            ascending=True,
            inplace=True
        )

    except Exception as e:

        print(e)

        kucoin_df = pd.DataFrame(
            columns=[
                'time',
                'open',
                'high',
                'low',
                'close',
                'volume'
            ]
        )

    finally:

        kucoin_df.insert(
            0,
            'Currencypair',
            ccy_pair
        )

    return kucoin_df

def pull_data_lbank(ccy_pair, granul, pull_date='2026-06-30'):
    """
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    if granul == 1:
        lbank_granul = 'hour1'
    elif granul == 1:
        lbank_granul = 'day1'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    lbank_ccy_pair = ccy_pair.replace(':', '_').lower()
    # lbank_pull_date_end = (pd.to_datetime(pull_date)
    # + pd.Timedelta('1 day')).value // 10 ** 9
    lbank_pull_date_start = pd.to_datetime(pull_date).value // 10 ** 9
    url = (f'https://api.lbkex.com/v2/kline.do'
           f'?symbol={lbank_ccy_pair}&size=2000&type={lbank_granul}'
           f'&time={lbank_pull_date_start}')
    print(url)
    try:
        r = requests.get(url, timeout=5)
        lbank_df = pd.DataFrame(r.json()['data'])
        lbank_df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
        lbank_df['dtime'] = pd.to_datetime(lbank_df['time'].astype('int64'),
                                           unit='s')
        lbank_df.set_index('dtime', inplace=True)
        lbank_df.sort_index(ascending=True, inplace=True)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(e)
        lbank_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        lbank_df.insert(0, 'Currencypair', ccy_pair)

    return lbank_df

def pull_data_bitget(ccy_pair,
                     granul,
                     pull_date='2026-06-30'):
    """
    Pull OHLC data from Bitget.
    """

    if granul == 1:
        interval = '1h'

    elif granul == 24:
        interval = '1day'

    else:
        raise KeyError(
            'invalid granul value, must be either 1 or 24'
        )

    bitget_symbol = ccy_pair.replace(':', '')

    start_time = int(
        pd.to_datetime(pull_date).timestamp() * 1000
    )

    end_time = int(
        (
            pd.to_datetime(pull_date)
            + pd.Timedelta('1 day')
        ).timestamp() * 1000
    )

    url = "https://api.bitget.com/api/v2/spot/market/candles"

    params = {
        "symbol": bitget_symbol,
        "granularity": interval,
        "startTime": start_time,
        "endTime": end_time
    }

    try:

        r = requests.get(
            url,
            params=params,
            timeout=10
        )

        r.raise_for_status()

        data = r.json()["data"]

        bitget_df = pd.DataFrame(
            data,
            columns=[
                'time',
                'open',
                'high',
                'low',
                'close',
                'volume',
                'quote_volume',
                'trade_count'
            ]
        )

        bitget_df.drop(
            columns=[
                'quote_volume',
                'trade_count'
            ],
            inplace=True,
            errors='ignore'
        )

        bitget_df['dtime'] = pd.to_datetime(
            bitget_df['time'],
            unit='ms'
        )

        bitget_df.set_index(
            'dtime',
            inplace=True
        )

        bitget_df.sort_index(
            ascending=True,
            inplace=True
        )

    except Exception as e:

        print(e)

        bitget_df = pd.DataFrame(
            columns=[
                'time',
                'open',
                'high',
                'low',
                'close',
                'volume'
            ]
        )

    finally:

        bitget_df.insert(
            0,
            'Currencypair',
            ccy_pair
        )

    return bitget_df

def pull_data_hyperliquid(ccy_pair,
                          granul,
                          pull_date='2026-06-30'):
    """
    Pull OHLC data from Hyperliquid.
    """

    if granul == 1:
        interval = "1h"
    elif granul == 24:
        interval = "1d"
    else:
        raise KeyError(
            'invalid granul value, must be either 1 or 24'
        )

    hyper_symbol = ccy_pair.split(':')[0]

    start_time = int(
        pd.to_datetime(pull_date).timestamp() * 1000
    )

    end_time = int(
        (pd.to_datetime(pull_date)
         + pd.Timedelta('1 day')).timestamp() * 1000
    )

    url = "https://api.hyperliquid.xyz/info"

    payload = {
        "type": "candleSnapshot",
        "req": {
            "coin": hyper_symbol,
            "interval": interval,
            "startTime": start_time,
            "endTime": end_time
        }
    }

    try:

        r = requests.post(
            url,
            json=payload,
            timeout=10
        )

        r.raise_for_status()

        data = r.json()
        print(
            f"{ccy_pair} -> coin sent: {hyper_symbol}"
        )

        hyper_df = pd.DataFrame(data)

        hyper_df.rename(
            columns={
                "t": "time",
                "o": "open",
                "h": "high",
                "l": "low",
                "c": "close",
                "v": "volume"
            },
            inplace=True
        )

        hyper_df['dtime'] = pd.to_datetime(
            hyper_df['time'],
            unit='ms'
        )

        hyper_df.set_index(
            'dtime',
            inplace=True
        )

        hyper_df.sort_index(
            ascending=True,
            inplace=True
        )

    except Exception as e:

        print(e)

        hyper_df = pd.DataFrame(
            columns=[
                'time',
                'open',
                'high',
                'low',
                'close',
                'volume'
            ]
        )

    finally:

        hyper_df.insert(
            0,
            'Currencypair',
            ccy_pair
        )

    return hyper_df


def pull_data_liquid(ccy_pair, granul, pull_date='2026-06-30'):
    """
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    if granul in (1, 24):
        liquid_granul = granul * 3600
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    liquid_ccy_pair = ccy_pair.replace(':', '')
    try:
        liquid_pairs_url = pd.DataFrame(
            requests.get('https://api.liquid.com/products').json())
        liquid_product_id = (liquid_pairs_url.loc[
            liquid_pairs_url['currency_pair_code'] == liquid_ccy_pair,
            'id'].values[0])
        url = (
            f'https://api.liquid.com/products/{liquid_product_id}'
            f'/ohlc?resolution={liquid_granul}')
        print(url)
        r = requests.get(url, timeout=5)
        liquid_df = pd.DataFrame(r.json()['data'])
        liquid_df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
        liquid_df['dtime'] = pd.to_datetime(liquid_df['time'].astype('int64'),
                                            unit='s')
        liquid_df.set_index('dtime', inplace=True)
        liquid_df.sort_index(ascending=True, inplace=True)
    except (json.JSONDecodeError, KeyError, ValueError, IndexError) as e:
        print(e)
        liquid_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        liquid_df.insert(0, 'Currencypair', ccy_pair)

    return liquid_df


def pull_data_okex(ccy_pair, granul, pull_date='2026-07-31'):
    """
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    if granul == 1:
        okex_granul = '1H'
    elif granul == 24:
        okex_granul = '1Dutc'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    okex_ccy_pair = ccy_pair.replace(':', '-')
    okex_pull_date_end = (pd.to_datetime(pull_date) + pd.Timedelta(
        '1 day')).value // 10 ** 9
    okex_pull_date_start = pd.to_datetime(pull_date).value // 10 ** 9
    url = (f'https://www.okx.com/api/v5/market/candles'
           f'?instId={okex_ccy_pair}&bar={okex_granul}'
           f'&before={okex_pull_date_end}&limit=200')
    print(url)
    try:
        r = requests.get(url, timeout=5)
        okex_df = pd.DataFrame(r.json()['data'])
        okex_df.columns = ['time', 'open', 'high', 'low', 'close', 'volume',
                           'ccyvol', 'quoteccyvol', 'confirm']
        okex_df.drop(columns=['ccyvol', 'quoteccyvol', 'confirm'], inplace=True)
        okex_df['dtime'] = pd.to_datetime(okex_df['time'].astype('int64'),
                                          unit='ms')
        okex_df.set_index('dtime', inplace=True)
        okex_df.sort_index(ascending=True, inplace=True)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(e)
        okex_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        okex_df.insert(0, 'Currencypair', ccy_pair)

    return okex_df


def pull_data_therocktrading(ccy_pair, granul, pull_date='2026-06-30'):
    """
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    if granul in (1, 24):
        therocktrading_granul = 60 * granul
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    therocktrading_ccy_pair = ccy_pair.replace(':', '')
    therocktrading_pull_date_end = (pd.to_datetime(pull_date) + pd.Timedelta(
        '1 day')).isoformat() + 'Z'
    therocktrading_pull_date_start = pd.to_datetime(pull_date).value // 10 ** 9
    url = (
        f'https://api.therocktrading.com/v1/funds/{therocktrading_ccy_pair}'
        f'/ohlc_statistics'
        f'?period={therocktrading_granul}'
        f'&before={therocktrading_pull_date_end}&sort=ASC')
    print(url)
    try:
        r = requests.get(url, timeout=5)
        therocktrading_df = pd.DataFrame(r.json())
        therocktrading_df = therocktrading_df[
            ['open', 'high', 'low', 'close', 'traded_volume',
             'interval_starts_at']]
        therocktrading_df.rename(
            columns={'interval_starts_at': 'time', 'traded_volume': 'volume'},
            inplace=True)
        therocktrading_df['dtime'] = pd.to_datetime(
            therocktrading_df['time']).dt.tz_localize(None)
        therocktrading_df.set_index('dtime', inplace=True)
        therocktrading_df.sort_index(ascending=True, inplace=True)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(e)
        therocktrading_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        therocktrading_df.insert(0, 'Currencypair', ccy_pair)

    return therocktrading_df


def pull_data_zbcom(ccy_pair, granul, pull_date='2026-06-30'):
    """
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    if granul == 1:
        zbcom_granul = '1hour'
    elif granul == 24:
        zbcom_granul = '1day'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    zbcom_ccy_pair = ccy_pair.replace(':', '_').lower()
    zbcom_pull_date_start = (pd.to_datetime(pull_date) - pd.Timedelta(
        '30 days')).value // 10 ** 6
    url = (
        f'https://api.zb.com/data/v1/kline'
        f'?market={zbcom_ccy_pair}&since={zbcom_pull_date_start}'
        f'&type={zbcom_granul}')
    print(url)
    try:
        r = requests.get(url, timeout=5)
        zbcom_df = pd.DataFrame(r.json()['data'])
        zbcom_df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
        zbcom_df['dtime'] = pd.to_datetime(zbcom_df['time'].astype('int64'),
                                           unit='ms')
        zbcom_df.set_index('dtime', inplace=True)
        zbcom_df.sort_index(ascending=True, inplace=True)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(e)
        zbcom_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        zbcom_df.insert(0, 'Currencypair', ccy_pair)

    return zbcom_df


def pull_data_bithumb(ccy_pair, granul, pull_date='2026-06-30'):
    """
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    if granul in (1, 24):
        bithumb_granul = str(granul) + 'h'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    bithumb_ccy_pair = ccy_pair.replace(':', '_')
    url = f'https://api.bithumb.com/public/candlestick' \
          f'/{bithumb_ccy_pair}/{bithumb_granul}'
    print(url)
    try:
        r = requests.get(url, timeout=5)
        bithumb_df = pd.DataFrame(r.json()['data'])
        bithumb_df.columns = ['time', 'close', 'open', 'high', 'low', 'volume']
        bithumb_df['dtime'] = pd.to_datetime(bithumb_df['time'].astype('int64'),
                                             unit='ms')
        bithumb_df.set_index('dtime', inplace=True)
        bithumb_df.sort_index(ascending=True, inplace=True)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(e)
        bithumb_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        bithumb_df.insert(0, 'Currencypair', ccy_pair)

    return bithumb_df


def pull_data_upbit(ccy_pair, granul, pull_date='2026-06-30'):
    """
    :param ccy_pair:
    :param granul:
    :param pull_date
    :return:
    """
    if granul == 1:
        upbit_granul = 'minutes/60'
    elif granul == 24:
        upbit_granul = 'days'
    else:
        raise KeyError('invalid granul value, must be either 1 or 24')
    upbit_ccy_pair = ccy_pair.split(':')
    upbit_ccy_pair.reverse()
    upbit_ccy_pair = '-'.join(upbit_ccy_pair)
    upbit_pull_date_end = (
            pd.to_datetime(pull_date) + pd.Timedelta('1 day')).strftime(
        '%Y-%m-%dT%H:%M:%SZ')
    url = (f'https://api.upbit.com/v1/candles/minutes/60'
           f'?market={upbit_ccy_pair}&count=200&to={upbit_pull_date_end}')
    print(url)
    try:
        r = requests.get(url, timeout=5)
        upbit_df = pd.DataFrame(r.json())
        upbit_df = upbit_df[[
            'candle_date_time_utc', 'trade_price', 'opening_price',
            'high_price', 'low_price',
            'candle_acc_trade_volume']]
        upbit_df.columns = ['time', 'close', 'open', 'high', 'low', 'volume']
        upbit_df['dtime'] = pd.to_datetime(upbit_df['time'])
        upbit_df.set_index('dtime', inplace=True)
        upbit_df.sort_index(ascending=True, inplace=True)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(e)
        upbit_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        upbit_df.insert(0, 'Currencypair', ccy_pair)

    return upbit_df


def pull_data_mexc(ccy_pair, granul, pull_date='2026-06-30'):
    """
    :param ccy_pair:
    :param granul:
    :param pull_date:
    :return:
    """
    mexc_CCY_pair = ccy_pair.replace(':', '')
    if granul == 1:
        mexc_granul = '60m'
    elif granul == 24:
        mexc_granul = '1d'
    mexc_pull_date_start = pd.to_datetime(pull_date).value // 10 ** 6
    mexc_pull_date_end = (pd.to_datetime(pull_date) + pd.Timedelta(
        '1 day')).value // 10 ** 6
    mrkt_url = 'https://api.mexc.com/api/v3/klines'
    try:
        r = requests.get(url=mrkt_url,
                         params={'symbol': mexc_CCY_pair,
                                 'interval': mexc_granul,
                                 'endTime': mexc_pull_date_end,
                                 'startTime': mexc_pull_date_start})
        print(mrkt_url)
        r_json = r.json()
        data_mexc = pd.DataFrame(r_json)
        data_mexc.columns = ['time', 'open', 'high', 'low', 'close', 'volume',
                             'close time', 'quote volume']
        # actual order: open high low close
        data_mexc = data_mexc[
            ['time', 'open', 'close', 'high', 'low', 'volume']]
        data_mexc['dtime'] = pd.to_datetime(data_mexc['time'] * 10 ** 6)
        data_mexc.set_index('dtime', inplace=True)
        data_mexc.sort_index(ascending=True, inplace=True)
    except (json.JSONDecodeError, ValueError) as e:
        print(e)
        print(input_ccy_pair)
        print(r.text)

        data_mexc = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        data_mexc.insert(0, 'Currencypair', ccy_pair)
    return data_mexc


def pull_data_bullish(ccy_pair, granul, pull_date='2026-06-30'):
    bullish_ccy_pair = ccy_pair.replace(':', '')
    if granul == 1:
        bullish_granul = '1h'
    elif granul == 24:
        bullish_granul = '1d'
    bullish_pull_date_start = pd.to_datetime(pull_date).isoformat(
        timespec='milliseconds') + 'Z'
    bullish_pull_date_end = (pd.to_datetime(pull_date) + pd.Timedelta(
        '1 day')).isoformat(timespec='milliseconds') + 'Z'
    mrkt_url = 'https://api.exchange.bullish.com/trading-api/v1/markets/' \
               + bullish_ccy_pair + '/candle'
    try:
        responses = requests.get(
            url=mrkt_url,
            params={
                'createdAtDatetime[gte]': bullish_pull_date_start,
                'createdAtDatetime[lte]': bullish_pull_date_end,
                'timeBucket': bullish_granul})
        print(responses.url)
        data_bullish = pd.DataFrame(responses.json())
        # data_bullish.columns =
        # ['open', 'dtime', 'time', 'high', 'low', 'close', 'volume']
        data_bullish.rename(columns={'createdAtDatetime': 'time',
                                     'createdAtTimestamp': 'dtime'},
                            inplace=True)
        data_bullish['dtime'] = pd.to_datetime(
            data_bullish['time']).dt.tz_localize(None)
        data_bullish.set_index('dtime', inplace=True)
        data_bullish.sort_index(ascending=True, inplace=True)
    except (json.JSONDecodeError, ValueError) as e:
        print(e)
        data_bullish = pd.DataFrame(0,
                                    columns=['time', 'open', 'high', 'low',
                                             'close', 'volume'])
    finally:
        data_bullish.insert(0, 'Currencypair', ccy_pair)
    return data_bullish



def pull_data_deribit(ccy_pair, granul, pull_date='2026-06-30'):
    request_end_time = pd.to_datetime(pull_date) + pd.Timedelta('1 day')
    request_start_time = (request_end_time
                          - pd.Timedelta(199, unit='hours')
                          ).value // 10 ** 6
    request_end_time = request_end_time.value // 10 ** 6
    request_ccy_pair = ccy_pair.replace(":", "_")
    if granul == 1:
        request_granul = 60
    elif granul == 24:
        request_granul = "1D"
    else:
        raise KeyError("only 1 and 24 are acceptable value for granul")
    url = (f'https://www.deribit.com/api/v2/public/get_tradingview_chart_data'
           f'?instrument_name={request_ccy_pair}'
           f'&resolution={request_granul}'
           f'&start_timestamp={request_start_time}'
           f'&end_timestamp={request_end_time}'
           )
    try:
        print(url)
        r = requests.get(url, timeout=5)
        data = r.json()['result']
        candle_df = pd.DataFrame(data)
        candle_df.rename(columns={'ticks': 'time'}, inplace=True)
        candle_df.drop(columns='status', inplace=True)
        candle_df['dtime'] = pd.to_datetime(
            candle_df['time'].astype('int64'), unit='ms')
        candle_df.set_index('dtime', inplace=True)
        candle_df.sort_index(ascending=True, inplace=True)
    except (ValueError, KeyError, requests.exceptions.RequestException) as e:
        print(e)
        candle_df = pd.DataFrame(
            columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    finally:
        candle_df.insert(0, 'Currencypair', ccy_pair)
    return candle_df


def pull_data(currencypairs, granul, exchanges, pull_date, to_csv=True,
              name_csv='ExchangesData'):
    """
    Function to pull data fromm various exchanges
    :param currencypairs: list of currency pairs to retrieve data.
    Each currency pair is in FOR:DOM format (e.g. BTC:USD).
    :param granul:
    :param exchanges:
    :param to_csv
    :param name_csv
    :return:
    """

    # initialize dataframe per exchange
    exchange_df = list()

    # Pulling data very every ccypair and exchange and concatenating
    # into DF by exchange
    for exchange in exchanges:
        for currencypair in currencypairs:
            tries = 0
            while tries <= 2:
                try:
                    func = f'pull_data_{exchange}(ccy_pair="{currencypair}",' \
                           f' granul={granul}, pull_date="{pull_date}")'
                    print(func)
                    exchange_ccy_df = eval(func)
                    exchange_ccy_df['exchange'] = exchange
                    print(exchange_ccy_df.head())
                    print(
                        f'Data request for exchange {exchange}, '
                        f'ticker {currencypair} on {pull_date} done')
                except (requests.RequestException, Exception) as e:
                    print(e)
                finally:
                    time.sleep(1.5)
                tries += 1
                print(f'code executed for {tries} try/tries.')
                if exchange_ccy_df is not None:
                    if exchange_ccy_df.shape[0] > 0:
                        exchange_df.append(exchange_ccy_df)
                        break

    exchange_df = pd.concat(exchange_df).drop_duplicates()
    if to_csv:
        output_path = Path(__file__).parents[
                          2] / 'output' / 'ExchangeDD' / pull_date
        if not output_path.exists():
            output_path.mkdir()
        output_file = (
                output_path
                / f'{name_csv}_{pull_date.replace("-", "")}'
                  f'{"_" + exchanges[0] if len(exchanges) == 1 else ""}'
                  f'_{pd.Timestamp.today().strftime("%Y%m%d")}.csv')
    exchange_df.to_csv(output_file)
    print(f'csv output saved as {output_file}')

    return exchange_df


"""
Constants
"""
granularity = 1  # duration between 2 samples in hours.
val_date = '2026-06-30'
exchanges = [
    'binance', 'binance.us', 'bitbank', 'bitfinex', 'bitflyer',
    'bitstamp', 'cex.io', 'coinbase',
    'gate.io', 'gemini', 'itbit', 'kraken', 'poloniex',
    'bibox', 'bitmex', 'bybit',
    'crypto.com', 'hitbtc', 'huobi', 'kucoin', 'lbank', 'liquid',
    'okex', 'therocktrading', 'zb.com',
     'bithumb', 'upbit', 'mexc','bitget', 'hyperliquid', 'bullish', 'deribit']
# exchanges_func_input = [
#      'binance', 'binanceus', 'bitbank', 'bitfinex', 'bitstamp', 'cexio',
#      'coinbase', 'gateio', 'gemini', 'kraken', 'poloniex', 'bibox', 'bitmex',
#      'bybit', 'cryptocom', 'hitbtc', 'huobi', 'kucoin', 'lbank', 'liquid',
#      'okex', 'therocktrading', 'zbcom', 'bithumb', 'upbit', 'bitget', 'hyperliquid', 'mexc', 'bullish',
#      'deribit']
exchanges_func_input = ['hyperliquid']
# ccy_pairs = ['AAVE:EUR','AAVE:GBP','AAVE:USD','ADA:EUR','ADA:USDT','APT:EUR','APT:USD','ATOM:EUR','ATOM:GBP',
#              'ATOM:USD','ATOM:USDT','AVAX:EUR','AVAX:USD','AVAX:USDT','BCH:EUR','BCH:GBP','BCH:JPY','BCH:USD',
#              'BCH:USDT','BNB:EUR','BNB:USD','BNB:USDT','BTC:EUR','BTC:GBP','BTC:JPY','BTC:USD','BTC:USDT','CRO:EUR',
#              'CRO:USD','CRO:USDT','DOGE:EUR','DOGE:GBP','DOGE:USD','DOGE:USDT','DOT:JPY','DOT:USD','DOT:USDT','ETC:EUR',
#              'ETC:USD','ETH:EUR','ETH:GBP','ETH:JPY','ETH:USD','ETH:USDT','HYPE:EUR','HYPE:USD','LINK:EUR','LINK:JPY',
#              'LINK:USD','LINK:USDT','LTC:EUR','LTC:GBP','LTC:JPY','LTC:USD','LTC:USDT','MNT:EUR','MNT:USD','PAXG:EUR',
#              'PAXG:USD','SHIB:EUR','SHIB:USD','SHIB:USDT','SOL:EUR','SOL:GBP','SOL:USD','SOL:USDT','SUI:EUR','SUI:GBP',
#              'SUI:USD','TRX:EUR','TRX:USD','UNI:USD','USDC:EUR','USDC:GBP','USDC:USD','USDC:USDT','USDE:USDT','USDT:EUR',
#              'USDT:GBP','USDT:JPY','USDT:USD','VVV:EUR','VVV:USD','XLM:EUR','XLM:GBP','XLM:USD','XMR:EUR','XMR:USD',
#              'XMR:USDT','XRP:EUR','XRP:GBP','XRP:USD','XRP:USDT','ZEC:EUR','ZEC:USD'
#
# ]
ccy_pairs = ['HYPE:EUR']

print(Path.cwd())

"""
Execution
"""
df = pull_data(ccy_pairs, granularity, exchanges_func_input, val_date,
               to_csv=True,
               name_csv='ExchangeData')
