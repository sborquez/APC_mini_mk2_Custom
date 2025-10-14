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
    from ableton.v3.live import liveobj_valid, get_bar_length
    from Live.Clip import MidiNoteSpecification  # type: ignore
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
    from .ableton.v3.live import liveobj_valid, get_bar_length
    try:
        from Live.Clip import MidiNoteSpecification  # type: ignore
    except ImportError:
        # Fallback for when Live.Clip is not available
        MidiNoteSpecification = None

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


class CustomVelocityProvider(EventObject):
    """
    Custom velocity provider that responds to accent and soft button states.
    This replaces the framework's full_velocity component for our custom velocity control.
    """
    enabled = listenable_property.managed(False)

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._accent_pressed = False
        self._soft_pressed = False
        self._current_velocity = NORMAL_VELOCITY
        logger.debug(f"CustomVelocityProvider initialized with velocity: {self._current_velocity}")

    def set_accent_pressed(self, pressed):
        """Set accent button state"""
        if self._accent_pressed != pressed:
            self._accent_pressed = pressed
            self._update_velocity()
            logger.debug(f"Accent button {'pressed' if pressed else 'released'}, velocity: {self._current_velocity}")

    def set_soft_pressed(self, pressed):
        """Set soft button state"""
        if self._soft_pressed != pressed:
            self._soft_pressed = pressed
            self._update_velocity()
            logger.debug(f"Soft button {'pressed' if pressed else 'released'}, velocity: {self._current_velocity}")

    def _update_velocity(self):
        """Update current velocity based on button states"""
        if self._accent_pressed:
            self._current_velocity = ACCENT_VELOCITY
        elif self._soft_pressed:
            self._current_velocity = SOFT_VELOCITY
        else:
            self._current_velocity = NORMAL_VELOCITY

    @property
    def velocity(self):
        """Get the current velocity value"""
        return self._current_velocity


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
        logger.info(f"DrumPadPitchProvider initialized with pitches: {self.pitches}")

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
            logger.debug("CustomDrumGroup: Registered target track listener")

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
                            logger.info(f"Selected drum pad: {pad_name} (MIDI note {note})")
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

class CustomNoteEditorComponent(NoteEditorComponent):
    """
    Custom note editor that uses our CustomVelocityProvider instead of the framework's full_velocity.
    Provides velocity-based step colors and smart note management:
    - Pressing a step with the same velocity as existing notes deletes them
    - Pressing a step with different velocity updates existing notes
    - Pressing an empty step adds new notes with current velocity
    - Automatically extends clip loop length when notes are added outside current loop
    - Automatically contracts clip loop length when notes are deleted and empty bars remain at the end
    """

    def __init__(self, custom_velocity_provider=None, *a, **k):
        # Don't pass full_velocity to parent - we'll handle it ourselves
        super().__init__(*a, **k)
        self._custom_velocity_provider = custom_velocity_provider
        logger.debug("CustomNoteEditorComponent initialized with custom velocity provider")

    def _add_new_note_in_step(self, pitch, time):
        """Override to use our custom velocity provider and handle loop extension"""
        if not self._has_clip():
            logger.warning("Cannot add note - no clip available")
            return

        if self._custom_velocity_provider:
            velocity = self._custom_velocity_provider.velocity
        else:
            velocity = NORMAL_VELOCITY  # Fallback to normal velocity

        if MidiNoteSpecification is None:
            logger.error("MidiNoteSpecification not available - cannot add note")
            return

        # Check if note is outside current loop and extend if necessary
        note_end_time = time + self.step_length
        if self._clip and hasattr(self._clip, 'loop_end'):
            current_loop_end = self._clip.loop_end

            if note_end_time > current_loop_end:
                # Calculate how many bars to extend (round up to next bar)

                bar_length = get_bar_length(self._clip)
                bars_to_extend = int((note_end_time - current_loop_end) / bar_length) + 1
                new_loop_end = current_loop_end + (bars_to_extend * bar_length)

                # Extend the loop
                if hasattr(self._clip, 'loop_end'):
                    self._clip.loop_end = new_loop_end
                if hasattr(self._clip, 'end_marker'):
                    self._clip.end_marker = new_loop_end
                logger.debug(f"Extended clip loop from {current_loop_end} to {new_loop_end} to accommodate note at {time}")

        note = MidiNoteSpecification(pitch=pitch,
          start_time=time,
          duration=(self.step_length),
          velocity=velocity,
          mute=False)

        # Add safety checks for clip methods
        if hasattr(self._clip, 'add_new_notes'):
            self._clip.add_new_notes((note,))  # type: ignore
        else:
            logger.error("Clip does not have add_new_notes method")
            return

        if hasattr(self._clip, 'deselect_all_notes'):
            self._clip.deselect_all_notes()  # type: ignore
        else:
            logger.warning("Clip does not have deselect_all_notes method")

        logger.debug(f"Added note with velocity: {velocity}")

    def _contract_loop_if_possible(self):
        """Remove empty bars from the end of the loop"""
        if not self._has_clip() or not self._clip or not hasattr(self._clip, 'loop_end'):
            return

        current_loop_end = self._clip.loop_end
        bar_length = get_bar_length(self._clip)

        # Start from the last bar and work backwards
        last_bar_start = current_loop_end - bar_length

        while last_bar_start >= bar_length:  # Don't go below 1 bar minimum
            # Check if this bar has any notes
            if self._bar_has_notes(last_bar_start, bar_length):
                break  # Found a bar with notes, stop here

            # This bar is empty, remove it
            new_loop_end = last_bar_start
            if hasattr(self._clip, 'loop_end'):
                self._clip.loop_end = new_loop_end
            if hasattr(self._clip, 'end_marker'):
                self._clip.end_marker = new_loop_end

            logger.debug(f"Contracted clip loop from {current_loop_end} to {new_loop_end} (removed empty bar)")
            current_loop_end = new_loop_end
            last_bar_start = current_loop_end - bar_length

    def _bar_has_notes(self, bar_start, bar_length):
        """Check if a bar contains any notes"""
        if not self._has_clip() or not self._clip:
            return False

        try:
            # Get all notes in this bar
            notes = self._clip.get_notes_extended(
                from_time=bar_start,
                from_pitch=0,
                time_span=bar_length,
                pitch_span=128
            )
            return len(notes) > 0
        except Exception as e:
            logger.warning(f"Error checking for notes in bar: {e}")
            return True  # If we can't check, assume there are notes to be safe

    def _get_velocity_for_step(self, step):
        """Get the velocity of the first note in a step"""
        if not self._has_clip():
            return None

        time_step = self._time_step(self._get_step_start_time(step))
        notes = time_step.filter_notes(self._clip_notes)

        if notes:
            return notes[0].velocity
        return None

    def _get_color_for_step(self, index, visible_steps):
        """Override to provide velocity-based colors"""
        # Get the base color from parent
        base_color = super()._get_color_for_step(index, visible_steps)

        # If there's a note in this step, check its velocity for color coding
        if self._has_clip() and index in visible_steps:
            step = visible_steps[index]
            notes = step.filter_notes(self._clip_notes)

            if len(notes) > 0:
                velocity = notes[0].velocity

                # Determine color based on velocity
                if velocity >= ACCENT_VELOCITY:
                    return "DrumStepSequencer.StepAccent"  # Accent velocity (127)
                elif velocity <= SOFT_VELOCITY:
                    return "DrumStepSequencer.StepSoft"    # Soft velocity (60)
                else:
                    return "DrumStepSequencer.StepNormal"  # Normal velocity (100)

        return base_color

    def _on_release_step(self, step, can_add_or_remove=False):
        """Override to handle velocity-based note operations"""
        if step.is_active:
            if can_add_or_remove:
                # Check if there are existing notes in this step
                time_step = self._time_step(self._get_step_start_time(step))
                existing_notes = time_step.filter_notes(self._clip_notes)

                if existing_notes:
                    # Get current velocity from velocity provider
                    if self._custom_velocity_provider:
                        current_velocity = self._custom_velocity_provider.velocity
                    else:
                        current_velocity = NORMAL_VELOCITY

                    # Get existing note velocity
                    existing_velocity = existing_notes[0].velocity

                    # If current velocity matches existing velocity, delete the note
                    if current_velocity == existing_velocity:
                        self._delete_notes_in_step(step)
                        logger.debug(f"Deleted note with matching velocity: {current_velocity}")
                        # After deleting notes, check if we can contract the loop
                        self._contract_loop_if_possible()
                    else:
                        # Different velocity - update existing notes with new velocity
                        self._update_notes_velocity_in_step(step)
                        logger.debug(f"Updated note velocity: {existing_velocity} → {current_velocity}")
                else:
                    # No existing notes - add new ones
                    for pitch in self._pitches:
                        self._add_note_in_step(step, pitch)

        step.is_active = False
        self._refresh_active_steps()

    def _update_notes_velocity_in_step(self, step):
        """Update the velocity of existing notes in a step"""
        if not self._has_clip() or not self._custom_velocity_provider:
            return

        new_velocity = self._custom_velocity_provider.velocity
        time_step = self._time_step(self._get_step_start_time(step))
        existing_notes = time_step.filter_notes(self._clip_notes)

        if existing_notes:
            # Update velocity for all notes in this step
            for note in existing_notes:
                note.velocity = new_velocity

            # Apply the modifications to the clip
            if hasattr(self._clip, 'apply_note_modifications'):
                self._clip.apply_note_modifications(self._clip_notes)  # type: ignore
            else:
                logger.warning("Clip does not have apply_note_modifications method")

            logger.debug(f"Updated {len(existing_notes)} note(s) to velocity: {new_velocity}")


class DrumStepSequencerComponent(Component):
    """
    Custom drum step sequencer component for APC Mini MK2.

    Layout:
    - Drum group: 4x4 grid (16 drum pads) in left-bottom area
    - Step sequencer: 4x8 grid (32 steps) in top area
    - Control grid: 2x4 grid (8 control buttons) in right-bottom area

    Velocity Control:
    - Hold accent button and press step buttons to add notes with ACCENT_VELOCITY (127)
    - Hold soft button and press step buttons to add notes with SOFT_VELOCITY (60)
    - Press step buttons without holding any velocity button to add notes with NORMAL_VELOCITY (100)
    - Pressing a step with existing notes of the same velocity deletes them
    - Pressing a step with existing notes of different velocity updates their velocity
    - Step colors indicate velocity: White (normal), Half-brightness (soft), Amber (accent)
    - Clip loop automatically extends when notes are added outside current loop length
    - Clip loop automatically contracts when notes are deleted and empty bars remain at the end
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
                logger.debug("Parent Component.__init__ successful")
            except Exception as e:
                logger.error(f"Parent Component.__init__ FAILED: {e}", exc_info=True)
                raise

            # Store dependencies
            self._target_track = target_track
            logger.debug(f"Stored target_track: {target_track}")

            # Listen to target track changes
            if self._target_track:
                self.register_slot(self._target_track, self._on_target_track_changed, "target_track")
                logger.debug("Registered target track listener")

            # Create custom velocity provider
            try:
                logger.debug("Creating CustomVelocityProvider...")
                self._velocity_provider = CustomVelocityProvider()
                logger.info("CustomVelocityProvider created successfully")
            except Exception as e:
                logger.error(f"CustomVelocityProvider FAILED: {e}", exc_info=True)
                raise

            # Create pitch provider first (needed by drum group)
            try:
                logger.debug("Creating DrumPadPitchProvider...")
                self._pitch_provider = DrumPadPitchProvider(
                    drum_group_component=None  # Will be set after drum group is created
                )
                logger.info("DrumPadPitchProvider created successfully")
            except Exception as e:
                logger.error(f"DrumPadPitchProvider FAILED: {e}", exc_info=True)
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
                logger.info("CustomDrumGroupComponent created successfully")
            except Exception as e:
                logger.error(f"CustomDrumGroupComponent FAILED: {e}", exc_info=True)
                raise

            # Create sequencer clip helper
            try:
                logger.debug("Creating SequencerClip...")
                self._sequencer_clip = SequencerClip(
                    target_track=target_track
                )
                logger.info("SequencerClip created successfully")
            except Exception as e:
                logger.error(f"SequencerClip FAILED: {e}", exc_info=True)
                raise

            # Create our own grid resolution component
            try:
                logger.debug("Creating GridResolutionComponent...")
                self._grid_resolution = GridResolutionComponent(
                    name="Grid_Resolution",
                    parent=self
                )
                logger.info("GridResolutionComponent created successfully")
            except Exception as e:
                logger.error(f"GridResolutionComponent FAILED: {e}", exc_info=True)
                raise

            # Note editor for step input (custom component with velocity control)
            try:
                logger.debug("Creating CustomNoteEditorComponent...")
                # Inject sequencer_clip dependency
                with inject(sequencer_clip=const(self._sequencer_clip)).everywhere():
                    self._note_editor = CustomNoteEditorComponent(
                        custom_velocity_provider=self._velocity_provider,
                        grid_resolution=self._grid_resolution,
                        parent=self
                    )
                logger.debug("Setting pitch provider on note editor...")
                self._note_editor.pitch_provider = self._pitch_provider
                logger.info("CustomNoteEditorComponent created successfully")

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
                logger.info("NoteEditorPaginator created successfully")
            except Exception as e:
                logger.error(f"NoteEditorPaginator FAILED: {e}", exc_info=True)
                raise

            # Loop selector (optional - may fail due to dependencies)
            self._loop_selector = None
            try:
                logger.debug("Creating LoopSelectorComponent (optional)...")
                self._loop_selector = LoopSelectorComponent(
                    paginator=self._paginator,
                    parent=self
                )
                logger.info("LoopSelectorComponent created successfully")
            except Exception as e:
                logger.warning(f"LoopSelectorComponent skipped: {e}")
                self._loop_selector = None

            # Playhead component removed for now (not working properly)
            self._playhead = None
            logger.debug("Playhead component disabled")

            logger.info("=" * 60)
            logger.info("✓✓DrumStepSequencerComponent INITIALIZED SUCCESSFULLY ✓✓✓")
            logger.info("=" * 60)

        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"✗✗DrumStepSequencerComponent INITIALIZATION FAILED ✗✗✗")
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
        self._velocity_provider.set_accent_pressed(True)
        # Change button color to pulsing
        button.color = "DrumStepSequencer.VelocityAccentOn"
        logger.info(f"Accent button pressed - velocity: {self._velocity_provider.velocity}")

    @velocity_accent_button.released
    def _on_velocity_accent_button_released(self, button):
        """Handle accent button release"""
        self._velocity_provider.set_accent_pressed(False)
        # Change button color back to dim
        button.color = "DrumStepSequencer.VelocityAccentOff"
        logger.info(f"Accent button released - velocity: {self._velocity_provider.velocity}")

    @velocity_soft_button.pressed
    def _on_velocity_soft_button_pressed(self, button):
        """Handle soft button press"""
        self._velocity_provider.set_soft_pressed(True)
        # Change button color to pulsing
        button.color = "DrumStepSequencer.VelocitySoftOn"
        logger.info(f"Soft button pressed - velocity: {self._velocity_provider.velocity}")

    @velocity_soft_button.released
    def _on_velocity_soft_button_released(self, button):
        """Handle soft button release"""
        self._velocity_provider.set_soft_pressed(False)
        # Change button color back to half-brightness
        button.color = "DrumStepSequencer.VelocitySoftOff"
        logger.info(f"Soft button released - velocity: {self._velocity_provider.velocity}")

    @property
    def drum_group(self):
        """Access to the composed drum group component"""
        return self._drum_group

    @property
    def current_velocity(self):
        """Get the current velocity value from the velocity provider"""
        return self._velocity_provider.velocity if self._velocity_provider else NORMAL_VELOCITY

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

