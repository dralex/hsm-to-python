# -----------------------------------------------------------------------------
#  HSM-to-Python conversion tool
#
#  The convertor class
#
#  Copyright (C) 2025 Alexey Fedoseev <aleksey@fedoseev.net>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program. If not, see https://www.gnu.org/licenses/
#
#  -----------------------------------------------------------------------------

import sys
import os
import traceback
import CyberiadaML

GLOBAL_INIT_LABEL = 'global initialization'
SM_CONSTRUCTOR = 'sm constructor arguments'
LOOP = 'loop'
INIT_SCRIPTS = 'init scripts'

HEADER_TEMPLATE = 'templates/header.templ'
FOOTER_TEMPLATE = 'templates/footer.templ'
TICK_EVENT = 'TIME_TICK'
STANDARD_EVENTS = {TICK_EVENT: 'Tick',
                   'TIME_TICK_1S': 'Tick1Sec',
                   'INIT': 'Init'}

def DEBUG(*args):
    sys.stderr.write(' '.join(map(str, args)) + '\n')

class ConvertorError(Exception):
    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg
    def __str__(self):
        return self.msg
class ParserError(ConvertorError):
    def __init__(self, msg):
        ConvertorError.__init__(self, msg)
class GeneratorError(ConvertorError):
    def __init__(self, msg):
        ConvertorError.__init__(self, msg)

class CodeGenerator:

    VERSION = '1.0' # generator version

    def __init__(self, graph_file, **kwargs):
        self.__load_graph(graph_file, **kwargs)

    def __load_graph(self, graph_file, **kwargs):
        try:
            self.__graph_file = graph_file
            self.__exit_on_term = kwargs['exit_on_term'] if 'exit_on_term' in kwargs else False
            self.__allow_empty_trans = kwargs['allow_empty_trans'] if 'allow_empty_trans' in kwargs else False
            self.__generate_loop = kwargs['generate_loop'] if 'generate_loop' in kwargs else False
            self.__use_ticks = kwargs['use_ticks'] if 'use_ticks' in kwargs else True
            if not self.__use_ticks and (self.__generate_loop or self.__allow_empty_trans):
                self.__use_ticks = True

            self.__doc = CyberiadaML.LocalDocument()
            self.__doc.open(graph_file, CyberiadaML.formatDetect, CyberiadaML.geometryFormatNone,
                            False, False, True)
            self.__graph = self.__doc.get_state_machines()[0]

            self.__sm_name = self.__graph.get_name()
            self.__sm_name_cap = self.__sm_name[0].upper() + self.__sm_name[1:].lower()

            self.__global_init = []
            sm_variables = []
            self.__loop = []
            self.__init_scripts = []
            comment_labels = {
                GLOBAL_INIT_LABEL: self.__global_init,
                SM_CONSTRUCTOR: sm_variables,
                LOOP: self.__loop,
                INIT_SCRIPTS: self.__init_scripts
            }

            for comment in self.__graph.find_elements_by_type(CyberiadaML.elementComment):
                text = comment.get_body()
                for label, var in comment_labels.items():
                    if text.lower().find(label) == 0:
                        for i, line in enumerate(text.splitlines()):
                            if i == 0:
                                continue
                            line = line.rstrip()
                            if len(line) == 0:
                                continue
                            var.append(line)
                        break

            self.__sm_variables = {}
            for smv in sm_variables:
                var, value = map(lambda s: s.strip(), smv.split('='))
                self.__sm_variables[var] = value

            init_id = None
            self.__initial = None
            self.__initial_behavior = None
            for state in self.__graph.get_children():
                if state.get_type() == CyberiadaML.elementInitial:
                    if init_id is not None:
                        raise ParserError('The graph {} has more than one initial'.format(self.__graph_file) +
                                          'pseudostate on the top level!\n')
                    init_id = state.get_id()
            if init_id is None:
                raise ParserError('The graph {} has no initial pseudostate!\n'.format(self.__graph_file))
            uniq_states = set([])

            self.__signals = {}
            self.__handlers = {}
            self.__transitions = []
            self.__local_transitions = []
            self.__final_states = len(self.__graph.find_elements_by_type(CyberiadaML.elementFinal)) > 0

            types = [CyberiadaML.elementTransition,
                     CyberiadaML.elementSimpleState,
                     CyberiadaML.elementCompositeState]
            for element in self.__graph.find_elements_by_types(types):
                if element.get_type() == CyberiadaML.elementTransition:
                    source_id = element.get_source_element_id()
                    if source_id == init_id:
                        target_id = element.get_target_element_id()
                        self.__initial = self.__graph.find_element_by_id(target_id)
                        self.__initial_behavior = element.get_action().get_behavior()
                        continue
                    source_state = self.__graph.find_element_by_id(source_id)
                    if source_state.get_type() == CyberiadaML.elementInitial:
                        continue
                    a = element.get_action()
                    if len(a.get_trigger()) == 0 and not self.__allow_empty_trans:
                        raise ParserError('The graph {} has state {} ({}->) with empty external transition!\n'.format(self.__graph_file,
                                                                                                                      element.get_id(),
                                                                                                                      source_state.get_name()))
                    self.__check_trigger_and_behavior(element.get_id(), a.get_trigger(), a.get_guard(), a.get_behavior())
                    if a.has_trigger():
                        self.__signals[self.__parse_trigger(a.get_trigger())[0]] = None
                    self.__transitions.append(element)
                else:
                    state_name = element.get_name()
                    if len(state_name) == 0:
                        raise ParserError('The graph {} has state {} with empty name!\n'.format(self.__graph_file,
                                                                                                element.get_id()))
                    if state_name.find(' ') >= 0:
                        raise ParserError('The graph {} has state {} with spaces in name "{}"!\n'.format(self.__graph_file,
                                                                                                         element.get_id(),
                                                                                                         state_name))
                    full_name = element.get_qualified_name().replace('::', '_')
                    if full_name in uniq_states:
                        raise ParserError('The graph {} has two states with the same qualfied name {}!\n'.format(self.__graph_file,
                                                                                                                 full_name))
                    uniq_states.add(full_name)
                    for a in element.get_actions():
                        if a.get_type() == CyberiadaML.actionTransition:
                            if len(a.get_trigger()) == 0:
                                raise ParserError('The graph {} has state {} with empty trigger in int.trans.!\n'.format(self.__graph_file,
                                                                                                                         element.get_id()))
                            self.__check_trigger_and_behavior(full_name, a.get_trigger(), a.get_guard(), a.get_behavior())
                            self.__signals[self.__parse_trigger(a.get_trigger())[0]] = None
                            self.__local_transitions.append(element)
                        else:
                            self.__check_trigger_and_behavior(full_name, None, None, a.get_behavior())
            if self.__initial is None:
                raise ParserError('The game graph {} has no initial state!\n'.format(self.__graph_file))

            self.__initial_states = {}
            # init_parent = self.__initial.get_parent()
            # if init_parent.get_type() != CyberiadaML.elementSM:
            #     self.__initial_states[init_parent.get_id()] = self.__initial.get_id()
            for element in self.__graph.find_elements_by_type(CyberiadaML.elementInitial):
                if element.get_id() in self.__initial_states:
                    continue
                for t in self.__transitions:
                    if t.get_source_element_id() == element.get_id():
                        parent = element.get_parent()
                        self.__initial_states[parent.get_id()] = element.get_target_element_id()
                        break
            for element in self.__graph.find_elements_by_type(CyberiadaML.elementCompositeState):
                if element.get_id() in self.__initial_states:
                    continue
                self.__initial_states[element.get_id()] = element.get_children()[0].get_id()

            for s in self.__signals:
                if s not in STANDARD_EVENTS:
                    self.__signals[s] = s[0].upper() + s[1:].lower()
            for s, v in STANDARD_EVENTS.items():
                self.__signals[s] = 'self.' + v

        except CyberiadaML.Exception as e:
            raise ParserError('Unexpected CyberiadaML exception: {}\n{}\n'.format(e.__class__,
                                                                                  traceback.format_exc()))
    def __check_trigger_and_behavior(self, context, trigger, guard, behavior):
        pass

    @classmethod
    def __w(cls, f, s):
        f.write(s)
    @classmethod
    def __w4(cls, f, s):
        f.write(' ' * 4 + s)
    @classmethod
    def __w8(cls, f, s):
        f.write(' ' * 8 + s)

    @classmethod
    def __insert_file(cls, f, filename):
        with open(filename) as input_file:
            for line in input_file.readlines():
                cls.__w(f, line)

    def __write_technical_info(self, f):
        self.__w(f, '# The SM class {} based on {} file\n'.format(self.__sm_name_cap, self.__graph_file))
        self.__w(f, '# Generated by HSM-to-Python script version {}\n\n'.format(self.VERSION))

    def __write_global_init(self, f):
        if self.__global_init:
            self.__w(f, '\n# Global Initializations:\n')
            self.__w(f, '\n'.join(self.__global_init) + '\n')

    def __write_class(self, f):
        self.__w(f, '\nclass {}:\n'.format(self.__sm_name_cap))

    def __write_constructor(self, f):
        var_pairs = map(lambda i: '{}={}'.format(*i),
                        sorted(self.__sm_variables.items(), key=lambda x: x[0]))
        self.__w(f, '\n')
        self.__w4(f, 'def __init__(self, {}):\n'.format(', '.join(var_pairs)))
        for var in self.__sm_variables:
            self.__w8(f, 'self.{var} = {var}\n'.format(var=var))
        self.__w8(f, 'self.__sm = pysm.StateMachine("{}")\n'.format(self.__sm_name))
        self.__w8(f, 'self.__terminated = False')
        if self.__use_ticks:
            self.__init_tick(f)
        self.__w8(f, 'self.__event_queue = []')

    @classmethod
    def __get_state_name(cls, state):
        return state.get_qualified_name().replace('::', '_')
    @classmethod
    def __parse_trigger(cls, trigger):
        if trigger.find('(') > 0:
            idx1 = trigger.find('(')
            idx2 = trigger.find(')')
            return trigger[0:idx1], trigger[idx1+1:idx2]
        return trigger, None

    def __write_entry_handler(self, f, state_name, entry, behavior):
        handler_name = 'on_st_{}_{}'.format(state_name, entry)
        if state_name not in self.__handlers:
            self.__handlers[state_name] = {}
        if entry not in self.__handlers[state_name]:
            self.__handlers[state_name][entry] = 'self.' + handler_name
        self.__w(f, '\n')
        self.__w4(f, 'def {}(self, *_):\n'.format(handler_name))
        # self.__w4(f, 'def {}(self, state, event):\n'.format(handler_name))
        for line in behavior.split('\n'):
            self.__w8(f, line + '\n')

    def __write_entries_recursively(self, f, state):
        for a in state.get_actions():
            if a.get_type() == CyberiadaML.actionEntry:
                self.__write_entry_handler(f, self.__get_state_name(state), 'enter', a.get_behavior())
            elif a.get_type() == CyberiadaML.actionExit:
                self.__write_entry_handler(f, self.__get_state_name(state), 'exit', a.get_behavior())
        for ch in state.get_children():
            if ch.get_type() in (CyberiadaML.elementSimpleState, CyberiadaML.elementCompositeState):
                self.__write_entries_recursively(f, ch)

    def __write_entries(self, f):
        self.__w(f, '\n')
        self.__w4(f, '# Entry & Exit Handlers:\n')
        for ch in self.__graph.get_children():
            if ch.get_type() in (CyberiadaML.elementSimpleState, CyberiadaML.elementCompositeState):
                self.__write_entries_recursively(f, ch)

    @classmethod
    def __write_guard_handler(cls, f, trigger_name, condition, argument):
        handler_name = "is_{}".format(trigger_name)
        cls.__w(f, '\n')
        # cls.__w4(f, "def {}(self, state, event):\n".format(handler_name))
        cls.__w4(f, "def {}(self, *_):\n".format(handler_name))
        if argument:
            cls.__w8(f, '{} = event.cargo["value"]\n'.format(argument))
        cls.__w8(f, 'return ({})\n'.format(condition))

    @classmethod
    def __write_trigger_action(cls, f, trigger_name, behavior, argument):
        handler_name = "on_{}".format(trigger_name)
        cls.__w(f, '\n')
        # cls.__w4(f, 'def {}(self, state, event):\n'.format(handler_name))
        cls.__w4(f, 'def {}(self, *_):\n'.format(handler_name))
        if argument:
            cls.__w8(f, '{} = event.cargo["value"]\n'.format(argument))
        for line in behavior.split('\n'):
            cls.__w8(f, line + '\n')

    def __write_guards_recursively(self, f, state):
        handlers = {}
        # internal triggers
        for a in state.get_actions():
            if a.get_type() == CyberiadaML.actionTransition:
                name, argument = self.__parse_trigger(a.get_trigger())
                trigger_name = '{}_{}'.format(self.__get_state_name(state), name)
                if trigger_name not in handlers:
                    handlers[trigger_name] = 1
                else:
                    handlers[trigger_name] += 1
                    trigger_name += '_{}'.format(handlers[trigger_name])
                if a.has_guard():
                    self.__write_guard_handler(f, trigger_name, a.get_guard(), argument)
                if a.has_behavior():
                    self.__write_trigger_action(f, trigger_name, a.get_behavior(), argument)

        # external triggers
        for t in self.__transitions:
            if t.get_source_element_id() != state.get_id():
                continue
            target = self.__graph.find_element_by_id(t.get_target_element_id())
            if target.get_type() == CyberiadaML.elementFinal:
                target_name = 'terminate'
            else:
                target_name = self.__get_state_name(target)
            a = t.get_action()
            if a.has_trigger():
                name, argument = self.__parse_trigger(a.get_trigger())
            else:
                name, argument = TICK_EVENT, None
            trigger_name = '{}_TO_{}_{}'.format(self.__get_state_name(state),
                                                target_name,
                                                name)
            if trigger_name not in handlers:
                handlers[trigger_name] = 1
            else:
                handlers[trigger_name] += 1
                trigger_name += '_{}'.format(handlers[trigger_name])
            if a.has_guard():
                self.__write_guard_handler(f, trigger_name, a.get_guard(), argument)
            if a.has_behavior():
                self.__write_trigger_action(f, trigger_name, a.get_behavior(), argument)

        for ch in state.get_children():
            if ch.get_type() in (CyberiadaML.elementSimpleState, CyberiadaML.elementCompositeState):
                self.__write_guards_recursively(f, ch)

    def __write_guards(self, f):
        self.__w(f, '\n')
        self.__w4(f, "# Transition Conditions and Actions:\n")
        if self.__initial_behavior:
            self.__write_trigger_action(f, "initial", self.__initial_behavior, None)
        for ch in self.__graph.get_children():
            if ch.get_type() in (CyberiadaML.elementSimpleState, CyberiadaML.elementCompositeState):
                self.__write_guards_recursively(f, ch)

    def __write_handlers(self, f, state_name):
        if state_name not in self.__handlers:
            return
        handlers_str = map(lambda i: '"{}": {}'.format(*i), self.__handlers[state_name].items())
        self.__w8(f, 'st_{}.handlers = '.format(state_name) +
                  '{' + ', '.join(handlers_str) + '}\n')

    def __write_states(self, f):
        self.__w(f, '\n')
        self.__w8(f, '# Hierarchical States:\n')
        self.__w8(f, 'st_initial = pysm.State("initial")\n')
        self.__w8(f, 'self.__sm.add_state(st_initial, initial=True)\n')
        if self.__final_states:
            self.__w8(f, 'st_terminate = pysm.State("terminate")\n')
            self.__w8(f, 'self.__sm.add_state(st_terminate)\n')
            self.__w8(f, 'st_terminate.handlers = {"enter": self.terminate}\n')
        for ch in self.__graph.get_children():
            if ch.get_type() in (CyberiadaML.elementSimpleState, CyberiadaML.elementCompositeState):
                self.__write_states_recursively(f, ch, 'self.__sm', ch.get_id() == self.__initial.get_id())

    def __write_states_recursively(self, f, state, parent_var, initial):
        state_name = self.__get_state_name(state)
        state_var = 'st_{}'.format(state_name)
        if state.get_type() == CyberiadaML.elementCompositeState:
            sm_class = "StateMachine"
        else:
            sm_class = "State"
        self.__w8(f, '{} = pysm.{}("{}")\n'.format(state_var, sm_class, state_name))
        self.__w8(f, '{}.add_state({}{})\n'.format(parent_var, state_var,
                                                   ', initial=True' if initial else ''))
        self.__write_handlers(f, state_name)
        if state.get_type() == CyberiadaML.elementCompositeState:
            initial_id = self.__initial_states[state.get_id()]
            for ch in state.get_children():
                if ch.get_type() in (CyberiadaML.elementSimpleState, CyberiadaML.elementCompositeState):
                    self.__write_states_recursively(f, ch, state_var, ch.get_id() == initial_id)

    def __write_events(self, f):
        self.__w(f, '\n')
        self.__w8(f, '# Events:\n\n')
        for s, v in self.__signals.items():
            self.__w8(f, '{} = "{}"\n'.format(v, s))
            self.__w8(f, '{ev}Event = pysm.Event({ev})\n'.format(ev=v))
        signals_str = map(lambda i: '"{}": {}Event'.format(*i), self.__signals.items())
        self.__w8(f, 'self.__events = {{{}}}\n'.format(', '.join(signals_str)))

    def __write_transitions(self, f):
        self.__w(f, '\n')
        self.__w8(f, '# Internal transitions:\n\n')
        for state in self.__local_transitions:
            handlers = {}
            for a in state.get_actions():
                if a.get_type() == CyberiadaML.actionTransition:
                    state_name = self.__get_state_name(state)
                    name, _ = self.__parse_trigger(a.get_trigger())
                    trigger_name = '{}_{}'.format(state_name, name)
                    if trigger_name not in handlers:
                        handlers[trigger_name] = 1
                    else:
                        handlers[trigger_name] += 1
                        trigger_name += '_{}'.format(handlers[trigger_name])
                    parts = ['st_{}'.format(self.__get_state_name(state)),
                             'None',
                             'events=[{}]'.format(self.__signals[name])]
                    if a.has_guard():
                        parts.append('condition=self.is_{}'.format(trigger_name))
                    if a.has_behavior():
                        parts.append('action=self.on_{}'.format(trigger_name))
                    parent = state.get_parent()
                    if parent.get_type() == CyberiadaML.elementSM:
                        owner = 'self.__sm'
                    else:
                        owner = 'st_{}'.format(self.__get_state_name(parent))
                    self.__w8(f, '{}.add_transition({})\n'.format(owner, ', '.join(parts)))

        self.__w(f, '\n')
        self.__w8(f, '# External transitions:\n\n')
        parts = ['st_initial',
                 'st_{}'.format(self.__get_state_name(self.__initial)),
                 'events=[self.Init]']
        if self.__initial_behavior:
            parts.append('action=self.on_initial')
        self.__w8(f, 'self.__sm.add_transition({})\n'.format(', '.join(parts)))

        # external triggers
        handlers = {}
        for t in self.__transitions:
            source = self.__graph.find_element_by_id(t.get_source_element_id())
            source_name = self.__get_state_name(source)
            if source_name not in handlers:
                handlers[source_name] = {}
            target = self.__graph.find_element_by_id(t.get_target_element_id())
            if target.get_type() == CyberiadaML.elementFinal:
                target_name = 'terminate'
            else:
                target_name = self.__get_state_name(target)
            a = t.get_action()
            if a.has_trigger():
                name, _ = self.__parse_trigger(a.get_trigger())
            else:
                name, _ = TICK_EVENT, None
            trigger_name = '{}_TO_{}_{}'.format(source_name,
                                                target_name,
                                                name)
            if trigger_name not in handlers:
                handlers[trigger_name] = 1
            else:
                handlers[trigger_name] += 1
                trigger_name += '_{}'.format(handlers[trigger_name])
            parts = ['st_{}'.format(source_name),
                     'st_{}'.format(target_name),
                     'events=[{}]'.format(self.__signals[name])]
            if a.has_guard():
                parts.append('condition=self.is_{}'.format(trigger_name))
            if a.has_behavior():
                parts.append('action=self.on_{}'.format(trigger_name))
            parent = source.get_parent()
            if parent.get_type() == CyberiadaML.elementSM:
                owner = 'self.__sm'
            else:
                owner = 'st_{}'.format(self.__get_state_name(parent))
            self.__w8(f, '{}.add_transition({})\n'.format(owner, ', '.join(parts)))

    def __write_standard_functions(self, f):
        self.__w(f, '\n')
        self.__w4(f, 'def initialize(self):\n')
        if self.__use_ticks:
            self.__w8(f, 'self.__time = self.__prev_time = time.time()\n')
        self.__w8(f, 'self.__sm.initialize()\n')
        self.__w8(f, 'self.__sm.dispatch(self.InitEvent)\n')
        self.__w(f, '\n')
        self.__w4(f, 'def dispatch(self, eventstr=None, arg=None):\n')
        if self.__use_ticks:
            self.__dispatch_tick(f)
        self.__w8(f, 'if eventstr is not None and eventstr in self.__events:\n')
        self.__w8(f, '    if arg is None:\n')
        self.__w8(f, '        self.__sm.dispatch(self.__events[eventstr])\n')
        self.__w8(f, '    else:\n')
        self.__w8(f, '        args = {"value": arg}\n')
        self.__w8(f, '        self.__sm.dispatch(pysm.Event(eventstr, **args))\n')
        self.__w8(f, 'while self.__event_queue:\n')
        self.__w8(f, '    eventstr = self.__event_queue.pop(0)\n')
        self.__w8(f, '    if eventstr in self.__events:\n')
        self.__w8(f, '        self.__sm.dispatch(self.__events[eventstr])\n')
        
        self.__w(f, '\n')
        self.__w4(f, 'def loop(self):\n')
        self.__w8(f, 'while not self.__terminated:\n')
        for l in self.__loop:
            self.__w8(f, '    {}\n'.format(l))
        if self.__use_ticks:
            self.__w8(f, '    self.dispatch()\n')
            self.__w8(f, '    time.sleep(self.__sleep_len)\n')
        self.__w(f, '\n')
        self.__w4(f, 'def terminate(self, *_):\n')
        self.__w8(f, 'self.__terminated = True\n')
        if self.__exit_on_term:
            self.__w8(f, 'sys.exit(0)\n')
        self.__w(f, '\n')
        self.__w4(f, 'def push_event(self, event):\n')
        self.__w8(f, 'self.__event_queue.append(event)\n')

    def __write_running_loop(self, f):
        self.__w(f, '\n')
        self.__w(f, '{} = {}()\n'.format(self.__sm_name, self.__sm_name_cap))
        self.__w(f, '{}.initialize()\n'.format(self.__sm_name))
        self.__w(f, '{}.loop()\n'.format(self.__sm_name))

    def __write_external_dispacth(self, f):
        self.__w(f, '\n')
        self.__w(f, 'def DISPATCH(event):\n')
        self.__w4(f, '{}.push_event(event)\n'.format(self.__sm_name))

    def __init_tick(self, f):
        self.__w8(f, '# Tick events constants & variables\n')
        self.__w8(f, 'self.__time = self.__prev_time = self.__tick = self.__tick_1s = 0\n')
        self.__w8(f, 'self.__tick_len = TICK_LEN / 1000.0\n')
        if self.__generate_loop:
            self.__w8(f, 'self.__sleep_len = self.__tick_len\n')

    def __dispatch_tick(self, f):
        self.__w8(f, '# Check tick events\n')
        self.__w8(f, 'self.__time = time.time()\n')
        self.__w8(f, 'timedelta = self.__time - self.__prev_time\n')
        self.__w8(f, 'self.__prev_time = self.__time\n')
        self.__w8(f, 'self.__tick += timedelta\n')
        self.__w8(f, 'self.__tick_1s += timedelta\n')
        self.__w8(f, 'if self.__tick >= self.__tick_len:\n')
        self.__w8(f, '    while self.__tick >= self.__tick_len:\n')
        self.__w8(f, '        self.__tick -= self.__tick_len\n')
        self.__w8(f, '    self.__sm.dispatch(self.TickEvent)\n')
        self.__w8(f, 'if self.__tick_1s >= 1.0:\n')
        self.__w8(f, '    while self.__tick_1s >= 1.0:\n')
        self.__w8(f, '        self.__tick_1s -= 1.0\n')
        self.__w8(f, '    self.__sm.dispatch(self.Tick1SecEvent)\n')

    def __insert_python_modules(self, f, basepath):
        path = os.path.dirname(os.path.abspath(basepath))
        modules = {}
        self.__w(f, '\n#Init script code:\n\n')
        for name in self.__init_scripts:
            if name.find('.py') < 0:
                continue
            filename = os.path.join(path, name)
            if not os.path.isfile(filename):
                raise GeneratorError('Cannot open impotred Python file {}'.format(filename))
            self.__w(f, '# code imported from {}\n'.format(name))
            self.__insert_file(f, filename)

    def generate_code(self, target=None):
        if target is not None:
            _f = open(target, 'w')
        else:
            _f = sys.stdout

        self.__write_technical_info(_f)
        self.__insert_file(_f, HEADER_TEMPLATE)
        self.__write_global_init(_f)
        self.__write_class(_f)
        self.__write_entries(_f)
        self.__write_guards(_f)
        self.__write_constructor(_f)
        self.__write_events(_f)
        self.__write_states(_f)
        self.__write_transitions(_f)
        self.__write_standard_functions(_f)
        self.__insert_python_modules(_f, self.__graph_file)
        if self.__generate_loop:
            self.__write_external_dispacth(_f)
            self.__write_running_loop(_f)
        self.__insert_file(_f, FOOTER_TEMPLATE)

        if target is not None:
            _f.close()
