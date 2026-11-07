"""Session-relative focus diagnostics; thresholds are practical heuristics."""
from collections import deque
import cv2
import numpy as np


class FocusMonitor:
    def __init__(self, pattern=None, history=25):
        self.pattern = pattern
        self.history_size = history
        self.reset()

    def reset(self):
        self.best = 0.0
        self.history = deque(maxlen=self.history_size)
        self.streak = 0

    def process(self, gray):
        score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        self.best = max(self.best, score)
        ratio = score / self.best if self.best > 0 else 0.0
        dark = float(np.mean(gray <= 5) * 100)
        bright = float(np.mean(gray >= 250) * 100)
        clipped = dark >= 20 or bright >= 20
        corners = None
        detected = False
        span = (0.0, 0.0)
        partial = False
        if self.pattern:
            detected, corners = cv2.findChessboardCorners(gray, self.pattern, cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
            if detected:
                corners = cv2.cornerSubPix(gray, corners, (5, 5), (-1, -1), (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 0.01))
                pts = corners.reshape(-1, 2)
                h, w = gray.shape
                lo = pts.min(axis=0); hi = pts.max(axis=0)
                span = ((hi[0]-lo[0])/w*100, (hi[1]-lo[1])/h*100)
                partial = bool(lo[0] < 5 or lo[1] < 5 or hi[0] >= w-5 or hi[1] >= h-5)
        centroid = corners.reshape(-1, 2).mean(axis=0) if detected else None
        self.history.append((score, detected, centroid))
        scores = np.array([v[0] for v in self.history])
        median = float(np.median(scores))
        variation = float(np.std(scores) / median) if median > 0 else float('inf')
        rate = sum(v[1] for v in self.history) / len(self.history)
        centers = [v[2] for v in self.history if v[2] is not None]
        motion = float(np.max(np.std(centers, axis=0))) if len(centers) >= 2 else float('inf')
        stable = len(self.history) == self.history_size and variation <= .15
        enough_size = span[0] >= 30 and span[1] >= 30
        qualifying = bool(self.pattern and detected and len(corners) == self.pattern[0]*self.pattern[1] and ratio >= .90 and stable and rate >= .90 and motion <= 3 and not clipped and enough_size and not partial)
        self.streak = self.streak + 1 if qualifying else 0
        if self.streak >= 5:
            status = 'GOOD ENOUGH FOR CALIBRATION'
        elif ratio < .55 or (self.pattern and not detected and rate < .2):
            status = 'TOO BLURRY'
        elif ratio >= .85 and (not self.pattern or rate >= .8):
            status = 'GOOD'
        else:
            status = 'IMPROVING / FAIR'
        return dict(score=score, best=self.best, ratio=ratio, median=median, variation=variation, stable=stable, detected=detected, corners=corners, rate=rate, motion=motion, span=span, partial=partial, small=bool(detected and not enough_size), dark=dark, bright=bright, status=status, past_best=ratio < .85 and self.best > 0, samples=len(self.history), streak=self.streak)
