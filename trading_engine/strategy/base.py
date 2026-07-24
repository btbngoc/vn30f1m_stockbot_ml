from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    def __init__(self, name="BaseStrategy"):
        self.name = name

    @abstractmethod
    def calculate_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Receives a DataFrame with computed indicators.
        Returns a DataFrame with score columns (e.g., TrendScore) appended.
        """
        pass
