from dataclasses import dataclass, asdict

@dataclass
class Config:
    window_us: int = 10000
    polarity: str = 'both'
    refractory_us: int = 1000
    support_radius: int = 1
    support_us: int = 10000
    minimum_support: int = 1
    line_threshold_px: float = 2.5
    minimum_inliers: int = 20
    seed: int = 42
    def as_dict(self): return asdict(self)
