#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This module contains methods for parsing matchfiles

TODO
----
* Add PerformanceTimeline?
* Allow for creating Notes and other elements from matchlines
"""
import re
import numpy as np
from fractions import Fraction

import logging
import warnings


__all__ = ['load_match']
LOGGER = logging.getLogger(__name__)

rational_pattern = re.compile('^([0-9]+)/([0-9]+)$')
LATEST_VERSION = 5.0

PITCH_CLASSES = [('C', 'n'), ('C', '#'), ('D', 'n'), ('D', '#'), ('E', 'n'), ('F', 'n'),
                 ('F', '#'), ('G', 'n'), ('G', '#'), ('A', 'n'), ('A', '#'), ('B', 'n')]

PC_DICT = dict(zip(range(12), PITCH_CLASSES))

NOTE_NAMES = ['C', 'D', 'E', 'F', 'G', 'A', 'B']

LATEST_VERSION = 5.0

# Ignore enharmonic keys above A# Maj (no E# Maj!)
KEY_SIGNATURES = {0: ('C', 'A'), 1: ('G', 'E'), 2: ('D', 'B'), 3: ('A', 'F#'),
                  4: ('E', 'C#'), 5: ('B', 'G#'), 6: ('F#', 'D#'), 7: ('C#', 'A#'),
                  8: ('G#', 'E#'), 9: ('D#', 'B#'), 10: ('A#', 'F##'),
                  -1: ('F', 'D'), -2: ('Bb', 'G'), -3: ('Eb', 'C'), -4: ('Ab', 'F'),
                  -5: ('Db', 'Bb'), -6: ('Gb', 'Eb'), -7: ('Cb', 'Ab')}


class MatchError(Exception):
    pass


def pitch_name_2_midi_PC(modifier, name, octave):
    """
    To be replaced!
    """
    if name == 'r':
        return (0, 0)
    base_class = ({'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}[name.lower()] +
                  {'b': -1, 'bb': -2, '#': 1, 'x': 2, '##': 2, 'n': 0}[modifier])
    mid = (octave + 1) * 12 + base_class
    # for mozartmatch files (in which the octave numbers are off by one)
    # mid = octave*12 + base_class
    pitchclass = np.mod(base_class, 12)
    return (mid, pitchclass)


def interpret_field(data):
    """
    Convert data to int, if not possible, to float, otherwise return
    data itself.

    Parameters
    ----------
    data : object
       Some data object

    Returns
    -------
    data : int, float or same data type as the input
       Return the data object casted as an int, float or return
       data itself.
    """

    try:
        return int(data)
    except ValueError:
        try:
            return float(data)
        except ValueError:
            return data


class ParseRationalException(Exception):
    def __init__(self, string):
        self.string = string

    def __str__(self):
        return 'Could not parse string "{0}"'.format(self.string)


class Ratio:
    def __init__(self, string):
        try:
            self.numerator, self.denominator = [
                int(i) for i in string.split('/')]
        except:
            raise ParseRationalException(string)


def interpret_field_rational(data, allow_additions=False):
    """Convert data to int, if not possible, to float, if not possible
    try to interpret as rational number and return it as float, if not
    possible, return data itself."""
    global rational_pattern
    v = interpret_field(data)
    if type(v) == str:
        m = rational_pattern.match(v)
        if m:
            groups = m.groups()
            return float(groups[0]) / float(groups[1])
        else:
            if allow_additions:
                parts = v.split('+')
                if len(parts) > 1:
                    iparts = [interpret_field_rational(
                        i, allow_additions=False) for i in parts]
                    # to be replaced with isinstance(i,numbers.Number)
                    if all(type(i) in (int, float) for i in iparts):
                        return sum(iparts)
                    else:
                        return v
                else:
                    return v
            else:
                return v
    else:
        return v

###################################################


class MatchLine(object):

    out_pattern = ''
    field_names = []
    re_obj = re.compile('')
    field_interpreter = interpret_field_rational

    def __str__(self):
        r = [self.__class__.__name__]
        for fn in self.field_names:
            r.append(' {0}: {1}'.format(fn, self.__dict__[fn]))
        return '\n'.join(r) + '\n'

    @property
    def matchline(self):
        raise NotImplementedError

    @classmethod
    def match_pattern(cls, s, pos=0):
        return cls.re_obj.search(s, pos=pos)

    @classmethod
    def from_matchline(cls, matchline, pos=0):
        match_pattern = cls.re_obj.search(matchline, pos)

        if match_pattern is not None:

            groups = [cls.field_interpreter(i) for i in match_pattern.groups()]
            kwargs = dict(zip(cls.field_names, groups))

            match_line = cls(**kwargs)

            return match_line

        else:
            raise MatchError('Input match line does not fit the expected pattern.')


class MatchInfo(MatchLine):
    out_pattern = 'info({Attribute},{Value}).'
    field_names = ['Attribute', 'Value']
    pattern = 'info\(\s*([^,]+)\s*,\s*(.+)\s*\)\.'
    re_obj = re.compile(pattern)

    def __init__(self, Attribute, Value):
        self.Attribute = Attribute
        self.Value = Value

    @property
    def matchline(self):
        return self.out_pattern.format(
            Attribute=self.Attribute,
            Value=self.Value)


class MatchMeta(MatchLine):

    out_pattern = 'meta({Attribute},{Value},{Bar},{TimeInBeats}).'
    field_names = ['Attribute', 'Value', 'Bar', 'TimeInBeats']
    pattern = 'meta\(\s*([^,]*)\s*,\s*([^,]*)\s*,\s*([^,]*)\s*,\s*([^,]*)\s*\)\.'
    re_obj = re.compile(pattern)

    def __init__(self, Attribute, Value, Bar, TimeInBeats):
        self.Attribute = Attribute
        self.Value = Value
        self.Bar = Bar
        self.TimeInBeats = TimeInBeats

    @property
    def matchline(self):
        return self.out_pattern.format(
            Attribute=self.Attribute,
            Value=self.Value,
            Bar=self.Bar,
            TimeInBeats=self.TimeInBeats)


class MatchSnote(MatchLine):
    """
    Class representing a score note
    """

    out_pattern = ('snote({Anchor},[{NoteName},{Modifier}],{Octave},'
               + '{Bar}:{Beat},{Offset},{Duration},'
               + '{OnsetInBeats},{OffsetInBeats},'
                   + '[{ScoreAttributesList}])')

    pattern = 'snote\(([^,]+),\[([^,]+),([^,]+)\],([^,]+),([^,]+):([^,]+),([^,]+),([^,]+),([^,]+),([^,]+),\[(.*)\]\)'
    re_obj = re.compile(pattern)

    field_names = ['Anchor', 'NoteName', 'Modifier', 'Octave',
                   'Bar', 'Beat', 'Offset', 'Duration',
                   'OnsetInBeats', 'OffsetInBeats', 'ScoreAttributesList']

    def __init__(self, Anchor, NoteName, Modifier, Octave, Bar, Beat,
                 Offset, Duration, OnsetInBeats, OffsetInBeats,
                 ScoreAttributesList=[]):

        self.Anchor = Anchor
        self.NoteName = NoteName
        self.Modifier = Modifier
        self.Octave = int(Octave)
        self.Bar = Bar
        self.Beat = Beat
        self.Offset = Offset
        self.Duration = Duration
        self.OnsetInBeats = OnsetInBeats
        self.OffsetInBeats = OffsetInBeats

        if isinstance(ScoreAttributesList, (list, tuple, np.ndarray)):
            # Always cast ScoreAttributesList as list?
            self.ScoreAttributesList = list(ScoreAttributesList)
        elif isinstance(ScoreAttributesList, str):
            self.ScoreAttributesList = ScoreAttributesList.split(',')
        else:
            raise ValueError('`ScoreAttributesList` must be a list or a string')

    @property
    def DurationInBeats(self):
        return self.OffsetInBeats - self.OnsetInBeats

    @property
    def DurationSymbolic(self):
        if isinstance(self.Duration, (float, int)):
            return str(Fraction.from_float(self.Duration))
        elif isinstance(self.Duration, str):
            return self.Duration

    @property
    def MidiPitch(self):
        return pitch_name_2_midi_PC(self.Modifier, self.NoteName, self.Octave)

    @property
    def matchline(self):
        return self.out_pattern.format(
            Anchor=self.Anchor,
            NoteName=self.NoteName,
            Modifier=self.Modifier,
            Octave=self.Octave,
            Bar=self.Bar,
            Beat=self.Beat,
            Offset=str(Fraction.from_float(self.Offset)),
            Duration=self.DurationSymbolic,
            OnsetInBeats=self.OnsetInBeats,
            OffsetInBeats=self.OffsetInBeats,
            ScoreAttributesList=','.join(self.ScoreAttributesList))


class MatchPnote(MatchLine):
    """
    Class representing the performed note part of a match line
    """
    out_pattern = ('note({Number},[{NoteName},{Modifier}],'
                   + '{Octave},{Onset},{Offset},{AdjOffset},{Velocity})')

    field_names = ['Number', 'NoteName', 'Modifier', 'Octave',
                   'Onset', 'Offset', 'AdjOffset', 'Velocity']
    pattern = 'note\(([^,]+),\[([^,]+),([^,]+)\],([^,]+),([^,]+),([^,]+),([^,]+),([^,]+)\)'

    re_obj = re.compile(pattern)

    # For backwards compatibility with Matchfile Version 1
    field_names_v1 = ['Number', 'NoteName', 'Modifier', 'Octave',
                      'Onset', 'Offset', 'Velocity']
    pattern_v1 = 'note\(([^,]+),\[([^,]+),([^,]+)\],([^,]+),([^,]+),([^,]+),([^,]+)\)'
    re_obj_v1 = re.compile(pattern_v1)

    def __init__(self, Number, NoteName, Modifier,
                 Octave, Onset, Offset, AdjOffset,
                 Velocity, MidiPitch=None, version=LATEST_VERSION):

        self.Number = Number

        # check if all pitch spelling information was provided
        has_pitch_spelling = not (
            NoteName is None or Modifier is None or Octave is None)

        # check if the MIDI pitch of the note was provided
        has_midi_pitch = MidiPitch is not None

        # Raise an error if neither pitch spelling nor MIDI pitch were provided
        if not has_pitch_spelling and not has_midi_pitch:
            raise ValueError('No note height information provided!')

        # Set attributes regarding pitch spelling
        if has_pitch_spelling:
            # Ensure that note name is uppercase
            if NoteName.upper() in NOTE_NAMES:
                self.NoteName = NoteName.upper()
            else:
                raise ValueError(
                    'Invalid note name. Should be in {0}'.format(','.join(NOTE_NAMES)))

            self.Modifier = Modifier
            self.Octave = int(Octave)

        else:
            # infer the pitch information from the MIDI pitch
            # Note that this is just a dummy method, and does not correspond to
            # musically correct pitch spelling.
            self.NoteName, self.Modifier = PC_DICT[int(np.mod(MidiPitch, 12))]
            self.Octave = int(MidiPitch // 12 - 1)

        # Check if the provided MIDI pitch corresponds to the correct pitch spelling
        if has_midi_pitch:
            if MidiPitch != pitch_name_2_midi_PC(self.Modifier,
                                                 self.NoteName,
                                                 self.Octave)[0]:
                raise ValueError('The provided pitch spelling information does not match '
                                 'the given MIDI pitch!')

            else:
                # Set the Midi pitch
                self.MidiPitch = (int(MidiPitch), int(np.mod(MidiPitch, 12)))

        self.Onset = Onset
        self.Offset = Offset
        self.AdjOffset = AdjOffset

        if AdjOffset is None:
            # Raise warning!
            self.AdjOffset = self.Offset

        self.Velocity = int(Velocity)

        # TODO
        # * check version and update necessary patterns
        self.version = version

    @property
    def matchline(self):
        return self.out_pattern.format(
            Number=self.Number,
            NoteName=self.NoteName,
            Modifier=self.Modifier,
            Octave=self.Octave,
            Onset=self.Onset,
            Offset=self.Offset,
            AdjOffset=self.AdjOffset,
            Velocity=self.Velocity)

    @property
    def Duration(self):
        return self.Offset - self.Onset

    def AdjDuration(self):
        return self.AdjOffset - self.Onset

    @classmethod
    def from_matchline(cls, matchline, pos=0):
        """Create a MatchPnote from a line

        """
        match_pattern = cls.re_obj.search(matchline, pos)

        if match_pattern is None:
            match_pattern = cls.re_obj_v1.search(matchline, pos)

            if match_pattern is not None:
                groups = [cls.field_interpreter(i) for i in match_pattern.groups()]
                kwargs = dict(zip(cls.field_names_v1, groups))
                kwargs['version'] = 1.0
                kwargs['AdjOffset'] = None
                match_line = cls(**kwargs)

                return match_line
            else:
                raise MatchError('Input matchline does not fit expected pattern')

        else:
            groups = [cls.field_interpreter(i) for i in match_pattern.groups()]
            kwargs = dict(zip(cls.field_names, groups))
            match_line = cls(**kwargs)
            return match_line


class MatchSnoteNote(MatchLine):
    """
    Class representing a "match" (containing snote and note)

    TODO:
    * More readable __str__ method

    """

    out_pattern = '{SnoteLine}-{NoteLine}.'
    pattern = MatchSnote.pattern + '-' + MatchPnote.pattern
    re_obj = re.compile(pattern)
    field_names = MatchSnote.field_names + MatchPnote.field_names

    # for version 1
    pattern_v1 = MatchPnote.pattern + '-' + MatchPnote.pattern_v1
    re_obj_v1 = re.compile(pattern_v1)
    field_names_v1 = MatchSnote.field_names + MatchPnote.field_names_v1

    def __init__(self, snote, note, same_pitch_spelling=True):
        self.snote = snote
        self.note = note

        # Set the same pitch spelling in both note and snote
        # (this can break if the snote is not exactly matched
        # to a note with the same pitch). Handle with care.
        if same_pitch_spelling:
            self.note.NoteName = self.snote.NoteName
            self.note.Modifier = self.snote.Modifier
            self.note.Octave = self.snote.Octave

    @property
    def matchline(self):
        return self.out_pattern.format(
            SnoteLine=self.snote.matchline,
            NoteLine=self.note.matchline)

    @classmethod
    def from_matchline(cls, matchline, pos=0):
        match_pattern = cls.re_obj.search(matchline, pos=0)

        if match_pattern is None:
            match_pattern = cls.re_obj_v1.search(matchline, pos)

            if match_pattern is not None:
                groups = [cls.field_interpreter(i) for i in match_pattern.groups()]

                snote_kwargs = dict(zip(MatchSnote.field_names,
                                        groups[:len(MatchSnote.field_names)]))
                note_kwargs = dict(zip(MatchPnote.field_names_v1,
                                       groups[len(MatchSnote.field_names):]))
                note_kwargs['version'] = 1.0
                note_kwargs['AdjOffset'] = None
                snote = MatchSnote(**snote_kwargs)
                note = MatchPnote(**note_kwargs)
                match_line = cls(snote=snote,
                                 note=note)

                return match_line
            else:
                raise MatchError('Input matchline does not fit expected pattern')

        else:
            groups = [cls.field_interpreter(i) for i in match_pattern.groups()]
            snote_kwargs = dict(zip(MatchSnote.field_names,
                                    groups[:len(MatchSnote.field_names)]))
            note_kwargs = dict(zip(MatchPnote.field_names,
                                   groups[len(MatchSnote.field_names):]))
            snote = MatchSnote(**snote_kwargs)
            note = MatchPnote(**note_kwargs)
            match_line = cls(snote=snote,
                             note=note)
            return match_line

    def __str__(self):
        # TODO:
        # Nicer print?
        return str(self.snote) + '\n' + str(self.note)


class MatchSnoteDeletion(MatchLine):
    out_pattern = '{SnoteLine}-deletion.'
    pattern = MatchSnote.pattern + '-deletion\.'
    re_obj = re.compile(pattern)
    field_names = MatchSnote.field_names

    def __init__(self, snote):
        self.snote = snote

    @property
    def matchline(self):
        return self.out_pattern.format(
            SnoteLine=self.snote.matchline)

    @classmethod
    def from_matchline(cls, matchline, pos=0):
        match_pattern = cls.re_obj.search(matchline, pos=0)

        if match_pattern is not None:
            groups = [cls.field_interpreter(i) for i in match_pattern.groups()]
            snote_kwargs = dict(zip(MatchSnote.field_names, groups))
            snote = MatchSnote(**snote_kwargs)
            match_line = cls(snote=snote)
            return match_line

        else:
            raise MatchError('Input matchline does not fit expected pattern')

    def __str__(self):
        return str(self.snote) + '\nDeletion'


class MatchInsertionNote(MatchLine):
    out_pattern = 'insertion-{NoteLine}.'
    pattern = 'insertion-' + MatchPnote.pattern + '.'
    re_obj = re.compile(pattern)
    field_names = MatchPnote.field_names

    def __init__(self, note):
        self.note = note
        for fn in self.field_names:
            setattr(self, fn, getattr(self.note, fn, None))

    @property
    def matchline(self):
        return self.out_pattern.format(
            NoteLine=self.note.matchline)

    @classmethod
    def from_matchline(cls, matchline, pos=0):
        match_pattern = cls.match_pattern(matchline, pos=0)

        if match_pattern is not None:
            groups = [cls.field_interpreter(i) for i in match_pattern.groups()]
            note_kwargs = dict(zip(MatchPnote.field_names, groups))
            note = MatchPnote(**note_kwargs)
            return cls(note=note)
        else:
            raise MatchError('Input matchline does not fit expected pattern')


class MatchSustainPedal(MatchLine):
    """
    Class for representing a sustain pedal line
    """
    out_pattern = 'sustain({Time},{Value}).'
    field_names = ['Time', 'Value']
    pattern = 'sustain\(\s*([^,]*)\s*,\s*([^,]*)\s*\)\.'
    re_obj = re.compile(pattern)

    def __init__(self, Time, Value):
        self.Time = Time
        self.Value = Value

    @property
    def matchline(self):

        return self.out_pattern.format(
            Time=self.Time,
            Value=self.Value)


class MatchSoftPedal(MatchLine):
    """
    Class for representing a soft pedal line
    """
    out_pattern = 'soft({Time},{Value}).'
    field_names = ['Time', 'Value']
    pattern = 'soft\(\s*([^,]*)\s*,\s*([^,]*)\s*\)\.'
    re_obj = re.compile(pattern)

    def __init__(self, Time, Value):
        self.Time = Time
        self.Value = Value

    @property
    def matchline(self):

        return self.out_pattern.format(
            Time=self.Time,
            Value=self.Value)


class MatchOrnamentNote(MatchLine):
    out_pattern = 'ornament({Anchor})-{PnoteLine}'
    field_names = ['Anchor'] + MatchPnote.field_names
    pattern = 'ornament\([^\)]*\)-' + MatchPnote.pattern
    re_obj = re.compile(pattern)

    def __init__(self, anchor, pnote):
        self.Anchor = anchor
        self.pnote = pnote

    @property
    def matchline(self):
        return self.out_pattern.format(
            Anchor=self.Anchor,
            PnoteLine=self.pnote.matchline)

    @classmethod
    def from_matchline(cls, matchline, pos=0):
        match_pattern = cls.match_pattern(matchline, pos=0)

        if match_pattern is not None:
            groups = [cls.field_interpreter(i) for i in match_pattern.groups()]
            pnote_kwargs = groups[1:]
            anchor = groups[0]
            pnote = MatchPnote(**pnote_kwargs)
            return cls(Anchor=anchor,
                       pnote=pnote)

        else:
            raise MatchError('Input matchline does not fit expected pattern')


def parse_matchline(l):
    """
    Return objects representing the line as one of:

    * hammer_bounce-PlayedNote.
    * info(Attribute, Value).
    * insertion-PlayedNote.
    * ornament(Anchor)-PlayedNote.
    * ScoreNote-deletion.
    * ScoreNote-PlayedNote.
    * ScoreNote-trailing_score_note.
    * trailing_played_note-PlayedNote.
    * trill(Anchor)-PlayedNote.
    * meta(Attribute, Value, Bar, Beat).

    or False if none can be matched

    Parameters
    ----------
    l : str
        Line of the match file

    Returns
    -------
    matchline : subclass of `MatchLine`
       Object representing the line. 
    """

    from_matchline_methods = [MatchSnoteNote.from_matchline,
                              MatchSnoteDeletion.from_matchline,
                              MatchInsertionNote.from_matchline,
                              MatchSustainPedal.from_matchline,
                              MatchSoftPedal.from_matchline,
                              MatchInfo.from_matchline,
                              MatchMeta.from_matchline
                              ]
    matchline = False
    for from_matchline in from_matchline_methods:
        try:
            matchline = from_matchline(l)
            break
        except MatchError:
            continue

    return matchline


class MatchFile(object):
    """
    Class for representing MatchFiles
    """

    def __init__(self, filename):

        fileData = [l.decode('utf8').strip() for l in open(filename, 'rb')]

        self.name = filename

        self.lines = np.array([parse_matchline(l) for l in fileData])

    @property
    def note_pairs(self):
        """
        Return all(snote, note) tuples

        """
        return [(x.snote, x.note) for x in self.lines if isinstance(x, SnoteNoteLine)]


if __name__ == '__main__':

    snote_line = 'snote(1-1,[E,n],4,0:1,0,1/4,-1.0,0.0,[staff1])'
    note_line = 'note(0,[E,n],4,471720,472397,472397,49)'
    old_note_line = 'note(0,[E,n],4,471720,472397,49)'
    snote_note_line = 'snote(1-1,[E,n],4,0:1,0,1/4,-1.0,0.0,[staff1])-note(0,[E,n],4,471720,472397,472397,49).'
    # snote_oldnote_line = snote_line + '-' + old_note_line + '.'
    snote_deletion_line = 'snote(1-1,[E,n],4,0:1,0,1/4,-1.0,0.0,[staff1])-deletion.'
    note_insertion_line = 'insertion-' + note_line + '.'
    info_line = 'info(matchFileVersion,4.0).'
    meta_line = 'meta(keySignature,C Maj/A min,0,-1.0).'
    sustain_line = 'sustain(779,59).'

    matchlines = [snote_note_line,
                  snote_deletion_line,
                  note_insertion_line,
                  info_line,
                  meta_line,
                  sustain_line]

    for ml in matchlines:
        mo = parse_matchline(ml)
        assert mo.matchline == ml
        print(mo.matchline)