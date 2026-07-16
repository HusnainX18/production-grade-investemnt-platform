"""
LSTM Model Architecture for Financial Time-Series Forecasting.

Defines:
 - LSTMRegressor: a 2-layer LSTM with dropout and a linear output head.
 - SequenceDataset: a PyTorch Dataset that builds sliding windows of features and targets.
"""

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset


class LSTMRegressor(nn.Module):
    """2-layer LSTM with dropout for scalar return prediction."""

    def __init__(self, input_size: int, hidden_size: int = 64, num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, input_size)
        out, _ = self.lstm(x)
        # Take only the last timestep output
        out = out[:, -1, :]
        out = self.dropout(out)
        return self.fc(out).squeeze(-1)


class SequenceDataset(Dataset):
    """Builds (X_seq, y) pairs from a 2-D numpy array using a sliding window."""

    def __init__(self, X: np.ndarray, y: np.ndarray, seq_len: int = 10):
        self.X = torch.from_numpy(X.astype(np.float32))
        self.y = torch.from_numpy(y.astype(np.float32))
        self.seq_len = seq_len

    def __len__(self) -> int:
        return len(self.y) - self.seq_len

    def __getitem__(self, index: int):
        return self.X[index : index + self.seq_len], self.y[index + self.seq_len]
