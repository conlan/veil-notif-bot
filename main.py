from flask import Flask, current_app
from flask import request

from google.cloud import datastore
from google.cloud import tasks_v2beta3
from google.protobuf import timestamp_pb2

import ssl
import math

import locale

import urllib.request
import urllib.parse

import twitter

from datetime import datetime
from datetime import timedelta

from eth_utils import (
    add_0x_prefix,
    apply_to_return_value,
    from_wei,
    is_address,
    is_checksum_address,
    keccak as eth_utils_keccak,
    remove_0x_prefix,
    to_checksum_address,
    to_wei,
)

import json
import requests

import web3;

# API
VEIL_MARKET_URL = "https://kovan.veil.co/market/"
VEIL_ENDPOINT_MARKETS = "https://api.kovan.veil.market/api/v1/markets?status=open&channel=";

# ABI


# Provider
providerURL = "https://chainkit-1.dev.kyokan.io/eth";

web3 = web3.Web3(web3.Web3.HTTPProvider(providerURL))

app = Flask(__name__)

def tweetStatus(status):
	# load these from a gitignored file
	twitter_credentials = json.loads(open("./twitter_credentials.json", "r").read());

	# twitter_consumer_key = twitter_credentials["twitter_consumer_key"];
	# twitter_consumer_secret = twitter_credentials["twitter_consumer_secret"];
	# twitter_access_token = twitter_credentials["twitter_access_token"];
	# twitter_token_secret = twitter_credentials["twitter_token_secret"];

	# print(status);

	# api = twitter.Api(consumer_key=twitter_consumer_key,
 #                  consumer_secret=twitter_consumer_secret,
 #                  access_token_key=twitter_access_token,
 #                  access_token_secret=twitter_token_secret)
	# api.PostUpdate(status)

def scheduleRefreshTask(delay_in_seconds):
	# schedule the next call to refresh debts here
	task_client = tasks_v2beta3.CloudTasksClient()

	# # Convert "seconds from now" into an rfc3339 datetime string.
	# d = datetime.utcnow() + timedelta(seconds=delay_in_seconds);
	# timestamp = timestamp_pb2.Timestamp();
	# timestamp.FromDatetime(d);
	
	# parent = task_client.queue_path("bloqboard-bot", "us-east1", "my-appengine-queue");

	# task = {
	# 	'app_engine_http_request': {
	# 		'http_method': 'GET',
	# 		'relative_uri': '/refreshdebts'
	# 	},
	# 	'schedule_time' : timestamp
	# }
	
	# task_client.create_task(parent, task);

@app.route('/')
def index():
	return "{}";

@app.route('/refreshchannel')
def refresh_channel():
	channel = exchange_address = request.args.get("channel");

	if (channel is None):
		return "XX";

	ctx = ssl.create_default_context()
	ctx.check_hostname = False
	ctx.verify_mode = ssl.CERT_NONE

	url = VEIL_ENDPOINT_MARKETS + channel;

	print(url);

	f = urllib.request.urlopen(url, context=ctx)

	markets = json.loads(f.read().decode('utf-8'));

	results = markets["data"]["results"];

	for market in results:
		market_uid = market["uid"];
		
		market_title = market["name"];

		# replace any keywords with hashtags
		# TODO put keywords into a map object
		market_title = market_title.replace(" Ethereum", " #Ethereum");
		market_title = market_title.replace(" ZRX", " $ZRX");
		market_title = market_title.replace(" BTC", " $BTC");
		market_title = market_title.replace(" REP", " $REP");

		market_type = market["type"]

		market_slug = market["slug"];

		market_url = VEIL_MARKET_URL + market_slug;

		market_channel = market["channel"];

		# compose the tweet
		tweet_text = [];
		tweet_text.append("\"");
		tweet_text.append(market_title);
		tweet_text.append("\"");

		# TODO scalar work
		if (market_type == "scalar"):
			market_denomination = market["denomination"];

			market_min_price = market["min_price"];
			market_min_price = str(from_wei(int(market_min_price), 'ether'));
			if (market_denomination == "USD"):
				market_min_price = "{:,.2f}".format(float(market_min_price));

			market_max_price = market["max_price"];
			market_max_price = str(from_wei(int(market_max_price), 'ether'));
			if (market_denomination == "USD"):
				market_max_price = "{:,.2f}".format(float(market_max_price));

			tweet_text.append(" (");
			tweet_text.append(str(market_min_price));
			tweet_text.append(" ");
			tweet_text.append(market_denomination);
			tweet_text.append(" - ");
			tweet_text.append(str(market_max_price));
			tweet_text.append(" ");
			tweet_text.append(market_denomination);
			tweet_text.append(")");

		tweet_text.append(" ");
		tweet_text.append(market_url);

		if (market_channel != None):
			tweet_text.append(" #");
			tweet_text.append(market_channel);

		print("".join(tweet_text));

	return "x";

if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [END gae_python37_app]