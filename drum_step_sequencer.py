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
        PlayableComponent,
        NoteEditorPaginator,
        SequencerClip
    )
    from ableton.v3.control_surface.controls import ButtonControl, control_matrix, ToggleButtonControl
    from ableton.v3.base import depends, listens, listenable_property, EventObject, inject, const, task
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
        PlayableComponent,
        NoteEditorPaginator,
        SequencerClip
    )
    from .ableton.v3.control_surface.controls import ButtonControl, control_matrix, ToggleButtonControl
    from .ableton.v3.base import depends, listens, listenable_property, EventObject, inject, const, task
    from .ableton.v3.live import liveobj_valid

from .logger_config import get_logger
from .colors import Skin

logger = get_logger('drum_step_sequencer')

# Constants for the 8x8 grid layout
# Sequencer steps (top 4x8 = 32 steps for 2 bars of 16 steps)
SEQUENCE_STEPS_WIDTH = 8
SEQUENCE_STEPS_HEIGHT = 4  # 2 bars of 16 steps = 32 steps total

# Default settings
DEFAULT_SEQUENCE_LENGTH = 1  # bars
DEFAULT_RESOLUTION = 16  # 1/16 notes
DEFAULT_GROOVE = 0  # -100 to 100

# Velocity modes
NORMAL_VELOCITY = 100
SOFT_VELOCITY = 60
ACCENT_VELOCITY = 127


class CustomPlayheadComponent(Component):
    """
    Custom playhead component that visually indicates the current playing step
    on the step sequencer grid. Works with button matrices unlike the built-in
    PlayheadComponent which requires hardware playhead elements.
    """

    def __init__(self, paginator=None, grid_resolution=None, *a, **k):
        super().__init__(*a, **k)
        self._paginator = paginator
        self._grid_resolution = grid_resolution
        self._matrix = None
        self._clip = None
        self._current_step = -1
        self._is_playing = False
        self._playhead_task = None

        # Task for periodic playhead updates
        try:
            self._playhead_task = self._tasks.add(task.loop(task.sequence(  # type: ignore
                task.run(self._update_playhead),
                task.wait(0.1)  # Update every 100ms
            )))
            self._playhead_task.kill()
        except Exception as e:
            logger.warning(f"Failed to create playhead task: {e}")

        # Listen to song playback state
        self._CustomPlayheadComponent__on_is_playing_changed.subject = self.song

        logger.debug("CustomPlayheadComponent initialized")

    def disconnect(self):
        """Clean up when component is disconnected"""
        if self._playhead_task:
            self._playhead_task.kill()
        super().disconnect()

    def set_matrix(self, matrix):
        """Set the button matrix for playhead visualization"""
        self._matrix = matrix
        logger.debug(f"CustomPlayheadComponent matrix set: {matrix}")

    def set_clip(self, clip):
        """Set the clip to track for playhead position"""
        if liveobj_valid(clip) and clip != self._clip:
            self._clip = clip
            logger.debug(f"CustomPlayheadComponent clip set: {clip}")
            self._update_playhead_state()

    @listens('is_playing')  # type: ignore
    def __on_is_playing_changed(self):
        """Called when song playback starts/stops"""
        self._update_playhead_state()

    def _update_playhead_state(self):
        """Update whether playhead should be actively tracking"""
        if not self._playhead_task:
            return

        is_playing = self.song.is_playing if self.song else False
        clip_is_playing = False

        if liveobj_valid(self._clip):
            clip_is_playing = self._clip.is_arrangement_clip or self._clip.is_playing  # type: ignore

        should_show_playhead = self.is_enabled() and is_playing and clip_is_playing

        if should_show_playhead and not self._playhead_task.is_running:
            self._playhead_task.restart()
            logger.debug("Playhead tracking started")
        elif not should_show_playhead and self._playhead_task.is_running:
            self._playhead_task.kill()
            self._clear_playhead()
            logger.debug("Playhead tracking stopped")

    def _update_playhead(self):
        """Update the current playhead position visualization"""
        if not self.is_enabled():
            logger.debug("Playhead not enabled")
            return

        if not self._matrix:
            logger.debug("Playhead has no matrix")
            return

        if not liveobj_valid(self._clip):
            logger.debug("Playhead has no valid clip")
            return

        if not self._grid_resolution:
            logger.debug("Playhead has no grid resolution")
            return

        # Get current playback position
        try:
            playing_position = self._clip.playing_position  # type: ignore
        except AttributeError:
            logger.debug("Clip has no playing_position")
            return

        # Calculate which step is currently playing
        step_length = self._grid_resolution.step_length
        page_time = self._paginator.page_time if self._paginator else 0.0

        # Calculate step index relative to current page
        position_in_page = playing_position - page_time
        current_step_index = int(position_in_page / step_length)

        # Only update if step changed
        if current_step_index != self._current_step:
            logger.debug(f"Playhead moved: pos={playing_position:.2f}, page={page_time:.2f}, step_len={step_length:.4f}, step={current_step_index}")
            self._clear_playhead()
            self._current_step = current_step_index
            self._draw_playhead()

    def _draw_playhead(self):
        """Draw the playhead indicator on the current step"""
        if not self._matrix:
            logger.debug("_draw_playhead: no matrix")
            return

        if self._current_step < 0:
            logger.debug(f"_draw_playhead: negative step {self._current_step}")
            return

        width = self._matrix.width if self._matrix else 8
        height = self._matrix.height if self._matrix else 4
        total_steps = width * height

        logger.debug(f"_draw_playhead: step={self._current_step}, width={width}, height={height}, total={total_steps}")

        if 0 <= self._current_step < total_steps:
            # Calculate row and column from step index
            # Matrix is organized as rows from top to bottom
            row = self._current_step // width
            col = self._current_step % width

            logger.debug(f"Drawing playhead at col={col}, row={row}")

            if row < height and col < width:
                button = self._matrix.get_button(col, row)
                logger.debug(f"Got button: {button}")

                if button:
                    # Set playhead color (green blink)
                    button.color = 'NoteEditor.Playhead'
                    logger.info(f"✓ Playhead drawn at step {self._current_step} (col={col}, row={row})")
                else:
                    logger.warning(f"No button at col={col}, row={row}")
        else:
            logger.debug(f"Step {self._current_step} out of range (0-{total_steps-1})")

    def _clear_playhead(self):
        """Clear the previous playhead indicator"""
        if not self._matrix or self._current_step < 0:
            return

        width = self._matrix.width if self._matrix else 8
        height = self._matrix.height if self._matrix else 4

        if 0 <= self._current_step < width * height:
            row = self._current_step // width
            col = self._current_step % width

            if row < height and col < width:
                button = self._matrix.get_button(col, row)
                if button:
                    # Let the note editor handle the normal button color
                    button.color = None

        self._current_step = -1

    def update(self):
        """Update component state"""
        super().update()
        if self.is_enabled():
            self._update_playhead_state()
        else:
            if self._playhead_task and self._playhead_task.is_running:
                self._playhead_task.kill()
            self._clear_playhead()


class NoteEditorWithPlayheadComponent(NoteEditorComponent):
    """
    Custom NoteEditorComponent that integrates playhead visualization.
    Overrides button rendering to show the current playing step.
    """

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._playhead_step = -1
        self._is_playing = False
        self._playhead_task = None

        # Task for periodic playhead updates
        try:
            self._playhead_task = self._tasks.add(task.loop(task.sequence(  # type: ignore
                task.run(self._update_playhead_position),
                task.wait(0.05)  # Update every 50ms for smooth playhead
            )))
            self._playhead_task.kill()
        except Exception as e:
            logger.warning(f"Failed to create playhead task: {e}")

        # Listen to song playback state
        self._NoteEditorWithPlayheadComponent__on_is_playing_changed.subject = self.song

        logger.debug("NoteEditorWithPlayheadComponent initialized")

    def disconnect(self):
        """Clean up when component is disconnected"""
        if self._playhead_task:
            self._playhead_task.kill()
        super().disconnect()

    @listens('is_playing')  # type: ignore
    def __on_is_playing_changed(self):
        """Called when song playback starts/stops"""
        self._update_playhead_state()

    def _update_playhead_state(self):
        """Update whether playhead should be actively tracking"""
        if not self._playhead_task:
            return

        is_playing = self.song.is_playing if self.song else False

        # Check if we have a valid clip
        clip = self._clip if hasattr(self, '_clip') else None
        clip_is_playing = False

        if liveobj_valid(clip):
            clip_is_playing = clip.is_arrangement_clip or clip.is_playing  # type: ignore

        should_show_playhead = self.is_enabled() and is_playing and clip_is_playing

        if should_show_playhead and not self._playhead_task.is_running:
            self._playhead_task.restart()
            self._is_playing = True
            logger.debug("Playhead tracking started")
        elif not should_show_playhead and self._playhead_task.is_running:
            self._playhead_task.kill()
            self._is_playing = False
            old_step = self._playhead_step
            self._playhead_step = -1
            # Refresh the old playhead button
            if 0 <= old_step < len(self.matrix):
                self._update_button(old_step)
            logger.debug("Playhead tracking stopped")

    def _update_playhead_position(self):
        """Update the current playhead position"""
        if not self.is_enabled() or not self._clip or not liveobj_valid(self._clip):
            return

        # Get current playback position
        try:
            playing_position = self._clip.playing_position  # type: ignore
        except AttributeError:
            return

        # Calculate which step is currently playing
        page_time = self._page_time if hasattr(self, '_page_time') else 0.0
        position_in_page = playing_position - page_time
        current_step = int(position_in_page / self.step_length)

        # Only update if step changed
        if current_step != self._playhead_step:
            old_step = self._playhead_step
            self._playhead_step = current_step

            # Refresh both old and new playhead buttons
            if 0 <= old_step < len(self.matrix):
                self._update_button(old_step)
            if 0 <= current_step < len(self.matrix):
                self._update_button(current_step)

    def _update_button(self, index):
        """Update a single button's color"""
        if not self.matrix or index < 0 or index >= len(self.matrix):
            return

        button = self.matrix[index]
        if not button:
            return

        # Determine button color based on state
        if self._is_playing and index == self._playhead_step:
            # Playhead takes priority
            button.color = 'NoteEditor.Playhead'
        else:
            # Use normal note editor coloring
            self._set_button_color_for_step(button, index)

    def _set_button_color_for_step(self, button, step_index):
        """Set button color based on note data (same as parent class logic)"""
        # This mimics the parent class's button coloring logic
        # We need to check if there's a note at this step
        time_step = self._time_step(self._get_step_start_time(step_index))

        has_notes = False
        for time, length in time_step.connected_time_ranges():
            notes = self._get_notes_info(time, length)
            if notes:
                has_notes = True
                break

        if has_notes:
            button.color = 'NoteEditor.StepFilled'
        else:
            button.color = 'NoteEditor.StepEmpty'

    def update(self):
        """Update component state"""
        super().update()
        if self.is_enabled():
            self._update_playhead_state()
        else:
            if self._playhead_task and self._playhead_task.is_running:
                self._playhead_task.kill()
            self._playhead_step = -1


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

    def __init__(self, name="Drum_Group", target_track=None, selection_only=False, pitch_provider=None, *a, **k):
        super().__init__(name=name, target_track=target_track, *a, **k)
        self._selection_only = selection_only
        self._pitch_provider = pitch_provider
        self._selected_drum_pad_note = None

        logger.debug(f"CustomDrumGroupComponent init: selection_only={selection_only}, pitch_provider={pitch_provider}")

        # If in selection-only mode, always keep pads in listenable mode
        if self._selection_only:
            self._set_control_pads_from_script(True)
            logger.debug("Set control pads from script (listenable mode)")

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

            # Note editor with integrated playhead for step input
            try:
                logger.debug("Creating NoteEditorWithPlayheadComponent...")
                # Inject sequencer_clip dependency
                with inject(sequencer_clip=const(self._sequencer_clip)).everywhere():
                    self._note_editor = NoteEditorWithPlayheadComponent(
                        grid_resolution=self._grid_resolution,
                        parent=self
                    )
                logger.debug("Setting pitch provider on note editor...")
                self._note_editor.pitch_provider = self._pitch_provider
                logger.info("✓ NoteEditorWithPlayheadComponent created successfully")
            except Exception as e:
                logger.error(f"✗ NoteEditorWithPlayheadComponent FAILED: {e}", exc_info=True)
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

            # Playhead is now integrated into NoteEditorWithPlayheadComponent
            self._playhead = None
            logger.debug("✓ Playhead integrated into NoteEditor")

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
        logger.debug(f"Setting drum group device: {drum_group_device}")
        self._drum_group.set_drum_group_device(drum_group_device)

    def set_step_sequence_matrix(self, matrix):
        """Set the matrix for the step sequencer grid (8x4 = 32 steps)"""
        logger.debug("Setting step sequence matrix")
        logger.debug(f"Matrix type: {type(matrix)}, Matrix: {matrix}")

        # Connect matrix to note editor - this handles step programming and visual feedback
        self._note_editor.set_matrix(matrix)

        # Connect matrix to custom playhead for current step indicator
        if self._playhead:
            self._playhead.set_matrix(matrix)
            logger.debug("✓ Playhead matrix connected")

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

    def update(self):
        """Update the component"""
        super().update()
        logger.debug("Updating drum step sequencer component")

        # Update composed components
        self._drum_group.update()
        self._note_editor.update()
        if self._loop_selector:
            self._loop_selector.update()
        if self._playhead:
            self._playhead.update()

