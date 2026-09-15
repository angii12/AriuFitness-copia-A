import torch
from torch import nn


class LSTMBranch(nn.Module):
    """Un ramo con due LSTM sequenziali, come nell'architettura finale a due rami."""

    def __init__(self, input_size, hidden_size_1=64, hidden_size_2=32, dropout=0.3):
        super().__init__()
        self.lstm1 = nn.LSTM(input_size, hidden_size_1, batch_first=True)
        self.dropout1 = nn.Dropout(dropout)
        self.lstm2 = nn.LSTM(hidden_size_1, hidden_size_2, batch_first=True)
        self.dropout2 = nn.Dropout(dropout)

    def forward(self, x):
        x, _ = self.lstm1(x)
        x = self.dropout1(x)
        x, _ = self.lstm2(x)
        x = self.dropout2(x)
        return x[:, -1, :]


class TwoBranchLSTM(nn.Module):
    """
    Modello binario a due rami:
      - ramo 1: keypoint (36 feature/frame)
      - ramo 2: angoli (8 feature/frame)

    Restituisce un logit grezzo. Il training usa BCEWithLogitsLoss, quindi NON
    deve esserci Sigmoid dentro il modello.
    """

    def __init__(
        self,
        keypoint_input_size=36,
        angle_input_size=8,
        hidden_size_1=64,
        hidden_size_2=32,
        dense_size=64,
        dropout=0.3,
    ):
        super().__init__()
        self.keypoint_branch = LSTMBranch(
            keypoint_input_size, hidden_size_1, hidden_size_2, dropout
        )
        self.angle_branch = LSTMBranch(
            angle_input_size, hidden_size_1, hidden_size_2, dropout
        )
        self.fc1 = nn.Linear(hidden_size_2 * 2, dense_size)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(dense_size, 1)
        self._reset_parameters()

    def _reset_parameters(self):
        for name, param in self.named_parameters():
            if "weight" in name and param.ndim >= 2:
                nn.init.xavier_uniform_(param)
            elif "bias" in name:
                nn.init.zeros_(param)

    def forward(self, keypoints, angles):
        kp = self.keypoint_branch(keypoints)
        ang = self.angle_branch(angles)
        x = torch.cat([kp, ang], dim=1)
        x = self.fc1(x)
        x = self.relu(x)
        x = self.dropout(x)
        return self.fc2(x).squeeze(1)
