# -*- coding: utf-8 -*-
"""
Created on Feb 14, 2014

@author: Tyranic-Moron
"""
from twisted.plugin import IPlugin
from pymoronbot.moduleinterface import IModule, ignore
from pymoronbot.modules.commandinterface import BotCommand
from zope.interface import implementer

import copy
try:
    import re2
except ImportError:
    import re as re2
import re
import sre_constants

from pymoronbot.message import IRCMessage
from pymoronbot.response import IRCResponse, ResponseType


@implementer(IPlugin, IModule)
class Sed(BotCommand):
    def actions(self):
        return super(Sed, self).actions() + [('message-channel', 1, self.handleSed),
                                             ('message-user', 1, self.handleSed),
                                             ('action-channel', 1, self.storeMessage),
                                             ('action-user', 1, self.storeMessage)]

    def triggers(self):
        return ['sed']
    
    historySize = 20
    
    def help(self, query):
        return 's/search/replacement/[flags] [input for c flag] - matches sed-like regex replacement patterns and attempts to execute them on the latest matching line from the last {}\n'\
           'flags are g (global), i (case-insensitive), o (only user messages), v (verbose, ignores whitespace), c (chained)\n'\
           'Example usage: "I\'d eat some tacos" -> s/some/all the/ -> "I\'d eat all the tacos"'.format(self.historySize)

    def onLoad(self):
        self.messages = {}
        self.unmodifiedMessages = {}

    @ignore
    def handleSed(self, message):
        if message.Command:
            return

        match = self.match(message.MessageString)

        return self.sed(message, match)

    def execute(self, message):
        """
        @type message: IRCMessage
        """
        match = self.match(message.Parameters)

        return self.sed(message, match)

    def sed(self, message, match):
        if match:
            search, replace, flags, text = match
            response = self.substitute(search, replace, flags, text, message, message.ReplyTo)

            if response is not None:
                responseType = ResponseType.Say
                if response.Type == 'ACTION':
                    responseType = ResponseType.Do

                return IRCResponse(responseType, response.MessageString, message.ReplyTo)

            else:
                return IRCResponse(ResponseType.Say, "No text matching '{}' found in the last {} messages".format(search, self.historySize), message.ReplyTo)

        else:
            self.storeMessage(message)

    @classmethod
    def match(cls, message):
        """Returns (search, replace, flags) if message is a replacement pattern, otherwise None"""
        if not (message.startswith('s/') or message.startswith('S/')):
            return
        parts = re.split(r'(?<!\\)/', message)
        if len(parts) < 3:
            return
        search, replace = parts[1:3]
        if len(parts) >= 4:
            flags = parts[3].split(' ')[0]
        else:
            flags = ''
        if len(parts) >= 4:
            text = ' '.join('/'.join(parts[3:]).split(' ')[1:])
        else:
            text = ''
        return search, replace, flags, text

    def substitute(self, search, replace, flags, text, inputMessage, channel):
        # Apparently re.sub understands escape sequences in the replacement string; strip all but the backreferences
        replace = replace.replace('\\', '\\\\')
        replace = re.sub(r'\\([1-9][0-9]?([^0-9]|$))', r'\1', replace)
        
        if channel not in self.messages:
            self.messages[channel] = []
            self.unmodifiedMessages[channel] = []
        
        messages = self.unmodifiedMessages[channel] if 'o' in flags else self.messages[channel]

        if 'g' in flags:
            count = 0
        else:
            count = 1

        subFlags = 0
        if 'i' in flags:
            subFlags |= re.IGNORECASE
        if 'v' in flags:
            subFlags |= re.VERBOSE

        if 'c' in flags:
            newMessage = copy.copy(inputMessage)
            
            try:
                searchC = re2.compile(search, subFlags)
                new = searchC.sub(replace, text, count)
            except sre_constants.error as e:
                newMessage.MessageString = "[Regex Error in Sed pattern: {}]".format(e.message)
                return newMessage
            
            if new != text:
                newMessage.MessageString = new
                self.storeMessage(newMessage, False)
            else:
                newMessage.MessageString = text
                self.storeMessage(newMessage, False)
            
            return newMessage

        for message in reversed(messages):
            try:
                searchC = re2.compile(search, subFlags)
                new = searchC.sub(replace, message.MessageString, count)
            except sre_constants.error as e:
                newMessage = copy.copy(inputMessage)
                newMessage.MessageString = "[Regex Error in Sed pattern: {}]".format(e.message)
                return newMessage

            new = new[:300]

            if searchC.search(message.MessageString):
                newMessage = copy.copy(message)
                newMessage.MessageString = new
                self.storeMessage(newMessage, False)
                return newMessage

        return None

    def storeMessage(self, message, unmodified=True):
        if message.ReplyTo not in self.messages:
            self.messages[message.ReplyTo] = []
            self.unmodifiedMessages[message.ReplyTo] = []
        self.messages[message.ReplyTo].append(message)
        self.messages[message.ReplyTo] = self.messages[message.ReplyTo][-self.historySize:]

        if unmodified:
            self.unmodifiedMessages[message.ReplyTo].append(message)
            self.unmodifiedMessages[message.ReplyTo] = self.unmodifiedMessages[message.ReplyTo][-self.historySize:]


sed = Sed()