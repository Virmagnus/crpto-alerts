# -*- coding: utf-8 -*-

import os
import sys
import json
import datetime
import telegram

from pycoingecko import CoinGeckoAPI

from pathlib import Path
from random import uniform, randint, choice
from time import sleep, time

import sqlite3
from sqlite3 import Error

from influxdb import InfluxDBClient


#LOAD config file
BASE_PATH = os.path.dirname(os.path.realpath(__file__))

with open(BASE_PATH+'/config.json') as json_data_file:
    config_data = json.load(json_data_file)



def wait_between(a,b):
    rand=uniform(a, b)
    #print(f'Sleep for {rand}')
    sleep(rand)


def show(curr_time,result_percentage,currency):
    #result_percentage = {'eth': {'percentage': -4.416920810771553, 'increase': -21.289999999999964, 'current_price': 460.72, 'my_price': 482.01} }
    print(curr_time)
    
    for coin in result_percentage:
        p = result_percentage[coin]["percentage"]
        pmov = result_percentage[coin]["increase"]
        curr = result_percentage[coin]["current_price"]
        mine = result_percentage[coin]["my_price"]
        print(f'\t{coin}: {p:.2f}% | price mov: {pmov:.3f} {currency} | current: {curr} {currency} | mine: {mine} {currency}')

def tnotify(keys,message):
    token = keys['token']
    chat_id = keys['chat_id']
    bot = telegram.Bot(token=token)
    wait_between(0.1,0.5)
    bot.sendMessage(chat_id=chat_id, text=message)

def to_influx(result_percentage,currency):
    current_time = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    client = InfluxDBClient('localhost', 8086, 'root', 'root', 'crypto')
    series = []

    for coin in result_percentage:
        percentage = result_percentage[coin]["percentage"]
        price_movement = result_percentage[coin]["increase"]
        curren_price = result_percentage[coin]["current_price"]
        

        pointValues = {
            "time": current_time,
            "measurement": "prices",
            "tags": {
                "coin": coin,
                "currency": currency
            },
            "fields": {
                "percentage": percentage,
                "current_price": curren_price,
                "price_movement": price_movement
            }
        }
        series.append(pointValues)
    client.write_points(series)


# def tclear(keys):
#     token = keys['token']
#     chat_id = keys['chat_id']
#     bot = telegram.Bot(token=token)
#     wait_between(0.1,0.5)
#     bot.deleteMessage(chat_id=update.message.chat.id, message_id=update.message.message_id)


# START Initial block to get coins
C_PATH = Path(__file__).parent.absolute()
coin_list_file = f'{C_PATH}/coin_list.json'

def get_coin_list():
    cg = CoinGeckoAPI()
    data = cg.get_coins_list()
    return data


def check_coin_list():
    # Create file list with all coins if file doesnt exist
    try:
        open(coin_list_file)
        pass
    except IOError:
        print("Coin file not created. Create")
        save_coin_list()

    # Example json entry file  
    # entry = {
    #     'ethereum': {currency: 482.01},
    #     'band': {currency: 4.74}
    #     }
    #entry.update({'api3': {currency:1.6}})


def save_coin_list():
    
    cg = CoinGeckoAPI()
    data = cg.get_coins_list()
    with open(coin_list_file, 'w') as f:
        json.dump(data, f)

# END Start Initial block to get coins

class CoinAlert:


    def create_coin_list(self,entry):
        coin_list = []
        #Create LIST to be passed to EP for Coingecko as coins list
        for symbol in entry:
            coin = self.from_symbol_to_id(symbol)
            coin_list.append(coin)

        coins = f'{", ".join(map(str, coin_list))}'
        return coins


    def from_symbol_to_id(self,symbol):
        n = ""
        with open(coin_list_file, 'r') as f:
            data = json.load(f)
            l_data = len(data)
            for i in range(l_data):
                #print(data[i]['id'])
                d = data[i]['symbol'].lower()
                if symbol == d:
                    n = data[i]['id']
        return n


    def get_price_list(self,coins,currency):
        self.currency = currency
        # API Call got Coingecko
        cg = CoinGeckoAPI()
        result = cg.get_price(ids=coins, vs_currencies=self.currency)
        #result = {'api3': {'eur': 1.58}, 'ethereum': {'eur': 476.4}, 'band-protocol': {'eur': 5.96}}
        r = {}
        for id in result:
            symbol = self.from_id_to_symbol(id)
            r[symbol] = result[id]
        return r


    def from_id_to_symbol(self,id):
        id = id
        n_sym = ""
        with open(coin_list_file, 'r') as f:
            data = json.load(f)
            l_data = len(data)
            for i in range(l_data):
                d = data[i]['id'].lower()
                if id == d:
                    n_sym = data[i]['symbol'].lower()
        return n_sym


    def calc_percentage(self,entry,price_list,currency):
        price_list = price_list
        entry = entry
        currency = currency
        result_percentage = {}
        #s = set((r_coin for r_coin in price_list))
        

        for e_coin in entry:
            for r_coin in price_list:
                if  r_coin == e_coin:
                    c_result = price_list[r_coin][currency]
                    e_result = entry[e_coin]["price"]
                    increase = float(c_result) - float(e_result)
                    increase_perc = (increase/e_result)*100
                    result_percentage.update({r_coin: {"percentage": increase_perc,
                        "increase":increase,
                        "current_price":c_result,
                        "my_price":e_result}})
                    #print(f"{r_coin}| my price: {e_result} | current price:{c_result} | incr: {increase_perc}")                    
        
        return result_percentage


    def process_alarm(self,alerts,result_percentage,keys):
        result = result_percentage
        alerts = alerts

        now = datetime.datetime.now()
        now_pretty = now.strftime("%Y-%m-%d %H:%M:%S")
        #alert_count = 0
        #result = {'eth': {'percentage': -4.416920810771553, 'increase': -21.289999999999964, 'current_price': 460.72, 'my_price': 482.01} }
    
        lvl1 = alerts["global"]["lvl1"]
        lvl2 = alerts["global"]["lvl2"]
        lvl3 = alerts["global"]["lvl3"]
        
        
        for r_coin in result:
            p = result[r_coin]["percentage"]
            inc = result[r_coin]["increase"]
            cp = result[r_coin]["current_price"]
            d = f'{now_pretty}'
            c = f'{r_coin}' 

            if p > 0:
                # Positive
                pge = f'{p:.2f}'
                
                if p >= lvl1 and p <= lvl2:
                    l = 1
                    alert = (d,c,pge,l,inc,cp)
                    self.trigger_alarm(alert,keys)
                    
                
                if p >= lvl2 and p <= lvl3:
                    l = 2
                    alert = (d,c,pge,l,inc,cp)
                    self.trigger_alarm(alert,keys)

                if p >= lvl3:
                    l = 3
                    alert = (d,c,pge,l,inc,cp)
                    self.trigger_alarm(alert,keys)

            else:
                # Negative
                n = abs(result[r_coin]["percentage"])
                pge = f'-{n:.2f}'

                if n >= lvl1 and n <= lvl2:
                    l = 1
                    alert = (d,c,pge,l,inc,cp)
                    self.trigger_alarm(alert,keys)

                    
                if n >= lvl2 and n <= lvl3:
                    l = 2
                    alert = (d,c,pge,l,inc,cp)
                    self.trigger_alarm(alert,keys)

                if n >= lvl3:
                    l = 3
                    alert = (d,c,pge,l,inc,cp)
                    self.trigger_alarm(alert,keys)


    def trigger_alarm(self,alert,keys):
        skull = '\U0001F480'
        rocket = '\U0001F680'
        chart_up = '\U0001F4C8'
        chart_down = '\U0001F4C9'
        cu = self.currency.upper()

        # alert = ('2020-12-12 10:03:46', 'band', '9.70', 1, 0.45999999999999996,484)
        coin = alert[1]
        perc = float(alert[2])
        level = alert[3]
        inc = f'{alert[4]:.2f}'
        cp = alert[5]

        da = DataAlert()
        exist = da.query_alert(coin)
        coin = coin.upper()
        current_data = f'\nChanged {inc} {cu}\nCurrent price: {cp} {cu}'
        
        if not exist:
            if perc > 0:
                change = rocket
                chart = chart_up
                change_smg = f'{change}{coin} is UP +{perc}% {chart}'
                
            else: 
                change = skull
                chart = chart_down
                change_smg = f'{change}{coin} is DOWN {perc}% {chart}'
            
            message = f'{change_smg}{current_data}'
            print("----=== Alert bc it doesnt exist ===-----")
            print(message)
            tnotify(keys,message)
            da.save_alert(alert)

        elif level != exist[0]:
            
            if perc > 0:
                change = rocket
                chart = chart_up
                change_smg = f'{change}{coin} is UP +{perc}% {chart}'
                
            else: 
                change = skull
                chart = chart_down
                change_smg = f'{change}{coin} is DOWN -{perc}% {chart}'
                
            message = f'{change_smg}{current_data}'
            print("----=== Alert bc changed LVL ===-----")
            print(message)
            tnotify(keys,message)
            da.save_alert(alert)
        
        #     message = alert
            #tnotify(keys,message)
            #print(f"{coin} - Current lvl:{level}| Previous lvl: {exist[0]}" )





class DataAlert:

    database = r"crypto-alets.db"

    def create_connection(self,db_file):
        """ create a database connection to the SQLite database
            specified by db_file
        :param db_file: database file
        :return: Connection object or None
        """
        conn = None
        try:
            conn = sqlite3.connect(db_file)
        except Error as e:
            print(e)

        return conn

    def execute_query(self,conn,sql,alert):
        data = alert
        sql = sql
        """
        Create a new alert
        :param conn:
        :param sql:
        :param alert:
        :return:
        """
        
        cur = conn.cursor()
        cur.execute(sql, data)
        conn.commit()
        #return cur.lastrowid
        return cur

    def query_alert(self,coin):

        sql = '''SELECT level FROM alerts WHERE coin=? ORDER BY date DESC LIMIT 1'''
        
        # create a database connection
        conn = self.create_connection(self.database)

        #cur = conn.cursor()
        #cur.execute(sql, (data,))

        with conn:
            response = self.execute_query(conn,sql, (coin,))
        
        return response.fetchone()

    def save_alert(self,alert):
        d = alert[0]
        coin = alert[1]
        perc = alert[2]
        level = alert[3]
        data = (d,coin,perc,level)

        sql = ''' INSERT INTO alerts(date,coin,percentage,level)
        VALUES(?,?,?,?) '''

        # create a database connection
        conn = self.create_connection(self.database)
        with conn:
            # Example
            # alert = ("2020-12-11 18:00:26", "api3", "2", "10.1")
            
            # send alert
            self.execute_query(conn,sql, data)
    
    def save_prices(self,prices):
        return 
        # prices = prices

        # sql = ''' INSERT INTO price(date,coin,percentage,level)
        # VALUES(?,?,?,?) '''

        # # create a database connection
        # conn = self.create_connection(self.database)
        # with conn:
        #     # Example
        #     # alert = ("2020-12-11 18:00:26", "api3", "2", "10.1")
            
        #     # send alert
        #     self.execute_query(conn,sql, prices)



def main():
                               
    entry = config_data['entry']
    wait = config_data['wait']
    alerts = config_data['alerts']
    currency = config_data['currency']
    keys = config_data['telegram']
    check_coin_list()

    ca = CoinAlert()
    coins = ca.create_coin_list(entry)

    while True:
        now = datetime.datetime.now()
        now_pretty = now.strftime("%Y-%m-%d %H:%M:%S")

        price_list = ca.get_price_list(coins,currency)
        result_percentage = ca.calc_percentage(entry,price_list,currency)

        
        # Show function n case you want to print data in realtime
        show(now_pretty,result_percentage,currency)
        to_influx(result_percentage,currency)

        #tnotify(result_percentage)
        ca.process_alarm(alerts,result_percentage,keys)
        sleep(wait)

if __name__ == "__main__":

    main()
