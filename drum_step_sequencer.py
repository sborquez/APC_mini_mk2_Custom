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
    from ableton.v3.base import depends, listenable_property, EventObject, inject, const, listens
    from ableton.v3.live import liveobj_valid, get_bar_length, playing_clip_slot, scene_index
    from Live.Clip import MidiNoteSpecification  # type: ignore
    from Live.Song import Quantization  # type: ignore
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
    from .ableton.v3.base import depends, listenable_property, EventObject, inject, const, listens
    from .ableton.v3.live import liveobj_valid, get_bar_length, playing_clip_slot, scene_index

    from Live.Clip import MidiNoteSpecification  # type: ignore
    from Live.Song import Quantization  # type: ignore


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

    def __init__(self, custom_velocity_provider=None, parent_sequencer=None, *a, **k):
        # Don't pass full_velocity to parent - we'll handle it ourselves
        super().__init__(*a, **k)
        self._custom_velocity_provider = custom_velocity_provider
        self._parent_sequencer = parent_sequencer  # Reference to parent to access double_time_active
        logger.debug("CustomNoteEditorComponent initialized with custom velocity provider and parent sequencer")

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

        # Check if double time mode is active
        double_time_active = False
        if self._parent_sequencer and hasattr(self._parent_sequencer, '_double_time_active'):
            double_time_active = self._parent_sequencer._double_time_active

        if double_time_active:
            # Add two notes with half the resolution (half the step length)
            half_duration = self.step_length / 2.0

            note1 = MidiNoteSpecification(
                pitch=pitch,
                start_time=time,
                duration=half_duration,
                velocity=velocity,
                mute=False
            )

            note2 = MidiNoteSpecification(
                pitch=pitch,
                start_time=time + half_duration,
                duration=half_duration,
                velocity=velocity,
                mute=False
            )

            # Add both notes
            if hasattr(self._clip, 'add_new_notes'):
                self._clip.add_new_notes((note1, note2))  # type: ignore
            else:
                return
        else:
            # Normal mode: add single note with full step length
            note = MidiNoteSpecification(
                pitch=pitch,
                start_time=time,
                duration=(self.step_length),
                velocity=velocity,
                mute=False
            )

            # Add safety checks for clip methods
            if hasattr(self._clip, 'add_new_notes'):
                self._clip.add_new_notes((note,))  # type: ignore
            else:
                return

        if hasattr(self._clip, 'deselect_all_notes'):
            self._clip.deselect_all_notes()  # type: ignore

    def _get_alternate_color_for_step(self, index, visible_steps):
        """Override to provide velocity-based and double time colors"""
        # Check if this step has notes
        if index in visible_steps:
            notes = visible_steps[index].filter_notes(self._clip_notes)
            if len(notes) > 0:
                # Double time takes priority over velocity modifiers
                if self._parent_sequencer and hasattr(self._parent_sequencer, '_double_time_active'):
                    if self._parent_sequencer._double_time_active:
                        logger.debug(f"Step {index}: Using double time color (blue)")
                        return "NoteEditor.StepDoubleTime"

                # Check velocity-based colors (only if double time is not active)
                if self._custom_velocity_provider:
                    velocity = self._custom_velocity_provider.velocity
                    if velocity >= 127:  # Accent velocity
                        logger.debug(f"Step {index}: Using accent color (amber), velocity: {velocity}")
                        return "NoteEditor.StepAccent"
                    elif velocity <= 60:  # Soft velocity
                        logger.debug(f"Step {index}: Using soft color (yellow), velocity: {velocity}")
                        return "NoteEditor.StepSoft"
                    else:  # Normal velocity
                        logger.debug(f"Step {index}: Using normal color (white), velocity: {velocity}")
                        return "NoteEditor.StepNormal"
        return None

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
        """Override to provide velocity-based and double time colors"""
        # Get the base color from parent
        base_color = super()._get_color_for_step(index, visible_steps)

        # If there's a note in this step, check for double time and velocity-based colors
        if self._has_clip() and index in visible_steps:
            step = visible_steps[index]
            notes = step.filter_notes(self._clip_notes)

            if len(notes) > 0:
                # Check if this step contains double time notes (two notes with half duration)
                if len(notes) >= 2:
                    # Check if the notes have half the expected duration (indicating double time)
                    expected_duration = self.step_length
                    half_duration = expected_duration / 2.0

                    # Check if both notes have approximately half duration
                    note1_duration = notes[0].duration
                    note2_duration = notes[1].duration if len(notes) > 1 else 0

                    if (abs(note1_duration - half_duration) < 0.01 and
                        abs(note2_duration - half_duration) < 0.01):
                        return "NoteEditor.StepDoubleTime"

                # Use the actual note velocity for single notes or non-double-time notes
                velocity = notes[0].velocity
                if velocity >= ACCENT_VELOCITY:
                    return "NoteEditor.StepAccent"
                elif velocity <= SOFT_VELOCITY:
                    return "NoteEditor.StepSoft"
                else:
                    return "NoteEditor.StepNormal"
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

    # Start/stop button
    play_button = ToggleButtonControl(
        color="DrumStepSequencer.PlayOff",
        on_color="DrumStepSequencer.PlayOn",
    )

    # auto_launch_button = ToggleButtonControl(
    #     color="DrumStepSequencer.AutoLaunchOff",
    #     on_color="DrumStepSequencer.AutoLaunchOn",
    # )

    up_button = ButtonControl(
        color="DrumStepSequencer.DirectionalOff",
        on_color="DrumStepSequencer.DirectionalOn",
    )

    down_button = ButtonControl(
        color="DrumStepSequencer.DirectionalOff",
        on_color="DrumStepSequencer.DirectionalOff",
    )

    add_variant_button = ButtonControl(
        color="DrumStepSequencer.AddVariantOff",
        on_color="DrumStepSequencer.AddVariantOn",
    )

    clear_clip_button = ButtonControl(
        color="DrumStepSequencer.ClearClipOff",
        on_color="DrumStepSequencer.ClearClipOn",
    )


    double_time_button = ButtonControl(
        color="DrumStepSequencer.DoubleTimeOff",
    )

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
                self.register_slot(self._target_track, self._on_target_clip_changed, "target_clip")
                logger.debug("Registered target track and clip listeners")


            # Create custom velocity provider
            try:
                logger.debug("Creating CustomVelocityProvider...")
                self._velocity_provider = CustomVelocityProvider()
                logger.info("CustomVelocityProvider created successfully")
            except Exception as e:
                logger.error(f"CustomVelocityProvider FAILED: {e}", exc_info=True)
                raise

            # Create double time state
            self._double_time_active = False
            logger.debug("Double time state initialized to False")

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
                        parent_sequencer=self,  # Pass self as parent to access double_time_active
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

    @play_button.toggled
    def _on_play_button_toggled(self, is_toggled, button):
        """Handle play button toggle - start/stop current clip"""
        logger.info(f"Play button toggled to: {is_toggled}")

        if not self._target_track or not self._target_track.target_track:
            logger.warning("No target track available for play button")
            return

        current_track = self._target_track.target_track
        current_clip = self._target_track.target_clip

        if not current_clip:
            logger.warning("No target clip available for play button")
            return

        try:
            if is_toggled:
                # Button pressed - start playing the clip with quantization
                if not current_clip.is_playing:
                    # Find the clip slot that contains this clip
                    clip_slot = self._find_clip_slot_for_clip(current_track, current_clip)
                    if clip_slot:
                        # Use the clip's own launch quantization setting, or fall back to quarter note
                        launch_quantization = getattr(clip_slot, 'launch_quantization', Quantization.q_quarter)
                        if launch_quantization == Quantization.q_no_q:
                            # If clip is set to no quantization, use quarter note for play button
                            launch_quantization = Quantization.q_quarter

                        # Fire the clip slot with quantization
                        clip_slot.fire(launch_quantization=launch_quantization)
                        logger.info(f"Started playing clip with quantization: {getattr(current_clip, 'name', 'Unnamed')}")
                    else:
                        # Fallback to immediate fire if clip slot not found
                        current_clip.fire()
                        logger.info(f"Started playing clip immediately: {getattr(current_clip, 'name', 'Unnamed')}")
                else:
                    logger.info("Clip is already playing")
            else:
                # Button released - stop playing the clip
                if current_clip.is_playing:
                    current_clip.stop()
                    logger.info(f"Stopped playing clip: {getattr(current_clip, 'name', 'Unnamed')}")
                else:
                    logger.info("Clip is already stopped")
        except Exception as e:
            logger.error(f"Error controlling clip playback: {e}")
            # Reset button state to match actual clip state
            self._update_play_button_state()

    # @auto_launch_button.toggled
    # def _on_auto_launch_button_toggled(self, is_toggled, button):
    #     """Handle auto launch button toggle"""
    #     logger.info(f"Auto launch button toggled to: {is_toggled}")

    @up_button.pressed
    def _on_up_button_pressed(self, button):
        """Handle up button press - navigate to previous clip slot"""
        logger.info("Up button pressed - navigating to previous clip slot")
        button.color = "DrumStepSequencer.DirectionalOn"
        self._navigate_clip_slot(-1)

    @up_button.released
    def _on_up_button_released(self, button):
        """Handle up button release"""
        button.color = "DrumStepSequencer.DirectionalOff"

    @down_button.pressed
    def _on_down_button_pressed(self, button):
        """Handle down button press - navigate to next clip slot"""
        logger.info("Down button pressed - navigating to next clip slot")
        button.color = "DrumStepSequencer.DirectionalOn"
        self._navigate_clip_slot(1)

    @down_button.released
    def _on_down_button_released(self, button):
        """Handle down button release"""
        button.color = "DrumStepSequencer.DirectionalOff"

    @add_variant_button.pressed
    def _on_add_variant_button_pressed(self, button):
        """Handle add variant button press - create variant of current clip"""
        logger.info("Add variant button pressed - creating variant")
        button.color = "DrumStepSequencer.AddVariantOn"
        self._create_clip_variant()

    @add_variant_button.released
    def _on_add_variant_button_released(self, button):
        """Handle add variant button release"""
        button.color = "DrumStepSequencer.AddVariantOff"

    @clear_clip_button.pressed
    def _on_clear_clip_button_pressed(self, button):
        """Handle clear clip button press - clear notes from current clip"""
        button.color = "DrumStepSequencer.ClearClipOn"
        self._clear_current_clip_notes()

    @clear_clip_button.released
    def _on_clear_clip_button_released(self, button):
        """Handle clear clip button release"""
        button.color = "DrumStepSequencer.ClearClipOff"


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

    def _on_target_clip_changed(self):
        """Handle target clip changes from framework's TargetTrackComponent"""
        if not self._target_track:
            return

        current_clip = self._target_track.target_clip
        clip_name = getattr(current_clip, 'name', 'None') if current_clip else 'None'
        logger.info(f"=== Target clip changed: {clip_name} ===")

        # Update play button state to reflect new clip's playing status
        self._update_play_button_state()

        # Set up listener for clip playing status changes
        self._setup_clip_playing_status_listener()

    # Double time button handlers
    @double_time_button.pressed
    def _on_double_time_button_pressed(self, button):
        """Handle double time button press - enables double time note creation"""
        self._double_time_active = True
        button.color = "DrumStepSequencer.DoubleTimeOn"
        if hasattr(self, '_note_editor') and self._note_editor:
            self._note_editor._update_editor_matrix()

    @double_time_button.released
    def _on_double_time_button_released(self, button):
        """Handle double time button release - disables double time note creation"""
        self._double_time_active = False
        button.color = "DrumStepSequencer.DoubleTimeOff"
        if hasattr(self, '_note_editor') and self._note_editor:
            self._note_editor._update_editor_matrix()

    # Velocity button handlers
    @velocity_accent_button.pressed
    def _on_velocity_accent_button_pressed(self, button):
        """Handle accent button press"""
        self._velocity_provider.set_accent_pressed(True)
        button.color = "DrumStepSequencer.VelocityAccentOn"
        if hasattr(self, '_note_editor') and self._note_editor:
            self._note_editor._update_editor_matrix()

    @velocity_accent_button.released
    def _on_velocity_accent_button_released(self, button):
        """Handle accent button release"""
        self._velocity_provider.set_accent_pressed(False)
        button.color = "DrumStepSequencer.VelocityAccentOff"
        if hasattr(self, '_note_editor') and self._note_editor:
            self._note_editor._update_editor_matrix()

    @velocity_soft_button.pressed
    def _on_velocity_soft_button_pressed(self, button):
        """Handle soft button press"""
        self._velocity_provider.set_soft_pressed(True)
        button.color = "DrumStepSequencer.VelocitySoftOn"
        if hasattr(self, '_note_editor') and self._note_editor:
            self._note_editor._update_editor_matrix()

    @velocity_soft_button.released
    def _on_velocity_soft_button_released(self, button):
        """Handle soft button release"""
        self._velocity_provider.set_soft_pressed(False)
        button.color = "DrumStepSequencer.VelocitySoftOff"
        if hasattr(self, '_note_editor') and self._note_editor:
            self._note_editor._update_editor_matrix()

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

        # Only set matrix if we have a valid matrix (not None)
        # This prevents the component from being disconnected when not in drum mode
        if matrix is not None:
            self._drum_group.set_matrix(matrix)
            logger.info("Drum group matrix set successfully via property")
        else:
            logger.debug("Skipping None matrix via property setter - component not in drum mode")

    def set_drum_group_matrix(self, matrix):
        """Set the matrix for the drum step sequencer (legacy method)"""
        logger.debug(f"Setting matrix for drum step sequencer via method - enabled: {self.is_enabled()}")
        logger.debug(f"Matrix type: {type(matrix)}, Matrix: {matrix}")

        # Only set matrix if we have a valid matrix (not None)
        # This prevents the component from being disconnected when not in drum mode
        if matrix is not None:
            # Pass the matrix to the drum group component
            self._drum_group.set_matrix(matrix)
            logger.info("Matrix set for drum step sequencer")
        else:
            logger.debug("Skipping None matrix - component not in drum mode")

    def set_drum_group_device(self, drum_group_device):
        """Set the drum group device for the drum group component"""
        self._drum_group.set_drum_group_device(drum_group_device)

    def set_step_sequence_matrix(self, matrix):
        """Set the matrix for the step sequencer grid (8x4 = 32 steps)"""
        logger.debug("Setting step sequence matrix")
        logger.debug(f"Matrix type: {type(matrix)}, Matrix: {matrix}")

        # Only set matrix if we have a valid matrix (not None)
        # This prevents the component from being disconnected when not in drum mode
        if matrix is not None:
            # Connect matrix to note editor - this handles step programming and visual feedback
            self._note_editor.set_matrix(matrix)
            logger.info("Step sequence matrix set successfully")
        else:
            logger.debug("Skipping None step sequence matrix - component not in drum mode")

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

    def _update_play_button_state(self):
        """Update play button state to reflect current clip's playing status"""
        if not self._target_track or not self._target_track.target_clip:
            # No clip available - button should be off
            self.play_button.is_on = False
            logger.debug("No target clip - play button set to OFF")
            return

        current_clip = self._target_track.target_clip
        is_playing = getattr(current_clip, 'is_playing', False)

        # Update button state to match clip playing status
        self.play_button.is_on = is_playing
        logger.debug(f"Play button state updated: {'ON' if is_playing else 'OFF'} (clip playing: {is_playing})")

    def _setup_clip_playing_status_listener(self):
        """Set up listener for clip playing status changes"""
        # Clear any existing listener
        self._DrumStepSequencerComponent__on_clip_playing_status_changed.subject = None

        if not self._target_track or not self._target_track.target_clip:
            logger.debug("No target clip available for playing status listener")
            return

        current_clip = self._target_track.target_clip
        if liveobj_valid(current_clip):
            # Set up listener for playing status changes
            self._DrumStepSequencerComponent__on_clip_playing_status_changed.subject = current_clip
            logger.debug(f"Set up playing status listener for clip: {getattr(current_clip, 'name', 'Unnamed')}")

    @listens("playing_status")  # type: ignore
    def _DrumStepSequencerComponent__on_clip_playing_status_changed(self):
        """Handle clip playing status changes"""
        logger.debug("Clip playing status changed")
        self._update_play_button_state()

    def _find_clip_slot_for_clip(self, track, clip):
        """Find the clip slot that contains the given clip"""
        if not track or not clip or not hasattr(track, 'clip_slots'):
            return None

        for clip_slot in track.clip_slots:
            if hasattr(clip_slot, 'clip') and clip_slot.clip == clip:
                return clip_slot

        return None

    def _navigate_clip_slot(self, direction):
        """Navigate to the next/previous clip slot"""
        # Check if sequencer is locked to a track
        if self._target_track and hasattr(self._target_track, 'is_locked_to_track') and self._target_track.is_locked_to_track:
            # If locked, use the locked track for clip creation
            current_track = self._target_track.target_track
            current_clip = self._target_track.target_clip
            logger.info(f"Sequencer is locked to track {current_track.name if current_track else 'None'}")
        else:
            # If not locked, use the currently selected track in Ableton Live
            if not hasattr(self.song.view, 'selected_track') or not self.song.view.selected_track:
                logger.warning("No track selected in Ableton Live for navigation")
                return

            current_track = self.song.view.selected_track
            current_clip = None

            # Get the currently highlighted clip if any
            if hasattr(self.song.view, 'highlighted_clip_slot') and self.song.view.highlighted_clip_slot:
                if hasattr(self.song.view.highlighted_clip_slot, 'clip'):
                    current_clip = self.song.view.highlighted_clip_slot.clip
            logger.info(f"Using currently selected track {current_track.name}")

        if not hasattr(current_track, 'clip_slots'):
            logger.warning("Target track has no clip slots")
            return

        # Find current clip slot index
        current_slot_index = None
        if current_clip:
            for i, clip_slot in enumerate(current_track.clip_slots):
                if hasattr(clip_slot, 'clip') and clip_slot.clip == current_clip:
                    current_slot_index = i
                    break

        # If no current clip, start from scene index
        if current_slot_index is None:
            current_slot_index = scene_index()

        # Calculate new slot index
        new_slot_index = current_slot_index + direction

        # Check bounds
        if new_slot_index < 0 or new_slot_index >= len(current_track.clip_slots):
            logger.info(f"Navigation would go out of bounds (index {new_slot_index})")
            return

        new_clip_slot = current_track.clip_slots[new_slot_index]

        # If the new slot is empty, create an empty clip
        if not hasattr(new_clip_slot, 'has_clip') or not new_clip_slot.has_clip:
            logger.info(f"Creating empty clip in slot {new_slot_index}")
            clip_created = self._create_empty_clip_in_slot(new_clip_slot)
            if not clip_created:
                logger.warning(f"Failed to create clip in slot {new_slot_index}")
                return

        # Always update Ableton Live's session view to show the navigation
        if hasattr(self.song.view, 'selected_track') and self.song.view.selected_track:
            # Find the corresponding clip slot in the currently viewed track
            viewed_track = self.song.view.selected_track
            if hasattr(viewed_track, 'clip_slots') and new_slot_index < len(viewed_track.clip_slots):
                viewed_clip_slot = viewed_track.clip_slots[new_slot_index]
                # Highlight the corresponding row in the currently viewed track
                if hasattr(self.song.view, 'highlighted_clip_slot'):
                    self.song.view.highlighted_clip_slot = viewed_clip_slot
                logger.info(f"Highlighted row {new_slot_index} in viewed track {viewed_track.name}")

        # Update the sequencer's target clip if locked
        if self._target_track and hasattr(self._target_track, 'is_locked_to_track') and self._target_track.is_locked_to_track:
            # If locked, update the sequencer's target clip
            if hasattr(new_clip_slot, 'clip') and new_clip_slot.clip:
                self._target_track._target_clip = new_clip_slot.clip
                self._target_track.notify_target_clip()
                self._on_target_clip_changed()
                logger.info(f"Updated sequencer target clip to slot {new_slot_index} of locked track {current_track.name}")
            else:
                self._target_track._target_clip = None
                self._target_track.notify_target_clip()
                self._on_target_clip_changed()
                logger.info(f"Updated sequencer target clip to None for slot {new_slot_index} of locked track {current_track.name}")

    def _create_empty_clip_in_slot(self, clip_slot):
        """Create an empty clip in the given clip slot"""
        try:
            if not hasattr(clip_slot, 'create_clip'):
                logger.warning("Clip slot does not support creating clips")
                return False

            # Create a 1-bar empty clip
            clip_length = get_bar_length()
            clip_slot.create_clip(clip_length)
            logger.info(f"Created empty clip with length {clip_length}")
            return True
        except Exception as e:
            logger.error(f"Error creating empty clip: {e}")
            return False

    def _create_clip_variant(self):
        """Create a variant (duplicate) of the current clip"""
        # Check if sequencer is locked to a track
        if self._target_track and hasattr(self._target_track, 'is_locked_to_track') and self._target_track.is_locked_to_track:
            # If locked, use the locked track for variant creation
            current_track = self._target_track.target_track
            current_clip = self._target_track.target_clip
            logger.info(f"Sequencer is locked to track {current_track.name if current_track else 'None'} for variant creation")
        else:
            # If not locked, use the currently selected track in Ableton Live
            if not hasattr(self.song.view, 'selected_track') or not self.song.view.selected_track:
                logger.warning("No track selected in Ableton Live for variant creation")
                return

            current_track = self.song.view.selected_track
            current_clip = None

            # Get the currently highlighted clip if any
            if hasattr(self.song.view, 'highlighted_clip_slot') and self.song.view.highlighted_clip_slot:
                if hasattr(self.song.view.highlighted_clip_slot, 'clip'):
                    current_clip = self.song.view.highlighted_clip_slot.clip
            logger.info(f"Using currently selected track {current_track.name} for variant creation")

        if not current_clip:
            logger.warning("No current clip to create variant from")
            return

        # Find current clip slot index
        current_slot_index = None
        for i, clip_slot in enumerate(current_track.clip_slots):
            if hasattr(clip_slot, 'clip') and clip_slot.clip == current_clip:
                current_slot_index = i
                break

        if current_slot_index is None:
            logger.warning("Could not find current clip slot")
            return

        # Find the next empty slot
        next_empty_slot = None
        next_empty_index = None

        # Look for empty slot after current position
        for i in range(current_slot_index + 1, len(current_track.clip_slots)):
            clip_slot = current_track.clip_slots[i]
            if not hasattr(clip_slot, 'has_clip') or not clip_slot.has_clip:
                next_empty_slot = clip_slot
                next_empty_index = i
                break

        if next_empty_slot is None:
            logger.warning("No empty slot found for variant creation")
            return

        try:
            # Use the proper Ableton Live API to duplicate the clip
            if hasattr(current_track, 'duplicate_clip_slot'):
                # Find the source clip slot index
                source_slot_index = None
                for i, clip_slot in enumerate(current_track.clip_slots):
                    if hasattr(clip_slot, 'clip') and clip_slot.clip == current_clip:
                        source_slot_index = i
                        break

                if source_slot_index is not None:
                    # Use the track's duplicate_clip_slot method
                    new_slot_index = current_track.duplicate_clip_slot(source_slot_index)
                    logger.info(f"Duplicated clip from slot {source_slot_index} to slot {new_slot_index}")

                    # Get the new clip slot
                    if new_slot_index < len(current_track.clip_slots):
                        next_empty_slot = current_track.clip_slots[new_slot_index]
                        next_empty_index = new_slot_index
                    else:
                        logger.warning(f"Duplicate returned invalid slot index: {new_slot_index}")
                        return
                else:
                    logger.warning("Could not find source clip slot for duplication")
                    return
            else:
                logger.warning("Track does not support clip duplication")
                return

            # Navigate to the new variant
            # Always update Ableton Live's session view to show the navigation
            if hasattr(self.song.view, 'selected_track') and self.song.view.selected_track:
                # Find the corresponding clip slot in the currently viewed track
                viewed_track = self.song.view.selected_track
                if hasattr(viewed_track, 'clip_slots') and next_empty_index < len(viewed_track.clip_slots):
                    viewed_clip_slot = viewed_track.clip_slots[next_empty_index]
                    # Highlight the corresponding row in the currently viewed track
                    if hasattr(self.song.view, 'highlighted_clip_slot'):
                        self.song.view.highlighted_clip_slot = viewed_clip_slot
                    logger.info(f"Highlighted variant row {next_empty_index} in viewed track {viewed_track.name}")

            # Update the sequencer's target clip if locked
            if self._target_track and hasattr(self._target_track, 'is_locked_to_track') and self._target_track.is_locked_to_track:
                # If locked, update the sequencer's target clip
                self._target_track._target_clip = next_empty_slot.clip
                self._target_track.notify_target_clip()
                self._on_target_clip_changed()
                logger.info(f"Updated sequencer target clip to variant in slot {next_empty_index} of locked track {current_track.name}")
        except Exception as e:
            logger.error(f"Error creating clip variant: {e}")

    def _clear_current_clip_notes(self):
        """Clear all notes from the current clip"""
        # Check if sequencer is locked to a track
        if self._target_track and hasattr(self._target_track, 'is_locked_to_track') and self._target_track.is_locked_to_track:
            current_track = self._target_track.target_track
            current_clip = self._target_track.target_clip
        else:
            if not hasattr(self.song.view, 'selected_track') or not self.song.view.selected_track:
                return

            current_track = self.song.view.selected_track
            current_clip = None

            if hasattr(self.song.view, 'highlighted_clip_slot') and self.song.view.highlighted_clip_slot:
                if hasattr(self.song.view.highlighted_clip_slot, 'clip'):
                    current_clip = self.song.view.highlighted_clip_slot.clip

        if not current_clip:
            return

        try:
            if hasattr(current_clip, 'is_midi_clip') and current_clip.is_midi_clip:
                current_clip.remove_notes_extended(
                    from_time=0,
                    from_pitch=0,
                    time_span=16.0,    # 4 bars
                    pitch_span=128     # All MIDI pitches
                )
        except Exception as e:
            logger.error(f"Error clearing clip notes: {e}")

    def update(self):
        """Update the component"""
        super().update()

        # Update composed components
        self._drum_group.update()
        self._note_editor.update()
        if self._loop_selector:
            self._loop_selector.update()

        # Update play button state on component update
        self._update_play_button_state()

