#state example
from util import Mapping, commandSplit

#Note: Must iterate over dicts with .keys()

def statecommand(event, bot):
	command, args = commandSplit(event.argument)
	
	if command == "channel":
		if not args:
			for chan in bot.state.channels.keys():
				bot.say("Users on channel (%s): %s" % (chan,
					", ".join(bot.state.channels.get(chan).users.keys())))
		else:
			chan = bot.state.channels.get(args, None)
			if chan:
				bot.say("Users on channel (%s): %s" % (args, 
					", ".join(chan.users.keys())))
			else:
				bot.say("lol dunno channel %s" % args)
	
	elif command == "bans":
		if not args:
			for chan in bot.state.channels.keys():
				bot.say("Bans on channel (%s): %s" % (chan,
					", ".join(bot.state.channels.get(chan).keys())))
		else:
			chan = bot.state.channels.get(args, None)
			if chan:
				bot.say("Bans on channel (%s): %s" % (args, 
					", ".join(chan.banlist.keys())))
			else:
				bot.say("lol dunno channel %s" % args)
	
	elif command == "network":
		bot.say("Known users on network: %s" % ", ".join(bot.state.users.keys()))
		
	elif command == "ops":
		for chan in bot.state.channels.keys():
			bot.say("Ops on %s: %s" % (chan, list(bot.state.channels.get(chan, None).ops))) # most likely not threadsafe, don't iterate over sets, probably.
	elif command == "channels":
		bot.say("On channels: %s" % ", ".join(bot.state.channels.keys()))
	else:
		bot.say("state: channel, network, channels, ops")

#mappings to methods
mappings = (Mapping(command="state", function=statecommand),)
