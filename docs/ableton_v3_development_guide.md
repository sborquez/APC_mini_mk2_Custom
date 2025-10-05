# Ableton Live v3 Control Surface Framework Documentation

Technical documentation for developing custom MIDI remote scripts and control surface implementations using the Ableton Live v3 framework.

## Framework Architecture

The v3 control surface framework implements a component-based architecture that separates hardware abstraction from software functionality. The system consists of four primary layers:

1. **Hardware Elements**: MIDI control definitions and communication
2. **Components**: Software modules providing specific functionality
3. **Mapping System**: Configuration layer connecting hardware to components
4. **Control Surface**: Orchestration layer managing the overall system

## Core Concepts

### Control Surface
The `ControlSurface` class serves as the primary orchestration layer, managing component lifecycle, MIDI communication protocols, and system-wide state coordination. It implements the `ControlSurfaceMappingMixin` to handle component instantiation and mapping resolution.

### Components
Components are modular software units that encapsulate specific functionality domains. Each component inherits from the base `Component` class and optionally implements `Renderable` for visual feedback. Components manage their own state and expose control interfaces through standardized methods.

### Elements
Elements represent hardware control abstractions, providing MIDI communication interfaces for physical controls. The framework supports various element types including buttons, encoders, matrices, and sysex elements, each with specific MIDI protocol implementations.

### Mapping System
The mapping system provides declarative configuration for connecting hardware elements to component controls. Mappings are resolved at runtime through the `ComponentMap` and `Layer` systems, enabling dynamic control reassignment and mode switching.

### Layer System
Layers implement a resource management system for control ownership. Components can acquire and release control elements through layers, enabling context-sensitive control behavior and preventing resource conflicts.

## Component Architecture

### Built-in Component Registry

The framework provides a comprehensive set of pre-built components accessible through the `ComponentMap` class. These components implement standard control surface functionality:

```python
# Core Components (from ableton.v3.control_surface.component_map)
"Accent"                    # AccentComponent - Velocity accent control
"Active_Parameter"          # ActiveParameterComponent - Parameter display
"Clip_Actions"              # ClipActionsComponent - Clip manipulation
"Device"                    # DeviceComponent - Device parameter control
"Device_Navigation"         # SimpleDeviceNavigationComponent - Device browsing
"Drum_Group"                # DrumGroupComponent - Drum pad control
"Mixer"                     # MixerComponent - Audio mixing controls
"Recording"                 # RecordingComponent - Recording functionality
"Session"                   # SessionComponent - Session view control
"Session_Navigation"        # SessionNavigationComponent - Session browsing
"Step_Sequence"             # StepSequenceComponent - Step sequencer
"Transport"                 # TransportComponent - Transport controls
"View_Control"              # ViewControlComponent - View management
```

### Component Implementation Pattern

Components follow a standardized implementation pattern defined by the base `Component` class:

```python
from ableton.v3.control_surface import Component, Renderable
from ableton.v3.control_surface.controls import ButtonControl, EncoderControl

class CustomComponent(Component, Renderable):
    # Control declarations using framework control types
    primary_button = ButtonControl(color="CustomComponent.Primary")
    parameter_encoder = EncoderControl()

    def __init__(self, name='Custom_Component', *a, **k):
        super().__init__(name=name, *a, **k)
        # Component initialization logic

    def set_primary_button(self, button):
        """Connect hardware element to component control"""
        self.primary_button.set_control_element(button)

    @primary_button.pressed
    def primary_button(self, _):
        """Handle button press events"""
        # Event handling implementation
        pass

    def update(self):
        """Refresh component state and visual feedback"""
        super().update()
        # State update logic
```

### Component Interface Contract

Components must implement the following interface methods:

- **`set_*()` methods**: Hardware element connection interface
- **`update()`**: State synchronization and visual feedback refresh
- **`set_enabled()`**: Component activation/deactivation
- **`disconnect()`**: Resource cleanup and event listener removal

## Mapping System Architecture

The mapping system implements a declarative configuration approach for hardware-to-software control binding. Mappings are defined through the `create_mappings()` function and processed by the `ControlSurfaceMappingMixin`.

### Mapping Configuration Structure

The mapping system uses a hierarchical dictionary structure where top-level keys represent different mapping categories:

```python
def create_mappings(control_surface):
    mappings = {}

    # Direct component mapping - maps hardware elements directly to components
    mappings["Mixer"] = dict(
        master_track_volume_control="master_fader"
    )

    # Mode-based component mapping - creates a ModesComponent for switching between different behaviors
    mappings["Pad_Modes"] = dict(
        mode_selection_control="pad_mode_control",  # Hardware control for mode selection
        session=dict(component="Session", clip_launch_buttons="clip_launch_buttons"),
        drum=dict(component="Step_Sequencer", step_buttons="drum_pads"),
    )

    return mappings
```

#### Why `_Modes` Suffix?

The `_Modes` suffix indicates that this mapping creates a `ModesComponent` rather than a direct component mapping. The framework automatically:

1. **Creates a ModesComponent** when it encounters a mapping with `_Modes` suffix
2. **Adds mode selection logic** to switch between different component behaviors
3. **Manages mode state** and provides mode switching functionality

The suffix is a naming convention that tells the framework to treat this as a mode-based mapping rather than a direct component mapping.

### Mapping Resolution Process

The mapping system resolves control assignments through the following process:

1. **Component Instantiation**: Components are created from the `ComponentMap` registry
2. **Layer Assignment**: Hardware elements are bound to component controls via `Layer` objects
3. **Mode Activation**: Mode behaviors determine control ownership and activation patterns

### Mapping Configuration Keys

#### Component Assignment
```python
"component": "Session"  # Target component from ComponentMap registry
```

#### Hardware Element Binding
```python
"clip_launch_buttons": "clip_launch_buttons"  # Element name -> Component control method
"volume_controls": "faders"                   # Element name -> Component control method
```

**Finding Component Control Methods**: Component control methods are defined in the component classes themselves. For example, in `SessionComponent`:

```python
# From ableton.v3.control_surface.components.session
class SessionComponent(Component, Renderable):
    def set_clip_launch_buttons(self, buttons):  # This is the control method
        self._clip_slots.set_control_element(buttons)

    def set_scene_launch_buttons(self, buttons):  # This is another control method
        self._scenes.set_control_element(buttons)
```

**Complete Mapping Example**:
```python
mappings["Session"] = dict(
    # Hardware element "clip_launch_buttons" -> SessionComponent.set_clip_launch_buttons()
    clip_launch_buttons="clip_launch_buttons",

    # Hardware element "scene_launch_buttons" -> SessionComponent.set_scene_launch_buttons()
    scene_launch_buttons="scene_launch_buttons",

    # Hardware element "stop_all_clips_button" -> SessionComponent.stop_all_clips_button.set_control_element()
    stop_all_clips_button="stop_all_clips_button"
)
```

#### Mode Configuration
```python
"behaviour": MomentaryBehaviour()  # Mode activation behavior
"priority": HIGH_PRIORITY         # Mode execution priority
"modes": [...]                   # Sub-mode definitions
"enable": True                   # Component activation state
```

### Mode Behavior Types

The framework provides several mode behavior implementations:

```python
# Immediate activation behavior
"behaviour": ImmediateBehaviour()

# Momentary activation (hold-to-activate)
"behaviour": MomentaryBehaviour()

# Toggle activation behavior
"behaviour": ToggleBehaviour()

# Custom re-enter behavior with callback
"behaviour": make_reenter_behaviour(
    ImmediateBehaviour,
    on_reenter=callback_function
)
```

## Hardware Element System

### Element Type Definitions

The framework provides several element types for different hardware control categories:

#### Button Elements
```python
# Single button element - for momentary or toggle buttons
self.add_button(122, "Shift_Button", msg_type=MIDI_NOTE_TYPE)
```
- **Purpose**: Individual buttons (momentary, toggle, etc.)
- **MIDI**: Sends/receives MIDI Note On/Off messages
- **Use Cases**: Mode switches, transport controls, clip triggers

#### Encoder Elements
```python
# Encoder element - for continuous control (knobs, faders)
self.add_encoder(56, "Master_Fader")
```
- **Purpose**: Continuous control elements (knobs, faders, jog wheels)
- **MIDI**: Sends/receives MIDI CC (Control Change) messages
- **Use Cases**: Volume controls, parameter adjustment, navigation

#### Button Matrix Elements
```python
# Button matrix element - for grid of buttons (8x8, 4x4, etc.)
self.add_button_matrix(
    create_matrix_identifiers(0, 64, width=8, flip_rows=True),
    "Clip_Launch_Buttons",
    msg_type=MIDI_NOTE_TYPE
)
```
- **Purpose**: Grid of buttons arranged in rows and columns
- **MIDI**: Multiple MIDI Note messages for each button
- **Use Cases**: Clip launch grids, drum pads, step sequencers

#### Encoder Matrix Elements
```python
# Encoder matrix element - for multiple encoders
self.add_encoder_matrix([range(48, 56)], "Faders")
```
- **Purpose**: Multiple encoders grouped together
- **MIDI**: Multiple MIDI CC messages for each encoder
- **Use Cases**: Mixer faders, parameter banks, track controls

#### Sysex Elements
```python
# Sysex element for proprietary protocols
self.add_sysex_element(
    PAD_MODE_HEADER,
    "Pad_Mode_Control",
    (lambda v: PAD_MODE_HEADER + (v, SYSEX_END))
)
```
- **Purpose**: Proprietary MIDI System Exclusive messages
- **MIDI**: Custom MIDI sysex messages
- **Use Cases**: Device-specific features, mode switching, display control

### Element Configuration Parameters

Elements are configured with the following parameters:

- **`identifier`**: MIDI note number or CC number
  - **Hardware Defined**: The identifier must match the MIDI message sent by your hardware controller
  - **Finding Values**: Check your controller's MIDI implementation chart or use MIDI monitoring software
  - **Examples**: Note 60 (Middle C), CC 7 (Volume), CC 10 (Pan)

- **`channel`**: MIDI channel assignment (0-15)
  - **Default**: Usually 0 (channel 1)
  - **Hardware Defined**: Must match your controller's MIDI channel

- **`msg_type`**: MIDI message type
  - **`MIDI_NOTE_TYPE`**: For buttons and pads
  - **`MIDI_CC_TYPE`**: For encoders and faders
  - **Hardware Defined**: Determined by your controller's MIDI implementation

- **`led_channel`**: LED feedback channel (for RGB controllers)
  - **RGB Controllers**: Separate channel for LED feedback
  - **Monochrome**: Usually same as input channel

- **`name`**: Element identifier for mapping resolution
  - **User Defined**: Choose descriptive names for your mappings

## Visual Feedback System

### Color Architecture

The framework implements a hierarchical color system through the `Skin` class, providing organized color definitions for different component states:

```python
class Rgb:
    OFF = SimpleColor(0)
    ON = SimpleColor(127)
    RED = RgbColor(127, 0, 0)
    GREEN = RgbColor(0, 127, 0)
    BLUE = RgbColor(0, 0, 127)

class Skin:
    class Session:
        ClipStopped = Rgb.OFF
        ClipPlaying = Rgb.GREEN
        ClipRecording = Rgb.RED
```

### Component Color Integration

Components integrate with the color system through control declarations. You must first define the colors in your skin, then reference them in your component:

```python
# First, define colors in your skin (colors.py)
class Skin:
    class CustomComponent:
        ButtonOff = Rgb.OFF
        ButtonOn = Rgb.GREEN
        Active = Rgb.BLUE
        Inactive = Rgb.OFF

# Then use them in your component
class CustomComponent(Component, Renderable):
    primary_button = ButtonControl(
        color="CustomComponent.ButtonOff",      # Default state color
        on_color="CustomComponent.ButtonOn"     # Pressed state color
    )
```

### Dynamic Color Management

Components can implement dynamic color changes through state-based color assignment:

```python
def _update_button_color(self, button):
    if self._is_active:
        button.color = "CustomComponent.Active"    # References skin color
    else:
        button.color = "CustomComponent.Inactive"  # References skin color
```

**Important**: All color references must be defined in your skin hierarchy. The framework will throw an error if you reference undefined colors.

## Custom Component Development

### Component Registration

Custom components are registered through the `ControlSurfaceSpecification.component_map` property:

```python
# In specification definition
from .custom_component import CustomComponent

class Specification(ControlSurfaceSpecification):
    component_map = {
        "Custom": CustomComponent
    }
```

### Component Implementation

Custom components must implement the standard component interface:

```python
from ableton.v3.control_surface import Component, Renderable
from ableton.v3.control_surface.controls import ButtonControl

class CustomComponent(Component, Renderable):
    primary_button = ButtonControl(color="Custom.Button")

    def __init__(self, name='Custom', *a, **k):
        super().__init__(name=name, *a, **k)
        self._state = False

    def set_primary_button(self, button):
        self.primary_button.set_control_element(button)

    @primary_button.pressed
    def primary_button(self, _):
        self._state = not self._state
        self._update_button_color()

    def _update_button_color(self):
        if self._state:
            self.primary_button.color = "Custom.Active"
        else:
            self.primary_button.color = "Custom.Inactive"
```

### Component Development Guidelines

1. **Inheritance**: Inherit from `Component` and optionally `Renderable`
2. **Control Declarations**: Use framework control types for hardware abstraction
3. **Event Handling**: Implement control event handlers using decorators
4. **Hardware Interface**: Provide `set_*()` methods for element connection
5. **State Management**: Implement `update()` for state synchronization
6. **Resource Management**: Implement `disconnect()` for cleanup

## Mode System Architecture

The mode system allows components to have different behaviors based on the current mode. Modes are managed by `ModesComponent` instances that can switch between different component configurations.

### Mode Configuration Structure

#### Simple Mode Configuration
```python
mappings["Control_Modes"] = dict(
    mode_selection_control="mode_selector_button",  # Hardware control for mode switching
    mode1=dict(component="Session", clip_launch_buttons="clip_launch_buttons"),
    mode2=dict(component="Mixer", volume_controls="faders")
)
```

**Expected Dictionary Structure**:
- **`mode_selection_control`**: Hardware element name for mode switching
- **Mode names** (e.g., `mode1`, `mode2`): Each mode defines which component and controls to use

#### Main_Modes: The Central Control Hub

`Main_Modes` is a special mapping name that serves as the central control hub for your control surface. It's typically used to implement a **shift-based modifier system** where holding a shift button changes the behavior of all other controls.

**Why "Main_Modes"?**
- **Central Control**: It manages the primary interaction modes of your controller
- **Modifier System**: Implements shift-based control modification (common in professional controllers)
- **Framework Convention**: The framework recognizes this name for special handling
- **User Experience**: Provides intuitive "hold shift for different functions" behavior

```python
mappings["Main_Modes"] = dict(
    shift_button="shift_button",                    # Hardware shift button
    default=dict(                                   # Normal mode (no shift)
        component="Session",
        scene_launch_buttons="scene_launch_buttons"
    ),
    shift=dict(                                     # Shift mode (shift held)
        modes=[                                     # Multiple sub-modes when shift is held
            dict(
                component="Session",
                stop_all_clips_button="scene_launch_buttons_raw[7]"
            ),
            dict(
                component="Track_Button_Modes",     # Reference to another mode group
                clip_stop_button="scene_launch_buttons_raw[0]",
                solo_button="scene_launch_buttons_raw[1]",
                mute_button="scene_launch_buttons_raw[2]",
                arm_button="scene_launch_buttons_raw[3]",
                track_select_button="scene_launch_buttons_raw[4]",
            ),
            dict(
                component="Fader_Modes",            # Another mode group reference
                volume_button="track_buttons_raw[0]",
                pan_button="track_buttons_raw[1]",
                send_button="track_buttons_raw[2]",
                device_button="track_buttons_raw[3]",
                priority=HIGH_PRIORITY,
            ),
            dict(
                component="Session_Navigation",     # Navigation controls
                up_button="track_buttons_raw[4]",
                down_button="track_buttons_raw[5]",
                left_button="track_buttons_raw[6]",
                right_button="track_buttons_raw[7]",
                priority=HIGH_PRIORITY,
            ),
        ],
        behaviour=MomentaryBehaviour()              # Only active while shift is held
    )
)
```

**How Main_Modes Works**:

1. **Default State**: When no shift button is pressed, controls use the `default` configuration
2. **Shift State**: When shift button is held, controls switch to the `shift` configuration
3. **Multiple Sub-modes**: The `shift` mode can contain multiple sub-modes that are all active simultaneously
4. **Component References**: Sub-modes can reference other mode groups (like `Track_Button_Modes`, `Fader_Modes`)
5. **Priority System**: Some sub-modes can have higher priority using `priority=HIGH_PRIORITY`

**Expected Dictionary Structure**:
- **`shift_button`**: Hardware element name for the modifier button
- **`default`**: Mode active when no modifier is pressed
- **`shift`**: Mode active when modifier is pressed
  - **`modes`**: List of sub-mode configurations (all active simultaneously)
  - **`behaviour`**: Mode behavior class instance (usually `MomentaryBehaviour`)

**Real-world Example**:
```python
# Normal mode: Scene buttons launch scenes
# Shift mode: Scene buttons become track controls, stop all clips, navigation, etc.
mappings["Main_Modes"] = dict(
    shift_button="shift_button",
    default=dict(
        component="Session",
        scene_launch_buttons="scene_launch_buttons"  # Normal: launch scenes
    ),
    shift=dict(
        modes=[
            # When shift is held, scene buttons become different controls
            dict(component="Session", stop_all_clips_button="scene_launch_buttons_raw[7]"),
            dict(component="Track_Button_Modes", solo_button="scene_launch_buttons_raw[1]"),
            dict(component="Session_Navigation", up_button="track_buttons_raw[4]"),
        ],
        behaviour=MomentaryBehaviour()  # Only while shift is held
    )
)
```

#### Advanced Mode Configuration
```python
mappings["Track_Button_Modes"] = dict(
    mode_selection_control="track_mode_selector",   # Mode selection control
    clip_stop=dict(                                 # Mode 1: Clip stop
        component="Session",
        clip_stop_buttons="track_buttons",
        behaviour=ImmediateBehaviour()
    ),
    solo=dict(                                      # Mode 2: Solo
        component="Mixer",
        solo_buttons="track_buttons",
        behaviour=ToggleBehaviour()
    ),
    mute=dict(                                      # Mode 3: Mute
        component="Mixer",
        mute_buttons="track_buttons",
        behaviour=ToggleBehaviour()
    ),
    arm=dict(                                       # Mode 4: Arm
        component="Mixer",
        arm_buttons="track_buttons",
        behaviour=ToggleBehaviour()
    ),
    track_select=dict(                              # Mode 5: Track select
        component="Mixer",
        track_select_buttons="track_buttons",
        behaviour=ImmediateBehaviour()
    )
)
```

### Mode Configuration Keys

#### Required Keys
- **`mode_selection_control`**: Hardware element for mode switching
- **Mode definitions**: Each mode must specify a `component`

#### Optional Keys
- **`behaviour`**: Mode behavior class (defaults to `ImmediateBehaviour`)
- **`priority`**: Mode execution priority
- **`enable`**: Whether the mode is enabled
- **`modes`**: List of sub-modes (for complex configurations)

### Mode Behavior Implementations

The framework provides several mode behavior classes:

- **`ImmediateBehaviour`**: Immediate activation on button press
- **`MomentaryBehaviour`**: Activation only while button is held
- **`ToggleBehaviour`**: Toggle activation with each button press
- **Custom behaviors**: Extend `ModeButtonBehaviour` for specialized behavior

## Implementation Example: Step Sequencer Component

The following example demonstrates a complete step sequencer component implementation:

```python
from ableton.v3.control_surface import Component, Renderable
from ableton.v3.control_surface.controls import ButtonControl, control_matrix

class StepSequencerComponent(Component, Renderable):
    matrix = control_matrix(ButtonControl, color=None)

    def __init__(self, name='Step_Sequencer', *a, **k):
        super().__init__(name=name, *a, **k)
        self._steps = [False] * 64  # 8x8 grid
        self._current_step = 0
        self._is_playing = False

    def set_matrix(self, matrix):
        self.matrix.set_control_element(matrix)
        self.update()

    @matrix.pressed
    def matrix(self, button):
        step_index = button.index
        self._steps[step_index] = not self._steps[step_index]
        self._update_button_color(button)

    def _update_button_color(self, button):
        step_index = button.index
        if self._steps[step_index]:
            if step_index == self._current_step and self._is_playing:
                button.color = "StepSequencer.CurrentStep"
            else:
                button.color = "StepSequencer.ActiveStep"
        else:
            button.color = "StepSequencer.EmptyStep"

    def update(self):
        super().update()
        for button in self.matrix:
            self._update_button_color(button)
```