"""
Scientific Reproducibility Utility: Deterministic Seed Setter.
Compliant with Open Science and peer-review reproducibility guidelines.
"""

import os
import random
from typing import Optional
import numpy as np
import torch


def set_seed(seed: int = 42, deterministic_cuda: bool = True) -> None:
    """
    Lock all pseudorandom number generators to guarantee exact reproducibility.
    
    Args:
        seed (int): Integer seed value. Default is 42.
        deterministic_cuda (bool): Whether to enforce CuDNN deterministic algorithms.
    """
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        
    if deterministic_cuda:
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
