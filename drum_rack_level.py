from __future__ import absolute_import, print_function, unicode_literals
try:
    from ableton.v3.control_surface.components.device import DeviceComponent
    from ableton.v3.control_surface.controls import control_list, MappedControl
    from ableton.v3.base import depends, listens
    from ableton.v3.live import liveobj_valid
except ImportError:
    from .ableton.v3.control_surface.components.device import DeviceComponent
    from .ableton.v3.control_surface.controls import control_list, MappedControl
    from .ableton.v3.base import depends, listens
    from .ableton.v3.live import liveobj_valid

from .logger_config import get_logger

logger = get_logger('drum_rack_level')

class DrumRackLevelComponent(DeviceComponent):
    """
    Controls the Level macro (last macro) of instrument racks within a drum rack's pads.

    Inherits from DeviceComponent to get device lock functionality and parameter management.
    Maps 8 faders to 8 drum pads, with support for row switching.
    Repurposes the Pan fader mode to control drum pad levels.
    """

    # Override the parameter controls to use MappedControl instead of MappedSensitivitySettingControl
    parameter_controls = control_list(MappedControl, control_count=8)

    @depends(target_track=None,
             device_provider=None,
             device_bank_registry=None,
             toggle_lock=None,
             show_message=None)
    def __init__(self, name="Drum_Rack_Level", target_track=None, device_provider=None, device_bank_registry=None, toggle_lock=None, show_message=None, *a, **k):
        try:
            # Initialize state before calling parent
            self._drum_rack = None
            self._pad_offset = 0  # 0 = bottom 2 rows (pads 0-7), 8 = top 2 rows (pads 8-15)
            self._target_track = target_track

            # Call parent DeviceComponent init with all dependencies
            super().__init__(name=name,
                           device_provider=device_provider,
                           device_bank_registry=device_bank_registry,
                           toggle_lock=toggle_lock,
                           show_message=show_message,
                           *a, **k)

            # Set up target track listener
            self.target_track = target_track

            # Initial drum rack update
            self._update_drum_rack()

            # Set up drum rack scroll listener
            self._setup_drum_rack_listeners()

            logger.info("✓ DrumRackLevelComponent initialized successfully")

        except Exception as e:
            logger.error(f"✗ DrumRackLevelComponent initialization failed: {e}")
            logger.error("Full traceback:", exc_info=True)
            raise

    @property
    def target_track(self):
        return self._target_track

    @target_track.setter
    def target_track(self, target_track):
        self._target_track = target_track
        # Set up listener using register_slot
        self.register_slot(target_track, self._on_target_track_changed, "target_track")

    def set_parameter_controls(self, controls):
        """
        Override the parent method to handle our custom parameter mapping.
        """
        # Set the controls on our parameter_controls
        if controls:
            self.parameter_controls.set_control_element(controls)
            self._update_parameter_mappings()
        else:
            # Clear controls
            self.parameter_controls.set_control_element(None)

    def _on_target_track_changed(self):
        """Handle target track changes."""
        track_name = getattr(self._target_track.target_track, 'name', 'None') if self._target_track and self._target_track.target_track else 'None'
        logger.info(f"🎯 DrumRackLevel: Target track changed to: {track_name}")
        self._update_drum_rack()

    def _setup_drum_rack_listeners(self):
        """Set up listeners for drum rack scroll changes."""
        if self._drum_rack and liveobj_valid(self._drum_rack):
            # Listen to drum rack scroll changes
            self.register_slot(self._drum_rack, self._on_drum_rack_scroll_changed, "visible_drum_pads")

    def _on_drum_rack_scroll_changed(self):
        """Handle drum rack scroll changes."""
        logger.debug("Drum rack scroll changed - updating parameter mappings")
        self._update_parameter_mappings()

    def _on_device_changed(self, device):
        """
        Override the parent method to handle device changes while respecting device lock and track lock.
        """

        # Check if device is locked
        if hasattr(self, '_device_provider') and self._device_provider and self._device_provider.is_locked_to_device:
            # Device is locked - only update if this is the locked device
            locked_device = self._device_provider.device
            if liveobj_valid(locked_device) and locked_device == device:
                logger.info(f"Device locked to '{locked_device.name}' - updating from device change")
                self._drum_rack = device
                self._update_parameter_mappings()
            else:
                logger.debug(f"Device locked to '{getattr(locked_device, 'name', 'None')}' - ignoring device change to '{getattr(device, 'name', 'None')}'")
        else:
            # Device not locked - update normally
            logger.debug(f"Device changed to '{getattr(device, 'name', 'None')}' - updating")
            self._drum_rack = device
            self._update_parameter_mappings()

    def _update_drum_rack(self):
        """
        Find and set the drum rack device on the current target track.
        Respects device lock and track lock from DrumStepSequencerComponent.
        """
        logger.debug("Updating drum rack from target track...")

        # Check if device is locked
        if hasattr(self, '_device_provider') and self._device_provider and self._device_provider.is_locked_to_device:
            logger.debug("Device is locked - skipping drum rack update from target track")
            return

        # Note: Track locking now handled by framework's TargetTrackComponent

        if not self._target_track:
            logger.warning("No target_track available")
            self.set_drum_rack_device(None)
            return

        track = self._target_track.target_track

        if not track:
            logger.debug("Target track is None")
            self.set_drum_rack_device(None)
            return

        if not liveobj_valid(track):
            logger.debug("Target track is not valid")
            self.set_drum_rack_device(None)
            return

        # Check if track can have MIDI devices
        if not hasattr(track, 'has_midi_input') or not track.has_midi_input:
            logger.debug(f"Track '{track.name}' is not a MIDI track")
            self.set_drum_rack_device(None)
            return

        # Find drum rack device
        logger.debug(f"Searching for Drum Rack on track '{track.name}'...")
        for device in track.devices:
            if liveobj_valid(device) and device.class_name == 'DrumGroupDevice':
                logger.info(f"✓ Found Drum Rack: '{device.name}' on track '{track.name}'")
                self.set_drum_rack_device(device)
                return

        # No drum rack found
        logger.debug(f"No Drum Rack found on track '{track.name}'")
        self.set_drum_rack_device(None)

    def set_drum_rack_device(self, drum_rack):
        """
        Set the drum rack device to control.
        Only update if device is not locked or if this is the locked device.

        Args:
            drum_rack: Live.DrumGroup.DrumGroup device or None
        """
        old_name = getattr(self._drum_rack, 'name', 'None') if self._drum_rack else 'None'
        new_name = getattr(drum_rack, 'name', 'None') if drum_rack else 'None'

        # Check if device is locked
        if hasattr(self, '_device_provider') and self._device_provider and self._device_provider.is_locked_to_device:
            # Device is locked - only update if this is the locked device
            locked_device = self._device_provider.device
            if liveobj_valid(locked_device) and locked_device == drum_rack:
                logger.info(f"Device locked to '{locked_device.name}' - updating mappings")
                self._drum_rack = drum_rack
                self._update_parameter_mappings()
            else:
                logger.debug(f"Device locked to '{getattr(locked_device, 'name', 'None')}' - ignoring '{new_name}'")
        else:
            # Device not locked - update normally
            logger.info(f"Drum rack changed: {old_name} → {new_name}")
            self._drum_rack = drum_rack

            # Set the device on the parent DeviceComponent
            self.device = drum_rack

            # Set up drum rack listeners
            self._setup_drum_rack_listeners()

            # Update our custom parameter mappings
            self._update_parameter_mappings()

    def _update_parameter_mappings(self):
        """
        Map faders to drum pad level macros based on current drum rack and offset.
        """
        logger.debug("Updating parameter mappings...")

        # Clear existing mappings
        for i in range(self.parameter_controls.control_count):
            self.parameter_controls[i].mapped_parameter = None

        if not self._drum_rack or not liveobj_valid(self._drum_rack):
            logger.debug("No valid drum rack - all faders unmapped")
            return

        logger.debug(f"Mapping faders for pad offset: {self._pad_offset}")

        # Map each fader to a drum pad's level parameter
        mapped_count = 0
        for i in range(8):
            level_param = self._get_level_parameter_for_pad(i)

            if level_param and i < self.parameter_controls.control_count:
                self.parameter_controls[i].mapped_parameter = level_param
                mapped_count += 1

        logger.info(f"✓ Mapped {mapped_count}/8 faders to drum pad levels")

    def _get_level_parameter_for_pad(self, pad_index):
        """
        Get the Level macro parameter for a drum pad.

        Args:
            pad_index: 0-7 for the 8 faders (bottom 2 rows of visible pads)

        Returns:
            Live.DeviceParameter.DeviceParameter or None
        """
        try:
            # Get visible drum pads from the drum rack
            if not hasattr(self._drum_rack, 'visible_drum_pads'):
                return None

            visible_pads = self._drum_rack.visible_drum_pads  # type: ignore

            # Calculate which visible pad to use based on pad_index and offset
            visible_pad_index = self._pad_offset + pad_index

            if visible_pad_index >= len(visible_pads):
                return None

            drum_pad = visible_pads[visible_pad_index]

            if not liveobj_valid(drum_pad):
                return None

            # Check if pad has chains
            if not hasattr(drum_pad, 'chains') or not drum_pad.chains:
                return None

            # Get first chain
            chain = drum_pad.chains[0]

            if not liveobj_valid(chain):
                return None

            # Find Instrument Rack in the chain
            if not hasattr(chain, 'devices'):
                return None

            for device in chain.devices:
                if not liveobj_valid(device):
                    continue

                if device.class_name == 'InstrumentGroupDevice':
                    # Found Instrument Rack - now find Level macro
                    parameters = device.parameters

                    # First try to find parameter named "Level"
                    for param in parameters:
                        if liveobj_valid(param) and param.name == "Level":
                            return param

                    # Last fallback: use last parameter
                    if len(parameters) > 1:
                        param = parameters[-1]
                        if liveobj_valid(param):
                            return param

                    return None

            logger.debug(f"No Instrument Rack found on pad {visible_pad_index}")
            return None

        except Exception as e:
            logger.warning(f"Error getting level parameter for pad {pad_index}: {e}")
            return None

    def cycle_pad_offset(self):
        """
        Cycle between bottom rows (offset 0) and top rows (offset 8).
        This allows switching between controlling the bottom 2 rows and top 2 rows.
        """
        if self._pad_offset == 0:
            self._pad_offset = 8  # Switch to top 2 rows (pads 8-15 in visible grid)
            logger.info("Switched to top 2 rows (visible pads 8-15)")
        else:
            self._pad_offset = 0  # Switch to bottom 2 rows (pads 0-7 in visible grid)
            logger.info("Switched to bottom 2 rows (visible pads 0-7)")

        # Update parameter mappings with new offset
        self._update_parameter_mappings()

    def update(self):
        """Update the component."""
        super().update()