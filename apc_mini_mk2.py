try:
    from ableton.v3.control_surface import ControlSurface, ControlSurfaceSpecification
    from ableton.v3.control_surface import create_skin
    from ableton.v3.control_surface.components import DEFAULT_DRUM_TRANSLATION_CHANNEL
    from ableton.v3.base import listens, const
except ImportError:
    from .ableton.v3.control_surface import ControlSurface, ControlSurfaceSpecification
    from .ableton.v3.control_surface import create_skin
    from .ableton.v3.control_surface.components import DEFAULT_DRUM_TRANSLATION_CHANNEL
    from .ableton.v3.base import listens, const
from .logger_config import get_logger
from .colors import Rgb, Skin
from .elements import PAD_MODE_HEADER, SYSEX_END, Elements
from .mappings import create_mappings
from .drum_step_sequencer import DrumStepSequencerComponent

logger = get_logger('apc_mini_mk2')

class Specification(ControlSurfaceSpecification):
    elements_type = Elements
    control_surface_skin = create_skin(skin=Skin)
    num_tracks = 8
    num_scenes = 8
    include_returns = True
    feedback_channels = [DEFAULT_DRUM_TRANSLATION_CHANNEL]
    playing_feedback_velocity = Rgb.GREEN.midi_value
    recording_feedback_velocity = Rgb.RED.midi_value
    identity_response_id_bytes = (71, 79, 0, 25)
    goodbye_messages = (PAD_MODE_HEADER + (0, SYSEX_END),)
    create_mappings_function = create_mappings
    component_map = {
        "Drum_Step_Sequencer": DrumStepSequencerComponent,
    }


class APC_mini_mk2(ControlSurface):

    def __init__(self, *a, **k):
        logger.debug("Initializing APC mini mk2 control surface")
        (super().__init__)(Specification, *a, **k)
        logger.info("APC mini mk2 control surface initialized")

    def setup(self):
        super().setup()
        self._APC_mini_mk2__on_pad_mode_changed.subject = self.component_map["Pad_Modes"]

    @staticmethod
    def _should_include_element_in_background(element):
        should_include = "Drum_Pad" not in element.name
        return should_include

    @listens("selected_mode")  # type: ignore
    def __on_pad_mode_changed(self, selected_mode):
        logger.info(f"Pad mode changed to: {selected_mode}")
        is_drum_mode = selected_mode == "drum"
        self.set_can_update_controlled_track(is_drum_mode)
        logger.debug(f"Can update controlled track set to: {is_drum_mode}")
        if is_drum_mode:
            logger.debug("Refreshing state for drum mode")
            self.refresh_state()
