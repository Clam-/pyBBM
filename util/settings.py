#settings and stuff
from os.path import join, exists
from copy import copy
from Queue import Queue
from json import dump, load, JSONEncoder
from collections import MutableSet, OrderedDict
#BurlyBot
from util.libs import OrderedSet
from util.container import Container
from util.dispatcher import Dispatcher

KEYS_COMMON = ("nick", "nicksuffix", "commandprefix", "admins")
KEYS_SERVER = ("serverlabel",) + KEYS_COMMON + ("host", "port", "channels", "allowmodules", "denymodules")
KEYS_SERVER_SET = set(KEYS_SERVER)
KEYS_MAIN = KEYS_COMMON + ("console", "debug", "datadir", "datafile", "enablestate", "modules", "servers")
KEYS_MAIN_SET = set(KEYS_MAIN)
#keys to create a copy of so no threading bads
KEYS_COPY = ("admins", "channels", "allowmodules", "denymodules", "modules")
#keys to deny getOption for:
KEYS_DENY = ("servers", "dispatcher")

EXAMPLE_OPTS = {
	"serverlabel" : "Example Server",
	"host" : "irc.domain.tld",
	"channels" : ["#channel1", "#channel2"],
}

EXAMPLE_OPTS2 = {
	"serverlabel" : "Example Server 2",
	"host" : "irc.domain.tld",
	"port" : "+7001",
	"channels" : ["#channel1", ["#channel2", "password"]],
}

class ConfigException(Exception):
	pass

class BaseServer(object):
	def __init__(self, opts):
		self.state = None
		self.setup(opts)
		
	def setup(self, opts):
		self.serverlabel = opts.get("serverlabel", None)
		if not self.serverlabel:
			raise ConfigException("Missing serverlabel" % self.serverlabel)

		if "nick" in opts:
			self.nick = opts["nick"].encode('utf-8')

		if "nicksuffix" in opts:
			self.nicksuffix = opts["nicksuffix"].encode('utf-8')

		self.host = opts.get("host", None)
		if not self.host:
			raise ConfigException("%s must have a host" % self.serverlabel)
		
		#process port number with SSL prefix
		#TODO: should we have a server config attribute called "ssl" instead?
		port = opts.get("port", "6667")
		if isinstance(port, int):
			self.ssl = False
		elif port.startswith("+"):
			port = port[1:]
			self.ssl = True
		else:
			self.ssl = False
		self.port = int(port)

		if "commandprefix" in opts:
			self.commandprefix = opts["commandprefix"]

		self.channels = []
		if "channels" in opts:
			for channel in opts['channels']:
				if isinstance(channel, list):
					if len(channel) > 1 and channel[1]:
						self.channels.append(
							(channel[0].encode('utf-8'), 
							channel[1].encode('utf-8'))
							)
					else:
						self.channels.append((channel[0].encode('utf-8'),))
				else:
					self.channels.append((channel.encode('utf-8'),))
		
		if "allowmodules" in opts:
			self.allowmodules = set(opts["allowmodules"])
		else: self.allowmodules = set([])
		if "denymodules" in opts:
			self.denymodules = set(opts["denymodules"])
		else: self.denymodules = set([])
		
		
	def _getDict(self):
		d = OrderedDict()
		for key in KEYS_SERVER:
			if key in self.__dict__:
				value = getattr(self, key)
				if value: 
					#preprocess channels
					if key == "channels":
						channels = []
						for channel in value:
							if len(channel) == 1:
								channels.append(channel[0])
							else:
								channels.append(channel)
						d[key] = channels
					elif key == "port":
						d[key] = value if not getattr(self, "ssl") else "+"+str(value)
					else:
						d[key] = value
		return d
		
class DummyServer(BaseServer):
	def __init__(self, opts, old=None):
		BaseServer.__init__(self, opts, old)

class Server(BaseServer):
	
	def __init__(self, opts):
		BaseServer.__init__(self, opts)
		#dispatcher placeholder (probably not needed)
		self.dispatcher = None
		self.container = Container(self)

	def initializeDispatcher(self):
		# this should only be done once.
		assert self.dispatcher is None
		#create dispatcher:
		self.dispatcher = Dispatcher(self)
		
	def __getattr__(self, name):
		# get Server setting if set, else fall back to global Settings
		if name in self.__dict__: 
			return getattr(self, name)
		else:
			return getattr(Settings, name)
	
	def getOption(self, opt):
		if opt in KEYS_DENY: raise AttributeError("Access denied. (%s)" % opt)
		if opt in KEYS_COPY:
			return copy(getattr(self, opt))
		return getattr(self, opt)
	
	def setOption(self, opt, value, globalSetting=False):
		if not globalSetting:
			if opt not in KEYS_SERVER_SET:
				raise AttributeError("Server has no option: %s to set." % opt)
			else:
				setattr(self, opt, value)
		else:
			if opt not in KEYS_MAIN_SET:
				raise AttributeError("Settings has no option: %s to set." % opt)
			else:
				setattr(Settings, opt, value)
	
	def getModuleOption(self, module, option):
		return Settings.getModuleOption(module, option, self.serverlabel)
	
	def setModuleOption(self, module, option, value, globalSetting=False):
		if globalSetting:
			Settings.setModuleOption(module, option, value)
		else:
			Settings.setModuleOption(module, option, value, self.serverlabel)
	
	def getModule(self, modname):
		if not self.isModuleAvailable():
			raise ConfigException("Module (%s) is not available." % modname)
		else:
			return Dispatcher.MODULEDICT[modname]
	
	def isModuleAvailable(self, modname):
		return (modname not in self.denymodules) and (modname in Dispatcher.MODULEDICT)
		

class SettingsBase:
	nick = "BurlyBot"
	nicksuffix = "_"
	commandprefix = "!"
	datadir = "data"
	debug = False
	datafile = "BurlyBot.db"
	enablestate = False
	console = True
	modules = OrderedSet(["core"])
	admins = []
	servers = {}
	botdir = None
	configfile = None
	moduleopts = {}
	moduledict = {}
	
	def _loadsettings(self):
		# TODO: need some exception handling for loading JSON
		try:
			newsets = load(open(self.configfile, "r"))
		except ValueError as e:
			raise ConfigException("Config file (%s) contains errors: %s"
				"\nTry http://jsonlint.com/ and make sure no trailing commas." % (self.configfile, e))
		
		# Only look for options we care about
		for opt in KEYS_MAIN:
			if opt in newsets:
				if opt == "servers":
					# Create servers and put them in the server map
					for serveropts in newsets["servers"]:
						if "serverlabel" not in serveropts: 
							# TODO: instead of raise, create error and continue loading.
							raise ConfigException("Missing serverlabel in config.")
						label = serveropts["serverlabel"]
						if label in self.servers:
							#refresh server settings
							self.servers[label].setup(serveropts)
						else:
							self.servers[label] = Server(serveropts)
				elif opt == "modules":
					setattr(self, opt, OrderedSet(newsets[opt]))
				else:
					setattr(self, opt, newsets[opt])
		if "moduleoptions" in newsets:
			moduleopts = newsets["moduleoptions"]
	
	def reload(self):
		#restore "defaults"
		for key in KEYS_MAIN:
			setattr(self, key, getattr(SettingsBase, key))
				
		if self.configfile:
			#attempt to load user options
			self._loadsettings()
	
	def reloadDispatchers(self, firstRun=False):
		# Reset Dispatcher loaded modules
		Dispatcher.reset()
		for server in self.servers.itervalues():
			if firstRun:
				server.initializeDispatcher()
			else:
				server.dispatcher.reload()
		Dispatcher.showLoadErrors()
	
	def getModuleOption(self, module, option, server=None):
		if module in self.moduleopts:
			if server and server in self.moduleopts[module]["servers"]:
				return self.moduleopts[module]["servers"][server][option]
			else:
				return self.moduleopts[module][option]
				
	def setModuleOption(self, module, option, value, server=None):
		if module in self.moduleopts:
			if server and server in self.moduleopts[module]["servers"]:
				self.moduleopts[module]["servers"][server][option] = value
			else:
				self.moduleopts[module][option] = value
	
	def saveOptions(self):
		d = OrderedDict()
		for key in KEYS_MAIN:
			d[key] = getattr(self, key)
		if self.servers:
			d["servers"] = [serv._getDict() for serv in self.servers.itervalues()]
		else:
			EXAMPLE_SERVER = DummyServer(EXAMPLE_OPTS)
			EXAMPLE_SERVER2 = DummyServer(EXAMPLE_OPTS2)
			d["servers"] = [EXAMPLE_SERVER._getDict(), EXAMPLE_SERVER2._getDict()]
		dump(d, open(self.configfile, "wb"), indent=4, separators=(',', ': '), cls=ConfigEncoder)
		
	#should have some set option helper methods I guess

class ConfigEncoder(JSONEncoder):
	def default(self, obj):
		if isinstance(obj, set):
			return list(obj)
		elif isinstance(obj, MutableSet):
			return list(obj)
		return JSONEncoder.default(self, obj)

Settings = SettingsBase()
