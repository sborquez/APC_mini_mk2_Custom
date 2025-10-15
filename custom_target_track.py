"""
Custom Target Track Component

This module provides a custom target track component that prioritizes the selected scene clip
over the playing clip, ensuring that when you select a different scene, the controller displays
the clip from that scene instead of continuing to show the playing clip.
"""

try:
    from ableton.v3.control_surface.components import TargetTrackComponent
    from ableton.v3.live import liveobj_valid, playing_clip_slot, scene_index
except ImportError:
    from .ableton.v3.control_surface.components import TargetTrackComponent
    from .ableton.v3.live import liveobj_valid, playing_clip_slot, scene_index


class CustomTargetTrackComponent(TargetTrackComponent):
    """
    Custom target track component that prioritizes selected scene clip over playing clip.

    This ensures that when you select a different scene, the controller displays the clip
    from that scene instead of continuing to show the playing clip.
    """

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        # Listen to selected scene changes
        if self.song and self.song.view:
            self.register_slot(self.song.view, self._on_selected_scene_changed, "selected_scene")

    def _on_selected_scene_changed(self):
        """Handle selected scene changes"""
        self._update_target_clip()

    def _target_clip_from_session(self):
        """Override to prioritize selected scene clip over playing clip"""
        if not self._target_track:
            return None

        # FIRST: Try to get the clip from the selected scene
        slot_index = scene_index()
        if hasattr(self._target_track, 'clip_slots') and slot_index < len(self._target_track.clip_slots):  # type: ignore
            clip_slot = self._target_track.clip_slots[slot_index]  # type: ignore
            self._TargetTrackComponent__on_target_clip_slot_has_clip_changed.subject = clip_slot
            if clip_slot and hasattr(clip_slot, 'has_clip') and clip_slot.has_clip:  # type: ignore
                return clip_slot.clip  # type: ignore

        # SECOND: Fall back to playing clip if no clip in selected scene
        playing_clip_slot_obj = playing_clip_slot(self._target_track)
        if liveobj_valid(playing_clip_slot_obj):
            self._TargetTrackComponent__on_target_clip_slot_has_clip_changed.subject = playing_clip_slot_obj
            if hasattr(playing_clip_slot_obj, 'has_clip') and playing_clip_slot_obj.has_clip:  # type: ignore
                return playing_clip_slot_obj.clip  # type: ignore

        return None
