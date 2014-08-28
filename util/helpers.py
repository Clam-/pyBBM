#timehelpers.py
from datetime import timedelta
from time import time

# adapted http://stackoverflow.com/a/2119512
def days_hours_minutes(td):
	return td.days, td.seconds//3600, (td.seconds//60)%60, td.seconds % 60

def pluralize(term, num):
	if num > 1: return term + "s"
	else: return term
	
#distance_of_time_in_words
def distance_of_time_in_words(fromtime, totime=None):
	if not totime:
		totime = time()
	past = True
	diff = totime-fromtime
	if diff < 0:
		past = False
		diff = abs(diff)
	if diff < 10:
		if past: return "Just a moment ago."
		else: return "In just a moment."
	
	td = timedelta(seconds=diff)
	days, hours, minutes, seconds = days_hours_minutes(td)
	
	chunks = []
	for term, value in (("day", days), ("hour", hours), ("minute", minutes), ("second", seconds)):
		if value:
			chunks.append((value, pluralize(term, value)))
	
	s = ""
	while chunks:
		s += "%s%s" % chunks.pop(0)
		if len(chunks) >= 2:
			s += ", "
		elif len(chunks) == 1:
			s += " and "
		else:
			if past: s += " ago."
			else: 
				s += "."
				s = "in " + s
	return s
			
#isIterable (the tuple or list kind of iterable)
# maybe there is a more apt name
def isIterable(i):
	return isinstance(i, tuple) or isinstance(i, list)
	
def processHostmask(h):
	if h:
		try:
			nick, ident = h.split('!', 1)
			ident, host = ident.split('@', 1)
		except ValueError:
			pass
		else:
			return (nick, ident, host)
	return (None, None, None)

# Useful thing http://stackoverflow.com/a/8528866
# This may return incorrectly decoded string because naive
ENCODINGS = ("utf-8", "sjis", "latin_1", "gb2312", "cp1251", "cp1252",
	"gbk", "cp1256", "euc_jp")
class UnknownEncoding(UnicodeDecodeError):
	pass
def coerceToUnicode(s):
	for enc in ENCODINGS:
		try:
			return s.decode(enc)
		except UnicodeDecodeError:
			continue
	s = s.decode("utf-8", "replace")
	print "Warning, unknown coded character encounted in %s" % s
	return s
		
		
		
		