import unittest
import cv2
import numpy as np
from event_camera.focus import FocusMonitor


class FocusTests(unittest.TestCase):
    def board(self):
        img = np.full((180,240), 128, dtype=np.uint8)
        for y in range(7):
            for x in range(10):
                img[34+y*16:34+(y+1)*16, 40+x*16:40+(x+1)*16] = 40 if (x+y)%2 else 210
        return img

    def test_blur_and_reset(self):
        m=FocusMonitor(); sharp=m.process(self.board()); blurred=m.process(cv2.GaussianBlur(self.board(),(9,9),3))
        self.assertGreater(sharp['score'], blurred['score'])
        self.assertLess(blurred['ratio'], 1)
        m.reset(); self.assertEqual(m.best, 0); self.assertEqual(len(m.history), 0)

    def test_readiness_requires_history_and_board(self):
        m=FocusMonitor((9,6)); image=self.board()
        first=m.process(image); self.assertTrue(first['detected']); self.assertEqual(len(first['corners']),54)
        self.assertNotEqual(first['status'], 'GOOD ENOUGH FOR CALIBRATION')
        for _ in range(29): result=m.process(image)
        self.assertEqual(result['status'], 'GOOD ENOUGH FOR CALIBRATION')
        self.assertTrue(result['stable'])
        clipped=m.process(np.zeros_like(image)); self.assertNotEqual(clipped['status'], 'GOOD ENOUGH FOR CALIBRATION')
        self.assertEqual(clipped['dark'],100)
        no_board=FocusMonitor()
        for _ in range(30): result=no_board.process(image)
        self.assertNotEqual(result['status'], 'GOOD ENOUGH FOR CALIBRATION')

if __name__ == '__main__': unittest.main()
