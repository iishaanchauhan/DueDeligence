import pandas as pd
import itertools
import numpy as np
import requests.exceptions


# def check_time_range(test_time, min_time, max_time):
#     """
#     Check whether 10 days prior to test_time and test_time are within the
#     range of min_time and max_time
#     :param test_time: time to be check it is in range
#     :param min_time: lower bound of the range
#     :param max_time: upper bound of the range
#     :return: Boolean, True if in range, False if outside range
#     """
#     offset_back = 10
#     offset_forward = 1
#     if (test_time - pd.DateOffset(offset_back) > min_time).bool() and (
#             test_time + pd.DateOffset(offset_forward) < max_time).bool():
#         return True
#     else:
#         return False


def scope_check(
        client_key, val_date='2022-09-30', exchanges=None, quote_ccys=None,
        export=True, values=False,
        lookback_period=10, granul='1m'):
    """
    Find all markets with available minutia data in CoinMetrics with optional
    constraint on exchanges and quote currencies to include.

    TODO: add diagnostic columns for each market (if 10 days vol check passed,
        first candle snapshot with data on val date)
    TODO: add diagnostic columns

    :param client_key: an instance of CoinMetrics API client class.
    :param val_date: valuation date
    :param exchanges: list of (reliable) exchanges to constraint the scope
    :param quote_ccys: list of (fiat) currencies to include as eligible quote
        currency
    :param lookback_period: how many days into the past should the daily volume
        be extracted
    :param granul: the candle frequency. Possible values are: '1m', '1h', '1d'.
        Default to be '1m'
    :return: a table of all markets with available minutia data in CoinMetrics
        with optional constraint on exchanges and quote currencies to
        include.

    Table columns:
        - market: market name in CoinMetrics format (e.g. coinbase-btc-usd-spot,
        - frequency: frequency of market data (e.g. 1m, 1h, etc.),
        - min_time: timestamp of the first trade,
        - max_time: timestamp of the most recent trade when this function
          is called,
        - exchange: name of exchange,
        - base: name of the crypto,
        - quote: name of the quoting currency,
        - market_type: type of market (spot, future, option),
        - full_name: full name of the crypto,
    """
    all_assets = client_key.catalog_market_candles(
        quote=None,
        market_type="spot").to_dataframe()
    all_assets['min_time'] = pd.to_datetime(all_assets['min_time'])
    all_assets['max_time'] = pd.to_datetime(all_assets['max_time'])
    all_assets = all_assets[(all_assets.frequency == granul)
                            & (all_assets.min_time <= pd.to_datetime(
        val_date).tz_localize('UTC')
                               - pd.Timedelta(f'{lookback_period} days')
                               )
                            & (all_assets.max_time >= pd.to_datetime(
        val_date).tz_localize('UTC')
                               + pd.Timedelta('1 day')
                               )
                            ]
    all_assets[['exchange', 'base', 'quote',
                'market_type']] = all_assets.market.str.split('-', expand=True)
    asset_names = client_key.catalog_assets().to_dataframe()
    all_assets = (
        all_assets.merge(asset_names[['full_name', 'asset']], left_on='base',
                         right_on='asset', how='left'))
    all_assets.drop('asset', axis=1, inplace=True)

    if exchanges is not None:
        print('exchange not None')
        # if there is constraint on exchange
        exchanges_df = pd.DataFrame(exchanges,
                                    columns=['exchange']).drop_duplicates()
        all_assets = pd.merge(all_assets, exchanges_df, on='exchange',
                              how='inner')

    if quote_ccys is not None:
        print('quuote_ccys not None')
        # if there is constraint on base currency
        quote_ccys_df = pd.DataFrame(quote_ccys,
                                     columns=['quote']).drop_duplicates()
        all_assets = pd.merge(all_assets, quote_ccys_df, on='quote',
                              how='inner')
    #
    # except ValueError as e:
    #     print(e)
    return all_assets


def get_avail_markets(exchanges_to_process, assets_to_process,
                      client_key, valuation_date, lookback_period=10,
                      asset_ccy=None, market_type='spot', quoted=None,
                      granul='1m'):
    """
    Request for all submitted exchanges and assets whether minutely market
    data candles are available.

    :param exchanges_to_process: list of exchanges as strings
    :param assets_to_process: Dataframe of assets as strings (Coinmetrics
        tickers) and fullname of the assets
    :param asset_ccy: dataframe of asset and their major trading currency across
        all reliable exchanges (if there are market restriction, calculate
        the table in Excel before feeding it into this function)
    :param client_key: Coinmetrics access key as string
    :param valuation_date: the valuation date to check market availability
    :param lookback_period: how many days into the past should the trading
        availability be checked
    :param market_type: spot or future market. Default spot
    :param quoted: denominating currency. Default usd
    :param granul: sampling frequency. Default 1m, can be 1h or 1d

    :return: Dataframe of all available markets, and dataframe with strings of
    not available markets
    """
    if quoted is None:
        quoted = ['usd']
    all_markets = client_key.catalog_full_market_candles(
        market_type='spot').to_dataframe()

    query_markets = pd.DataFrame(
        [list(i) + [('-'.join(i))] for i in
         itertools.product(exchanges_to_process,
                           assets_to_process['asset'].to_list(),
                           quoted,
                           ['spot'])],
        columns=['exchange', 'asset', 'ccy', 'market type', 'market'])
    query_markets = (query_markets
                     .merge(all_markets[all_markets['frequency'] == granul],
                            how='inner', on='market')
                     .merge(assets_to_process, how='inner', on='asset'))
    query_markets = query_markets[
        (
                query_markets['min_time'].dt.tz_localize(
                    None) <= pd.to_datetime(valuation_date)
                - pd.Timedelta(lookback_period, unit='day'))
        & (
                query_markets['max_time'].dt.tz_localize(
                    None) >= pd.to_datetime(valuation_date)
                + pd.Timedelta(1, unit='day'))]
    query_markets.drop('market type', axis=1, inplace=True)
    return query_markets


def request_data(market, val_date, client_key, granul='1m', lookback_price=0,
                 lookback_volume=10,
                 vol_hist=False):
    """
    :param market:
    :param val_date:
    :param client_key:
    :param granul:
    :param lookback_price:
    :param lookback_volume:
    :param vol_hist:
    :return:
    """
    start_minute_vol = (
        (pd.to_datetime(val_date) - pd.offsets.DateOffset(
            lookback_volume)).strftime('%Y-%m-%dT%H:%M:%S'))
    start_minute_price = (
        (pd.to_datetime(val_date) - pd.offsets.DateOffset(
            lookback_price)).strftime('%Y-%m-%dT%H:%M:%S'))
    end_minute = val_date + 'T24:00:00'
    df_foo = client_key.get_market_candles(
        markets=market,
        frequency=granul,
        start_time=start_minute_price,
        end_time=end_minute).to_dataframe().sort_values(
        'time')
    df_foo2 = client_key.get_market_candles(
        markets=market,
        frequency='1d',
        start_time=start_minute_vol,
        end_time=end_minute,
        end_inclusive=False).to_dataframe().sort_values(
        'time')
    df_foo3 = client_key.get_market_quotes(
        markets=market,
        start_time=start_minute_price,
        end_time=end_minute,
        granularity='1h').to_dataframe()
    pivot_cols = ['volume', 'candle_trades_count']
    pivot_col_names = (['volume_1d_T' + str(lag) for lag in
                        range(-lookback_volume, 1)] +
                       ['tradescount_1d_T' + str(lag) for lag in
                        range(-lookback_volume, 1)])

    if vol_hist:
        df_foo2 = df_foo2.pivot(index='market', columns='time',
                                values=pivot_cols)
        df_foo2.columns = pivot_col_names
        if df_foo3.shape[0] != 0:
            df_foo3.loc[
                (df_foo3['time'].dt.minute != 0) | (
                        df_foo3['time'].dt.second != 0),
                ['bid_price', 'ask_price']] = pd.NA
            df_foo = (df_foo
                      .merge(
                df_foo3[['market', 'time', 'bid_price', 'ask_price']],
                how='left', on=['market', 'time'])
                      .merge(df_foo2, how='left', on='market'))
        else:
            df_foo = df_foo.merge(df_foo2, how='left', on='market')
            df_foo[['bid_price', 'ask_price']] = pd.NA

        df_foo.rename(
            columns={'market_x': 'market', 'volume_1d_T0': 'volume_1d',
                     'tradescount_1d_T0': 'tradescount_1d'},
            inplace=True)
        df_foo.drop(['vwap'], axis=1, inplace=True)

    else:
        if df_foo3.shape[0] != 0:
            df_foo = (df_foo
                      .merge(
                df_foo3[['market', 'time', 'bid_price', 'ask_price']],
                how='left', on=['market', 'time'])
                      .merge(df_foo2[['market', 'time', 'volume']], how='left',
                             left_on=['market', df_foo['time'].dt.floor('D')],
                             right_on=['market', df_foo2['time']]))
            df_foo.rename(
                columns={'market_x': 'market', 'volume_y': 'volume_1d',
                         'time_x': 'time'}, inplace=True)
        else:
            df_foo = (df_foo
                      .merge(df_foo2[['market', 'time', 'volume']], how='left',
                             left_on=['market', df_foo['time'].dt.floor('D')],
                             right_on=['market', df_foo2['time']]))
            df_foo.rename(
                columns={'market_x': 'market', 'volume_y': 'volume_1d',
                         'time_x': 'time'}, inplace=True)

    df_foo.sort_values(['market', 'time'], inplace=True)
    return df_foo


def get_markets_data(markets, val_date: str, client_key, granul='1m',
                     lookback_price=0, lookback_volume=10,
                     vol_hist=False):
    """
    Function to request minutely market candle data for all submitted markets as
    of valuation date

    :param markets: dataframe of markets as strings to be requested (in
        Coinmetrics format, e.g. 'coinbase-btc-usd-spot' must be an output
        of a function call to scope_check
    :param val_date:
    :param client_key: Coinmetrics client object
    :param granul: sampling frequency. Default '1m', can be '1h' or '1d'
    :param lookback_price: how many days in the past should the price history be
        downloaded
    :param lookback_volume: how many days in the past should the daily trading
        volume be downloaded
    :param vol_hist: whether should the historical daily trading volume be
        pivoted. If False, return long table format with only 1 column for
        daily trading volume. If True, return a wide table format with
        several columns for prev days' trading volume. lookback_price must
        be 0 in this case

    :return: Dataframe with all data
    """
    df_list = []
    markets.rename({'full_name': 'fullname'}, axis=1, inplace=True)
    if (vol_hist is True) and (lookback_price > 0):
        raise KeyError('can not download past prices if table format is wide')
    else:
        for chunk in np.array_split(markets.index, markets.shape[0] // 3 + 1):
            try:
                tries = 0
                while tries <= 2:
                    candle_sub_df = request_data(
                        market=markets.loc[chunk, 'market'].to_list(),
                        val_date=val_date,
                        client_key=client_key, granul=granul,
                        lookback_price=lookback_price,
                        lookback_volume=lookback_volume,
                        vol_hist=vol_hist)
                    tries += 1
                    if candle_sub_df.shape[0] > 0:
                        print(
                            'Market data of {0} for {1} day(s) before {2} '
                            'was downloaded'
                            .format(markets.loc[chunk, 'market'].to_list(),
                                    lookback_price, val_date))
                        break
                    if tries > 2:
                        print(
                            'Warning: Market data of {0} for {1} day(s) '
                            'before {2} was not downloaded'
                            .format(markets.loc[chunk, 'market'].to_list(),
                                    lookback_price, val_date))
                        break
                df_list.append(candle_sub_df)
            except (KeyError, ValueError, requests.exceptions.HTTPError) as e:
                print(e)
                pass
        df = pd.concat(df_list)
        df = df.merge(markets[['market', 'fullname']], on='market')
        df['val_date'] = val_date
    return df


def vol_stats(client_key, markets, val_date, lookback_volume=10):
    """
    Return daily trade volume

    :param markets: list of markets to request data in Coinmetrics format, e.g.
        'coinbase-btc-usd-spot'
    :param val_date: valuation date
    :param client_key: coinmetrics API key
    :param lookback_volume: how many days in the past should the daily trading
        volume be downloaded
    :return:
    """
    start_minute_vol = (
        (pd.to_datetime(val_date) - pd.offsets.DateOffset(
            lookback_volume)).strftime('%Y-%m-%dT%H:%M:%S'))
    end_minute = (
        (pd.to_datetime(val_date) + pd.offsets.DateOffset(1)).strftime(
            '%Y-%m-%dT%H:%M:%S'))
    try:
        df_foo = client_key.get_market_candles(
            markets=markets,
            frequency='1d',
            start_time=start_minute_vol,
            end_time=end_minute,
            end_inclusive=False).to_dataframe().sort_values(
            'time')
        print(
            'Volume statistics for {0} on {1} day(s) before {2} was downloaded'
            .format(markets, lookback_volume, val_date))
    except (KeyError, ValueError) as e:
        print(e)
        print(
            'Volume statistics for {0} on {1} day(s) before {2} was '
            'not downloaded'
            .format(markets, lookback_volume, val_date))
    pass
    return df_foo
