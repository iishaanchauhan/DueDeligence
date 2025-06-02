import pandas as pd
import numpy as np
import requests.exceptions


def scope_check(
        client_key, val_date='2022-09-30', exchanges=None, quote_ccys=None,
        lookback_period=10, granul='1m'):
    """
    Find all markets with available minutia data in CoinMetrics with optional
    constraint on exchanges and quote currencies to include.

    :param client_key: an instance of the CoinMetrics API client class.
    :param val_date: the valuation date
    :param exchanges: a historical table of reliable exchanges with
        specified reliability period (from, until)
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
    all_assets = client_key.catalog_market_candles_v2(
        quote=None,
        market_type="spot").to_dataframe()
    all_assets['min_time'] = pd.to_datetime(all_assets['min_time'])
    all_assets['max_time'] = pd.to_datetime(all_assets['max_time'])
    all_assets = all_assets[
        (all_assets.frequency == granul)
        & (all_assets.min_time <=
           pd.to_datetime(val_date).tz_localize('UTC')
           - pd.Timedelta(f'{lookback_period} days')
           )
        & (all_assets.max_time >=
           pd.to_datetime(val_date).tz_localize('UTC')
           + pd.Timedelta('1 day')
           )
        ]

    all_assets[['exchange', 'base', 'quote',
                'market_type']] = all_assets.market.str.split('-', expand=True)
    asset_names = client_key.reference_data_assets().to_dataframe()
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
        (pd.to_datetime(val_date)
         - pd.offsets.DateOffset(lookback_volume))
        .strftime('%Y-%m-%dT%H:%M:%S'))
    start_minute_price = (
        (pd.to_datetime(val_date)
         - pd.offsets.DateOffset(lookback_price)
         - pd.offsets.DateOffset(hours=0)
         )
        .strftime('%Y-%m-%dT%H:%M:%S'))
    end_minute_volume = val_date + 'T24:00:00'
    end_minute_price = (
        (pd.to_datetime(val_date)
         + pd.offsets.DateOffset(days=1)
         + pd.offsets.DateOffset(hours=0)
         )
        .strftime('%Y-%m-%dT%H:%M:%S'))
    price_df = client_key.get_market_candles(
        markets=market,
        frequency=granul,
        start_time=start_minute_price,
        end_time=end_minute_price).to_dataframe().sort_values('time')
    vol_df = client_key.get_market_candles(
        markets=market,
        frequency='1d',
        start_time=start_minute_vol,
        end_time=end_minute_volume,
        end_inclusive=False).to_dataframe().sort_values('time')
    bidask_df = client_key.get_market_quotes(
        markets=market,
        start_time=start_minute_price,
        end_time=end_minute_price,
        granularity='1h').to_dataframe()
    pivot_cols = ['volume', 'candle_trades_count']
    pivot_col_names = (['volume_1d_T' + str(lag) for lag in
                        range(-lookback_volume, 1)] +
                       ['tradescount_1d_T' + str(lag) for lag in
                        range(-lookback_volume, 1)])

    if vol_hist:
        vol_df = vol_df.pivot(index='market', columns='time',
                              values=pivot_cols)
        vol_df.columns = pivot_col_names
        if bidask_df.shape[0] != 0:
            bidask_df.loc[
                (bidask_df['time'].dt.minute != 0) | (
                        bidask_df['time'].dt.second != 0),
                ['bid_price', 'ask_price']] = pd.NA
            price_df = (price_df
                        .merge(
                bidask_df[['market', 'time', 'bid_price', 'ask_price']],
                how='left', on=['market', 'time'])
                        .merge(vol_df, how='left', on='market'))
        else:
            price_df = price_df.merge(vol_df, how='left', on='market')
            price_df[['bid_price', 'ask_price']] = pd.NA

        price_df.rename(
            columns={'market_x': 'market', 'volume_1d_T0': 'volume_1d',
                     'tradescount_1d_T0': 'tradescount_1d'},
            inplace=True)
        price_df.drop(['vwap'], axis=1, inplace=True)

    else:
        if bidask_df.shape[0] != 0:
            price_df = (price_df
                        .merge(
                bidask_df[['market', 'time', 'bid_price', 'ask_price']],
                how='left', on=['market', 'time'])
                        .merge(vol_df[['market', 'time', 'volume']], how='left',
                               left_on=['market',
                                        price_df['time'].dt.floor('D')],
                               right_on=['market', vol_df['time']]))
            price_df.rename(
                columns={'market_x': 'market', 'volume_y': 'volume_1d',
                         'time_x': 'time'}, inplace=True)
        else:
            price_df = (price_df
                        .merge(vol_df[['market', 'time', 'volume']], how='left',
                               left_on=['market',
                                        price_df['time'].dt.floor('D')],
                               right_on=['market', vol_df['time']]))
            price_df.rename(
                columns={'market_x': 'market', 'volume_y': 'volume_1d',
                         'time_x': 'time'}, inplace=True)

    price_df.sort_values(['market', 'time'], inplace=True)
    return price_df


def get_market_data(
        markets, val_date, client_key, granul='1m',
        lookback_price=0, lookback_volume=10,
        vol_hist=False):
    """
    Function to request minutely market candle data for all submitted markets
        as of valuation date

    :param markets: dataframe of markets as strings to be requested (in
        Coinmetrics format, e.g. 'coinbase-btc-usd-spot' must be an output
        of a function call to scope_check
    :param val_date: the valuation date
    :param client_key: an instance of the CoinMetrics API client class.
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
                while True:
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
                            'was downloaded on the {3}-th try'
                            .format(
                                markets.loc[chunk, 'market'].to_list(),
                                lookback_price, val_date, tries))
                        df_list.append(candle_sub_df)
                        break
                    if tries > 10:
                        print(
                            'Warning: Market data of {0} for {1} day(s) '
                            'before {2} was not downloaded after {3}-th try'
                            .format(markets.loc[chunk, 'market'].to_list(),
                                    lookback_price, val_date, tries))
                        break

            except (KeyError, ValueError, requests.exceptions.HTTPError) as e:
                print(e)
                pass
        df = pd.concat(df_list)
        df = df.merge(markets[['market', 'fullname']], on='market')
        df['val_date'] = val_date
    return df


def vol_stats(client_key, markets, val_date, lookback_volume=10,
              silent=False):
    """
    Return daily trade volume

    :param markets: list of markets to request data in Coinmetrics format, e.g.
        'coinbase-btc-usd-spot'
    :param val_date: the valuation date
    :param client_key: an instance of the CoinMetrics API client class.
    :param lookback_volume: how many days in the past should the daily trading
        volume be downloaded
    :param silent: whether to suppress infor message
    :return:
    """
    start_minute_vol = (
        (pd.to_datetime(val_date) - pd.offsets.DateOffset(
            lookback_volume)).strftime('%Y-%m-%dT%H:%M:%S'))
    end_minute = (
        (pd.to_datetime(val_date) + pd.offsets.DateOffset(1)).strftime(
            '%Y-%m-%dT%H:%M:%S'))
    try:
        price_df = client_key.get_market_candles(
            markets=markets,
            frequency='1d',
            start_time=start_minute_vol,
            end_time=end_minute,
            end_inclusive=False).to_dataframe().sort_values(
            'time')
        if not silent:
            print(
                'Volume statistics for {0} on {1} day(s) before {2} was downloaded'
                .format(markets, lookback_volume, val_date))
        return price_df
    except (KeyError, ValueError) as e:
        print(e)
        if not silent:
            print(
                'Volume statistics for {0} on {1} day(s) before {2} was '
                'not downloaded'
                .format(markets, lookback_volume, val_date))
        return None


def cont_check(val_date, markets, client, lookback_period=10):
    """
    Determine whether there are continuous trading activity in the past,
    :param val_date: the valuation date
    :param markets: a Dataframe containing the markets in Coinmetrics format
        (exchange-base-quote-spot). The column header must be "market"
    :param client: an instance of the Coinmetrics API client.
    :param lookback_period: number of days to check for continuous trading
        activity. Default to be 10.
    :return: a Dataframe with 2 columns: market name and its trading continuity
        status
    """
    hist_vol = []
    for chunk in np.array_split(markets.index,
                                markets.shape[0] // 20 + 1):
        df = vol_stats(
            markets=markets.loc[chunk, 'market'].to_list(),
            val_date=val_date, client_key=client,
            lookback_volume=lookback_period,
            silent=True)
        hist_vol.append(df)

    hist_vol = pd.concat(hist_vol)
    cont_trade_ind = (
        hist_vol
        .groupby('market').min()
        .loc[:, ['volume']]
        .reset_index()
    )
    cont_trade_ind['volume'] = cont_trade_ind['volume'].astype('bool')
    cont_trade_ind.rename(
        columns={'volume': 'Continuous activity in the last 10 days'},
        inplace=True)

    return cont_trade_ind


def first_trade(val_date, markets, client):
    """
    Return the first minutia candle snapshot with non-zero trade volume.
    :param val_date: the valuation date
    :param markets: a Dataframe containing the markets in Coinmetrics format
        (exchange-base-quote-spot). The column header must be "market"
    :param client: an instance of the Coinmetrics API client.
    :return: a Dataframe with 2 columns: market name and its first snapshot
        with non-zero trading volume.
    """
    first_trade_time = []
    start_time = pd.to_datetime(val_date)
    end_time = pd.to_datetime(val_date) + pd.Timedelta('1 day')
    for chunk in np.array_split(markets.index,
                                markets.shape[0] // 20 + 1):
        df = client.get_market_candles(
            markets=markets.loc[chunk, 'market'].to_list(),
            frequency='1h',
            start_time=start_time.strftime('%Y-%m-%dT%H:%M:%S'),
            end_time=end_time.strftime('%Y-%m-%dT%H:%M:%S'),
            end_inclusive=False
        ).to_dataframe()
        first_trade_time.append(df)
    first_trade_time = pd.concat(first_trade_time)
    first_trade_time = (
        first_trade_time.loc[
            first_trade_time['volume'] > 0, ['market', 'time']]
        .groupby('market')
        .min()
        .reset_index()
        .rename(columns={'time': 'First snapshot with volume'}))
    first_trade_time['First snapshot with volume'] = (
        (first_trade_time['First snapshot with volume']
         + pd.Timedelta('1 hour')
         )
        .dt.strftime('%H:%M:%S')
    )
    return first_trade_time


##  Functions


def scope_check_icave(
        val_date,
        exchange_df,
        fiat_currency_df,
        crypto_currency_df,
        client,
        output_path,
        lookback_period=10):
    """
    Returns all crypto-fiat markets among reliable exchange_df.

    :param val_date: the valuation date
    :param fiat_currency_df: the static dataframe of all fiat currencies
    :param crypto_currency_df: the dataframe of the crypto assets to query
        scope for
    :param exchange_df: the input list of reliable exchanges as a dataframe
        with entry and exit dates
    :param client: the instance of CoinMetrics API Python client
    :param lookback_period: the period to check for available trading activities
    :param output_path: the folder path to export data
    :return: 3 DataFrames. The first one lists all available crypto-fiat
    markets. The second one lists all available crypto-crypto markets,
    while the 3rd one is a subset of the 1st one, limited to top 50 cryptos
    with the largest market cap. All Dataframes are limited to quotes among
    reliable exchanges.

    Table columns:
        - market: market name in CoinMetrics format (e.g. coinbase-btc-usd-spot,
        - frequency: frequency of market data (e.g. 1m, 1h, etc.),
        - min_time: timestamp of the first trade,
        - max_time: timestamp of the most recent trade when this function is
          called,
        - exchange: name of exchange,
        - base: name of the crypto,
        - quote: name of the quoting currency,
        - market_type: type of market (spot, future, option),
        - full_name: full name of the crypto
    """
    # intermediate variables
    val_date_dt = pd.to_datetime(val_date)
    output_file_exchanges = (
            output_path / 'iCAVE current reliable exchange.csv')
    # determine currently reliable exchanges as of val_date
    exchange_output = exchange_df.loc[
        (
                (
                        exchange_df['from'].isnull() | (
                        exchange_df['from'] <= val_date_dt))
                & (
                        exchange_df['until'].isnull() | (
                        exchange_df['until'] >= val_date_dt)))
        , 'exchange']
    crypto_default_output = crypto_currency_df.loc[
        (
                (
                        crypto_currency_df['from'].isnull() | (
                        crypto_currency_df['from'] <= val_date_dt))
                & (
                        crypto_currency_df['until'].isnull() | (
                        crypto_currency_df['until'] >= val_date_dt))),
        ['base', 'full_name']
    ]
    # export static data as of val date
    exchange_output.to_csv(output_file_exchanges, index=False)
    # market scoping
    all_markets = scope_check(
        client_key=client,
        val_date=val_date,
        exchanges=exchange_output.str.lower().to_list(),
        lookback_period=lookback_period)
    fiat_crypto_markets = all_markets.merge(
        fiat_currency_df, how='outer', on='quote', indicator=True
    )
    fiat_crypto_markets = fiat_crypto_markets[
        fiat_crypto_markets['_merge'].isin(['both', 'left_only'])]
    fiat_markets = (
        fiat_crypto_markets[fiat_crypto_markets['_merge'] == 'both']
        .drop('_merge', axis=1))
    crypto_markets = (
        fiat_crypto_markets[fiat_crypto_markets['_merge'] == 'left_only']
        .drop('_merge', axis=1))
    default_markets = fiat_markets.merge(
        crypto_default_output, how='inner', on=['base', 'full_name'],
        indicator=True
    )
    # only check first snapshot and trade cont with volume for default markets
    print('checking trade continuity ...')
    cont_check_df = cont_check(
        val_date=val_date,
        markets=default_markets,
        client=client,
        lookback_period=lookback_period
    )
    print('checking first snapshot with trades ...')
    first_trade_df = first_trade(
        val_date=val_date,
        client=client,
        markets=default_markets
    )
    default_markets = (
        default_markets
        .merge(cont_check_df, on='market')
        .merge(first_trade_df, on='market', how='left'))
    print(crypto_default_output.shape[0])
    print(
        'number of markets in default coverage: '
        f'{default_markets
        .loc[default_markets["_merge"] == "both"].shape[0]}')
    return [fiat_markets, crypto_markets, default_markets]


def scope_check_manual(
        val_date, client, exchange_df, fiat_currency_df, crypto_currency_df,
        crypto_only, lookback_period=10):
    """
    Returns all crypto markets for the queried crypto assets among
    reliable exchange_df and export to csv.

    :param val_date: the valuation date
    :param fiat_currency_df: the static dataframe of all fiat currencies
    :param crypto_currency_df: the dataframe of the crypto assets to query
        scope for
    :param exchange_df: the input list of reliable exchanges as a dataframe
        with entry and exit dates
    :param client: the instance of CoinMetrics API Python client
    :param lookback_period: the period to check for available trading activities
    :param crypto_only: boolean, whether the trading pairs are crypto-fiat or
        crypto_currency_df
    :return: a Dataframe of all crypto-fiat markets with available minutia
        data in CoinMetrics with optional constraints on exchanges,
        currencies and crypto assets.

    Table columns:
        - market: market name in CoinMetrics format (e.g. coinbase-btc-usd-spot,
        - frequency: frequency of market data (e.g. 1m, 1h, etc.),
        - min_time: timestamp of the first trade,
        - max_time: timestamp of the most recent trade when this function is
          called,
        - exchange: name of exchange,
        - base: name of the crypto,
        - quote: name of the quoting currency,
        - market_type: type of market (spot, future, option),
        - full_name: full name of the crypto
    """
    print(val_date)
    val_date_dt = pd.to_datetime(val_date)

    # determine currently reliable exchanges as of val_date
    exchange_output = exchange_df.loc[
        (
                (exchange_df['from'].isnull() | (
                        exchange_df['from'] <= val_date_dt))
                & (exchange_df['until'].isnull() | (
                exchange_df['until'] >= val_date_dt))
        ),
        'exchange']

    # extract all markets
    all_markets = scope_check(client_key=client,
                              val_date=val_date,
                              exchanges=exchange_output.str.lower().to_list(),
                              lookback_period=lookback_period)

    if crypto_only:
        # Left join to take everything which are NOT fiat quotes
        pricing_markets = (
            all_markets
            .merge(crypto_currency_df, how='inner', on='base')
            .merge(fiat_currency_df, how='left', on='quote', indicator=True)
        )
        pricing_markets = pricing_markets[
            pricing_markets['_merge'] == 'left_only']
        pricing_markets['quote type'] = 'pricing'
        conv_markets = (
            pricing_markets['quote'].drop_duplicates().to_frame().rename(
                columns={'quote': 'base'})
            .merge(all_markets, how='inner', left_on='base',
                   right_on='base')
            .merge(fiat_currency_df, how='inner', left_on='quote',
                   right_on='quote')
        )
        conv_markets['quote type'] = 'conv'
        full_markets = pd.concat([pricing_markets, conv_markets])
        return full_markets
    else:
        markets = (all_markets
                   .merge(crypto_currency_df, how='inner', on='base')
                   .merge(fiat_currency_df, how='inner', on='quote',
                          indicator=True)
                   .drop_duplicates())
        markets['quote type'] = 'pricing'
        cont_check_df = cont_check(
            val_date=val_date,
            markets=markets,
            client=client,
            lookback_period=lookback_period
        )
        # only check first snapshot with volume for fiat markets
        first_trade_df = first_trade(
            val_date=val_date,
            client=client,
            markets=markets[markets['_merge'] == 'both']
        )
        markets = (markets
                   .merge(cont_check_df, on='market')
                   .merge(first_trade_df, on='market', how='left'))
    return markets


def export_scope_icave(
        val_date, crypto_markets, fiat_markets, default_markets,
        output_path):
    """
    Export all market coverage files to csv and xlsx files.
    :param val_date: the valuation date
    :param crypto_markets: a Dataframe containing the full set of all
        markets among reliable exchange as of the valuation date
    :param fiat_markets: a subset of fiat_crypto_markets containing 
        all fiat-crypto markets among reliable exchanges
    :param default_markets: a subset of fiat_markets containing top 50 
        largest cryptos by market cap as of the valuation date
    :param output_path: the folder path to export data
    :return: None
    """
    output_file_fiat = output_path / 'iCAVE fiat markets.csv'
    output_file_crypto = output_path / 'iCAVE crypto markets.csv'
    output_file_default = output_path / 'iCAVE default markets.csv'
    output_file_overview = (
            output_path / f'iCAVE coverage_{val_date.replace("-", "")}.xlsx')

    # default iCAVE coverage scoping
    default_markets[['min_time', 'max_time']] = (
        default_markets[['min_time', 'max_time']].apply(
            lambda x: x.dt.tz_localize(None))
    )
    # manual assessment scoping
    crypto_markets[['min_time', 'max_time']] = (
        crypto_markets[['min_time', 'max_time']].apply(
            lambda x: x.dt.tz_localize(None))
    )
    print(f'market availability check done for {val_date}')
    print(f'number of fiat markets:{fiat_markets.shape[0]}')
    print(f'number of default fiat markets:'
          f'{default_markets.loc[default_markets["_merge"] == "both"]
          .shape[0]}')
    print(f'number of crypto markets: {crypto_markets.shape[0]}')
    crypto_market_coverage = crypto_markets.drop_duplicates(
        subset='full_name')
    # export data to csv and xlsx format
    fiat_markets.to_csv(output_file_fiat, index=False)
    crypto_markets.to_csv(output_file_crypto, index=False)
    (
        default_markets.drop('_merge', axis=1)
        .to_csv(output_file_default, index=False)
    )
    with pd.ExcelWriter(output_file_overview, mode='w',
                        engine="xlsxwriter") as writer:
        fiat_market_coverage = (
            fiat_markets.drop_duplicates(
                subset='full_name')
            .merge(default_markets['market'],on='market',indicator=True,
                   how='left'))
        fiat_market_coverage['status'] = np.where(
            fiat_market_coverage['_merge'] == 'both',
            'Yes',
            'No, but can be manually extracted from data vendor')
        (
            fiat_market_coverage
            .sort_values(
                ['status', 'base'],
                ascending=[False, True])
            .drop(
                [col for col in fiat_market_coverage.columns if
                 col not in ['base', 'full_name', 'status']],
                axis=1)
            .rename(
                {'base': 'Asset',
                 'full_name': 'Full name',
                 'status': 'Market data available in iCAVE by default'},
                axis=1)
            .to_excel(
                excel_writer=writer,
                sheet_name='iCAVE Coverage',
                index=False)
        )
        (
            default_markets
            .drop('_merge', axis=1)
            .to_excel(excel_writer=writer,
                      sheet_name='iCAVE All Markets',
                      index=False)
        )
        (
            crypto_market_coverage
            .drop(
                [col for col in crypto_market_coverage.columns if
                 col not in ['base', 'full_name']],
                axis=1)
            .sort_values(
                ['base'],
                ascending=[True])
            .rename(
                {'base': 'Asset',
                 'full_name': 'Full name'},
                axis=1)
            .to_excel(
                excel_writer=writer,
                sheet_name='Manual Assessment Coverage',
                index=False)
        )
        (
            crypto_markets
            .to_excel(excel_writer=writer,
                      sheet_name='All crypto markets',
                      index=False)
        )
    return None


def export_scope_manual(fiat_crypto_markets, output_path, crypto_only):
    """
    Export all market coverage files to csv files

    :param fiat_crypto_markets: a Dataframe containing the full set of all
        markets among reliable exchange as of the valuation date
    :param output_path: the folder path to export data
    :param crypto_only: boolean, whether the trading pairs are crypto-fiat or
        crypto_currency_df
    :return: None
    """
    output_pricing = output_path / 'iCAVE manual extraction markets.csv'
    output_conversion = output_path / 'iCAVE manual extraction conversion.csv'
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
    output_pricing.unlink(missing_ok=True)
    output_conversion.unlink(missing_ok=True)
    if crypto_only:
        pricing_markets = fiat_crypto_markets[
            fiat_crypto_markets['quote type'] == 'pricing']
        conv_markets = fiat_crypto_markets[
            fiat_crypto_markets['quote type'] == 'conv']
        print(f'number of crypto-fiat quotes: {conv_markets.shape[0]}')
        print(f'number of crypto-crypto quotes: {pricing_markets.shape[0]}')
        # export to csv
        conv_markets.to_csv(output_conversion, index=False)
        pricing_markets.to_csv(output_pricing, index=False)
    else:
        fiat_crypto_markets.to_csv(output_pricing, index=False)
        print(f'number of crypto-fiat quotes: {fiat_crypto_markets.shape[0]}')

    return None


def get_market_data_auto(
        client_key,
        val_date,
        granul,
        fiat_crypto_markets,
        output_path):
    """
    Extract all pricing data for the selected cryptocurrencies on the
    specified date

    :param val_date: the valuation date
    :param client_key: an instance of the CoinMetrics API client class.
    :param granul: sampling frequency of the market data
    :param fiat_crypto_markets: a Dataframe contains the full set of all
        markets among reliable exchange as of the valuation date
    :param output_path: the folder path to export data

    :return: Dataframe with all data
    """
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_file = (
                output_path
                / f'CoinMetricsData_{val_date.replace("-", "")}'
                  f'_{pd.Timestamp.today().strftime("%Y%m%d")}'
                  f'.csv')

        df = get_market_data(
            markets=fiat_crypto_markets,
            val_date=val_date,
            client_key=client_key,
            granul=granul,
            lookback_price=0,
            lookback_volume=10,
            vol_hist=True)
        df.to_csv(output_file, index=False)
    return None


def get_market_data_manual(
        client_key,
        val_date,
        granul,
        fiat_crypto_markets,
        output_path,
        crypto_only=False,
        skip_conv=False):
    """
    Extract all pricing data for the selected cryptocurrencies on the
    specified date and type of trading pair (crypto-fiat / crypto-crypto)

    :param client_key: an instance of the CoinMetrics API client class.
    :param val_date: the valuation date
    :param fiat_crypto_markets: a Dataframe contains the full set of all
        markets among reliable exchange as of the valuation date
    :param granul: the granularity of the market data
    :param output_path: the folder path to export data
    :param crypto_only: boolean, whether the trading pairs are crypto-fiat or
        crypto-crypto
    :param skip_conv: boolean, whether to skip conversion market data
        extraction in case market data is requested for crypto-crypto trading
        pairs
    :return: Dataframe with all data
    """
    if crypto_only:
        output_pricing = (
                output_path /
                'CoinMetricsData_manualpricing'
                f'_{val_date.replace("-", "")}'
                f'_{pd.Timestamp.today().strftime("%Y%m%d")}'
                '.csv'
        )
        pricing_markets = (
            fiat_crypto_markets[
                fiat_crypto_markets['quote type'] == 'pricing'])
        if skip_conv:
            print("crypto-crypto market requested but conversion market data"
                  " request skipped")
        else:
            # crypto-fiat market data for price conversion
            print(
                'crypto-crypto market data requested. getting crypto-fiat data '
                'for price conversion ...')
            output_conversion = (
                    output_path /
                    'CoinMetricsData_manualconv'
                    f'_{val_date.replace("-", "")}'
                    f'_{pd.Timestamp.today().strftime("%Y%m%d")}'
                    f'.csv'
            )
            conv_markets = fiat_crypto_markets[
                fiat_crypto_markets['quote type'] == 'conv']
            df = get_market_data(
                markets=conv_markets,
                val_date=val_date,
                client_key=client_key,
                granul=granul,
                lookback_price=0,
                lookback_volume=10,
                vol_hist=True)
            df.to_csv(output_conversion, index=False)
    else:
        output_pricing = (
                output_path /
                'CoinMetricsData_iCAVEpricing'
                f'_{val_date.replace("-", "")}'
                f'_{pd.Timestamp.today().strftime("%Y%m%d")}'
                '.csv'
        )
        pricing_markets = fiat_crypto_markets
        print(
            'if the data extraction is intended for manual assessment, '
            'please ensure that the flag crypto_only is True')
    df = get_market_data(
        markets=pricing_markets,
        val_date=val_date,
        client_key=client_key,
        granul=granul,
        lookback_price=0,
        lookback_volume=10,
        vol_hist=True)
    df.to_csv(output_pricing, index=False)
