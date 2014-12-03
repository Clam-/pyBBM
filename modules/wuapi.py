# Weather Undergroun api module used by weather and location
# http://www.wunderground.com/
# require APIkey module option

from util import Mapping, commandSplit, functionHelp
from urllib2 import Request, urlopen, HTTPError
from urllib import urlencode
from json import load

from traceback import format_exc
		
OPTIONS = {
	"API_KEY" : (unicode, "API key for use with Weather Underground services.", u"not_a_key"),
}

# key, features, lat, lon
URL = "http://api.wunderground.com/api/%s/%s/q/%s,%s.json"
LOC_URL = "http://autocomplete.wunderground.com/aq?%s"

API_KEY = None
CSE_ID = None

def lookup_location(query):
	""" helper to ask WU for location data. Returns name, lat, lon"""
	f = urlopen(LOC_URL % (urlencode({"query" : query.encode("utf-8")})))
	locdata = load(f)
	if f.getcode() == 200:
		if "RESULTS" in locdata:
			item = locdata["RESULTS"]
			if len(item) == 0:
				return None
			item = locdata["RESULTS"][0]
			return item["name"], item["lat"], item["lon"]
		else:
			return None
	else:
		raise RuntimeError("Error (%s): %s" % (f.getcode(), locdata.replace("\n", " ")))

def get_weather(lat, lon):
	""" helper to ask WU for current weather."""
	f = urlopen(URL % (API_KEY, "conditions", lat, lon))
	weather_data = load(f)
	if f.getcode() == 200:
		if "current_observation" in weather_data:
			obs = weather_data["current_observation"]
			return obs #TODO: Griff to complete
		else:
			return None
	else:
		raise RuntimeError("Error (%s): %s" % (f.getcode(), weather_data.replace("\n", " ")))
	
def get_forecast(stuff):
	""" helper to ask WU for forecasted weather."""
	f = urlopen(URL % (API_KEY, "forecast", lat, lon))
	weather_data = load(f)
	if f.getcode() == 200:
		if "forecast" in weather_data:
			forecast = weather_data["forecast"]
			return forecast #TODO: Griff to complete
		else:
			return None
	else:
		raise RuntimeError("Error (%s): %s" % (f.getcode(), weather_data.replace("\n", " ")))
	

def init(bot):
	global API_KEY # oh nooooooooooooooooo
	API_KEY = bot.getOption("API_KEY", module="wuapi")
	return True
