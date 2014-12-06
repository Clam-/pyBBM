
# Google services
# require APIkey module option

# TODO: maybe implement some of these neat filters:
# https://developers.google.com/custom-search/json-api/v1/reference/cse/list#request

from urllib2 import Request, urlopen, HTTPError
from urllib import urlencode, quote
from json import load
		
OPTIONS = {
	"API_KEY" : (unicode, "API key for use with Google services.", u"not_a_key"),
	"CSE_ID" : (unicode, "ID of Custom Search Engine to use with Google search.", u"not_an_ID"),
}

SEARCH_URL = "https://www.googleapis.com/customsearch/v1?%s"
LOC_URL = "https://maps.googleapis.com/maps/api/geocode/json?%s"
TIMEZONE_URL = "https://maps.googleapis.com/maps/api/timezone/json?%s"
YOUTUBE_URL = "https://www.googleapis.com/youtube/v3/search?%s"
YOUTUBE_CHECK_URL = "http://gdata.youtube.com/feeds/api/videos/%s"
YOUTUBE_INFO_URL = "https://www.googleapis.com/youtube/v3/videos?%s"
API_KEY = None
CSE_ID = None

def google(query, num_results=1):
	""" google helper. Will return Google search results using the provided query up to num_results results."""
	d = { "q" : query.encode("utf-8"), "key" : API_KEY, "cx" : CSE_ID, "num" : num_results,
		"fields" : "spelling/correctedQuery,items(title,link,snippet)" }
		
	f = urlopen(SEARCH_URL % (urlencode(d)))
	gdata = load(f)
	if f.getcode() == 200:
		results = []
		spelling =  gdata.get("spelling")
		if spelling: spelling = spelling["correctedQuery"]
		if "items" in gdata:
			for item in gdata["items"]:
				snippet = item["snippet"].replace(" \n", " ")
				results.append((item["title"], snippet, item["link"]))
		return (spelling, results)
	else:
		raise RuntimeError("Error: %s" % (gdata.replace("\n", " ")))

def google_image(query, num_results):
	""" google image search helper. Will return Google images using the provided query up to num_results results."""
	d = { "q" : query.encode("utf-8"), "key" : API_KEY, "cx" : CSE_ID, "num" : num_results, "searchType" : "image",
		"fields" : "spelling/correctedQuery,items(title,link)"}
		#TODO: consider displaying img stats like file size and resolution?
	f = urlopen(SEARCH_URL % (urlencode(d)))
	gdata = load(f)
	if f.getcode() == 200:
		results = []
		spelling =  gdata.get("spelling")
		if spelling: spelling = spelling["correctedQuery"]
		if "items" in gdata:
			for item in gdata["items"]:
				results.append((item['title'], item['link']))
		return (spelling, results)
	else:
		raise RuntimeError("Error: %s" % (gdata.replace("\n", " ")))
		
def google_timezone(lat, lon, t):
	""" helper to ask google for timezone information about a location."""
	d = { "location" : "%s,%s" % (lat, lon), "key" : API_KEY, "timestamp" : int(t) }
	# I've seen this request fail quite often, so we'll add a retry
	try:
		f = urlopen(TIMEZONE_URL % (urlencode(d)), timeout=1)
	except URLError:
		f = urlopen(TIMEZONE_URL % (urlencode(d)), timeout=2)
	gdata = load(f)
	if f.getcode() == 200:
		return gdata["timeZoneId"], gdata["timeZoneName"], gdata["dstOffset"], gdata["rawOffset"]
	else:
		raise RuntimeError("Error (%s): %s" % (f.getcode(), gdata.replace("\n", " ")))
		
def google_geocode(query):
	""" helper to ask google for location data. Returns name, lat, lon"""
	d = {"address" : query.encode("utf-8"), "key" : API_KEY }
	f = urlopen(LOC_URL % (urlencode(d)))
	locdata = load(f)
	if f.getcode() == 200:
		if "results" in locdata:
			item = locdata["results"]
			if len(item) == 0:
				return None
			item = item[0]
			ll = item.get("geometry", {}).get("location") # lol tricky
			if not ll: return None
			return item["formatted_address"], ll["lat"], ll["lng"]
		else:
			return None
	else:
		raise RuntimeError("Error (%s): %s" % (f.getcode(), locdata.replace("\n", " ")))
		
def google_youtube_search(query, relatedTo=None):
	""" helper to ask google for youtube search. returns numresults, results[(title, url)]"""
	# TODO: make module option for safesearch
	d = {"q" : query.encode("utf-8"), "part" : "snippet", "key" : API_KEY, "safeSearch" : "none",
		"type" : "video,channel"}
	if relatedTo:
		d["relatedToVideoId"] = relatedTo
	f = urlopen(YOUTUBE_URL % (urlencode(d)))
	ytdata = load(f)
	# TODO: handle "badRequest (400)  invalidVideoId"  for relatedTo
	if f.getcode() == 200:
		numresults = ytdata.get("pageInfo", {}).get("totalResults")
		if "items" in ytdata:
			results = ytdata["items"]
			if len(results) == 0:
				return numresults, []
			return numresults, results
		return numresults, []
	else:
		raise RuntimeError("Error (%s): %s" % (f.getcode(), ytdata.replace("\n", " ")))

def google_youtube_check(id):
	""" helper to ask google if youtube ID is valid."""
	try:
		f = urlopen(YOUTUBE_CHECK_URL % (quote(id)))
		return f.getcode() == 200
	except HTTPError:
		return False
		
def google_youtube_details(vidid):
	""" helper to ask google for youtube video details."""
	# TODO: make module option for safesearch
	d = {"id" : quote(vidid), "part" : "contentDetails,id,snippet,statistics,status", "key" : API_KEY}
	
	f = urlopen(YOUTUBE_INFO_URL % (urlencode(d)))
	ytdata = load(f)
	if f.getcode() == 200:
		if "items" in ytdata:
			results = ytdata["items"]
			if len(results) == 0:
				return None
			return results[0]
	else:
		raise RuntimeError("Error (%s): %s" % (f.getcode(), ytdata.replace("\n", " ")))

def init(bot):
	global API_KEY # oh nooooooooooooooooo
	global CSE_ID # oh nooooooooooooooooo
	API_KEY = bot.getOption("API_KEY", module="google")
	CSE_ID = bot.getOption("CSE_ID", module="google")
	return True

