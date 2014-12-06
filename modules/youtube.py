# youtube search/info module

from util import Mapping, commandSplit, functionHelp, fetchone
from re import compile as recompile
from urlparse import urlparse, parse_qs

from time import strftime, strptime

REQUIRES = ("googleapi",)
GAPI_MODULE = None

# title: snippet (url)
RESULT_TEXT = "{%s} (%%s)"

RESULTS_SPELL_IMG = "(SP: %s?) {0}{1}{2}{3}"
RESULTS_IMG = "{0}{1}{2}{3}"

SHORTURL = "https://youtu.be/%s"
CHANNELURL = "https://youtube.com/channel/%s"

#(URL): TITLE [duration] Views: XXX Like/Dislike: XXX/XXX Fav: XXX Comments: XXX Description: XXX
VID_INFO = "%s {0} [%s] %sViews: %s Like/Dislike: %s/%s Fav: %s Comments: %s Description: {1}"
THREEDEE = "\x034,11\x023\x0311,4\x1fD\x0f"

DURATION_FORMATS = ['PT%HH%MM%SS', 'PT%MM%SS', 'PT%SS']

def seen_video(event, bot):
	#verify ID exists:
	#TODO: is this bad? I can't find reference of "regs" in re docs but it seems to hold what I want
	match = event.regex_match
	pos = match.regs[0]
	url = urlparse(match.string[pos[0]:pos[1]])
	id = None
	if url.netloc.endswith("youtu.be"):
		id = url.path.lstrip("/")
	elif url.netloc.endswith("youtube.com"):
		q = parse_qs(url.query)
		if "v" in q:
			if len(q['v']) > 0:
				id = q['v'][0]
	if id and GAPI_MODULE.google_youtube_check(id):
		bot.dbQuery("""INSERT OR REPLACE INTO youtubeseen (source, id) 
			VALUES (?,?);""", (event.target, id))

def _process_duration(s):
	t = None
	for format in DURATION_FORMATS:
		try: t = strptime(s, format)
		except ValueError: continue
	if t:
		if t.tm_hour: return strftime("%H:%M:%S", t)
		else: return strftime("%M:%S", t)
	else: return "?:??"

def show_youtube_info(event, bot):
	if not event.argument:
		row = bot.dbQuery("""SELECT id FROM youtubeseen 
								WHERE source=?;""", (event.target,), fetchone)
		if not row:
			return bot.say("Haven't seen any youtubes in here.")
		id = row['id']
	else:
		id = event.argument
	result = GAPI_MODULE.google_youtube_details(id)
	stats = result.get('statistics', {})
	views = stats.get('viewCount')
	likes = stats.get('likeCount')
	dislikes = stats.get('dislikeCount')
	favs = stats.get('favoriteCount')
	comments = stats.get('commentCount')
	contde = result.get('contentDetails')
	duration = _process_duration(contde.get('duration'))
	definition = contde.get('definition',"").upper()
	dimension = contde.get('dimension',"")
	dimension = THREEDEE if dimension == '3d' else ""
	plus18 = contde.get('contentRating', {}).get('ytRating', "")
	if plus18: plus18 = "18+"
	flags = ""
	if plus18 or dimension or definition:
		flags = "(%s) " % ",".join((x for x in [definition, dimension, plus18] if x))
	#print result
	bot.say(VID_INFO % (SHORTURL % result['id'], duration, flags, views, likes, dislikes, favs, comments), 
		strins=[result['snippet']['title'], result['snippet']['description'].replace("\n", " ")])

def youtube(event, bot):
	""" youtube [searchterm/ID/"random"]. If no argument is provided will look up the details of the last youtube video. 
	Otherwise will search Google using the provided searchterm, 
	or provide detailed video information if youtube video ID is provided. random will display random video."""
	if not event.argument: 
		return show_youtube_info(event, bot)
	if GAPI_MODULE.google_youtube_check(event.argument):
		return show_youtube_info(event, bot)
	numresults, results = GAPI_MODULE.google_youtube_search(event.argument)
	if results:
		lr = len(results)
		rpl = ", ".join([RESULT_TEXT] * lr)
		links = []
		titles = []
		for item in results:
			id = item['id']
			if id['kind'] == 'youtube#video':
				links.append(SHORTURL % item['id']['videoId'])
			elif id['kind'] == 'youtube#channel':
				links.append(CHANNELURL % item['id']['channelId'])
			titles.append(item['snippet']['title'])
		rpl = (rpl % tuple(xrange(lr))) % tuple(links)
		
		bot.say(rpl, fcfs=False, strins=titles)
	else:
		bot.say("(%s) No results found." % numresults)

def init(bot):
	global GAPI_MODULE # oh nooooooooooooooooo
	
	bot.dbCheckCreateTable("youtubeseen", 
		'''CREATE TABLE youtubeseen(
			source TEXT PRIMARY KEY COLLATE NOCASE,
			id TEXT
		);''')
	GAPI_MODULE = bot.getModule("googleapi")
	return True

#mappings to methods
mappings = (Mapping(command=("youtube", "yt"), function=youtube), 
	Mapping(types=["privmsged"], regex=recompile(r"\bhttp(s)?\://(www\.)?youtu\.be\/[a-zA-Z0-9_-]{11}.*\b"), function=seen_video),
	Mapping(types=["privmsged"], regex=recompile(r"\bhttp(s)?\://(www\.)?youtube\.com\/.*v\=[a-zA-Z0-9_-]{11}.*\b"), function=seen_video),)
