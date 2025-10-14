from __future__ import absolute_import, print_function, unicode_literals

try:
    from ableton.v3.control_surface import Component
    from ableton.v3.control_surface.components import (
        NoteEditorComponent,
        LoopSelectorComponent,
        GridResolutionComponent,
        DrumGroupComponent,
        NoteEditorPaginator,
        SequencerClip
    )
    from ableton.v3.control_surface.controls import ButtonControl, ToggleButtonControl
    from ableton.v3.base import depends, listenable_property, EventObject, inject, const, task
    from ableton.v3.live import liveobj_valid
except ImportError:
    from .ableton.v3.control_surface import Component
    from .ableton.v3.control_surface.components import (
        NoteEditorComponent,
        LoopSelectorComponent,
        GridResolutionComponent,
        DrumGroupComponent,
        NoteEditorPaginator,
        SequencerClip
    )
    from .ableton.v3.control_surface.controls import ButtonControl, ToggleButtonControl
    from .ableton.v3.base import depends, listenable_property, EventObject, inject, const, task
    from .ableton.v3.live import liveobj_valid

from .logger_config import get_logger

logger = get_logger('drum_step_sequencer')

# Constants for the 8x8 grid layout
# Sequencer steps (top 4x8 = 32 steps for 2 bars of 16 steps)
SEQUENCE_STEPS_WIDTH = 8
SEQUENCE_STEPS_HEIGHT = 4  # 2 bars of 16 steps = 32 steps total

# Default settings
DEFAULT_SEQUENCE_LENGTH = 1  # bars
DEFAULT_RESOLUTION = 16  # 1/16 notes

# Velocity modes
NORMAL_VELOCITY = 100
SOFT_VELOCITY = 60
ACCENT_VELOCITY = 127


# Playhead components removed - not working properly yet
# Will be re-implemented in the future with proper matrix visualization


class DrumPadPitchProvider(EventObject):
    """
    Provides the pitch of the currently selected drum pad to the note editor.
    This allows the step sequencer to edit notes for the selected drum pad.

    The pitch automatically updates when a drum pad is selected in the drum group.
    """
    # Use managed properties for automatic listener notifications
    pitches = listenable_property.managed([36])
    is_polyphonic = listenable_property.managed(False)

    def __init__(self, drum_group_component=None, *a, **k):
        super().__init__(*a, **k)
        self._drum_group = drum_group_component  # Can be None initially, set later
        logger.info(f"✓ DrumPadPitchProvider initialized with pitches: {self.pitches}")

    def set_pitch(self, pitch):
        """Manually set the pitch to edit"""
        if isinstance(pitch, list):
            new_pitches = pitch
        else:
            new_pitches = [pitch]

        if new_pitches != self.pitches:
            logger.debug(f"Pitch changed: {self.pitches} → {new_pitches}")
            self.pitches = new_pitches  # Managed property automatically notifies listeners!


class CustomDrumGroupComponent(DrumGroupComponent):
    """
    Custom drum group component for APC Mini MK2.
    Adds selection-only mode toggle functionality and pitch tracking.

    Note: The APC Mini MK2 has fixed velocity (127) in hardware, so velocity
    modification would require external MIDI processing or Live's Velocity device.
    """

    @depends(target_track=None)
    def __init__(self, name="Drum_Group", target_track=None, selection_only=False, pitch_provider=None, *a, **k):
        super().__init__(name=name, target_track=target_track, *a, **k)
        self._selection_only = selection_only
        self._pitch_provider = pitch_provider
        self._selected_drum_pad_note = None
        self._parent_sequencer = None  # Will be set by parent
        self._target_track = target_track

        logger.debug(f"CustomDrumGroupComponent init: selection_only={selection_only}, pitch_provider={pitch_provider}")

        # Listen to target track changes
        if self._target_track:
            self.register_slot(self._target_track, self._on_target_track_changed, "target_track")
            logger.debug("✓ CustomDrumGroup: Registered target track listener")

        # If in selection-only mode, always keep pads in listenable mode
        if self._selection_only:
            self._set_control_pads_from_script(True)
            logger.debug("Set control pads from script (listenable mode)")

    def set_parent_sequencer(self, parent_sequencer):
        """Set reference to parent DrumStepSequencerComponent for lock state checking"""
        self._parent_sequencer = parent_sequencer
        logger.debug(f"CustomDrumGroup: Set parent sequencer reference: {parent_sequencer}")

    # Note: Lock functionality now handled by framework's TargetTrackComponent

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
        """Override to handle selection-only mode and pitch tracking"""
        logger.debug(f"_on_matrix_pressed called: selection_only={self._selection_only}, button={button}")

        if self._selection_only:
            # In selection-only mode, handle drum pad selection
            button_coordinate = getattr(button, 'coordinate', None)
            logger.debug(f"Button coordinate: {button_coordinate}")
            logger.debug(f"Drum group device valid: {liveobj_valid(self._drum_group_device)}")
            logger.debug(f"Drum group device: {self._drum_group_device}")

            if button_coordinate and liveobj_valid(self._drum_group_device):
                # Get the drum pad for this button
                pad = self._pad_for_button(button)
                logger.debug(f"Got pad for button: {pad}, valid={liveobj_valid(pad)}")

                if liveobj_valid(pad):
                    # Get pad name and note
                    pad_name = getattr(pad, 'name', None)
                    if pad_name:
                        pad_name = str(pad_name)
                    else:
                        note = getattr(pad, 'note', None)
                        pad_name = f"Pad {note}" if note is not None else "Unknown Pad"

                    # Get the MIDI note for this pad
                    note = getattr(pad, 'note', None)
                    logger.debug(f"Pad note: {note}, pad_name: {pad_name}")

                    if note is not None:
                        self._selected_drum_pad_note = note
                        # Update pitch provider if available
                        if self._pitch_provider:
                            self._pitch_provider.set_pitch(note)
                            logger.info(f"✓ Selected drum pad: {pad_name} (MIDI note {note})")
                        else:
                            logger.warning("No pitch provider available!")

                    # Select the drum pad in Live
                    self._do_select_pad(pad, pad_name)
                else:
                    logger.warning(f"Pad not valid or not found")
            else:
                if not button_coordinate:
                    logger.warning("No button coordinate")
                if not liveobj_valid(self._drum_group_device):
                    logger.warning("Drum group device not valid - is a Drum Rack loaded?")
        else:
            # Use normal drum group behavior - this requires a drum group device
            logger.debug("Not in selection-only mode, using normal drum group behavior")
            if liveobj_valid(self._drum_group_device):
                super()._on_matrix_pressed(button)
            else:
                logger.warning("Cannot use drum group - no drum rack device")

    def _on_target_track_changed(self):
        """Handle target track changes from framework's TargetTrackComponent"""
        if not self._target_track:
            return
        current_track = self._target_track.target_track
        track_name = getattr(current_track, 'name', 'Unknown') if current_track else 'None'

        # Update drum group device for the new target track
        if not current_track:
            return

        # Find drum rack device on the target track
        drum_rack_device = None
        for device in current_track.devices:
            if hasattr(device, 'can_have_chains') and device.can_have_chains:
                drum_rack_device = device
                break

        if drum_rack_device:
            self.set_drum_group_device(drum_rack_device)

class DrumStepSequencerComponent(Component):
    """
    Custom drum step sequencer component for APC Mini MK2.

    Layout:
    - Drum group: 4x4 grid (16 drum pads) in left-bottom area
    - Step sequencer: 4x8 grid (32 steps) in top area
    - Control grid: 2x4 grid (8 control buttons) in right-bottom area
    """

    # Toggle button for switching between selection and playable mode
    mode_toggle_button = ToggleButtonControl(
        color="DrumStepSequencer.ModeToggleOff",
        on_color="DrumStepSequencer.ModeToggleOn"
    )

    # Resolution cycle button
    resolution_button = ButtonControl(
        color="NoteEditor.Resolution"
    )

    # Reserved for future use - these buttons provide visual feedback but don't
    # modify velocity (APC Mini MK2 has fixed hardware velocity of 127).
    # Possible future uses: track selection, scene control, transport, etc.
    velocity_accent_button = ButtonControl(
        color="DrumStepSequencer.VelocityAccentOff"
    )
    velocity_soft_button = ButtonControl(
        color="DrumStepSequencer.VelocitySoftOff"
    )

    @depends(target_track=None)
    def __init__(self, name="Drum_Step_Sequencer", target_track=None, *a, **k):
        try:
            logger.info("=" * 60)
            logger.info("STARTING DrumStepSequencerComponent.__init__")
            logger.info("=" * 60)

            logger.debug(f"Args: name={name}, target_track={target_track}")
            logger.debug(f"Additional args: {a}, kwargs: {k}")

            # Call parent init
            try:
                super().__init__(name=name, *a, **k)
                logger.debug("✓ Parent Component.__init__ successful")
            except Exception as e:
                logger.error(f"✗ Parent Component.__init__ FAILED: {e}", exc_info=True)
                raise

            # Store dependencies
            self._target_track = target_track
            logger.debug(f"✓ Stored target_track: {target_track}")

            # Listen to target track changes
            if self._target_track:
                self.register_slot(self._target_track, self._on_target_track_changed, "target_track")
                logger.debug("✓ Registered target track listener")

            # Velocity state
            self._current_velocity = NORMAL_VELOCITY
            logger.debug(f"✓ Set velocity: {self._current_velocity}")

            # Create pitch provider first (needed by drum group)
            try:
                logger.debug("Creating DrumPadPitchProvider...")
                self._pitch_provider = DrumPadPitchProvider(
                    drum_group_component=None  # Will be set after drum group is created
                )
                logger.info("✓ DrumPadPitchProvider created successfully")
            except Exception as e:
                logger.error(f"✗ DrumPadPitchProvider FAILED: {e}", exc_info=True)
                raise

            # Initialize composed drum group component with pitch provider reference
            try:
                logger.debug("Creating CustomDrumGroupComponent...")
                self._drum_group = CustomDrumGroupComponent(
                    name="Drum_Group",
                    target_track=target_track,
                    selection_only=True,
                    pitch_provider=self._pitch_provider,
                )
                # Set parent sequencer reference for lock state checking
                self._drum_group.set_parent_sequencer(self)
                # Update the pitch provider's drum group reference
                self._pitch_provider._drum_group = self._drum_group
                logger.info("✓ CustomDrumGroupComponent created successfully")
            except Exception as e:
                logger.error(f"✗ CustomDrumGroupComponent FAILED: {e}", exc_info=True)
                raise

            # Create sequencer clip helper
            try:
                logger.debug("Creating SequencerClip...")
                self._sequencer_clip = SequencerClip(
                    target_track=target_track
                )
                logger.info("✓ SequencerClip created successfully")
            except Exception as e:
                logger.error(f"✗ SequencerClip FAILED: {e}", exc_info=True)
                raise

            # Create our own grid resolution component
            try:
                logger.debug("Creating GridResolutionComponent...")
                self._grid_resolution = GridResolutionComponent(
                    name="Grid_Resolution",
                    parent=self
                )
                logger.info("✓ GridResolutionComponent created successfully")
            except Exception as e:
                logger.error(f"✗ GridResolutionComponent FAILED: {e}", exc_info=True)
                raise

            # Note editor for step input (regular component - we'll handle locking differently)
            try:
                logger.debug("Creating NoteEditorComponent...")
                logger.info(f"📎 Injecting CustomSequencerClip: {self._sequencer_clip}")
                # Inject sequencer_clip dependency
                with inject(sequencer_clip=const(self._sequencer_clip)).everywhere():
                    self._note_editor = NoteEditorComponent(
                        grid_resolution=self._grid_resolution,
                        parent=self
                    )
                logger.debug("Setting pitch provider on note editor...")
                self._note_editor.pitch_provider = self._pitch_provider
                logger.info("✓ NoteEditorComponent created successfully")

                # Check if the note editor has a sequencer_clip property
                if hasattr(self._note_editor, 'sequencer_clip'):
                    logger.info(f"NoteEditor has sequencer_clip: {self._note_editor.sequencer_clip}")
                else:
                    logger.info("NoteEditor does not have sequencer_clip property")

            except Exception as e:
                logger.error(f"NoteEditorComponent FAILED: {e}", exc_info=True)
                raise

            # Paginator for page management
            try:
                logger.debug("Creating NoteEditorPaginator...")
                self._paginator = NoteEditorPaginator(
                    note_editor=self._note_editor,
                    parent=self
                )
                logger.info("✓ NoteEditorPaginator created successfully")
            except Exception as e:
                logger.error(f"✗ NoteEditorPaginator FAILED: {e}", exc_info=True)
                raise

            # Loop selector (optional - may fail due to dependencies)
            self._loop_selector = None
            try:
                logger.debug("Creating LoopSelectorComponent (optional)...")
                self._loop_selector = LoopSelectorComponent(
                    paginator=self._paginator,
                    parent=self
                )
                logger.info("✓ LoopSelectorComponent created successfully")
            except Exception as e:
                logger.warning(f"⚠ LoopSelectorComponent skipped: {e}")
                self._loop_selector = None

            # Playhead component removed for now (not working properly)
            self._playhead = None
            logger.debug("✓ Playhead component disabled")

            logger.info("=" * 60)
            logger.info("✓✓✓ DrumStepSequencerComponent INITIALIZED SUCCESSFULLY ✓✓✓")
            logger.info("=" * 60)

        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"✗✗✗ DrumStepSequencerComponent INITIALIZATION FAILED ✗✗✗")
            logger.error(f"Error: {e}")
            logger.error("=" * 60)
            logger.error("Full traceback:", exc_info=True)
            raise

    @mode_toggle_button.toggled
    def _on_mode_toggle_button_toggled(self, is_toggled, button):
        """Handle mode toggle button toggle"""
        logger.info(f"Mode toggle button toggled to: {is_toggled}")
        # Set the selection mode based on the toggle state (inverted logic)
        # When button is ON (is_toggled=True) → Playable mode (selection_only=False)
        # When button is OFF (is_toggled=False) → Selection mode (selection_only=True)
        self.set_selection_only_mode(not is_toggled)
        logger.info(f"Mode set to: {'Selection' if not is_toggled else 'Playable'}")

    def _on_target_track_changed(self):
        """Handle target track changes from framework's TargetTrackComponent"""
        if not self._target_track:
            return
        current_track = self._target_track.target_track
        track_name = getattr(current_track, 'name', 'Unknown') if current_track else 'None'
        is_locked = getattr(self._target_track, 'is_locked_to_track', False)
        logger.info(f"Target track changed: {track_name} (locked: {is_locked})")

        # Update child components to use new target track
        self._update_child_components()

        # Update drum group device for the new target track
        if not current_track:
            return

        # Find drum rack device on the target track
        drum_rack_device = None
        for device in current_track.devices:
            if hasattr(device, 'can_have_chains') and device.can_have_chains:
                drum_rack_device = device
                break

        if drum_rack_device:
            self.set_drum_group_device(drum_rack_device)


    @resolution_button.pressed
    def _on_resolution_button_pressed(self, button):
        """Cycle through grid resolutions"""
        current_index = self._grid_resolution.index
        next_index = (current_index + 1) % 8  # 8 resolutions available
        self._grid_resolution.index = next_index
        resolution_name = self._grid_resolution._resolutions[next_index].name
        logger.info(f"Grid resolution changed to: {resolution_name}")

    # Velocity button handlers
    @velocity_accent_button.pressed
    def _on_velocity_accent_button_pressed(self, button):
        """Handle accent button press"""
        self._current_velocity = ACCENT_VELOCITY
        # Change button color to pulsing
        button.color = "DrumStepSequencer.VelocityAccentOn"

    @velocity_accent_button.released
    def _on_velocity_accent_button_released(self, button):
        """Handle accent button release"""
        self._current_velocity = NORMAL_VELOCITY
        # Change button color back to dim
        button.color = "DrumStepSequencer.VelocityAccentOff"

    @velocity_soft_button.pressed
    def _on_velocity_soft_button_pressed(self, button):
        """Handle soft button press"""
        self._current_velocity = SOFT_VELOCITY
        # Change button color to pulsing
        button.color = "DrumStepSequencer.VelocitySoftOn"

    @velocity_soft_button.released
    def _on_velocity_soft_button_released(self, button):
        """Handle soft button release"""
        self._current_velocity = NORMAL_VELOCITY
        # Change button color back to half-brightness
        button.color = "DrumStepSequencer.VelocitySoftOff"

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

        # Pass the matrix to the drum group component
        self._drum_group.set_matrix(matrix)

        logger.info("Matrix set for drum step sequencer")

    def set_drum_group_device(self, drum_group_device):
        """Set the drum group device for the drum group component"""
        self._drum_group.set_drum_group_device(drum_group_device)

    def set_step_sequence_matrix(self, matrix):
        """Set the matrix for the step sequencer grid (8x4 = 32 steps)"""
        logger.debug("Setting step sequence matrix")
        logger.debug(f"Matrix type: {type(matrix)}, Matrix: {matrix}")

        # Connect matrix to note editor - this handles step programming and visual feedback
        self._note_editor.set_matrix(matrix)

        logger.info("Step sequence matrix set successfully")

    @property
    def step_sequence_matrix(self):
        """Get the step sequence matrix (required by Ableton framework)"""
        return self._note_editor.matrix

    @step_sequence_matrix.setter
    def step_sequence_matrix(self, matrix):
        """Set the step sequence matrix via property (required by Ableton framework)"""
        self.set_step_sequence_matrix(matrix)

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

    def _update_child_components(self):
        """Update all child components to use the current target track"""
        if not self._target_track:
            return
        current_track = self._target_track.target_track
        if not current_track:
            return
        # Update drum group to use current target track
        if hasattr(self._drum_group, 'set_target_track'):
            self._drum_group.set_target_track(current_track)

        # Update sequencer clip to use current target track
        if hasattr(self._sequencer_clip, 'set_target_track'):
            self._sequencer_clip.set_target_track(current_track)

    def set_drum_rack_level_component(self, drum_rack_level_component):
        """Set reference to the DrumRackLevelComponent for coordination"""
        if not drum_rack_level_component:
            return
        drum_rack_level_component.set_drum_step_sequencer(self)

    # Note: Component target management now handled by framework's TargetTrackComponent

    def update(self):
        """Update the component"""
        super().update()
        logger.debug("Updating drum step sequencer component")

        # Update composed components
        self._drum_group.update()
        self._note_editor.update()
        if self._loop_selector:
            self._loop_selector.update()

