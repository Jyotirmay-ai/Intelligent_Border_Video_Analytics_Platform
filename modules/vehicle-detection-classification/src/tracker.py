class VehicleTracker:
    def __init__(self):
        # Initialize ByteTrack or your chosen tracking library here
        self.next_id = 1
        # The best single model result seen for each tracked vehicle.
        self.best_classifications = {}
        
    def format_track_id(self, raw_id: int) -> str:
        """
        Ensures vehicle track IDs are prefixed with 'v_' as per CONTRACTS.md.
        This differentiates vehicle tracks from human tracks (which use 'h_').
        """
        return f"v_{raw_id:04d}"

    def best_classification(self, track_id: str, detected_class: str, confidence: float) -> tuple[str, float, bool]:
        """Keep only the class associated with this track's highest confidence.

        Returns the selected class, its maximum confidence, and whether this
        frame established a new maximum.
        """
        previous = self.best_classifications.get(track_id)
        if previous is None or confidence > previous[1]:
            self.best_classifications[track_id] = (detected_class, confidence)
            return detected_class, confidence, True
        return previous[0], previous[1], False
        
    def update(self, detections):
        """
        Update the tracker with new detections from the shared YOLO26 model.
        Returns a list of tracks with formatted IDs.
        """
        # TODO: Replace with actual ByteTrack update logic
        tracks = []
        for det in detections:
            tracks.append({
                "track_id": self.format_track_id(self.next_id),
                "bbox": det["bbox"]
            })
            self.next_id += 1
        return tracks
