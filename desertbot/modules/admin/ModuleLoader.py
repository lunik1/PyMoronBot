from twisted.plugin import IPlugin
from desertbot.moduleinterface import IModule
from desertbot.modules.commandinterface import BotCommand, admin
from zope.interface import implementer

from typing import List, Tuple

from desertbot.message import IRCMessage
from desertbot.modulehandler import ModuleHandler
from desertbot.response import IRCResponse, ResponseType

ReturnTuple = Tuple[List[str], List[str], List[str]]


@implementer(IPlugin, IModule)
class ModuleLoader(BotCommand):
    def triggers(self):
        return ['load', 'reload', 'unload']

    def help(self, arg):
        return "load/reload/unload <module> - handles loading/reloading/unloading of modules."

    @admin
    def execute(self, message: IRCMessage):
        if len(message.parameterList) == 0:
            return IRCResponse(ResponseType.Say,
                               "You didn't specify a module name! Usage: {0}"
                               .format(self.help(None)),
                               message.replyTo)

        command = {
            'load': self.load,
            'reload': self.reload,
            'unload': self.unload
        }[message.command.lower()]

        successes, failures, exceptions = command(message.parameterList, self.bot.moduleHandler)

        responses = []
        if len(successes) > 0:
            responses.append(IRCResponse(ResponseType.Say,
                                         "'{}' {}ed successfully".format(', '.join(successes),
                                                                         message.command.lower()),
                                         message.replyTo))
        if len(failures) > 0:
            responses.append(IRCResponse(ResponseType.Say,
                                         "'{}' failed to {}, or (they) do not exist"
                                         .format(', '.join(failures), message.command.lower()),
                                         message.replyTo))
        if len(exceptions) > 0:
            responses.append(IRCResponse(ResponseType.Say,
                                         "'{}' threw an exception (printed to console)"
                                         .format(', '.join(exceptions)),
                                         message.replyTo))

        return responses

    def load(self, moduleNames: List[str], moduleHandler: ModuleHandler) -> ReturnTuple:
        moduleNameCaseMap = {m.lower(): m for m in moduleNames}

        successes = []
        failures = []
        exceptions = []

        for moduleName in moduleNameCaseMap:
            try:
                success = moduleHandler.loadModule(moduleName)
                if success:
                    successes.append(moduleNameCaseMap[moduleName])
                else:
                    failures.append(moduleNameCaseMap[moduleName])
            except Exception as x:
                xName = x.__class__.__name__
                exceptions.append("{} ({})".format(moduleNameCaseMap[moduleName], xName))
                self.logger.exception("Exception when loading module {!r}"
                                      .format(moduleNameCaseMap[moduleName]))
                self.bot.reraiseIfDebug(x)

        return successes, failures, exceptions

    def reload(self, moduleNames: List[str], moduleHandler: ModuleHandler) -> ReturnTuple:
        moduleNameCaseMap = {m.lower(): m for m in moduleNames}

        successes = []
        failures = []
        exceptions = []

        if len(moduleNames) == 1 and 'all' in moduleNameCaseMap:
            for name, _ in moduleHandler.modules.items():
                if name == 'ModuleLoader':
                    continue

                moduleHandler.reloadModule(name)

            return ['all commands'], [], []

        for moduleName in moduleNameCaseMap:
            if moduleName == 'moduleloader':
                failures.append("ModuleLoader (I can't reload myself)")
            else:
                try:
                    success = moduleHandler.reloadModule(moduleName)
                    if success:
                        successes.append(moduleHandler.caseMap[moduleName])
                    else:
                        failures.append(moduleNameCaseMap[moduleName])

                except Exception as x:
                    xName = x.__class__.__name__
                    exceptions.append("{} ({})".format(moduleNameCaseMap[moduleName], xName))
                    self.logger.exception("Exception when loading module {!r}"
                                          .format(moduleNameCaseMap[moduleName]))
                    self.bot.reraiseIfDebug(x)

        return successes, failures, exceptions

    def unload(self, moduleNames: List[str], moduleHandler: ModuleHandler) -> ReturnTuple:
        moduleNameCaseMap = {m.lower(): m for m in moduleNames}

        successes = []
        failures = []
        exceptions = []

        for moduleName in moduleNameCaseMap.keys():
            try:
                success = moduleHandler.unloadModule(moduleName)
                if success:
                    successes.append(moduleNameCaseMap[moduleName])
                else:
                    failures.append(moduleNameCaseMap[moduleName])
            except Exception as x:
                xName = x.__class__.__name__
                exceptions.append("{} ({})".format(moduleNameCaseMap[moduleName], xName))
                self.logger.exception("Exception when loading module {!r}"
                                      .format(moduleNameCaseMap[moduleName]))
                self.bot.reraiseIfDebug(x)

        return successes, failures, exceptions


moduleloader = ModuleLoader()
