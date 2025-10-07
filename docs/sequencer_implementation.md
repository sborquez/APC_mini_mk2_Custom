# Drum Step Sequencer Implementation Plan

## Project Overview
Replace the basic drum mode in the APC Mini MK2 custom script with an advanced drum step sequencer that provides better control and functionality for creating drum patterns.

## Current State Analysis

### Existing Drum Mode
- **Component**: `DrumGroupComponent` (from Ableton's framework)
- **Functionality**: Basic drum pad triggering
- **Limitations**:
  - No step sequencing
  - Limited to 4x4 grid (16 pads)
  - Only live triggering, no pattern creation
  - No visual feedback for patterns
  - No settings mode like the Note mode has

### Hardware Layout
- **APC Mini MK2**: 8x8 grid (64 pads total)
- **Current Usage**:
  - Pads 0-63: Clip Launch Buttons (Session mode)
  - Pads 64-127: Drum Pads (Drum mode)
- **Available**: Full 8x8 grid for step sequencer

## Proposed Step Sequencer Design

### Core Features

#### 1. Step Sequencer Mode
```
APC Mini MK2 8x8 Grid Layout:
                  ┌───────────────--──────────┐
                  │ 1  2  3  4    5  6  7  8  │ < 2x4 Steps 1/16 of a first bar
                  │ 9  10 11 12   13 14 15 16 │
                  │ 17 18 19 20   21 22 23 24 │ < 2x4 Steps 1/16 of a second bar
                  │ 25 26 27 28   29 30 31 32 │
                  │ ───────────────────────── │
 4x4 Drum Group > │ 33 34 35 36 | 37 38 39 40 │ < 2x4 8-Bar view and settings controls aids
                  │ 41 42 43 44 | 45 46 47 48 │
                  │             | ─────────── │
                  │ 49 50 51 52 | 53 54 55 56 │ < 2x4 Control Grid for different settings
                  │ 57 58 59 60 | 61 62 63 64 │
                  └──────────────--───────────┘
                  [ 1  2  3  4    5  6  7  8  ] < Device faders for a selected drum instrument (maybe device mappeable inside ableton live)
```

- **A 2 bars of 16 steps sequences**: Visualize the steps in a 2 bars of 16 steps sequences, each step is a different control
- **Playing**: The current step is highlighted, and if there are more bars, displayed sequence is swapped when current step reaches the end of the lower bar. The tempo is synced with Ableton Live's tempo.
- **Ableton Piano Roll**: The sequence is displayed in the piano roll too.
- **Step Toggle**: Select a drum note from the 4x4 grid, and then toggle the step on/off. The sequence is highlighting the steps where the current drum note is playing.
- **Bars view**: You can see in in the control grid, in the first 2x4 grid, the number of bars of the sequence, highlighted in green when the sequence is playing. You can press to see and lock the bars of the sequence in the Steps view, and press again to unlock the bars of the sequence.
- **Sequence Length**: The sequence default length is 2 bars of 16 steps. Hold the length button, then in select the length of the sequence from 1 to 8 bars in the control grid. You can also add notes to the sequence outside the sequence length, but will not be part of the sequence playing unless you add them to the sequence length.
- **Step Copy/Paste**: Hold the copy button, then select the bar to copy, then hold the paste button, then select the bar to paste.
- **Velocity Control**: Press and cycle between normal, accent, or soft hit button before pressing the step to set the velocity higher or lower. Color changes to match the selected velocity.
- **Mappeable 4 buttom controls**: The 4 MIDI CC buttoms for Ableton Live custom mapping.


#### 2. Settings Mode

APC Mini MK2 8x8 Grid Layout:
 ┌─────────────────────────┐
 │ 1  2  3  4  5  6  7  8  │
 │ 9  10 11 12 13 14 15 16 │
 │ 17 18 19 20 21 22 23 24 │
 │ 25 26 27 28 29 30 31 32 │
 │ 33 34 35 36 37 38 39 40 │
 │ 41 42 43 44 45 46 47 48 │
 │ 49 50 51 52 53 54 55 56 │
 │ 57 58 59 60 61 62 63 64 │
 └─────────────────────────┘

- **Enable settings Mode**:  Press and hold shift, this will change the control grid to the settings grid.
- **Resolution**: Toggle the resolution button, then select the resolution betwwen 1/16 or 1/32.
- **Drum base octave**:
- **Groove setting**: Increase or decrease the groove setting. The groove setting is a value between -100 to 100


### Visual Feedback System

#### LED Colors
- **StepEmpty**: Off - No step programmed
- **StepActiveNormal**: White - Step is active with normal velocity
- **StepActiveSoft**: Dimmed white - Step is active with soft velocity
- **StepActiveAccent**: Highligh light orange - Step is active with accent velocity
- **CurrentStep**: Blue - Currently playing step
