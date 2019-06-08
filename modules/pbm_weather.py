# https://openweathermap.org
# require APIkey module option

from util import Mapping, WDAY_SHORTMAP, irctools
from time import gmtime, time

REQUIRES = ("pbm_location", "pbm_openweathermap_api")
OWNAPI_MODULE = None
LOC_MODULE = None
MAX_OUTPUT_LEN = 350

# Weather for Lansing, MI: 32.2F (0.1C), Wind Chill of 25F (-4C), Partly Cloudy, Humidity 67%, Wind from the East at 8.0mph (12.9km/h) 
#gusting to 14.0mph (22.5km/h), Low/High 38F/41F (3C/5C).  Flurries or snow showers possible early. A mix of clouds and sun. 
# High 41F. Winds S at 10 to 20 mph.
WEATHER_RPL = "Weather for %s: \x02%.1fF\x02 (\x02%.1fC\x02), Low/High \x02%.1fF\x02/\x02%.1fF\x02 (\x02%.1fC\x02/\x02%.1fC\x02), %s, Humidity %s%%, %s"
WEATHER_RPL_WC = "Weather for %s: \x02%.1fF\x02 (\x02%.1fC\x02), Wind Chill of \x02%.1fF\x02 (\x02%.1fC\x02), Low/High \x02%.1fF\x02/\x02%.1fF\x02 (\x02%.1fC\x02/\x02%.1fC\x02), %s, Humidity %s%%, %s"
# Forecast for Ann Arbor, MI: Today - Chance of Showers 54F/77F (12C/25C), Wed - Clear 55F/81F (13C/27C), Thu - Mostly Sunny 57F/84F (14C/29C), Fri - Mostly Sunny 63F/88F (17C/31C)
FORECAST_RPL = "3 Hour Forecasts for %s: "
# Today - Chance of Showers 54F/77F (12C/25C) PoP: %s Hum: %s
FORECAST_DAY = "%s - %s \x02%.1fF\x02/\x02%.1fF\x02 (\x02%.1fC\x02/\x02%.1fC\x02) Hum: \x02%s%%\x02"
FORECAST_DELIMITER = ' | '

def c2f(temp_c):
	return (temp_c * 1.8) + 32.0

def f2c(temp_f):
	return (temp_f - 32) * (5.0/9.0)

def kph2mph(kph):
	return kph / 1.6093440

def degrees_to_cardinal(d, reverse=False):
	"""
	This is an approximation
	"""
	if reverse:
		d = (d + 180) % 360
	dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
			"S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
	ix = int((d + 11.25)/22.5)
	return dirs[ix % 16]


def wind_chill(temp_c, wind_speed):
	""" Compute wind chill given temperature and wind speed if the
		temperature is 50 degrees Fahrenheit or less and the wind speed is
		above 3 mph, otherwise return 'nan' (not-a-number) because it's an
		undefined quantity in those situations.
	"""
	temp_f = c2f(temp_c)
	wind_speed = kph2mph(wind_speed)
	if temp_f <= 50 and wind_speed > 3:
		windchill = (35.74 + (0.6215 * temp_f) - 35.75 * (wind_speed ** 0.16)
				+ 0.4275 * temp_f * (wind_speed ** 0.16))
		# Not sure on this, we'll try it out
		if abs(temp_f - windchill) >= 3.0:
			return f2c(windchill)
	return None


def _build_locname(place, cc):
	return '%s, %s' % (place, cc)


def weather(event, bot):
	""" weather [user/location]. If user/location is not provided, weather is displayed for the requesting nick.
	Otherwise the weather for the requested user/location is displayed."""
	loc = LOC_MODULE.getLocationWithError(bot, event.argument, event.nick)
	if not loc: return
	name, lat, lon = loc
	weather = OWNAPI_MODULE.get_weather(lat, lon)
	place_name = weather['name']
	country_code = weather['sys']['country']
	temp_c = weather['main']['temp']
	temp_max_c = weather['main']['temp_max']
	temp_min_c = weather['main']['temp_min']
	humidity = weather['main']['humidity']
	wind_kph = weather['wind']['speed']
	wind_cardinal = degrees_to_cardinal(weather['wind']['deg'])
	simple_conditions = weather['weather'][0]['main']
	windchill_c = wind_chill(temp_c, wind_kph)
	if wind_kph <= 4:
		wind = 'Calm wind.'
	else:
		wind = "Wind from the %s at %.1f/%.1f MPH/KPH." % (wind_cardinal, kph2mph(wind_kph), wind_kph)
	if windchill_c:
		bot.say(WEATHER_RPL_WC % (_build_locname(place_name, country_code), c2f(temp_c), temp_c, c2f(windchill_c), windchill_c,
			c2f(temp_min_c), c2f(temp_max_c), temp_min_c, temp_max_c, simple_conditions, humidity, wind))
	else:
		bot.say(WEATHER_RPL % (_build_locname(place_name, country_code), c2f(temp_c), temp_c,
			c2f(temp_min_c), c2f(temp_max_c), temp_min_c, temp_max_c, simple_conditions, humidity, wind))


def forecast(event, bot):
	""" forecast [user/location]. If user/location is not provided, weather forecast information is displayed for the requesting nick.
	Otherwise the weather forecast for the requested user/location is displayed."""
	loc = LOC_MODULE.getLocationWithError(bot, event.argument, event.nick)
	if not loc: return
	name, lat, lon = loc
	DAY_IN_SECONDS = 60.0 * 60.0 * 24.0
	forecast_data = OWNAPI_MODULE.get_forecast(lat, lon)
	city_name = forecast_data['city']['name']
	country_code = forecast_data['city']['country']

	if not forecast_data['list']:
		return bot.say('No forecast returned for %s, %s (?)' % (city_name, country_code))
	current_wday = gmtime(time()).tm_wday
	forecast_time = 0
	output_str = FORECAST_RPL % (_build_locname(city_name, country_code))
	for forecast in forecast_data['list']:
		# Go for 24 hour intervals starting now
		if (forecast['dt'] - forecast_time) < DAY_IN_SECONDS:
			continue
		forecast_time = forecast['dt']

		f_gmtime = gmtime(forecast_time)
		f_wday = gmtime(forecast_time).tm_wday
		timestr = '%d%02dZ' % (f_gmtime.tm_hour, f_gmtime.tm_min)
		# Testing for wday incrementing by 1, 0-6, so test the wraparound value (Sun into Mon)
		if f_wday == current_wday:
			# First iteration, forecast is for the next 3 hours
			# may want to revisit this
			datestr = "Next 3 Hours"
		elif (f_wday - current_wday) in (1, -6):
			datestr = 'Tomorrow@%s' % timestr
		else:
			datestr = '%s@%s' % (WDAY_SHORTMAP[f_wday], timestr)

		# temp_c = forecast['main']['temp']
		temp_max_c = forecast['main']['temp_max']
		temp_min_c = forecast['main']['temp_min']
		humidity = forecast['main']['humidity']
		wind_kph = forecast['wind']['speed']
		# Direction wind is blowing, instead of coming from
		wind_cardinal = degrees_to_cardinal(forecast['wind']['deg'], reverse=True)
		# cloudiness = forecast['clouds']['all']
		# windchill_c = wind_chill(temp_c, wind_kph)
		# simple_conditions = forecast['weather'][0]['main']
		condition_description = forecast['weather'][0]['description'].title()
		precip = ''
		if 'rain' in forecast:
			precip += ' \x02%.2f\x02mm/3h of rain' % forecast['rain']['3h']
		if 'snow' in forecast:
			precip += ' \x02%.2f\x02mm/3h of snow' % forecast['snow']['3h']
		if precip:
			condition_description += ', %s' % precip.lstrip()

		wind = " WND \x02%s\x02@\x02%.1f\x02/\x02%.1f\x02 MPH/KPH" % (wind_cardinal, kph2mph(wind_kph), wind_kph)

		daily_str = FORECAST_DAY % (datestr, condition_description, c2f(temp_min_c), c2f(temp_max_c),
			temp_min_c, temp_max_c, humidity)
		if wind_kph > 20:
			daily_str += wind
		if (len(output_str) + len(daily_str) + len(FORECAST_DELIMITER)) <= MAX_OUTPUT_LEN:
			output_str += daily_str + FORECAST_DELIMITER

	# Pop last delimiter off
	output_str = output_str[:(len(FORECAST_DELIMITER) * -1)]
	return bot.say(output_str)


def init(bot):
	global OWNAPI_MODULE # oh nooooooooooooooooo
	global LOC_MODULE # oh nooooooooooooooooo
	
	OWNAPI_MODULE = bot.getModule("pbm_openweathermap_api")
	LOC_MODULE = bot.getModule("pbm_location")
	return True

#mappings to methods
mappings = (Mapping(command="weather", function=weather), Mapping(command="forecast", function=forecast),)
