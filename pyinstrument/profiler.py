# -*- coding: utf-8 -*-
import timeit
import warnings, time, sys
from pyinstrument import renderers
from pyinstrument.session import ProfilerSession
from pyinstrument.util import object_with_import_path, deprecated
from pyinstrument_cext import setstatprofile

try:
    from time import process_time
except ImportError:
    process_time = None

timer = timeit.default_timer


class NotMainThreadError(Exception):
    '''deprecated as of 0.14'''
    pass


class SignalUnavailableError(Exception):
    '''deprecated as of 0.14'''
    pass


class Profiler(object):
    def __init__(self, interval=0.001, use_signal=None, recorder=None):
        if use_signal is not None:
            warnings.warn('use_signal is deprecated and should no longer be used.', 
                          DeprecationWarning,
                          stacklevel=2)
        if recorder is not None:
            warnings.warn('recorder is deprecated and should no longer be used.',
                          DeprecationWarning,
                          stacklevel=2)

        self.interval = interval
        self.last_profile_time = 0.0
        self.frame_records = []
        self._start_time = None
        self._start_process_time = None
        self.last_session = None

    def start(self):
        self.last_profile_time = timer()
        self._start_time = time.time()

        if process_time:
            self._start_process_time = process_time()

        setstatprofile(self._profile, self.interval)

    def stop(self):
        setstatprofile(None)
        if process_time:
            cpu_time = process_time() - self._start_process_time
            self._start_process_time = None
        else:
            cpu_time = None

        self.last_session = ProfilerSession(
            frame_records=self.frame_records,
            start_time=self._start_time,
            duration=time.time() - self._start_time,
            sample_count=len(self.frame_records),
            program=' '.join(sys.argv),
            cpu_time=cpu_time,
        )
        return self.last_session

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    # pylint: disable=W0613
    def _profile(self, frame, event, arg):
        now = timer()
        time_since_last_profile = now - self.last_profile_time

        if time_since_last_profile < self.interval:
            return

        if event == 'call':
            frame = frame.f_back

        self.frame_records.append((self._call_stack_for_frame(frame), time_since_last_profile))

        self.last_profile_time = now

    def _call_stack_for_frame(self, frame):
        call_stack = []

        while frame is not None:
            identifier = '%s\x00%s\x00%i' % (
                frame.f_code.co_name, frame.f_code.co_filename, frame.f_code.co_firstlineno
            )
            call_stack.append(identifier)
            frame = frame.f_back

        # we iterated from the leaf to the root, we actually want the call stack
        # starting at the root, so reverse this array
        call_stack.reverse()
        return call_stack

    @deprecated
    def root_frame(self):
        if self.last_session:
            return self.last_session.root_frame()

    @deprecated
    def first_interesting_frame(self):
        """
        Traverse down the frame hierarchy until a frame is found with more than one child
        """
        root_frame = self.root_frame()
        frame = root_frame

        while len(frame.children) <= 1:
            if frame.children:
                frame = frame.children[0]
            else:
                # there are no branches
                return root_frame

        return frame

    @deprecated
    def starting_frame(self, root=False):
        if root:
            return self.root_frame()
        else:
            return self.first_interesting_frame()

    def output_text(self, root=None, unicode=False, color=False):
        return renderers.ConsoleRenderer(unicode=unicode, color=color).render(self.last_session)

    def output_html(self, root=None):
        return renderers.HTMLRenderer().render(self.last_session)

    def output(self, renderer, root=None):
        return renderer.render(self.last_session)
