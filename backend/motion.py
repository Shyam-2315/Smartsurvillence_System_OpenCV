class MotionCompensator:
    """Future interface for moving-camera stabilization before tracking."""
    def compensate(self, frame): raise NotImplementedError
class NoOpMotionCompensator(MotionCompensator):
    def compensate(self, frame): return frame
