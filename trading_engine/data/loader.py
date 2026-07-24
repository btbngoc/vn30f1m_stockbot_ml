import pandas as pd
import sqlite3
import os

class DataLoader:
    def __init__(self, data_path=None):
        self.data_path = data_path or 'data/'
        
    def load_csv(self, filename):
        file_path = os.path.join(self.data_path, filename)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        df = pd.read_csv(file_path, parse_dates=['Date'])
        # Set Date as index if not already
        if df.index.name != 'Date':
            df.set_index('Date', inplace=True)
            
        # Ensure correct column names
        df.columns = [col.capitalize() for col in df.columns]
        
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
                
        return df

    def load_sqlite(self, db_name, table_name):
        db_path = os.path.join(self.data_path, db_name)
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found: {db_path}")
            
        conn = sqlite3.connect(db_path)
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql_query(query, conn, parse_dates=['Date'])
        
        if 'Date' in df.columns:
            df.set_index('Date', inplace=True)
            
        df.columns = [col.capitalize() for col in df.columns]
        conn.close()
        return df

    def create_mock_data(self, num_rows=1000):
        """Creates dummy data for testing purposes if no data is available."""
        import numpy as np
        dates = pd.date_range(end=pd.Timestamp.now(), periods=num_rows, freq='1h')
        
        # Random walk for Close
        close_prices = np.random.randn(num_rows).cumsum() + 1000
        
        df = pd.DataFrame({
            'Date': dates,
            'Open': close_prices + np.random.randn(num_rows) * 2,
            'High': close_prices + np.abs(np.random.randn(num_rows) * 5),
            'Low': close_prices - np.abs(np.random.randn(num_rows) * 5),
            'Close': close_prices,
            'Volume': np.abs(np.random.randn(num_rows) * 1000)
        })
        df.set_index('Date', inplace=True)
        return df
