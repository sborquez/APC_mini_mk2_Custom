try:
    from ableton.v3.control_surface import ControlSurface, ControlSurfaceSpecification
    from ableton.v3.control_surface import create_skin
    from ableton.v3.control_surface.components import DEFAULT_DRUM_TRANSLATION_CHANNEL, TargetTrackComponent
    from ableton.v3.base import listens
except ImportError:
    from .ableton.v3.control_surface import ControlSurface, ControlSurfaceSpecification
    from .ableton.v3.control_surface import create_skin
    from .ableton.v3.control_surface.components import DEFAULT_DRUM_TRANSLATION_CHANNEL, TargetTrackComponent
    from .ableton.v3.base import listens
from .logger_config import get_logger
from .colors import Rgb, Skin
from .elements import PAD_MODE_HEADER, SYSEX_END, Elements
from .mappings import create_mappings
from .drum_step_sequencer import DrumStepSequencerComponent
from .custom_target_track import CustomTargetTrackComponent
from .drum_rack_level import DrumRackLevelComponent

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
    target_track_component_type = CustomTargetTrackComponent
    component_map = {
        "Drum_Step_Sequencer": DrumStepSequencerComponent,
        "Drum_Rack_Level": DrumRackLevelComponent,
    }


class APC_mini_mk2(ControlSurface):

    def __init__(self, *a, **k):
        try:
            logger.info("=" * 60)
            logger.info("STARTING APC_mini_mk2.__init__")
            logger.info("=" * 60)
            (super().__init__)(Specification, *a, **k)

            logger.info("=" * 60)
            logger.info("✓✓✓ APC_mini_mk2 INITIALIZED SUCCESSFULLY ✓✓✓")
            logger.info("=" * 60)
        except Exception as e:
            logger.error("=" * 60)
            logger.error("✗✗✗ APC_mini_mk2 INITIALIZATION FAILED ✗✗✗")
            logger.error(f"Error: {e}")
            logger.error("=" * 60)
            logger.error("Full traceback:", exc_info=True)
            raise

    def setup(self):
        try:
            logger.debug("Starting setup()...")
            super().setup()
            self._APC_mini_mk2__on_pad_mode_changed.subject = self.component_map["Pad_Modes"]

            logger.info("✓ setup() complete")
        except Exception as e:
            logger.error(f"✗ setup() FAILED: {e}", exc_info=True)
            raise

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
