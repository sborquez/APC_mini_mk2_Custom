from __future__ import absolute_import, print_function, unicode_literals
try:
    from ableton.v3.control_surface import Component
    from ableton.v3.control_surface.components import (
        StepSequenceComponent,
        NoteEditorComponent,
        LoopSelectorComponent,
        PlayheadComponent,
        GridResolutionComponent,
        DrumGroupComponent,
        PlayableComponent
    )
    from ableton.v3.control_surface.controls import ButtonControl, control_matrix, ToggleButtonControl
    from ableton.v3.base import depends, listens, listenable_property
    from ableton.v3.live import liveobj_valid
except ImportError:
    from .ableton.v3.control_surface import Component
    from .ableton.v3.control_surface.components import (
        StepSequenceComponent,
        NoteEditorComponent,
        LoopSelectorComponent,
        PlayheadComponent,
        GridResolutionComponent,
        DrumGroupComponent,
        PlayableComponent
    )
    from .ableton.v3.control_surface.controls import ButtonControl, control_matrix, ToggleButtonControl
    from .ableton.v3.base import depends, listens, listenable_property
    from .ableton.v3.live import liveobj_valid

from .logger_config import get_logger
from .colors import Skin

logger = get_logger('drum_step_sequencer')

# Constants for the 8x8 grid layout
# Sequencer steps (top 4x8 = 32 steps for 2 bars of 16 steps)
SEQUENCE_STEPS_WIDTH = 8
SEQUENCE_STEPS_HEIGHT = 4  # 2 bars of 16 steps = 32 steps total

# Control grid (right 4x4)
CONTROL_GRID_WIDTH = 4
CONTROL_GRID_HEIGHT = 4

# Drum group (left 4x4)
DRUM_GROUP_WIDTH = 4
DRUM_GROUP_HEIGHT = 4

# Default settings
DEFAULT_SEQUENCE_LENGTH = 2  # bars
DEFAULT_RESOLUTION = 16  # 1/16 notes
DEFAULT_DRUM_BASE_NOTE = 36  # C1
DEFAULT_GROOVE = 0  # -100 to 100

# Velocity modes
NORMAL_VELOCITY = 100
SOFT_VELOCITY = 60
ACCENT_VELOCITY = 127


class CustomDrumGroupComponent(DrumGroupComponent):
    """
    Custom drum group component for APC Mini MK2.
    """
    def __init__(self, name="Drum_Group", target_track=None, selection_only=False, *a, **k):
        super().__init__(name=name, target_track=target_track, *a, **k)
        self._selection_only = selection_only
        self._select_mode = False

        # If in selection-only mode, always keep pads in listenable mode
        if self._selection_only:
            self._set_control_pads_from_script(True)

    def set_matrix(self, matrix):
        """Override set_matrix to ensure selection-only mode is applied after matrix connection"""
        super().set_matrix(matrix)

        # Set the mode AFTER the matrix is connected
        if self._selection_only:
            self._set_control_pads_from_script(True)
            self._update_control_from_script()

    def set_selection_only_mode(self, enabled):
        """Enable or disable selection-only mode"""
        self._selection_only = enabled
        if enabled:
            # Force pads into listenable mode (selection only)
            self._set_control_pads_from_script(True)
        else:
            # Allow normal playable mode
            self._set_control_pads_from_script(False)

    def _on_matrix_pressed(self, button):
        """Override to handle selection-only mode"""
        if self._selection_only:
            # In selection-only mode, handle drum pad selection
            button_coordinate = getattr(button, 'coordinate', None)

            if button_coordinate and liveobj_valid(self._drum_group_device):
                # Get the drum pad for this button
                pad = self._pad_for_button(button)

                if liveobj_valid(pad):
                    # Get pad name safely
                    pad_name = getattr(pad, 'name', None)
                    if pad_name:
                        pad_name = str(pad_name)
                    else:
                        note = getattr(pad, 'note', None)
                        pad_name = f"Pad {note}" if note is not None else "Unknown Pad"

                    # Select the drum pad in Live
                    self._do_select_pad(pad, pad_name)
        else:
            # Use normal drum group behavior - this requires a drum group device
            if liveobj_valid(self._drum_group_device):
                super()._on_matrix_pressed(button)

class DrumStepSequencerComponent(Component):
    """
    Custom drum step sequencer component for APC Mini MK2.

    APC Mini MK2 8x8 Grid Layout (64 pads total, MIDI notes 64-127):

    Pads 0-31:  Top 4x8 rows - Step sequencer (32 steps for 2 bars of 16 steps)
    Pads 32-47: Middle 2x8 rows - Reserved for future use
    Pads 48-51: Row 6, cols 0-3 - Drum group (left 4x4, top row)
    Pads 52-55: Row 6, cols 4-7 - Control grid (right 4x4, top row)
    Pads 56-59: Row 7, cols 0-3 - Drum group (left 4x4, bottom row)
    Pads 60-63: Row 7, cols 4-7 - Control grid (right 4x4, bottom row)

    (The actual MIDI numbers are set in the elements.py file)

    Current implementation:
    - Drum group: 2x4 grid (8 drum pads) in left-bottom area
    - Step sequencer: To be implemented in top 4x8 area
    - Control grid: To be implemented in right 4x4 area
    """

    # Toggle button for switching between selection and playable mode
    mode_toggle_button = ToggleButtonControl(
        color="DrumStepSequencer.ModeToggleOff",
        on_color="DrumStepSequencer.ModeToggleOn"
    )

    @depends(target_track=None)
    def __init__(self, name="Drum_Step_Sequencer", target_track=None, *a, **k):
        super().__init__(name=name, *a, **k)

        # Store dependencies
        self._target_track = target_track

        # Initialize composed drum group component in selection-only mode
        self._drum_group = CustomDrumGroupComponent(
            name="Drum_Group",
            target_track=target_track,
            selection_only=True,  # Enable selection-only mode
            parent=self
        )

        logger.info("DrumStepSequencerComponent initialized successfully")

    @mode_toggle_button.toggled
    def _on_mode_toggle_button_toggled(self, is_toggled, button):
        """Handle mode toggle button toggle"""
        logger.info(f"Mode toggle button toggled to: {is_toggled}")
        # Set the selection mode based on the toggle state (inverted logic)
        # When button is ON (is_toggled=True) → Playable mode (selection_only=False)
        # When button is OFF (is_toggled=False) → Selection mode (selection_only=True)
        self.set_selection_only_mode(not is_toggled)
        logger.info(f"Mode set to: {'Selection' if not is_toggled else 'Playable'}")

    @property
    def drum_group(self):
        """Access to the composed drum group component"""
        return self._drum_group

    @property
    def drum_group_matrix(self):
        """Get the drum group matrix (required by Ableton framework)"""
        return self._drum_group.matrix

    @drum_group_matrix.setter
    def drum_group_matrix(self, matrix):
        """Set the matrix for the drum step sequencer (required by Ableton framework)"""
        logger.debug("Setting drum group matrix via property setter")
        logger.debug(f"Matrix type: {type(matrix)}, Matrix: {matrix}")
        self._drum_group.set_matrix(matrix)
        logger.info("Drum group matrix set successfully via property")

    def set_drum_group_matrix(self, matrix):
        """Set the matrix for the drum step sequencer (legacy method)"""
        logger.debug("Setting matrix for drum step sequencer via method")
        logger.debug(f"Matrix type: {type(matrix)}, Matrix: {matrix}")

        # For now, pass the matrix to the drum group component
        self._drum_group.set_matrix(matrix)

        logger.info("Matrix set for drum step sequencer")

    def set_drum_group_device(self, drum_group_device):
        """Set the drum group device for the drum group component"""
        logger.debug(f"Setting drum group device: {drum_group_device}")
        self._drum_group.set_drum_group_device(drum_group_device)

    def set_selection_only_mode(self, enabled):
        """Enable or disable selection-only mode for drum pads"""
        logger.info(f"Setting selection-only mode: {enabled}")
        self._drum_group.set_selection_only_mode(enabled)

    def toggle_selection_only_mode(self):
        """Toggle between selection-only and normal playable mode"""
        current_mode = self._drum_group._selection_only
        new_mode = not current_mode
        self.set_selection_only_mode(new_mode)
        logger.info(f"Toggled selection-only mode to: {new_mode}")
        return new_mode

    def update(self):
        """Update the component"""
        super().update()
        logger.debug("Updating drum step sequencer component")

        # Update composed drum group component
        self._drum_group.update()
