#settings and stuff
from os.path import join, exists
from os import execv
from copy import deepcopy
from Queue import Queue
from json import dump, load, JSONEncoder
from collections import MutableSet, OrderedDict
from sys import modules, argv, executable
from atexit import register

from twisted.python import log

try: 
	SSL = True
	from twisted.internet.ssl import CertificateOptions, PrivateCertificate, platformTrust
except:
	SSL = None
from twisted.internet import reactor
from twisted.internet.threads import blockingCallFromThread

#BurlyBot
from util.libs import OrderedSet
from util.container import Container
from util.dispatcher import Dispatcher
from util.client import BurlyBotFactory
from util.db import DBManager
from util.timer import Timers

KEYS_COMMON = ("admins", "altnicks", "cert", "commandprefix", "datafile", "encoding", "moduleopts", 
	"nick", "nickservpass", "nicksuffix", "verify")
KEYS_SERVER = ("serverlabel",) + KEYS_COMMON + ("host", "port", "channels", "allowmodules", "denymodules")
KEYS_SERVER_SET = set(KEYS_SERVER)
KEYS_MAIN = KEYS_COMMON + ("console", "debug", "datadir", "enablestate", "logfile", "modules", "servers")
KEYS_MAIN_SET = set(KEYS_MAIN)
#keys to create a copy of so no threading bads
KEYS_COPY = set(("admins", "channels", "allowmodules", "denymodules", "modules"))
#keys to deny getOption for:
# TODO: probably needs more things here
KEYS_DENY = set(("_admins", "servers", "dispatcher", "moduleopts"))
# TODO: this may be incomplete
# list of module setting types to copy to make sure no thread bads
TYPE_COPY = set((list, tuple, dict))

PROPERTIES_MAP = { "admins" : "_admins" }

OPTION_DESC = {
	"altnicks" : "nicknames to be tried when desired nick is in use/unavailable.",
	"encoding" : "encoding to be used for sending and received messages.",
	"nick" : "nickname to be used.",
	"nickservpass" : "password to be send to nickserv on connect.",
	"nicksuffix" : "suffix to be appended to nick when nick is in use/unavailable.",
	#TODO: populate the rest of this.
}

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
	
class NoDefault(object):
	pass

# This is managed from dispatcher, but accessed is managed through settings, and called from container.
# (container wrapped the call in callfromthread if needed and settings managed allowed access)
class _ADDONS(object):
	def __init__(self):
		self._dict = {}
	
	def clear(self):
		self._dict.clear()
		
	def _add(self, addonname, modulename, f):
		self._dict[addonname] = (modulename, f)
		
	def _getModuleAddon(self, addonname):
		return self._dict[addonname]

class BaseServer(object):
	moduleopts = None # {}
	
	def __init__(self, opts):
		self.moduleopts = {}
		self.setup(opts)
	
	# special handler for .admins (.lowers() each nick on set to make for easier checking in wrapper.isadmin)
	@property
	def admins(self):
		return self.__dict__.get("_admins", getattr(Settings, "_admins"))
	@admins.setter
	def admins(self, value):
		self._admins = [x.lower() for x in value]
	
	def setup(self, opts):
		self.channels = []
		for key in KEYS_SERVER:
			opt = opts.get(key, None)
			if key == "serverlabel":
				if opt is None:
					raise ConfigException("Missing serverlabel.")
				elif ":" in opt:
					raise ConfigException('serverlabel ($s) cannot contain ":"' % self.serverlabel)
			elif key == "host" and opt is None:
				raise ConfigException("%s must have a host" % self.serverlabel)
			
			if key == "altnicks":
				if opt:
					self.altnicks = opt if isinstance(opt, list) else (opt,)
			elif key == "port":
				#process port number with SSL prefix
				#TODO: should we have a server config attribute called "ssl" instead?
				opt = opt if opt else "6667"
				if isinstance(opt, int):
					self.ssl = False
				elif opt.startswith("+"):
					opt = opt[1:]
					self.ssl = True
				else:
					self.ssl = False
				self.port = int(opt)
			elif key == "channels":
				if opt:
					for channel in opt:
						if isinstance(channel, list):
							if len(channel) > 1 and channel[1]:
								self.channels.append((channel[0], channel[1]))
							else:
								self.channels.append((channel[0],))
						else:
							self.channels.append((channel,))
		
			elif key == "allowmodules":
				self.allowmodules = set(opt) if opt else set([])
			elif key == "denymodules":
				self.denymodules = set(opt) if opt else set([])
			elif opt:
				setattr(self, key, opt)
		
	def _getDict(self):
		d = OrderedDict()
		for key in KEYS_SERVER:
			# TODO: really bad hack for .admins (and other) property
			okey = key
			key = PROPERTIES_MAP.get(key, key)
			if key in self.__dict__:
				value = self.__dict__[key] #bypass __getattr__ override
				if value: 
					#preprocess channels
					if okey == "channels":
						channels = []
						for channel in value:
							if len(channel) == 1:
								channels.append(channel[0])
							else:
								channels.append(channel)
						d[okey] = channels
					elif okey == "port":
						d[okey] = value if not self.__dict__["ssl"] else "+"+str(value)
					else:
						d[okey] = value
		return d
		
DummyServer = BaseServer # alias to make example server code clear

class Server(BaseServer):
	
	def __init__(self, opts):
		BaseServer.__init__(self, opts)
		self.addons = None
		#dispatcher placeholder (probably not needed)
		self.dispatcher = None
		# TODO: fix the complicated relationship between Factory<->Settings<->Container
		#       also the relationship between Dispatcher<->Settings<->Dispatcher
		self.container = Container(self)
		self._factory = BurlyBotFactory(self)

	def initializeReload(self):
		# Addons should only be created once
		if self.addons is None: self.addons = _ADDONS()
		else: self.addons.clear()
		# Dispatcher should only be created once.
		if self.dispatcher is None:
			#create dispatcher:
			self.dispatcher = Dispatcher(self)
		#else reload it
		else:
			self.dispatcher.reload()
		
	def __getattr__(self, name):
		# get Server setting if set, else fall back to global Settings
		if name in self.__dict__: 
			return getattr(self, name)
		else:
			return getattr(Settings, name)
	
	def getOptions(self, opts, **kwargs):
		vals = []
		for opt in opts:
			vals.append(self.getOption(opt, **kwargs))
		return vals
	
	# if channel or server is set, retrieve for that specific thing.
	# if channel or server is False, retrieve "global" for that thing.
	# TODO: make sure this optimized as it can be
	def getOption(self, opt, module=None, channel=None, server=None, default=NoDefault, setDefault=True, inreactor=False):
		if opt in KEYS_DENY: raise ValueError("Access denied. (%s)" % opt)
		if module:
			if server or server is None:
				# try searching for option in a server object
				if not server is None:
					try: moduleopts = Settings.servers[server].moduleopts
					except KeyError:
						raise ValueError("Server (%s) not found" % server)
				else:
					moduleopts = self.moduleopts
				if module in moduleopts:
					mod = moduleopts[module]
					if channel and "_channels" in mod and channel in mod["_channels"] and opt in mod["_channels"][channel]:
						value = mod["_channels"][channel][opt]
						if type(value) in TYPE_COPY: # copy value if compound datatype
							return deepcopy(value) if inreactor else blockingCallFromThread(reactor, deepcopy, value)
						else: return value
					if opt in mod:
						value = mod[opt]
						if type(value) in TYPE_COPY: # copy value if compound datatype
							return deepcopy(value) if inreactor else blockingCallFromThread(reactor, deepcopy, value)
						else: return value
			# fall back to global moduleopts (or server was False)
			moduleopts = Settings.moduleopts
			# duplicated code from above, micro-optimization because bad.
			if module in moduleopts:
				mod = moduleopts[module]
				if channel and "_channels" in mod and channel in mod["_channels"] and opt in mod["_channels"][channel]:
					value = mod["_channels"][channel][opt]
					if type(value) in TYPE_COPY: # copy value if compound datatype
						return deepcopy(value) if inreactor else blockingCallFromThread(reactor, deepcopy, value)
					else: return value
				if opt in mod:
					value = mod[opt]
					if type(value) in TYPE_COPY: # copy value if compound datatype
						return deepcopy(value) if inreactor else blockingCallFromThread(reactor, deepcopy, value)
					else: return value
			if default is NoDefault:
				raise AttributeError("No setting (%s) for module: %s" % (opt, module))
			else:
				if setDefault:
					moduleopts.setdefault(module, {})[opt] = default
				return default
		#non-module (core) options
		if server is None:
			server = self
		elif server:
			if not server in Settings.servers:
				raise ValueError("Server label (%s) not found." % server)
			server = Settings.servers[server]
		
		if server and opt in KEYS_SERVER_SET:
			value = getattr(self, opt)
		else:
			if not server or server is self:
				if opt not in KEYS_MAIN_SET:
					raise ValueError("Settings has no option: (%s) to get." % opt)
				else:
					value = getattr(Settings, opt)	
			else:
				#case where a server setting is specifically attempted to be got, but it's not in KEYS_SERVER
				# instead of falling back to KEYS_MAIN, raise error
				raise ValueError("Server setting has no option: (%s) to get." % opt)
		if opt in KEYS_COPY: # copy value if compound datatype
			return deepcopy(value) if inreactor else blockingCallFromThread(reactor, deepcopy, value)
		else: return value
	
	def setOption(self, opt, value, module=None, channel=None, server=None):
		if opt in KEYS_DENY: raise ValueError("Access denied. (%s)" % opt)
		if type(value) in TYPE_COPY: value = deepcopy(value) # copy value if compound datatype
		
		if module:
			if server or server is None:
				# try searching for option in a server object
				if not server is None:
					try: moduleopts = Settings.servers[server].moduleopts
					except KeyError:
						raise ValueError("Server (%s) not found" % server)
				else:
					moduleopts = self.moduleopts
				mod = moduleopts.setdefault(module, {})
				if channel: 
					mod.setdefault("_channels", {}).setdefault(channel, {})[opt] = value
				else:
					mod[opt] = value
				return
			# if server was False, (setting "global")
			moduleopts = Settings.moduleopts
			# duplicated code from above, micro-optimization because bad.
			mod = moduleopts.setdefault(module, {})
			if channel: 
				mod.setdefault("_channels", {}).setdefault(channel, {})[opt] = value
			else:
				mod[opt] = value
		else:
			if server is None:
				server = self
			elif server:
				if not server in Settings.servers:
					raise ValueError("Server label (%s) not found." % server)
				server = Settings.servers[server]
			
			if server and opt in KEYS_SERVER_SET:
				setattr(self, opt, value)
			else:
				if not server or server is self:
					if opt not in KEYS_MAIN_SET:
						raise ValueError("Settings has no option: (%s) to set." % opt)
					else:
						setattr(Settings, opt, value)	
				else:
					#case where a server setting is specifically attempted to be set, but it's not in KEYS_SERVER
					# instead of falling back to KEYS_MAIN, raise error
					raise ValueError("Server settings has no option: (%s) to set." % opt)
				
	def getModule(self, modname):
		if not self.isModuleAvailable(modname):
			raise ConfigException("Module (%s) is not available." % modname)
		else:
			return Dispatcher.MODULEDICT.get(modname)
	
	def isModuleAvailable(self, modname):
		return (modname not in self.denymodules) and (modname in Dispatcher.MODULEDICT)
		
	def getAddon(self, addonname):
		try:
			modname, f = self.addons._getModuleAddon(addonname)
		except KeyError:
			raise AttributeError("No provider for %s" % addonname)
		if self.isModuleAvailable(modname):
			return f
		else:
			raise AttributeError("Provider %s is not available because module (%s) is not available." % (addonname, modname))
	

class SettingsBase(object):
	nick = "BurlyBot"
	altnicks = None # []
	nicksuffix = "_"
	nickservpass = None
	commandprefix = "!"
	datadir = "data"
	debug = False
	datafile = "BurlyBot.db"
	enablestate = False
	encoding = "utf-8"
	cert = None
	verify = False
	console = True
	logfile = None
	modules = None # OrderedSet(["core"])
	_admins = None
	servers = None # {}
	botdir = None
	configfile = None
	moduleopts = None # {}
	databasemanager = None
	
	@property
	def admins(self):
		return self._admins
	
	@admins.setter
	def admins(self, value):
		# When we reset defaults, we grab values from SettingsBase... But 'admins' tries to get the property.
		if isinstance(value, property): return # TODO: Don't know how to handle this more cleanly
		self._admins = [x.lower() for x in value]
	
	#TODO: not sure if the following is needed or not. Class.dict seems to behave strangely
	def _setDefaults(self):
		self.altnicks = []
		self.modules = OrderedSet(["core"])
		self._admins = []
		self.moduleopts = {}
	
	def __init__(self):
		self.servers = {}
		self._setDefaults()

	def _loadsettings(self):
		# TODO: need some exception handling for loading JSON
		try:
			newsets = load(open(self.configfile, "r"))
		except ValueError as e:
			raise ConfigException("Config file (%s) contains errors: %s"
				"\nTry http://jsonlint.com/ and make sure no trailing commas." % (self.configfile, e))
		
		self.newservers = newservers = []
		self.oldservers = oldservers = []
		# Only look for options we care about
		for opt in KEYS_MAIN:
			if opt in newsets:
				if opt == "servers":
					# calculate difference to know which servers to disconnect:
					oldservers = set(self.servers.iterkeys())
					# Create servers and put them in the server map
					for serveropts in newsets["servers"]:
						if "serverlabel" not in serveropts: 
							# TODO: instead of raise, create warning and continue loading.
							print "Missing serverlabel in config. Skipping server"
							continue
						label = serveropts["serverlabel"]
						if label in self.servers:
							#refresh server settings
							try:
								self.servers[label].setup(serveropts)
							except Exception as e:
								print "Error in server setup for (%s), server settings may be in inconsistent state. %s" % (label, e)
								continue
						else:
							try:
								s = Server(serveropts)
							except Exception as e:
								print "Error in server setup for (%s), skipping. %s" % (label, e)
								continue
							self.servers[label] = s
							newservers.append(s)
						try: oldservers.remove(label) #remove new server from old set
						except KeyError: pass
				elif opt == "modules":
					setattr(self, opt, OrderedSet(newsets[opt]))
				else:
					setattr(self, opt, newsets[opt])
		# store servers for connection/disconnection at a latter time
		self.newservers = newservers
		self.oldservers = oldservers
		
	def _connect(self, servers):
		for server in servers:
			if server.ssl:
				if not SSL:
					print "Error: Cannot connect to '%s', pyOpenSSL not installed" % server.serverlabel
					self.databasemanager.delServer(server.serverlabel)
					continue
				try: reactor.connectSSL(server.host, server.port, server._factory, createCertOptions(server))
				except Exception as e:
					print "SSL Error: Cannot connect to '%s' (%s)" % (server.serverlabel, e)
					self.databasemanager.delServer(server.serverlabel)
			else:
				reactor.connectTCP(server.host, server.port, server._factory)
			
	def createDatabases(self, servers):
		for server in servers:
			self.databasemanager.addServer(server.serverlabel, server.datafile)
			
	def _disconnect(self, servers):
		#NOTE: this is serverlabel
		for server in servers:
			print "DISCONNECTING: %s" % server
			server = self.servers[server]
			if server.container._botinst:
				server.container._botinst.quit()
			server._factory.stopTrying()
			#callLater delserver so that just incase some modules catch quit or error event, and use DB for it
			# May cause race condition when connecting to new server that uses same name but different DBfile
			# Hope someone doesn't do that...
			reactor.callLater(1.0, self.databasemanager.delServer, server.serverlabel)
			#remove oldservers from servers dict
			try: del self.servers[server.serverlabel]
			except KeyError: print "Warning: tried to remove server that didn't exist"
		
	def load(self):
		self.reloadStage1()
	
	def reloadStage1(self):
		#restore "defaults"
		for key in KEYS_MAIN:
			if key == "servers": continue #never nuke servers
			setattr(self, key, getattr(SettingsBase, key))
		self._setDefaults()
				
		if self.configfile:
			#attempt to load user options
			self._loadsettings()
	
	def reloadStage2(self):
		#disconnect before reloading dispatchers
		self._disconnect(self.oldservers)
		# Reset Dispatcher loaded modules
		# get a list of previously loaded modules so can track stale modules
		oldmodules = set(Dispatcher.MODULEDICT.keys())
		Dispatcher.reset()
		#create databases so init() can do database things.
		self.createDatabases(self.newservers)
		for server in self.servers.itervalues():
			server.initializeReload()
		Dispatcher.showLoadErrors()
		#compare currently loaded modules to oldmodules
		oldmodules = oldmodules.difference(set(Dispatcher.MODULEDICT.keys()))
		#remove oldmodules from sys.modules
		for module in oldmodules:
			print "Removing module: %s" % module
			try: del modules[module]
			except KeyError:
				print "WARNING: module was never in modules %s" % module
		# connect after load dispatchers
		self._connect(self.newservers)
		self.oldservers = self.newservers = []
		
	# TODO: when twisted supports good logger, consider allowing per-server logfile
	# NOTE: logfile is not chat logging
	# This must be called only once
	def initialize(self, logger=None):
		#setup log options
		if not self.console:
			logger.stop()
		if self.logfile:
			log.startLogging(open(join(self.botdir, self.logfile), 'a'), setStdout=False)
		
		# setup global database and databasemanager
		self.databasemanager = DBManager(self.datadir, self.datafile)
		self.reloadStage2()
		#start dbcommittimer
		# TODO: figure out if actually need this, and what SQLite transaction/journaling mode we should be using
		Timers._addTimer("_dbcommit", 60*60, self.databasemanager.dbcommit, reps=-1) #every hour (60*60)
	
	def saveOptions(self):
		d = OrderedDict()
		for key in KEYS_MAIN:
			if key == "servers": continue
			val = getattr(self, key)
			if val:
				d[key] = val
		if self.servers:
			d["servers"] = [serv._getDict() for serv in self.servers.itervalues()]
		else:
			EXAMPLE_SERVER = DummyServer(EXAMPLE_OPTS)
			EXAMPLE_SERVER2 = DummyServer(EXAMPLE_OPTS2)
			d["servers"] = [EXAMPLE_SERVER._getDict(), EXAMPLE_SERVER2._getDict()]
		dump(d, open(self.configfile, "wb"), indent=4, separators=(',', ': '), cls=ConfigEncoder)
	
	def shutdown(self, relaunch=False):
		self._disconnect(self.servers.keys())
		#stop timers or just not care...
		Timers._stopall()
		reactor.callLater(2.0, self.databasemanager.shutdown) # to give time for individual shutdown
		Dispatcher.unloadModules()
		reactor.callLater(2.5, reactor.stop) # to give time for individual shutdown
		# TODO: make sure this works properly
		# 	it may act odd on Windows due to execv not replacing current process.
		if relaunch:
			register(relaunchfunc, executable, argv)
			
	def hardshutdown(self):
		Timers._stopall()
		Dispatcher.unloadModules()
		self.databasemanager.shutdown()

def relaunchfunc(pythonbin, args):
	args.insert(0, pythonbin)
	execv(pythonbin, args)

class ConfigEncoder(JSONEncoder):
	def default(self, obj):
		if isinstance(obj, set):
			return list(obj)
		elif isinstance(obj, MutableSet):
			return list(obj)
		return JSONEncoder.default(self, obj)

def createCertOptions(server):
	pk = None
	cert = None
	if server.cert:
		pc = PrivateCertificate.loadPEM(open(server.cert,"rb").read())
		pk = pc.privateKey.original
		cert = pc.original
	tr = platformTrust() if server.verify else None
	return CertificateOptions(privateKey=pk, certificate=cert, trustRoot=tr)

Settings = SettingsBase()
