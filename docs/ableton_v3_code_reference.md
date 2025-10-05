# Ableton Live v3 Framework Code Reference

Comprehensive code map and class hierarchy reference for the Ableton Live v3 control surface framework.

## Framework Structure Overview

```
ableton/v3/
├── base/                    # Core utilities and base classes
├── control_surface/         # Main control surface framework
│   ├── components/         # Built-in components
│   ├── controls/           # Control type definitions
│   ├── display/            # Display and notification system
│   ├── elements/           # Hardware element implementations
│   └── mode/               # Mode system implementation
└── live/                   # Live API integration layer
```

## Base Layer (`ableton/v3/base/`)

### Core Utilities (`util.py`)

```python
class CallableBool:
    """Boolean wrapper that can be called as a function"""
    def __init__(self, value: bool)
    def __call__(self) -> bool
    def __bool__(self) -> bool
    def __int__(self) -> int

def get_default_ascii_translations() -> Dict[str, int]
def as_ascii(string: str, ascii_translations: Dict) -> Tuple[int, ...]
def hex_to_rgb(hex_value: int) -> Tuple[int, int, int]
def pitch_index_to_string(index: int, pitch_names: List[str]) -> str
```

## Control Surface Framework (`ableton/v3/control_surface/`)

### Core Classes

#### Component System

**Base Component** (`component.py`)
```python
class Component(ControlManager):
    """Base class for all control surface components"""
    __events__ = ('enabled',)
    canonical_parent = None
    num_layers = 0

    def __init__(self, name='', parent=None, register_component=None,
                 song=None, layer=None, is_enabled=True, is_private=True)
    def set_enabled(self, enable: bool)
    def is_enabled(self, explicit: bool = False) -> bool
    def add_children(self, *children)
    def update(self)
    def disconnect(self)
```

**Component Map** (`component_map.py`)
```python
class ComponentMap(dict):
    """Registry for all available components"""
    def __init__(self, specification)
    def get(self, key, **_)
    def __getitem__(self, key)
    def __contains__(self, key) -> bool
    def _create_component_map(self, specification)
```

#### Control Surface Core

**Main Control Surface** (`control_surface.py`)
```python
class ControlSurface(SimpleControlSurface, ControlSurfaceMappingMixin):
    """Main control surface implementation"""
    def __init__(self, specification=None, *a, **k)
    def disconnect(self)
    def refresh_state(self)
    def update(self)
    def update_display(self)
    def can_lock_to_devices(self) -> bool
    def lock_to_device(self, device)
    def unlock_from_device(self, _)
```

**Control Surface Mapping** (`control_surface_mapping.py`)
```python
class ControlSurfaceMappingMixin(Disconnectable):
    """Handles component creation and mapping resolution"""
    def __init__(self, specification=None, *a, **k)
    def setup(self)
    def _create_component(self, name, component_mappings)
    def _create_modes_component(self, name, modes_config)
    def _add_mode(self, mode_name, mode_spec, modes_component)
```

**Control Surface Specification** (`control_surface_specification.py`)
```python
class ControlSurfaceSpecification(SimpleNamespace):
    """Configuration specification for control surfaces"""
    elements_type = None
    control_surface_skin = default_skin
    display_specification = DisplaySpecification()
    num_tracks = 8
    num_scenes = 1
    include_returns = False
    include_master = False
    component_map = {}
    create_mappings_function = lambda *x: {}
```

### Component Registry (`components/`)

#### Core Components

**Session Component** (`session.py`)
```python
class SessionComponent(Component, Renderable):
    """Session view control component"""
    stop_all_clips_button = ButtonControl(...)
    stop_track_clip_buttons = control_list(ButtonControl)

    def set_clip_launch_buttons(self, buttons)
    def set_scene_launch_buttons(self, buttons)
    def set_stop_track_clip_buttons(self, buttons)
    def set_modifier_button(self, button, name, clip_slots_only=False)
```

**Mixer Component** (`mixer.py`)
```python
class MixerComponent(Component):
    """Audio mixing control component"""
    prehear_volume_control = MappedControl()
    crossfader_control = MappedControl()
    cycle_send_index_button = ButtonControl(...)

    def set_prehear_volume_control(self, control)
    def set_crossfader_control(self, control)
    def set_send_controls(self, controls)
    def channel_strip(self, index) -> ChannelStripComponent
```

**Device Component** (`device.py`)
```python
class DeviceComponent(ParameterProvider, Component, Renderable):
    """Device parameter control component"""
    device_on_off_button = MappedButtonControl(...)
    device_lock_button = ToggleButtonControl(...)

    def set_parameter_controls(self, controls)
    def device(self) -> Device
    def bank_name(self) -> str
```

**Transport Component** (`transport.py`)
```python
class TransportComponent(Component, Renderable):
    """Transport control component"""
    play_button = ButtonControl(...)
    stop_button = ButtonControl(...)
    record_button = ButtonControl(...)
    loop_button = ToggleButtonControl(...)
    metronome_button = ToggleButtonControl(...)

    def set_play_button(self, button)
    def set_stop_button(self, button)
    def set_record_button(self, button)
```

#### Specialized Components

**Step Sequence Component** (`step_sequence.py`)
```python
class StepSequenceComponent(Component):
    """Step sequencer component"""
    def __init__(self, name='Step_Sequence', grid_resolution=None,
                 note_editor_component_type=None, *a, **k)
    def set_pitch_provider(self, provider)
    def set_step_buttons(self, buttons)
    def set_resolution_buttons(self, buttons)
    def set_loop_buttons(self, matrix)
    def set_prev_page_button(self, button)
    def set_next_page_button(self, button)
```

**Drum Group Component** (`drum_group.py`)
```python
class DrumGroupComponent(PlayableComponent, PitchProvider, Renderable):
    """Drum pad control component"""
    mute_button = ButtonControl(...)
    solo_button = ButtonControl(...)
    delete_button = ButtonControl(...)

    def set_matrix(self, matrix)
    def set_drum_group_device(self, drum_group_device)
    def set_copy_button(self, button)
    def quantize_pitch(self, note)
    def delete_pitch(self, drum_pad)
```

**Note Editor Component** (`note_editor.py`)
```python
class NoteEditorComponent(Component):
    """Note editing component for step sequencer"""
    matrix = control_matrix(StepButtonControl)

    def set_clip(self, clip)
    def set_pitches(self, pitches)
    def set_matrix(self, matrix)
    def is_pitch_active(self, pitch) -> bool
    def toggle_pitch_for_all_active_steps(self, pitch)
```

### Control System (`controls/`)

#### Control Base Classes

**Button Control** (`button.py`)
```python
class ButtonControl(ButtonControlBase):
    class State(ButtonControlBase.State, Renderable):
        is_held = listenable_property.managed(False)
        color = control_color("DefaultButton.On")
        on_color = control_color(None)

        def _send_button_color(self)
        def _call_listener(self, listener_name, *a)

class TouchControl(ButtonControl):
    """Touch-sensitive button control"""
```

**Toggle Button Control** (`toggle_button.py`)
```python
class ToggleButtonControl(ButtonControl):
    """Toggle button with state management"""
    toggled = control_event("toggled")

    class State(ButtonControl.State, Connectable):
        def connect_property(self, *a)
        def on_connected_property_changed(self, value)
```

**Mapped Controls** (`mapped.py`)
```python
class MappedButtonControl(ButtonControlBase):
    """Button control with parameter mapping"""
    class State(ButtonControlBase.State, MappableButton):
        def _call_listener(self, listener_name, *_)

class MappedSensitivitySettingControl(MappedSensitivitySettingControlBase):
    """Control with sensitivity settings"""
```

**Control Lists** (`control_list.py`)
```python
class ControlList(ControlListBase):
    """List of controls"""
    class State(ControlListBase.State):
        def set_control_element_at_index(self, control_element, index)

class FixedRadioButtonGroup(RadioButtonGroup):
    """Fixed-size radio button group"""
    class State(RadioButtonGroup.State):
        def active_control_count(self) -> int
```

### Hardware Elements (`elements/`)

#### Element Base Classes

**Button Element** (`button.py`)
```python
class ButtonElement(ButtonElementBase, Renderable):
    """Hardware button element"""
    class ProxiedInterface(ButtonElementBase.ProxiedInterface):
        is_momentary = CallableBool(True)
        is_pressed = CallableBool(False)

    def receive_value(self, value)
    def send_value(self, value, force=False, channel=None)
    def _do_draw(self, color)

class SysexSendingButtonElement(ButtonElement):
    """Button element with sysex support"""
```

**Encoder Element** (`encoder.py`)
```python
class EncoderElement(EncoderElementBase, Renderable):
    """Hardware encoder element"""
    __events__ = ('parameter',)
    mapped_object = listenable_property.managed(None)

    def connect_to(self, parameter)
    def release_parameter(self)
    def receive_value(self, value)
    def is_mapped_to_parameter(self) -> bool
```

**Button Matrix Element** (`button_matrix.py`)
```python
class ButtonMatrixElement(ButtonMatrixElementBase, Renderable):
    """Matrix of button elements"""
    @property
    @slicer(2)
    def submatrix(self, col_slice, row_slice)
```

**Color System** (`color.py`)
```python
class Color(ABC):
    """Base color class"""
    @abstractmethod
    def draw(self, interface)
    @property
    def midi_value(self)

class SimpleColor(Color):
    """Simple single-value color"""

class RgbColor(Color):
    """RGB color implementation"""

class ComplexColor(Color):
    """Complex multi-part color"""
```

**Sysex Element** (`sysex.py`)
```python
class SysexElement(InputControlElement):
    """Sysex message element"""
    def receive_value(self, value)
    def send_value(self, *a, **k)
    def enquire_value(self)
    def reset(self)
```

### Mode System (`mode/`)

#### Mode Core Classes

**Modes Component** (`modes.py`)
```python
class ModesComponent(Component, Renderable):
    """Component for managing multiple modes"""
    mode_selection_control = SendValueInputControl()
    cycle_mode_button = ButtonControl()
    default_behaviour = ImmediateBehaviour()
    previous_mode = listenable_property.managed(None)

    def add_mode(self, name, mode_or_component, groups=None,
                 behaviour=None, selector=None)
    def push_mode(self, mode, delay=0)
    def pop_mode(self, mode, delay=0)
    def cycle_mode(self, delta=1)
```

**Mode Behaviors** (`behaviour.py`)
```python
class ToggleBehaviour(ModeButtonBehaviour):
    """Toggle mode behavior"""
    def __init__(self, return_to_default=False, *a, **k)
    def press_immediate(self, component, mode)

class MomentaryBehaviour(ModeButtonBehaviour):
    """Momentary mode behavior"""
    def press_immediate(self, component, mode)
    def release_immediate(self, component, mode)

def make_reenter_behaviour(base_behaviour, on_reenter=None, *a, **k):
    """Create re-enter behavior"""
```

**Mode Implementation** (`mode.py`)
```python
class EnablingAddLayerMode(LayerModeBase):
    """Mode that adds a layer to a component"""
    def enter_mode(self)
    def leave_mode(self)

class CallFunctionMode(Mode):
    """Mode that calls functions on enter/exit"""
    def __init__(self, on_enter_fn=nop, on_exit_fn=nop, *a, **k)
    def enter_mode(self)
    def leave_mode(self)
```

### Display System (`display/`)

#### Display Core

**Display** (`display_specification.py`)
```python
class Display(Disconnectable):
    """Main display system"""
    def __init__(self, specification: DisplaySpecification,
                 renderable_components, elements)
    def react(self, event)
    def render(self)
    def display(self, content)
    def render_and_update_display(self)
```

**State Management** (`state.py`)
```python
class State:
    """Display state management"""
    def __init__(self)
    def set_delayed(self, attr_name: str, value, delay_time: Optional[float])
    def get_repr_data(self)
    def trigger_timers(self, from_test=False)
```

**Text Rendering** (`text.py`)
```python
class Text(UserString):
    """Text rendering class"""
    class Justification(Enum):
        LEFT = auto()
        CENTER = auto()
        RIGHT = auto()
        NONE = auto()

    def as_ascii(self, adjust_string_fn: Callable) -> Tuple[int, ...]
    def as_string(self, adjust_string_fn: Callable) -> str
```

#### Notifications

**Notification System** (`notifications/all.py`)
```python
class Notifications:
    """Notification message definitions"""
    identify = lambda: "Live {}\nConnected".format(major_version())
    full_velocity = toggle_text_generator("Full Velocity\n{}")
    note_repeat = toggle_text_generator("Note Repeat\n{}")

    class Transport:
        metronome = toggle_text_generator("Metronome\n{}")
        loop = toggle_text_generator("Loop\n{}")
        tap_tempo = lambda tempo: "Tap Tempo\n{}".format(tempo)

    class Session:
        select = "{}\nselected".format
        delete = "{}\ndeleted".format
```

### Live API Integration (`live/`)

#### Action System

**Live Actions** (`action.py`)
```python
@action
def arm(track: Track, exclusive=None) -> bool:
    """Arm a track for recording"""

@action
def delete(deletable: Union[Clip, ClipSlot, Scene, Track]) -> bool:
    """Delete Live objects"""

@action
def duplicate(duplicatable: Union[Clip, ClipSlot, Scene, Track]) -> bool:
    """Duplicate Live objects"""

@action
def fire(fireable: Union[Clip, ClipSlot, Scene], button_state=None) -> bool:
    """Fire clips and scenes"""

@action
def select(selectable: Union[Clip, ClipSlot, Scene, Track]) -> bool:
    """Select Live objects"""
```

#### Live Utilities

**Live Utilities** (`util.py`)
```python
def song() -> Song:
    """Get current Live song"""

def application() -> Application:
    """Get Live application"""

def get_bar_length(clip=None) -> float:
    """Get bar length in beats"""

def is_track_armed(track) -> bool:
    """Check if track is armed"""

def display_name(obj: Union[Scene, Clip, ClipSlot, DeviceParameter],
                 strip_space=True) -> str:
    """Get display name for Live objects"""

def liveobj_valid(obj) -> bool:
    """Check if Live object is valid"""
```

## Class Hierarchy

### Component Hierarchy
```
Component (base)
├── SessionComponent
├── MixerComponent
├── DeviceComponent
├── TransportComponent
├── StepSequenceComponent
├── DrumGroupComponent
├── NoteEditorComponent
├── ModesComponent
└── Custom Components
```

### Control Hierarchy
```
ControlBase
├── ButtonControl
│   ├── ToggleButtonControl
│   └── MappedButtonControl
├── EncoderControl
├── ControlList
└── RadioButtonGroup
```

### Element Hierarchy
```
ControlElement
├── ButtonElement
│   └── SysexSendingButtonElement
├── EncoderElement
├── ButtonMatrixElement
├── SysexElement
└── TouchElement
```

### Mode Hierarchy
```
Mode
├── EnablingAddLayerMode
├── CallFunctionMode
└── ShowDetailClipMode

ModeButtonBehaviour
├── ToggleBehaviour
├── MomentaryBehaviour
└── ImmediateBehaviour
```

## Key Integration Points

### Component Registration
```python
# In ControlSurfaceSpecification
component_map = {
    "Custom_Component": CustomComponentClass
}
```

### Element Definition
```python
# In Elements class
def add_button(self, identifier, name, **k)
def add_encoder(self, identifier, name, **k)
def add_button_matrix(self, identifiers, base_name, **k)
```

### Mapping Configuration
```python
# In create_mappings function
mappings["Component_Name"] = dict(
    control_method="element_name"
)
```

### Color Definition
```python
# In Skin class
class CustomSkin:
    class CustomComponent:
        ButtonOff = Rgb.OFF
        ButtonOn = Rgb.GREEN
```

This reference provides a comprehensive map of the v3 framework's code structure, class hierarchies, and key integration points for developing custom control surface implementations.
