from __future__ import absolute_import, print_function, unicode_literals
try:
    from ableton.v3.base import memoize  # type: ignore
    from ableton.v3.control_surface import STANDARD_COLOR_PALETTE, STANDARD_FALLBACK_COLOR_TABLE
    from ableton.v3.control_surface.elements import SimpleColor
    from ableton.v3.live import liveobj_color_to_value_from_palette
except ImportError:
    from .ableton.v3.base import memoize  # type: ignore
    from .ableton.v3.control_surface import STANDARD_COLOR_PALETTE, STANDARD_FALLBACK_COLOR_TABLE
    from .ableton.v3.control_surface.elements import SimpleColor
    from .ableton.v3.live import liveobj_color_to_value_from_palette

# Initialize logger for this module
HALF_BRIGHTNESS_CHANNEL = 1
FULL_BRIGHTNESS_CHANNEL = 6
PULSE_CHANNEL = 10
BLINK_CHANNEL = 14

@memoize
def make_simple_color(value) -> SimpleColor:
    color = SimpleColor(value)
    return color

def make_color_for_liveobj(obj) -> SimpleColor:
    color_value = liveobj_color_to_value_from_palette(obj,
      palette=STANDARD_COLOR_PALETTE,
      fallback_table=STANDARD_FALLBACK_COLOR_TABLE)
    color = make_simple_color(color_value)
    return color

class Basic:
    ON = make_simple_color(1)
    BLINK = make_simple_color(2)


class Rgb:
    BLACK = make_simple_color(0)
    GREY = make_simple_color(1)
    RED = make_simple_color(5)
    RED_BLINK = SimpleColor(5, channel=BLINK_CHANNEL)
    RED_PULSE = SimpleColor(5, channel=PULSE_CHANNEL)
    RED_HALF = SimpleColor(5, channel=HALF_BRIGHTNESS_CHANNEL)
    AMBERISH = make_simple_color(108)
    AMBER = make_simple_color(9)
    AMBER_HALF = SimpleColor(9, channel=HALF_BRIGHTNESS_CHANNEL)
    AMBER_PULSE = SimpleColor(9, channel=PULSE_CHANNEL)
    YELLOWISH = make_simple_color(8)
    YELLOW = make_simple_color(97)
    GREENISH = make_simple_color(16)
    GREEN = make_simple_color(21)
    GREEN_BLINK = SimpleColor(21, channel=BLINK_CHANNEL)
    GREEN_PULSE = SimpleColor(21, channel=PULSE_CHANNEL)
    GREEN_HALF = SimpleColor(21, channel=HALF_BRIGHTNESS_CHANNEL)
    PURPLE = make_simple_color(81)
    OCEAN = make_simple_color(41)
    BLUE = make_simple_color(45)
    WHITE = make_simple_color(127)
    WHITE_HALF = SimpleColor(127, channel=HALF_BRIGHTNESS_CHANNEL)

class Skin:

    class Session:
        SlotRecordButton = Rgb.RED_HALF
        ClipStopped = make_color_for_liveobj
        ClipTriggeredPlay = Rgb.GREEN_BLINK
        ClipTriggeredRecord = Rgb.RED_BLINK
        ClipPlaying = Rgb.GREEN_PULSE
        ClipRecording = Rgb.RED_PULSE
        SceneTriggered = Basic.BLINK
        StopClipTriggered = Basic.BLINK
        StopClip = Basic.ON

    class DrumGroup:
        PadEmpty = Rgb.GREY
        PadFilled = Rgb.PURPLE
        PadSelected = Rgb.GREENISH
        PadMuted = Rgb.AMBER
        PadMutedSelected = Rgb.OCEAN
        PadSoloed = Rgb.BLUE
        PadSoloedSelected = Rgb.OCEAN

    class DrumStepSequencer:
        # Step sequencer
        StepEmpty = Rgb.BLACK
        StepActiveSoft = Rgb.WHITE_HALF
        StepActiveNormal = Rgb.WHITE
        StepActiveAccent = Rgb.AMBER
        CurrentStep = Rgb.GREEN_BLINK
        StepFilled = Rgb.PURPLE
        StepMuted = Rgb.GREY
        NoClip = Rgb.GREY
        StepDisabled = Rgb.BLACK
        PageEmpty = Rgb.BLACK
        PageFilled = Rgb.BLUE
        CurrentPage = Rgb.BLUE

        # Mode toggle button colors - following proper naming convention
        ModeToggleOff = Rgb.GREENISH  # Greenish for selection mode (off state)
        ModeToggleOn = Rgb.GREEN      # Green for playable mode (on state)

        # Velocity button states (off/on)
        # NOTE: APC Mini MK2 may not support pulse/half-brightness via MIDI channels
        # Using same colors for now - just testing if colors show at all
        VelocityAccentOff = Rgb.AMBERISH
        VelocityAccentOn = Rgb.AMBER
        VelocitySoftOff = Rgb.YELLOWISH
        VelocitySoftOn = Rgb.YELLOW

    class NoteEditor:
        # Step colors
        StepEmpty = Rgb.BLACK
        StepFilled = Rgb.WHITE
        StepActivated = Rgb.GREEN
        StepMuted = Rgb.GREY
        StepDisabled = Rgb.BLACK

        # Playhead - current playing step
        Playhead = Rgb.GREEN_BLINK
        PlayheadMuted = Rgb.GREY

        # Page navigation
        PageNavigation = Rgb.BLUE
        PageNavigationPressed = Rgb.WHITE

        # Grid resolution colors
        class Resolution:
            Selected = Rgb.AMBER
            NotSelected = Rgb.AMBERISH

    class LoopSelector:
        # Loop/page selection
        PageEmpty = Rgb.BLACK
        PageFilled = Rgb.BLUE
        PageFilledAlternate = Rgb.PURPLE
        PageActive = Rgb.WHITE

        # Navigation buttons
        Navigation = Rgb.BLUE
        NavigationPressed = Rgb.WHITE
        NavigationDisabled = Rgb.GREY