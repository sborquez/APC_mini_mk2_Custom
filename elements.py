from __future__ import absolute_import, print_function, unicode_literals
try:
    from ableton.v3.control_surface import MIDI_NOTE_TYPE, ElementsBase, create_matrix_identifiers
    from ableton.v3.control_surface.midi import SYSEX_END, SYSEX_START
except ImportError:
    from .ableton.v3.control_surface import MIDI_NOTE_TYPE, ElementsBase, create_matrix_identifiers
    from .ableton.v3.control_surface.midi import SYSEX_END, SYSEX_START
from .colors import FULL_BRIGHTNESS_CHANNEL
from .logger_config import get_logger

# Initialize logger for this module
logger = get_logger('elements')

PAD_MODE_HEADER = (SYSEX_START, 71, 127, 79, 98, 0, 1)


class Elements(ElementsBase):
    def __init__(self, *a, **k):
        try:
            logger.info("=" * 60)
            logger.info("STARTING Elements.__init__")
            logger.info("=" * 60)
            logger.debug("Calling ElementsBase.__init__...")
            (super().__init__)(*a, **k)
            logger.debug("✓ ElementsBase.__init__ successful")

            logger.debug("Adding modifier button: Shift_Button")
            self.add_modifier_button(122, "Shift_Button", msg_type=MIDI_NOTE_TYPE)

            logger.debug("Adding clip launch buttons matrix")
            self.add_button_matrix(
                create_matrix_identifiers(0, 64, width=8, flip_rows=True),
                "Clip_Launch_Buttons",
                msg_type=MIDI_NOTE_TYPE,
                led_channel=FULL_BRIGHTNESS_CHANNEL,
            )

            logger.debug("Adding drum pads matrix")
            self.add_button_matrix(
                [
                 [88, 89, 90, 91],
                 [80, 81, 82, 83],
                 [72, 73, 74, 75],
                 [64, 65, 66, 67],
                ],
                "Drum_Pads",
                msg_type=MIDI_NOTE_TYPE,
                channels=9,
            )
            logger.debug("Adding control pads matrix")
            self.add_button_matrix(
                [
                    [92, 93, 94, 95],
                    [84, 85, 86, 87],
                ],
                "Control_Pads",
                msg_type=MIDI_NOTE_TYPE,
                channels=9,
            )
            logger.debug("Adding sequence pads matrix")
            self.add_button_matrix(
                create_matrix_identifiers(96, 128, width=8, flip_rows=True),
                "Sequence_Pads",
                msg_type=MIDI_NOTE_TYPE,
                channels=9,
            )
        # logger.debug("Adding sequence pages matrix")
        # self.add_button_matrix(
        #     [
        #         [76, 77, 78, 79],
        #         [68, 69, 70, 71],
        #     ],
        #     "Sequence_Pages",
        #     msg_type=MIDI_NOTE_TYPE,
        #     channels=9,
        # )

            logger.debug("Adding track buttons matrix")
            self.add_button_matrix([range(100, 108)], "Track_Buttons", msg_type=MIDI_NOTE_TYPE)

            logger.debug("Adding scene launch buttons matrix")
            self.add_button_matrix([range(112, 120)], "Scene_Launch_Buttons", msg_type=MIDI_NOTE_TYPE)

            logger.debug("Adding master fader encoder")
            self.add_encoder(56, "Master_Fader")

            logger.debug("Adding faders encoder matrix")
            self.add_encoder_matrix([range(48, 56)], "Faders")

            def pad_mode_message_generator(v):
                """Generate pad mode SYSEX message and log the value"""
                message = PAD_MODE_HEADER + (v, SYSEX_END)
                logger.debug(f"Sending pad mode SYSEX message with value: {v}")
                return message

            logger.debug("Adding pad mode control sysex element")
            self.add_sysex_element(
                PAD_MODE_HEADER,
                "Pad_Mode_Control",
                pad_mode_message_generator,
                use_first_byte_as_value=True,
            )

            logger.info("=" * 60)
            logger.info("✓✓✓ Elements INITIALIZED SUCCESSFULLY ✓✓✓")
            logger.info("=" * 60)
        except Exception as e:
            logger.error("=" * 60)
            logger.error("✗✗✗ Elements INITIALIZATION FAILED ✗✗✗")
            logger.error(f"Error: {e}")
            logger.error("=" * 60)
            logger.error("Full traceback:", exc_info=True)
            raise
