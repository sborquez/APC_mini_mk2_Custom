from __future__ import absolute_import, print_function, unicode_literals
try:
  from ableton.v3.control_surface import HIGH_PRIORITY
  from ableton.v3.control_surface.mode import (
      ImmediateBehaviour,
      MomentaryBehaviour,
      make_reenter_behaviour,
  )
except ImportError:
  from .ableton.v3.control_surface import HIGH_PRIORITY
  from .ableton.v3.control_surface.mode import (
      ImmediateBehaviour,
      MomentaryBehaviour,
      make_reenter_behaviour,
  )
from .logger_config import get_logger

# Initialize logger for this module
logger = get_logger('mappings')


def create_mappings(control_surface):
    try:
        logger.info("=" * 60)
        logger.info("STARTING create_mappings()")
        logger.info("=" * 60)
        mappings = {}

        mappings["Mixer"] = dict(master_track_volume_control="master_fader")

        mappings["Session"] = dict(clip_slot_select_button="shift_button")

        mappings["Track_Button_Modes"] = dict(
            clip_stop=dict(component="Session", stop_track_clip_buttons="track_buttons"),
            solo=dict(component="Mixer", solo_buttons="track_buttons"),
            mute=dict(component="Mixer", mute_buttons="track_buttons"),
            arm=dict(component="Mixer", arm_buttons="track_buttons"),
            track_select=dict(component="Mixer", track_select_buttons="track_buttons"),
        )

        mappings["Fader_Modes"] = dict(
            volume=dict(component="Mixer", volume_controls="faders"),
            pan=dict(component="Mixer", pan_controls="faders"),
            send=dict(
                component="Mixer",
                send_controls="faders",
                behaviour=make_reenter_behaviour(
                    ImmediateBehaviour,
                    on_reenter=(control_surface.component_map["Mixer"].cycle_send_index),
                ),
            ),
            device=dict(component="Device", parameter_controls="faders"),
        )

        mappings["Pad_Modes"] = dict(
            mode_selection_control="pad_mode_control",
            session=dict(component="Session", clip_launch_buttons="clip_launch_buttons"),
            note=None,
            drum=dict(
                component="Drum_Step_Sequencer",
                drum_group_matrix="drum_pads",
                step_sequence_matrix="sequence_pads",  # 8x4 step sequencer grid
                mode_toggle_button="control_pads_raw[0]",  # Button 92 - Toggle selection/playable mode
                resolution_button="control_pads_raw[2]",  # Button 94 - Cycle grid resolution
                # prev_page_button="control_pads_raw[4]",  # Button 84 - Previous page (disabled for now)
                # next_page_button="control_pads_raw[5]",  # Button 85 - Next page (disabled for now)
                velocity_accent_button="control_pads_raw[6]",  # Button 86 - Accent velocity (127)
                velocity_soft_button="control_pads_raw[7]",  # Button 87 - Soft velocity (60)
            ),
            note_edit=None,
        )

        # This is when you press the shift button
        mappings["Main_Modes"] = dict(
            shift_button="shift_button",
            default=dict(
                component="Session",
                scene_launch_buttons="scene_launch_buttons"
            ),
            shift=dict(
                modes=[
                    dict(
                        component="Session",
                        stop_all_clips_button="scene_launch_buttons_raw[7]"
                    ),
                    dict(
                        component="Track_Button_Modes",
                        clip_stop_button="scene_launch_buttons_raw[0]",
                        solo_button="scene_launch_buttons_raw[1]",
                        mute_button="scene_launch_buttons_raw[2]",
                        arm_button="scene_launch_buttons_raw[3]",
                        track_select_button="scene_launch_buttons_raw[4]",
                    ),
                    dict(
                        component="Fader_Modes",
                        volume_button="track_buttons_raw[0]",
                        pan_button="track_buttons_raw[1]",
                        send_button="track_buttons_raw[2]",
                        # TODO: this should be drums sequencer
                        device_button="track_buttons_raw[3]",
                        priority=HIGH_PRIORITY,
                    ),
                    dict(
                        component="Session_Navigation",
                        up_button="track_buttons_raw[4]",
                        down_button="track_buttons_raw[5]",
                        left_button="track_buttons_raw[6]",
                        right_button="track_buttons_raw[7]",
                        priority=HIGH_PRIORITY,
                    ),
                ],
                behaviour=(MomentaryBehaviour()),
            ),
        )

        logger.info("=" * 60)
        logger.info(f"✓✓✓ Created mappings for {len(mappings)} component groups ✓✓✓")
        logger.info(f"Groups: {list(mappings.keys())}")
        logger.info("=" * 60)
        return mappings
    except Exception as e:
        logger.error("=" * 60)
        logger.error("✗✗✗ create_mappings() FAILED ✗✗✗")
        logger.error(f"Error: {e}")
        logger.error("=" * 60)
        logger.error("Full traceback:", exc_info=True)
        raise
