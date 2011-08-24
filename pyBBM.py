#pyBBM

# twisted imports
from twisted.words.protocols.irc import IRCClient
from twisted.internet import reactor
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.python import log

# system imports
from time import asctime, time, localtime
from sys import stdout
from optparse import OptionParser

#bbm imports
from util import Settings
from util.dispatcher import Dispatcher

class Event:
	def __init__(self, type=None, args=None, hostmask=None, channel=None, msg=None):
		self.type = type
		# Consider args as a dict of uncommon event attributes
		self.args = args
		self.hostmask = hostmask
		self.nick = None
		self.ident = None
		self.host = None
		if hostmask:
			try:
				nick, ident = hostmask.split('!', 1)
				ident, host = ident.split('@', 1)
			except ValueError:
				pass
			else:
				self.nick = nick
				self.ident = ident
				self.host = host
		# This can be a user, too. Should probably do something to distinguish
		# I think module should distinguish (if channel==user) this is a real PM	-Clam
		self.channel = channel
		if msg: self.msg = msg.decode("utf-8")
		else: self.msg = msg
		# Set by dispatcher, for convenience in module
		self.command = None
		self.input = None

class BBMBot(IRCClient):
	"""BBM"""

	#nickname = None
	#lineRate = 1
	
	def connectionMade(self):
		IRCClient.connectionMade(self)
		#reset connection factory delay:
		self.factory.resetDelay()
		# do we restart the message queues here?
		#self.outbound = Queue() whatever

	def connectionLost(self, reason):
		IRCClient.connectionLost(self, reason)
		print "[disconnected at %s]" % asctime(localtime(time()))

	# callbacks for events

	def signedOn(self):
		"""Called when bot has succesfully signed on to server."""
		print "[Signed on]"
		for chan in Settings.servers[self.servername].channels:
			if isinstance(chan, list):
				if len(chan) > 1: self.join(chan[0], chan[1])
				else: self.join(chan[0])
			else: self.join(chan)
		Dispatcher.dispatch(self, Event(type="signedOn"))

	def joined(self, channel):
		"""This will get called when the bot joins the channel."""
		print "[I have joined %s]" % channel
		Dispatcher.dispatch(self, Event(type="joined", channel=channel))

	def privmsg(self, hostmask, channel, msg):
		"""This will get called when the bot receives a message."""
		Dispatcher.dispatch(self, Event(type="privmsg", hostmask=hostmask, channel=channel, msg=msg))

	def action(self, hostmask, channel, msg):
		"""This will get called when the bot sees someone do an action."""
		Dispatcher.dispatch(self, Event(type="action", hostmask=hostmask, channel=channel, msg=msg))

	def irc_NICK(self, hostmask, params):
		"""
		Called when a user changes their nickname.
		"""
		nick = hostmask.split('!', 1)[0]
		if nick == self.nickname:
			self.nickChanged(params[0])
			Dispatcher.dispatch(self, Event(type="nickChanged", hostmask=hostmask, args={'newname': params[0]}))
		else:
			self.userRenamed(nick, params[0])
			Dispatcher.dispatch(self, Event(type="userRenamed", hostmask=hostmask, args={'newname': params[0]}))
		
	
	def sendmsg(self, dest, msg):
		#check if there's hooks, if there is, dispatch, if not, send directly
		if Dispatcher.hostmap[self.servername]["SENDHOOKS"]:
			#dest is Event.channel, or Event.args
			Dispatcher.dispatch(self, Event(type="sendmsg", channel=dest, msg=msg))
		else:
			self.msg(dest, msg)
	
	#overriding msg
	# need to consider dipatching this event and allow for some override somehow
	def msg(self, user, msg, length=None):
		msg = msg.encode("utf-8")
		if length: IRCClient.msg(self, user, msg, length)
		else: IRCClient.msg(self, user, msg)
	
	#def myInfo(self, servername, version, umodes, cmodes):
		#We could always use this to get server hostname
		# more like dispatch
		
	# override the method that determines how a nickname is changed on
	# collisions. The default method appends an underscore.
	#Just kidding, actually let's do this after all - user option
	def alterCollidedNick(self, nickname):
		return nickname + Settings.servers[self.servername].nicksuffix
		
	#callback to handle module returns
	#do we sanitize input? lol what input
	def moduledata(self, result):
		pass
	
	def moduleerr(self, e):
		print "error:", e #exception, or Failure thing



class BBMBotFactory(ReconnectingClientFactory):
	"""A factory for BBMBot.
	A new protocol instance will be created each time we connect to the server.
	"""

	# the class of the protocol to build when new connection is made
	protocol = BBMBot

	def __init__(self, servername):
		#reconnect settings
		self.servername = servername
		self.maxDelay = 60
		self.factor = 1.6180339887498948
	
	def buildProtocol(self, address):
		proto = ReconnectingClientFactory.buildProtocol(self, address)
		proto.nickname = Settings.servers[self.servername].nick
		proto.servername = self.servername
		return proto



if __name__ == '__main__':
	from os.path import exists
	# initialize logging
	log.startLogging(stdout)
	
	parser = OptionParser(usage="usage: %prog [options] [configfile]")
	parser.add_option("-d", "--dummy", action="store_true", dest="dummy", default=None,
		help="Dummy option. Placeholder.")
	(options, args) = parser.parse_args()
	#get settings file
	settingsf = None
	if len(args) > 0:
		settingsf = args[0]
	
	#make settings object with defaults.json
	#then make settings object with options.json and converge somehow...
	# I've done this before ghetto style, but we'll see what happens. 
	#(okay it's going to be pretty different to what I've done before)
	if settingsf and exists(settingsf):
		Settings.configfile = settingsf
	else:
		print "Settings file not found, running with defaults..."
	Settings.reload()
	#doing it this way so no circular reference, if we refactor dispatcher out of this file we can do away with it
	# it's only used for core.reload
	Settings.dispatcher = Dispatcher 
	Settings.dbThread.start()
	try: Dispatcher.reload()
	except:
		Settings.dbQueue.put("STOP")
		raise
	
	# create factory protocol and application
	#f = BBMBotFactory(sys.argv[1], sys.argv[2])
	for server in Settings.servers.values():
		reactor.connectTCP(server.host, server.port, BBMBotFactory(server.name))
	
	# run bot
	reactor.run()
	Settings.dbQueue.put("STOP")
	Settings.dbThread.join()
