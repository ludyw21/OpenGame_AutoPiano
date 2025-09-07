"""Audio processing modules for MeowField AutoPiano.

This package contains audio conversion, MIDI processing, and PianoTrans management
functionality that handles all audio-related operations.
"""

from .converter import AudioConverter
from .midi_processor import MidiProcessor

__all__ = ['AudioConverter', 'MidiProcessor']