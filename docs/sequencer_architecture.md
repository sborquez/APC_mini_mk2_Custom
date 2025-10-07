# Step Sequencer Architecture Analysis

## Overview
This document explores the Ableton Live v3 step sequencer architecture and outlines how to implement a custom sequencer for the APC mini mk2 custom controller.

## Available Hardware Layout

### APC Mini MK2 Grid (8x8 = 64 pads)
- **Sequence Pads** (8x4 = 32 pads): Top 4 rows - Main step sequencer grid
- **Drum Pads** (4x2 = 8 pads): Bottom left area - Drum pad selection/playing
- **Control Pads** (4x2 = 8 pads): Bottom right area - Control functions

### MIDI Note Assignments (from elements.py)
- **Sequence_Pads**: Notes 96-127 (8 wide, 4 high, channel 9)
- **Drum_Pads**: Notes 64-67, 72-75, 80-83, 88-91 (4x4 grid, channel 9)
- **Control_Pads**: Notes 84-87, 92-95 (4x2 grid, channel 9)

## Ableton V3 Step Sequencer Components

### 1. StepSequenceComponent (Main Coordinator)
**File**: `ableton/v3/control_surface/components/step_sequence.py`

**Responsibilities**:
- Coordinates all sub-components
- Manages grid resolution
- Connects note editor, loop selector, and playhead components

**Key Methods**:
```python
def set_pitch_provider(provider)           # Sets which pitches/notes to edit
def set_step_buttons(buttons)              # Main step grid matrix
def set_resolution_buttons(buttons)        # Grid resolution selection
def set_loop_buttons(matrix)               # Loop/page selection
def set_prev_page_button(button)           # Previous page navigation
def set_next_page_button(button)           # Next page navigation
```

**Composed Components**:
- `NoteEditorComponent` - Handles note editing
- `NoteEditorPaginator` - Handles page management
- `LoopSelectorComponent` - Handles loop/page selection
- `PlayheadComponent` - Visual playback feedback
- `GridResolutionComponent` - Step resolution (1/16, 1/8, etc.)

### 2. NoteEditorComponent
**File**: `ableton/v3/control_surface/components/note_editor.py`

**Responsibilities**:
- Manages the step button matrix
- Handles note input (adding/removing notes)
- Visual feedback for active steps
- Supports polyphonic editing

**Key Concepts**:
- `PitchProvider`: Provides the pitches (MIDI notes) to edit
- `TimeStep`: Represents a single time step in the sequencer
- Matrix buttons control note on/off for each step

**Key Methods**:
```python
def set_matrix(matrix)                     # Set step button matrix
pitch_provider = property/setter           # Which pitches to edit
```

### 3. GridResolutionComponent
**File**: `ableton/v3/control_surface/components/grid_resolution.py`

**Responsibilities**:
- Manages grid resolution (step length)
- Supports standard and triplet subdivisions

**Available Resolutions**:
```python
GRID_RESOLUTIONS = (
    GridResolution("1/32t", 0.083, GridQuantization.g_thirtysecond, True),
    GridResolution("1/32",  0.125, GridQuantization.g_thirtysecond, False),
    GridResolution("1/16t", 0.167, GridQuantization.g_sixteenth, True),
    GridResolution("1/16",  0.25,  GridQuantization.g_sixteenth, False),  # Default
    GridResolution("1/8t",  0.333, GridQuantization.g_eighth, True),
    GridResolution("1/8",   0.5,   GridQuantization.g_eighth, False),
    GridResolution("1/4t",  0.667, GridQuantization.g_quarter, True),
    GridResolution("1/4",   1.0,   GridQuantization.g_quarter, False)
)
```

**Key Properties**:
- `step_length`: Length of each step in beats
- `clip_grid`: Grid quantization for the clip
- `is_triplet`: Whether current resolution is triplet

### 4. LoopSelectorComponent
**File**: `ableton/v3/control_surface/components/loop_selector.py`

**Responsibilities**:
- Page/loop navigation
- Visual feedback for current page
- Note deletion per page

**Key Features**:
- Matrix shows available pages (bars)
- Next/prev buttons for navigation
- Delete button + matrix for deleting notes in a bar

### 5. PlayheadComponent
**File**: `ableton/v3/control_surface/components/playhead.py`

**Responsibilities**:
- Visual feedback of playback position
- Shows current step being played

**Key Concepts**:
- Uses the same note matrix as step buttons
- Sends MIDI notes to light up current step
- Automatically adjusts for triplet vs regular resolutions

### 6. SequencerClip Helper Class
**File**: `ableton/v3/control_surface/components/step_sequence.py`

**Responsibilities**:
- Manages the relationship between target track and clip
- Provides clip creation functionality
- Monitors clip changes

**Key Methods**:
```python
def create_clip(length=None)               # Create new sequencer clip
```

**Key Properties**:
- `clip`: Current clip being edited
- `length`: Loop length in beats
- `bar_length`: Length of one bar
- `num_bars`: Number of bars in loop

## Implementation Strategy for APC Mini MK2

### Recommended Approach: Leverage Existing Components

Since the v3 components are already available, the best approach is to **compose** them into a custom component that fits the APC Mini MK2 layout.

### Layout Proposal

```
┌─────────────────────────────────────────┐
│  SEQUENCE PADS (8x4 = 32 steps)         │
│  ┌───┬───┬───┬───┬───┬───┬───┬───┐     │
│  │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │ 7 │ 8 │ Row 1│
│  ├───┼───┼───┼───┼───┼───┼───┼───┤     │
│  │ 9 │10 │11 │12 │13 │14 │15 │16 │ Row 2│
│  ├───┼───┼───┼───┼───┼───┼───┼───┤     │
│  │17 │18 │19 │20 │21 │22 │23 │24 │ Row 3│
│  ├───┼───┼───┼───┼───┼───┼───┼───┤     │
│  │25 │26 │27 │28 │29 │30 │31 │32 │ Row 4│
│  └───┴───┴───┴───┴───┴───┴───┴───┘     │
├─────────────────────────────────────────┤
│  DRUM PADS    │  CONTROL PADS           │
│  (4x2 = 8)    │  (4x2 = 8)              │
│  ┌─┬─┬─┬─┐    │  ┌─┬─┬─┬─┐             │
│  │D│D│D│D│    │  │M│ │R│ │  Row 5      │
│  ├─┼─┼─┼─┤    │  ├─┼─┼─┼─┤             │
│  │D│D│D│D│    │  │◄│►│A│S│  Row 6      │
│  └─┴─┴─┴─┘    │  └─┴─┴─┴─┘             │
└─────────────────────────────────────────┘

Legend:
D = Drum pad selection
M = Mode toggle (selection/playable)
R = Resolution (cycle through)
◄ = Previous page
► = Next page
A = Accent velocity
S = Soft velocity
```

### Component Mapping

#### Option 1: Full-Featured Sequencer (Recommended)

**Sequence_Pads (8x4 matrix)**:
- 8 steps wide × 4 rows
- Can show 32 steps (2 bars at 1/16 notes)
- Or 8 steps × 4 different pitches (polyphonic)

**Control_Pads (4x2 = 8 buttons)**:
```
Button 92: Mode toggle (selection/playable for drum pads)
Button 93: [Available]
Button 94: Resolution cycle/select
Button 95: [Available]
Button 84: Previous page
Button 85: Next page
Button 86: Accent velocity
Button 87: Soft velocity
```

**Drum_Pads (4x2 = 8 pads)**:
- Drum pad selection/playing
- Works with current CustomDrumGroupComponent

#### Option 2: Simpler Step Sequencer

**Sequence_Pads** (8 wide × 4 high):
- Row 0: Steps 1-8 (first half bar at 1/16)
- Row 1: Steps 9-16 (second half bar at 1/16)
- Row 2: Loop selector / page navigation
- Row 3: Grid resolution selection

This gives a complete self-contained sequencer interface.

## Implementation Steps

### Step 1: Create Custom Step Sequencer Component

Create a new component that composes the v3 components:

```python
class APCStepSequencerComponent(Component):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)

        # Grid resolution
        self._grid_resolution = GridResolutionComponent(parent=self)

        # Note editor (the main step grid)
        self._note_editor = NoteEditorComponent(
            grid_resolution=self._grid_resolution,
            parent=self
        )

        # Paginator
        self._paginator = NoteEditorPaginator(
            note_editor=self._note_editor,
            parent=self
        )

        # Loop selector
        self._loop_selector = LoopSelectorComponent(
            paginator=self._paginator,
            parent=self
        )

        # Playhead
        self._playhead = PlayheadComponent(
            grid_resolution=self._grid_resolution,
            paginator=self._paginator,
            parent=self
        )

    def set_step_buttons(self, matrix):
        """Map the 8x4 sequence pads matrix"""
        self._note_editor.set_matrix(matrix)

    def set_resolution_button(self, button):
        """Cycle through resolutions"""
        # Could use a single button to cycle
        # or multiple buttons for direct selection
        pass

    def set_prev_page_button(self, button):
        self._loop_selector.prev_page_button.set_control_element(button)

    def set_next_page_button(self, button):
        self._loop_selector.next_page_button.set_control_element(button)
```

### Step 2: Integrate with DrumStepSequencerComponent

The current `DrumStepSequencerComponent` handles drum pads. We should either:

**Option A**: Expand it to include the step sequencer
```python
class DrumStepSequencerComponent(Component):
    def __init__(self, *a, **k):
        # ... existing drum group code ...

        # Add step sequencer
        self._step_sequencer = APCStepSequencerComponent(parent=self)

    def set_step_sequence_matrix(self, matrix):
        self._step_sequencer.set_step_buttons(matrix)
```

**Option B**: Keep them separate and coordinate at the control surface level

### Step 3: Update Mappings

Add the step sequencer mappings:

```python
mappings["Pad_Modes"] = dict(
    drum=dict(
        component="Drum_Step_Sequencer",
        drum_group_matrix="drum_pads",
        step_sequence_matrix="sequence_pads",  # Add this
        mode_toggle_button="control_pads_raw[0]",
        resolution_button="control_pads_raw[2]",  # Add this
        prev_page_button="control_pads_raw[4]",  # Add this
        next_page_button="control_pads_raw[5]",  # Add this
        velocity_accent_button="control_pads_raw[6]",
        velocity_soft_button="control_pads_raw[7]",
    ),
)
```

### Step 4: Add Colors

Extend the color scheme:

```python
class Skin:
    class NoteEditor:
        # Step states
        StepEmpty = Rgb.BLACK
        StepFilled = Rgb.WHITE
        StepActive = Rgb.GREEN
        StepMuted = Rgb.GREY

        # Current playing step
        Playhead = Rgb.GREEN_BLINK

        # Resolution selection
        class Resolution:
            Selected = Rgb.AMBER
            NotSelected = Rgb.AMBER_HALF

    class LoopSelector:
        # Page/loop selection
        PageEmpty = Rgb.BLACK
        PageFilled = Rgb.BLUE
        CurrentPage = Rgb.BLUE
        Navigation = Rgb.WHITE_HALF
        NavigationPressed = Rgb.WHITE
```

## Advanced Features

### Pitch Provider Integration
The NoteEditorComponent uses a PitchProvider to determine which MIDI notes to edit. This can be:

1. **Drum Pad Selection**: Edit the currently selected drum pad
2. **Fixed Pitch**: Always edit a specific note (e.g., C1)
3. **Polyphonic**: Edit multiple pitches simultaneously (each row = different pitch)

Example:
```python
class DrumPadPitchProvider(PitchProvider):
    """Provides the pitch of the currently selected drum pad"""

    def __init__(self, drum_group_component, *a, **k):
        super().__init__(*a, **k)
        self._drum_group = drum_group_component
        self._update_pitch()
        self._drum_group.register_slot(
            drum_group_component,
            self._update_pitch,
            'selected_drum_pad'
        )

    def _update_pitch(self):
        if self._drum_group.selected_drum_pad:
            self.pitches = [self._drum_group.selected_drum_pad.note]
```

### Velocity Control
While the APC Mini MK2 has fixed velocity (127) in hardware, you can:
1. Set default velocity for new notes
2. Modify existing note velocities
3. Use different colors to show different velocity levels

### Multiple Pages
With 32 steps showing:
- At 1/16 resolution: 2 bars visible
- At 1/8 resolution: 4 bars visible
- At 1/4 resolution: 8 bars visible

Use prev/next buttons to navigate through longer clips.

## Comparison: Custom vs Built-in Components

### Using Built-in Components (Recommended)
**Pros**:
- Well-tested and maintained
- Automatic clip management
- Proper undo/redo support
- Playhead visualization
- Page management

**Cons**:
- Less flexibility
- May need workarounds for specific features
- Dependency on Ableton's implementation

### Building Custom (Not Recommended)
**Pros**:
- Full control
- Custom features

**Cons**:
- Complex clip note manipulation
- Need to handle edge cases
- More maintenance
- Potential for bugs

## Recommended Next Steps

1. **Start Simple**: Implement basic step sequencer using v3 components
2. **Test Integration**: Ensure it works with drum pad selection
3. **Add Features**: Page navigation, resolution control
4. **Polish UX**: Colors, feedback, edge cases
5. **Advanced Features**: Polyphonic mode, velocity editing, copy/paste

## Example Implementation

See `drum_step_sequencer.py` for a starting point. The next iteration should:
1. Add `StepSequenceComponent` or compose its sub-components
2. Wire up the Sequence_Pads element
3. Add PitchProvider that follows drum pad selection
4. Map control buttons for navigation and settings

