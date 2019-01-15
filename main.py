from flask import Flask
from flask import request

from google.cloud import datastore
from google.cloud import tasks_v2beta3
from google.protobuf import timestamp_pb2

import urllib.request
import urllib.parse

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
import ssl
import twitter

# API
VEIL_MARKET_URL = "https://app.veil.co/market/"
VEIL_ENDPOINT_MARKETS = "https://api.veil.co/api/v1/markets?status=open&page=0";

app = Flask(__name__)

def tweetStatus(status, media):
	# load these from a gitignored file
	twitter_credentials = json.loads(open("./twitter_credentials.json", "r").read());

	twitter_consumer_key = twitter_credentials["twitter_consumer_key"];
	twitter_consumer_secret = twitter_credentials["twitter_consumer_secret"];
	twitter_access_token = twitter_credentials["twitter_access_token"];
	twitter_token_secret = twitter_credentials["twitter_token_secret"];

	print(status);

	api = twitter.Api(consumer_key=twitter_consumer_key,
                  consumer_secret=twitter_consumer_secret,
                  access_token_key=twitter_access_token,
                  access_token_secret=twitter_token_secret)
	
	api.PostUpdate(status, media=media);


def scheduleRefreshTask(delay_in_seconds):
	# schedule the next call to refresh debts here
	task_client = tasks_v2beta3.CloudTasksClient()

	# Convert "seconds from now" into an rfc3339 datetime string.
	d = datetime.utcnow() + timedelta(seconds=delay_in_seconds);
	timestamp = timestamp_pb2.Timestamp();
	timestamp.FromDatetime(d);
	
	parent = task_client.queue_path("veil-market-bot", "us-east1", "my-appengine-queue");

	task = {
		'app_engine_http_request': {
			'http_method': 'GET',
			'relative_uri': '/refreshmarkets'
		},
		'schedule_time' : timestamp
	}
	
	task_client.create_task(parent, task);

@app.route('/')
def index():
	return "{}";

@app.route('/refreshmarkets')
def refresh_markets():
	ds = datastore.Client();

	defaults_data = None;

	query = ds.query(kind='defaults');

	query_iterator = query.fetch();

	for entity in query_iterator:
		defaults_data = entity;
		break;

	if (defaults_data is None):
		return "xx";

	tweetedList = defaults_data["tweetedList"];

	decorations = json.loads(defaults_data["decorations"]);

	ctx = ssl.create_default_context()
	ctx.check_hostname = False
	ctx.verify_mode = ssl.CERT_NONE

	url = VEIL_ENDPOINT_MARKETS;

	print(url);

	f = urllib.request.urlopen(url, context=ctx)

	markets = json.loads(f.read().decode('utf-8'));

	results = markets["data"]["results"];

	# reverse the results so that the oldest market is first
	results.reverse();

	has_untweeted_markets = False;

	tweet_text = [];

	for market in results:
		market_uid = market["uid"];

		# continue if we encounter a market already tweeted
		if (market_uid in tweetedList):
			print("Already tweeted " + market_uid);
			continue;

		# check if we already tweeted something, if so then we need to call this quickly again to work through the rest
		# of the list
		if (len(tweet_text) > 0):
			has_untweeted_markets = True;
			break;

		# add this market id to the tweeted list so that we don't tweet it again subsequently
		tweetedList.append(market_uid);
		
		market_title = market["name"];

		# replace any keywords with hashtags
		# TODO put keywords into a map object
		market_title = market_title.replace(" Ethereum", " #Ethereum");
		market_title = market_title.replace(" Bitcoin", " #Bitcoin");		
		market_title = market_title.replace(" ZRX", " $ZRX");
		market_title = market_title.replace(" BTC", " $BTC");
		market_title = market_title.replace(" REP", " $REP");
		
		market_title = market_title.replace(" Best Picture", " #BestPicture");
		market_title = market_title.replace(" Academy Awards?", " #AcademyAwards?");

		market_type = market["type"]

		market_slug = market["slug"];

		market_url = VEIL_MARKET_URL + market_slug;

		market_channel = market["channel"];

		# metadata work
		market_metadata = market["metadata"];

		market_media = None;
		
		if ((market_metadata is None) == False):
			if ("image_url" in market_metadata):
				market_media = market_metadata["image_url"];

		# compose the tweet		
		tweet_text.append("\"");
		tweet_text.append(market_title);
		tweet_text.append("\"");

		# scalar work
		if (market_type == "scalar"):
			market_denomination = market["denomination"];

			# format correctly for USD denomination
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

		# append channel as a hashtag if possible
		if (market_channel != None):
			tweet_text.append(" #");
			tweet_text.append(market_channel);

			if (market_channel in decorations):
				# append this channel's emoji decoration
				tweet_text.append(" ");
				tweet_text.append(decorations[market_channel]);

		# update the tweeted list
		defaults_data.update({
			"tweetedList" : tweetedList
	    })
		ds.put(defaults_data);

		# make the tweet
		tweetStatus("".join(tweet_text), market_media);


	if (has_untweeted_markets):
		# schedule a follow up task quickly after this
		scheduleRefreshTask(70); # 70 seconds if we're going to immediately tweet again 
	else:
		# schedule a follow up task leisurely after this
		scheduleRefreshTask(60 * 10); # 10 minutes if we're going to check again fresh

	return "{x}";

if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [END gae_python37_app]
