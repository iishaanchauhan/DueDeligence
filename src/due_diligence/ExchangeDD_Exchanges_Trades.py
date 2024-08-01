"""
Functions
"""
import json
# Import of all required packages
from pathlib import Path
import time
import pandas as pd
import requests
import io
from coinmetrics.api_client import CoinMetricsClient

client = CoinMetricsClient('zzHnUvjMgthSKDZuZOUb')


def pull_trades_cexio(ccy_pair, end_time='2023-08-01T00:00:00',
                      timeframe='1 hour'):
    """

    :param ccy_pair:
    :param end_time:
    :param start_date:
    :return:
    """
    input_ccy_pair = ccy_pair.replace(':', '/')
    cm_markets = 'coinbase-' + ccy_pair.replace(':', '-').lower() + '-spot'
    last_trade_cm = client.get_market_trades(
        cm_markets,
        start_time=(pd.to_datetime(end_time) - pd.Timedelta(
            timeframe)).isoformat(),
        limit_per_market=1,
        paging_from='start',
        start_inclusive=True).to_dataframe()
    last_cm_id = last_trade_cm.loc[
                     last_trade_cm.index[-1], 'coin_metrics_id'] - 1
    output_list = []
    try:
        while True:
            url = f'https://cex.io/api/trade_history/{input_ccy_pair}&since={last_cm_id}'
            print(url)
            r = requests.get(url)
            cexio_df = pd.DataFrame(r.json())
            cexio_df.rename(
                columns={'type': 'type', 'date': 'time', 'amount': 'amount',
                         'tid': 'UID'}, inplace=True)
            cexio_df['dtime'] = pd.to_datetime(cexio_df['time'].astype('int64'),
                                               unit='s')
    except (json.JSONDecodeError, ValueError, requests) as e:
        print(e)
    finally:
        cexio_df.insert(0, 'Currencypair', ccy_pair)
    return cexio_df


def pull_trades_coinbase(ccy_pair, end_time='2023-08-01T00:00:00',
                         timeframe='1 hour', client=client):
    """
    function to pull trade history from coimbase
    :param ccy_pair:
    :param end_date:
    :param start_date:
    :param client: CoinMetrics client, default to the globally defined one
    :return:
    """
    input_ccy_pair = ccy_pair.replace(':', '-')
    input_start_time = pd.to_datetime(end_time) - pd.Timedelta(timeframe)
    cm_markets = 'coinbase-' + input_ccy_pair.lower() + '-spot'
    cm_trades = client.get_market_trades(
        cm_markets,
        end_time=pd.to_datetime(end_time),
        paging_from='end',
        limit_per_market=1,
        end_inclusive=False
    ).to_dataframe()
    last_trade_id = cm_trades.loc[0, 'coin_metrics_id'] + 1
    output_list = []
    while True:
        try:
            url = (f'https://api.exchange.coinbase.com/products/'
                   f'{input_ccy_pair}/trades?after={last_trade_id}'
                   f'&limit={1000}')
            print(url)
            r = requests.get(url)
            output_sub_df = pd.DataFrame(r.json())
            output_sub_df.rename(
                columns={'trade_id': 'UID', 'side': 'type', 'size': 'amount',
                         'time': 'time'},
                inplace=True)
            output_sub_df['dtime'] = pd.to_datetime(
                output_sub_df['time']).dt.tz_localize(None)
            output_list.append(output_sub_df)
            last_trade_id = output_sub_df.iloc[-1, 0]
            last_trade_timestamp = output_sub_df
        except (
                json.JSONDecodeError, ValueError,
                requests.exceptions.HTTPError) as e:
            print(e)
        if last_trade_timestamp <= input_start_time:
            break
    output_df = pd.concat(output_list)
    output_df.insert(0, 'Currencypair', ccy_pair)

    return output_df


def pull_trades_gateio(ccy_pair, end_time='2023-08-01T00:00:00',
                       timeframe='1 hour'):
    """
    function to pull trade history from gate.io
    :param ccy_pair:
    :param end_date:
    :param start_date:
    :return:
    """
    input_ccy_pair = ccy_pair.replace(':', '_')
    input_end_timestamp = (
            pd.to_datetime(end_time) - pd.Timedelta('1 day')).strftime(
        '%Y%m')
    url = f'https://download.gatedata.org/spot/deals/' \
          f'{input_end_timestamp}/{input_ccy_pair}-{input_end_timestamp}.csv.gz'
    try:
        print(url)
        r = requests.get(url)
        output_df = pd.read_csv(io.BytesIO(r.content), compression='gzip')
        output_df.columns = ['time', 'UID', 'price', 'amount', 'type']
        output_df['dtime'] = pd.to_datetime(output_df['time'].astype('float64'),
                                            unit='s').dt.tz_localize(None)
    except (json.JSONDecodeError, ValueError) as e:
        print(e)
    finally:
        output_df.insert(0, 'Currencypair', ccy_pair)
        output_df = output_df.iloc[-1000:, :]
    return output_df


def pull_trades_cryptocom(ccy_pair, end_time='2023-08-01T00:00:00',
                          timeframe='1 hour'):
    """

    :param ccy_pair:
    :param end_date:
    :param start_date:
    :return:
    """
    input_ccy_pair = ccy_pair.replace(':', '_')
    input_end_time = pd.to_datetime(end_time).value // 10 ** 6
    input_start_time = (pd.to_datetime(end_time) - pd.Timedelta(
        timeframe)).value // 10 ** 6
    output_list = []
    try:
        while True:
            url = (f'https://api.crypto.com/exchange/v1/public/get-trades?'
                   f'end_ts={input_end_time}&instrument_name={input_ccy_pair}')
            print(url)
            r = requests.get(url)
            output_sub_df = pd.DataFrame(r.json()['result']['data'])
            output_sub_df.rename(
                columns={'s': 'type', 'p': 'price', 'q': 'amount', 't': 'time',
                         'd': 'UID'},
                inplace=True)
            output_sub_df.drop(columns=['i'], inplace=True)
            output_sub_df['dtime'] = pd.to_datetime(
                output_sub_df['time'].astype('int64'), unit='ms')
            output_list.append(output_sub_df)
            input_end_time = int(
                output_sub_df.loc[output_sub_df.index[-1], 'time'])
            time.sleep(1)
            if input_end_time <= input_start_time:
                break
    except(
            ValueError, json.JSONDecodeError,
            requests.exceptions.HTTPError) as e:
        print(e)
    finally:
        output_df = pd.concat(output_list)
        output_df.drop_duplicates(inplace=True)
        output_df.insert(0, 'Currencypair', ccy_pair)
    return output_df


def pull_trades_bitflyer(ccy_pair, end_time='2023-08-01T00:00:00',
                         timeframe='1 hour', client=client):
    """

    :param ccy_pair:
    :param end_time:
    :param timeframe:
    :param client
    :return:
    """
    input_ccy_pair = ccy_pair.replace(":", "_")
    cm_markets = 'bitflyer-' + ccy_pair.replace(':', '-').lower() + '-spot'
    input_start_time = pd.to_datetime(end_time) - pd.Timedelta(timeframe)
    last_trade_cm = client.get_market_trades(
        cm_markets,
        end_time=pd.to_datetime(end_time),
        paging_from='end',
        limit_per_market=1,
        end_inclusive=False
    ).to_dataframe()
    last_trade_id = last_trade_cm.loc[0, 'coin_metrics_id'] + 1
    output_df_list = []
    while True:
        try:
            url = f'https://api.bitflyer.com/v1/getexecutions?' \
                  f'product_code={input_ccy_pair}&before={last_trade_id}'
            print(url)
            r = requests.get(url)
            output_sub_df = pd.DataFrame(r.json())
            output_sub_df.rename(
                columns={'id': 'UID', 'side': 'type', 'size': 'amount',
                         'exec_date': 'time'}, inplace=True)
            output_sub_df = output_sub_df[
                ['UID', 'type', 'amount', 'price', 'time']]
            output_sub_df['dtime'] = pd.to_datetime(output_sub_df['time'],
                                                    format='mixed')
            last_trade_id = output_sub_df.loc[output_sub_df.index[-1], 'UID']
            last_trade_timestamp = output_sub_df.loc[
                output_sub_df.index[-1], 'dtime'].tz_localize(None)

            output_df_list.append(output_sub_df)
            time.sleep(1)
        except (
                json.JSONDecodeError, ValueError,
                requests.exceptions.HTTPError) as e:
            print(e)
        if last_trade_timestamp <= input_start_time:
            break

    output_df = pd.concat(output_df_list)
    output_df.insert(0, 'Currencypair', ccy_pair)
    return output_df


def pull_trades_bullish(ccy_pair, end_time='2023-08-01T00:00:00',
                        timeframe='1 hour', client=client):
    """

    :param ccy_pair:
    :param end_time:
    :param timeframe:
    :param client:
    :return:
    """
    input_ccy_pair = ccy_pair.replace(":", "")
    url = f'https://api.exchange.bullish.com/trading-api/v1/history/markets/{input_ccy_pair}/trades'
    print(url)
    try:
        r = requests.get(url)
        output_df = pd.DataFrame(r.json())
        output_df.rename(
            columns={
                'tradeId': 'UID', 'quantity': 'amount', 'side': 'type',
                'createdAtTimestamp': 'time', 'createdAtDatetime': 'dtime'},
            inplace=True
        )
        output_df = output_df[
            ['UID', 'amount', 'price', 'type', 'time', 'dtime']]
        output_df['dtime'] = pd.to_datetime(output_df['dtime'],
                                            format='mixed').dt.tz_localize(None)
    except (
            json.JSONDecodeError, ValueError,
            requests.exceptions.HTTPError) as e:
        print(e)
    finally:
        output_df.insert(0, 'Currencypair', ccy_pair)

    return output_df


def pull_trades_itbit(ccy_pair, end_time='2023-08-01T00:00:00',
                      timeframe='1 hour', client=client):
    """

    :param ccy_pair:
    :param end_time:
    :param timeframe:
    :param client:
    :return:
    """
    input_ccy_pair = ccy_pair.replace(':', '')
    url = f'https://api.paxos.com/v2/markets/{input_ccy_pair}/recent-executions'
    try:
        r = requests.get(url)
        output_df = pd.DataFrame(r.json()['items'])
        output_df.rename(columns={'match_number': 'UID', 'executed_at': 'time'},
                         inplace=True)
        output_df['dtime'] = pd.to_datetime(output_df['time'],
                                            format='mixed').dt.tz_localize(None)
    except (
            json.JSONDecodeError, ValueError,
            requests.exceptions.HTTPError) as e:
        print(e)
    finally:
        output_df.insert(0, 'Currencypair', ccy_pair)
    return output_df


def pull_trades_lbank(ccy_pair, end_time='2023-08-01T00:00:00',
                      timeframe='1 hour', client=client):
    """

    :param ccy_pair:
    :param end_time:
    :param timeframe:
    :param client:
    :return:
    """
    input_ccy_pair = ccy_pair.replace(':', '_').lower()
    input_start_time = (pd.to_datetime(end_time) - pd.Timedelta(
        timeframe)).value // 10 ** 6
    input_end_dtime = pd.to_datetime(end_time)
    output_df_list = []
    while True:
        try:
            url = f'https://api.lbkex.com/v2/trades.do?' \
                  f'symbol={input_ccy_pair}&size=600&time={input_start_time}'
            print(url)
            r = requests.get(url)
            output_sub_df = pd.DataFrame(r.json()['data'])
            output_sub_df.rename(columns={'date_ms': 'time', 'tid': 'UID'},
                                 inplace=True)
            output_sub_df['dtime'] = pd.to_datetime(
                output_sub_df['time'].astype('int64'), unit='ms')
            output_df_list.append(output_sub_df)

            input_start_time = output_sub_df['time'].astype('int64').max()
            max_dtime = output_sub_df['dtime'].max()
            time.sleep(1)
        except (ValueError, KeyError, requests.exceptions.HTTPError) as e:
            print(e)
        if max_dtime >= input_end_dtime:
            break
    output_df = pd.concat(output_df_list)
    output_df.insert(0, 'Currencypair', ccy_pair)
    return output_df


def pull_trades(currencypairs, exchanges, pull_date='2022-08-01T00:00:00',
                timeframe='1 hour', to_csv=True,
                name_csv='ExchangesData'):
    """

    :param currencypairs:
    :param exchanges:
    :param pull_date:
    :param timeframe:
    :param to_csv:
    :param name_csv:
    :return:
    """

    # initialize dataframe per exchange
    exchange_df = list()
    # Pulling data for every ccypair and exchange and concatenating into DF by
    # exchange
    end_time = (pd.to_datetime(pull_date) + pd.Timedelta('1 day')).strftime(
        '%Y-%m-%d')
    for currencypair in currencypairs:
        for exchange in exchanges:
            tries = 0
            exchange_ccy_df = pd.DataFrame()
            while tries <= 2:
                try:
                    func = (f'pull_trades_{exchange}'
                            f'(ccy_pair="{currencypair}", end_time="{end_time}",'
                            f'timeframe="{timeframe}")')
                    print(func)
                    exchange_ccy_df = eval(func)
                    exchange_ccy_df['exchange'] = exchange
                    exchange_df.append(exchange_ccy_df)
                    print(exchange_ccy_df.head())
                    print(
                        f'Data request for exchange '
                        f'{exchange}, ticker {currencypair} done')
                except (requests.RequestException, Exception) as e:
                    print(e)
                finally:
                    time.sleep(1.5)
                tries += 1
                print(f'code executed for {tries} try/tries.')
                if exchange_ccy_df.shape[0] > 0:
                    break

    exchange_df = pd.concat(exchange_df)
    if to_csv:
        output_path = (
                Path(__file__).parents[2] / 'output' / 'ExchangeDD' /
                (pd.to_datetime(end_time) - pd.Timedelta(timeframe)).strftime(
                    '%Y-%m-%d'))
        if not output_path.exists():
            output_path.mkdir()
        output_file = (output_path
                       / f'{name_csv}_{pd.Timestamp.today().strftime("%Y%m%d")}.csv')
    exchange_df.to_csv(output_file, index=False)
    print(f'csv output saved as {output_file}')

    return exchange_df


"""
Constants
"""
exchanges = ['bitflyer', 'itbit']
exchanges_func_input = ['bitflyer', 'itbit']
ccy_pairs = [
    'ADA:USD', 'ADA:USDT', 'ADA:EUR', 'AR:USDT', 'ATOM:USD', 'ATOM:USDT',
    'ATOM:EUR', 'BCH:USD', 'BCH:USDT', 'BCH:EUR', 'BNB:USDT', 'BONK:USD',
    'BONK:USDT', 'BTC:JPY', 'BTC:USD', 'BTC:USDT', 'BTC:EUR', 'DAI:USD',
    'DAI:USDT', 'DOGE:USD', 'DOGE:USDT', 'DOGE:EUR', 'DOT:USD', 'DOT:USDT',
    'DOT:EUR', 'ETH:JPY', 'ETH:USD', 'ETH:USDT', 'ETH:EUR', 'IMX:USD',
    'IMX:USDT', 'INJ:USD', 'INJ:USDT', 'SOL:USD', 'SOL:USDT', 'SOL:EUR',
    'TON:USDT', 'USDC:USD', 'USDC:USDT', 'USDC:EUR', 'USDT:USD', 'USDT:EUR',
    'XMR:USDT', 'XRP:USD', 'XRP:USDT'
]
pull_date = '2024-07-31'
csv_timestamp = (
    pd.Timestamp.utcnow().tz_localize(None)
    .isoformat(timespec="hours")
    .replace(":", "").replace("-", "")
)
"""
Execution
"""
df = pull_trades(
    ccy_pairs, exchanges_func_input, pull_date=pull_date,
    timeframe='1 hour', to_csv=True,
    name_csv=f'ExchangeData_Trades_'
             f'{exchanges[0] if len(exchanges) == 1 else "exchanges"}'
             f'_{csv_timestamp}')
