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
from .logger_config import get_logger

# Initialize logger for this module
logger = get_logger('colors')
HALF_BRIGHTNESS_CHANNEL = 1
FULL_BRIGHTNESS_CHANNEL = 6
PULSE_CHANNEL = 10
BLINK_CHANNEL = 14

@memoize
def make_simple_color(value):
    logger.debug(f"Creating simple color with value: {value}")
    color = SimpleColor(value)
    logger.debug(f"Simple color created: {color}")
    return color


def make_color_for_liveobj(obj):
    logger.debug(f"Creating color for live object: {obj}")
    color_value = liveobj_color_to_value_from_palette(obj,
      palette=STANDARD_COLOR_PALETTE,
      fallback_table=STANDARD_FALLBACK_COLOR_TABLE)
    logger.debug(f"Color value from palette: {color_value}")
    color = make_simple_color(color_value)
    logger.debug(f"Color for live object created: {color}")
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
    AMBER = make_simple_color(9)
    YELLOW = make_simple_color(13)
    GREEN = make_simple_color(21)
    GREEN_BLINK = SimpleColor(21, channel=BLINK_CHANNEL)
    GREEN_PULSE = SimpleColor(21, channel=PULSE_CHANNEL)
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
        PadSelected = Rgb.OCEAN
        PadMuted = Rgb.AMBER
        PadMutedSelected = Rgb.OCEAN
        PadSoloed = Rgb.BLUE
        PadSoloedSelected = Rgb.OCEAN

    # class StepSequencer:
    #     StepEmpty = Rgb.GREY
    #     StepActiveNormal = Rgb.WHITE
    #     StepActiveSoft = Rgb.WHITE_HALF
    #     StepActiveAccent = Rgb.AMBER
    #     CurrentStep = Rgb.GREEN_PULSE
