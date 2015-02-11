# IRC formatting helpers

from re import compile as compile_re
from random import randint

MIRC_CONTROL_BOLD = '\x02'
MIRC_CONTROL_COLOR = '\x03'
MIRC_CONTROL_UNDERLINE = '\x1f'
MIRC_CONTROL_ITALICIZE = '\x1d'
MIRC_CONTROL_CLEARFORMATTING = '\x0f'


# http://www.mirc.com/colors.html
MIRC_COLORS = {
	"white": 0,
	"black": 1,
	"blue": 2, "navy": 2,
	"green": 3,
	"red": 4,
	"brown": 5,	"maroon": 5, "javad": 5, #Ahaheuaheuaehu
	"purple": 6,
	"orange": 7, "olive": 7,
	"yellow": 8,
	"light green": 9, "lime": 9,
	"teal": 10,	"green/blue": 10, "green/blue cyan": 10,
	"light cyan": 11, "cyan": 11, "aqua": 11,
	"light blue": 12, "royal": 12,
	"pink": 13,	"light purple": 13,	"fuschia": 13,
	"grey": 14,	"cloud": 14,
	"light grey": 15, "silver": 15
}


def colorize(s, fg=None, bg=None):
	if fg:
		fg_orig = fg
		try:
			fg = int(fg)
		except ValueError:
			try:
				fg = MIRC_COLORS[fg.lower()]
			except (ValueError, KeyError):
				fg = None
		finally:
			if not fg or fg < 0 or fg > 15:
				raise ValueError('Invalid color:  %s' % fg_orig)
	if bg:
		bg_orig = bg
		try:
			bg = int(bg)
		except ValueError:
			try:
				bg = MIRC_COLORS[bg.lower()]
			except (ValueError, KeyError):
				bg = None
		finally:
			if not bg or bg < 0 or bg > 15:
				raise ValueError('Invalid color:  %s' % bg_orig)
	if fg and bg:
		color_s = '%s,%s' % (fg, bg)
	elif fg:
		color_s = '%s' % fg
	elif bg:
		# mIRC's behavior here is to honor the BG color if the FG color is any
		# (valid or not) 2 digit number.  If the FG color is invalid the BG
		# color will display without modifying the FG color, oddly.
		# So we'll just use 99 in these cases to avoid modifying the FG color
		color_s = '99,%s' % bg
	return MIRC_CONTROL_COLOR + color_s + s + MIRC_CONTROL_COLOR


def bold(s):
	return MIRC_CONTROL_BOLD + s + MIRC_CONTROL_BOLD


def underline(s):
	return MIRC_CONTROL_UNDERLINE + s + MIRC_CONTROL_UNDERLINE


def italicize(s):
	return MIRC_CONTROL_ITALICIZE + s + MIRC_CONTROL_ITALICIZE


RE_COLOR_CODE = r'(\x03(([0-9]{1,2})(,[0-9]{1,2})?|[0-9]{2},[0-9]{1,2}))+'
RE_TRAILING_COLOR_CODE = compile_re(RE_COLOR_CODE + r'$')
RE_COLOR_CODE = compile_re(RE_COLOR_CODE)


# Regarding mIRC color codes: Any valid FG or BG value will cause the text color
# to be modified.  All of the following will do something:
# '\x0399,00', '\x0300,99', '\x0303,3238' (will display '38' in green text)
def escape_control_codes(s):
	'''
	Append the appropriate mIRC control character to string s to escape the
	active string control codes, or append MIRC_CONTROL_CLEARFORMATTING (\x0f)
	if multiple control codes are in play.  e.g.:

	escape_control_codes('\x02\x1d\x0315TEST STRING')
	>>> '\x02\x1d\x0315TEST STRING\x0f'
	escape_control_codes('\x02TEST \x1fSTRI\x02NG')
	>>> '\x02TEST \x1fSTRI\x02NG\x1f'
	'''
	s_len = len(s)
	# Pop control characters off of the right side since we'll be escaping them anyways
	s = s.rstrip(MIRC_CONTROL_BOLD + MIRC_CONTROL_UNDERLINE +
	MIRC_CONTROL_ITALICIZE + MIRC_CONTROL_COLOR + MIRC_CONTROL_CLEARFORMATTING)
	s = RE_TRAILING_COLOR_CODE.sub('', s)
	control_tracking = set()
	for index, c in enumerate(s):
		if c in (MIRC_CONTROL_BOLD,	MIRC_CONTROL_UNDERLINE,	MIRC_CONTROL_ITALICIZE):
			if c in control_tracking:
				control_tracking.remove(c)
			else:
				control_tracking.add(c)
		elif c == MIRC_CONTROL_COLOR:
			fg_color_num = ''
			bg_color_num = ''
			# Peek ahead to see if the color code is valid ('0' - '15')
			if (index + 1) < s_len and s[index + 1].isdigit():
				fg_color_num += s[index + 1]
				if (index + 2) < s_len and s[index + 2].isdigit():
					fg_color_num += s[index + 2]
			if fg_color_num:
				# Valid FG color, color mode activated, we can bail out for this iteration here
				if 0 <= int(fg_color_num) <= 15:
					control_tracking.add(c)
					continue
				# Invalid FG color, peek farther (if we can) to check for a valid BG color
				elif (index + 4) < s_len and s[index + 3] == ',' and s[index + 4].isdigit():
					bg_color_num += s[index + 4]
					if (index + 5) < s_len and s[index + 5].isdigit():
						bg_color_num += s[index + 5]
			# Valid BG color, regardless of FG color this will have an impact on color
			if bg_color_num and 0 <= int(bg_color_num) <= 15:
					control_tracking.add(c)
			# Invalid FG and BG color, so it'll cancel any active colors, stop tracking.
			elif c in control_tracking:
				control_tracking.remove(c)
		elif c == MIRC_CONTROL_CLEARFORMATTING:
				control_tracking.clear()
	if len(control_tracking) > 1:
		s += MIRC_CONTROL_CLEARFORMATTING
	elif len(control_tracking) == 1:
		s += control_tracking.pop()
	return s


def AAA(s):
	e = type(s)
	s = list(s)
	s_len = len(s)
	count = 0
	x = 0
	while True:
		if count == 0:
			x += randint(int(s_len * .08), int(s_len * .18))
			s.insert(x, e(MIRC_CONTROL_BOLD))
		elif count == 1:
			x += randint(int(s_len * .1), int(s_len * .25))
			s.insert(x, e(MIRC_CONTROL_UNDERLINE))
		elif count == 2:
			x += randint(int(s_len * .1), int(s_len * .25))
			if s[x].isdigit():
				s.insert(x, e(MIRC_CONTROL_COLOR + '04'))
			else:
				s.insert(x, e(MIRC_CONTROL_COLOR + '4'))
		elif count == 3:
			x += randint(int(s_len * .2), s_len - x)
			s.insert(x, e(MIRC_CONTROL_ITALICIZE))
			break
		count += 1
	return e(''.join(s))
