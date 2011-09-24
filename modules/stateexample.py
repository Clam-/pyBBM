#state example
from util import Mapping, Settings, State

def statecommand(event, botinst):
	command = ""
	if event.input:
		command = event.input.split(" ", 1)
		if len(command) > 1:
			command, input = command
		else:
			command, input = command[0], None
	
	if command == "channel":
		if not input:
			for chan in State.networks[botinst.network].channels.keys():
				botinst.msg(event.channel, "Channel: %s" % chan)
				for user in State.networks[botinst.network].channels[chan].users:
					botinst.msg(event.channel, "- %s" % user)
		else:
			if input in State.networks[botinst.network].channels:
				botinst.msg(event.channel, "Channel: %s:" % input)
				for user in State.networks[botinst.network].channels[input].users:
					botinst.msg(event.channel, "- %s" % user)
			else:
				botinst.msg(event.channel, "lol dunno channel %s" % input)
		
	elif command == "network":
		botinst.msg(event.channel, "Known users on network: %s" % ", ".join(State.networks[botinst.network].users.keys()))

	elif command == "lol":
		print botinst.supported.getFeature("PREFIX")
		
	elif command == "channels":
		botinst.msg(event.channel, ", ".join(State.networks[botinst.network].channels.keys()))


def init():
	#lol do what now...
	return True

#mappings to methods
mappings = (Mapping(types=["privmsg"], command="state", function=statecommand),)