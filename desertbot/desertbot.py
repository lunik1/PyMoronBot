import logging
import os

from twisted.internet.interfaces import ISSLTransport
from twisted.internet import reactor
from datetime import datetime
from desertbot.config import Config
from desertbot.input import InputHandler
from desertbot.ircbase import IRCBase
from desertbot.modulehandler import ModuleHandler
from desertbot.output import OutputHandler
from desertbot.support import ISupport
from desertbot.utils.string import isNumber
from typing import Dict, Optional, List
from weakref import WeakValueDictionary


class DesertBot(IRCBase, object):
    def __init__(self, factory: 'DesertBotFactory', config: Config):
        self.logger = logging.getLogger('desertbot.core')
        self.factory = factory
        self.config = config
        self.input = InputHandler(self)
        self.output = OutputHandler(self)
        self.supportHelper = ISupport()
        self.channels = {}
        self.userModes = {}
        self.users = WeakValueDictionary()
        self.loggedIn = False
        self.secureConnection = False
        self.quitting = False
        self.nick = None
        self.gecos = None
        self.ident = None
        self.server = self.config['server']
        self.commandChar = self.config.getWithDefault('commandChar', '!')

        self.rootDir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))
        self.dataPath = os.path.join(self.rootDir, 'data', self.server)
        if not os.path.exists(self.dataPath):
            os.makedirs(self.dataPath)

        # set the logging path
        self.logPath = os.path.join(self.rootDir, 'logs')

        reactor.addSystemEventTrigger('before', 'shutdown', self.cleanup)

        self.moduleHandler = ModuleHandler(self)
        self.moduleHandler.loadAll()

        # set start time after modules have loaded, some take a while
        self.startTime = datetime.utcnow()

    def cleanup(self) -> None:
        self.config.writeConfig()
        self.logger.info('Saved config and data.')

    def connectionMade(self) -> None:
        # Connection finalizing.
        if ISSLTransport.providedBy(self.transport):
            self.secureConnection = True

        self.supportHelper.network = self.server
        self.logger.info('Connection established.')

        # Initialize login data from the config.
        self.nick = self.config.getWithDefault('nickname', 'DesertBot')
        self.gecos = self.config.getWithDefault('realname', self.nick)
        self.ident = self.config.getWithDefault('username', self.nick)

        # Send a server password if defined.
        password = self.config.getWithDefault('password', None)
        if password:
            self.bot.log.info('Sending network password...')
            self.output.cmdPASS(password)

        # Start logging in.
        self.logger.info('Logging in as {}!{} :{}...'.format(self.nick, self.ident, self.gecos))
        self.output.cmdNICK(self.nick)
        self.output.cmdUSER(self.ident, self.gecos)

    def handleCommand(self, command: str, params: List[str], prefix: str, tags: Dict[str, Optional[str]]) -> None:
        self.logger.debug('IN: {} {} {} {}'.format(tags, prefix, command, ' '.join(params)))
        if isNumber(command):
            self.input.handleNumeric(command, prefix, params)
        else:
            self.input.handleCommand(command, prefix, params)

    def sendMessage(self, command, *parameter_list, **prefix):
        self.logger.debug('OUT: {} {}'.format(command, ' '.join(parameter_list)))
        IRCBase.sendMessage(self, command, *parameter_list, **prefix)

    def disconnect(self, reason: str = '') -> None:
        self.quitting = True
        self.output.cmdQUIT(reason)
        self.transport.loseConnection()

    def setUserModes(self, modes: str) -> Optional[Dict]:
        adding = True
        modesAdded = []
        modesRemoved = []
        for mode in modes:
            if mode == '+':
                adding = True
            elif mode == '-':
                adding = False
            elif mode not in self.supportHelper.userModes:
                self.logger.warning('Received unknown MODE char {} in MODE string {}.'.format(mode, modes))
                return None
            elif adding:
                self.userModes[mode] = None
                modesAdded.append(mode)
            elif not adding and mode in self.userModes:
                del self.userModes[mode]
                modesRemoved.append(mode)
        return {
            'added': modesAdded,
            'removed': modesRemoved
        }