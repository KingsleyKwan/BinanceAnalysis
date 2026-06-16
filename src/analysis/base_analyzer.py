from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd

class BaseAnalyzer(ABC):
    """Pluggable analyzer interface. Each implementation represents a 'model'."""

    name: str = "base"

    @abstractmethod
    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Dict[str, Any]:
        """
        Return a decision dict:
        {
            "action": "BUY" | "SELL" | "BOTH" | "HOLD",
            "confidence": float (0-1),
            "score": float (-1 to 1),
            "reason": str,
            "model": self.name,
            ...
        }
        """
        pass
