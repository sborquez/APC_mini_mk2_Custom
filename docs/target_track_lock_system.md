# Target Track Lock System - Implementation Guide

## Overview

The Ableton Live control surface framework uses a sophisticated target track management system that allows components to either follow the currently selected track or lock to a specific track. This document explains how this system works and how to implement it properly.

## Framework Architecture

### 1. TargetTrackComponent (Core Framework)

The `TargetTrackComponent` is the foundation of the target track system:

```python
class TargetTrackComponent(Component, Renderable):
    lock_button = ToggleButtonControl(color="TargetTrack.LockOff", on_color="TargetTrack.LockOn")

    def __init__(self, name='Target_Track', is_private=False, *a, **k):
        self._target_track = None
        self._target_clip = None
        self._locked_to_track = False
        self.lock_button.connect_property(self, "is_locked_to_track")
        self.register_slot(self.song.view, self._selected_track_changed, "selected_track")
```

**Key Properties:**
- `target_track`: The currently active track (either selected or locked)
- `target_clip`: The active clip on the target track
- `is_locked_to_track`: Boolean indicating if locked to a specific track

**Core Logic:**
- When `is_locked_to_track = False`: Follows `song.view.selected_track`
- When `is_locked_to_track = True`: Stays on the locked track regardless of selection changes

### 2. Dependency Injection System

Components receive target track through dependency injection:

```python
@depends(target_track=None)
def __init__(self, target_track=None, *a, **k):
    self._target_track = target_track
```

The `target_track` dependency is automatically provided by the framework when a `TargetTrackComponent` is registered in the control surface.

### 3. Child Component Integration

Child components that need track awareness should:

1. **Accept target_track dependency:**
```python
@depends(target_track=None)
def __init__(self, target_track=None, *a, **k):
    self._target_track = target_track
```

2. **Listen to target_track changes:**
```python
self.register_slot(self._target_track, self._on_target_track_changed, "target_track")
```

3. **Update their state when target changes:**
```python
def _on_target_track_changed(self):
    # Update component to use new target track
    self._update_for_target_track()
```

## Implementation Plan for DrumStepSequencerComponent

### Current Issues

1. **Manual Lock Implementation**: The current code implements its own lock system instead of using the framework's `TargetTrackComponent`
2. **No Dependency Integration**: Child components don't properly receive and respond to target track changes
3. **Inconsistent State Management**: Lock state is managed separately from the framework's target track system

### Solution Architecture

#### 1. Use Framework's TargetTrackComponent

Instead of implementing custom lock logic, use the framework's `TargetTrackComponent`:

```python
class DrumStepSequencerComponent(Component):
    @depends(target_track=None)
    def __init__(self, name="Drum_Step_Sequencer", target_track=None, *a, **k):
        super().__init__(name=name, *a, **k)
        self._target_track = target_track

        # Listen to target track changes
        self.register_slot(self._target_track, self._on_target_track_changed, "target_track")

        # Create child components with target_track dependency
        self._drum_group = CustomDrumGroupComponent(target_track=target_track)
        self._sequencer_clip = SequencerClip(target_track=target_track)
```

#### 2. Update Child Components

All child components should accept and use the target_track dependency:

```python
class CustomDrumGroupComponent(DrumGroupComponent):
    @depends(target_track=None)
    def __init__(self, target_track=None, *a, **k):
        super().__init__(target_track=target_track, *a, **k)
        self._target_track = target_track
        self.register_slot(self._target_track, self._on_target_track_changed, "target_track")
```

#### 3. Remove Custom Lock Logic

Remove the custom lock implementation and use the framework's lock button:

```python
# Remove these custom properties:
# - lock_button (use target_track.lock_button instead)
# - _is_locked, _locked_track
# - _on_lock_button_toggled
# - _update_components_to_locked_track
# - _update_components_to_current_track
```

#### 4. Update Control Surface Integration

In the main control surface, ensure the `TargetTrackComponent` is properly registered:

```python
class APC_Mini_MK2_Custom(ControlSurface):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)

        # Create target track component
        self._target_track = TargetTrackComponent()

        # Create drum step sequencer with target_track dependency
        self._drum_step_sequencer = DrumStepSequencerComponent(target_track=self._target_track)

        # Connect lock button to control_pads_raw[1]
        self._target_track.lock_button.set_control_element(self._control_pads_raw[1])
```

## Benefits of This Approach

1. **Framework Consistency**: Uses the same lock system as other Ableton components
2. **Automatic State Management**: Lock state is handled by the framework
3. **Proper Event Propagation**: Target track changes automatically propagate to all child components
4. **Simplified Code**: Removes custom lock logic and state management
5. **Better Integration**: Works seamlessly with other framework components

## Implementation Steps

1. **Remove custom lock implementation** from `DrumStepSequencerComponent`
2. **Add target_track dependency** to all child components
3. **Update control surface** to use `TargetTrackComponent`
4. **Connect lock button** to `control_pads_raw[1]`
5. **Test lock functionality** with track selection changes

This approach leverages the framework's built-in target track management system, providing a robust and consistent locking mechanism that integrates properly with Ableton Live's track selection system.
