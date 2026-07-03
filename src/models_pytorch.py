import torch
import torch.nn as nn
import torch.nn.init as init

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

class RamoLSTM(nn.Module):
    """
    Classe che definisce un ramo di input per il modello LSTM.
    """

    def __init__(self, input_size, hidden_size_1, hidden_size_2, dropout_rate):
        """
        Costruttore della classe ramoLstm. Inizializza i layer LSTM e i layer fully connected.

        Args:
        - input_size (int): dimensione dell'input.
        - hidden_size_1 (int): dimensione dell'hidden state del primo layer LSTM.
        - hidden_size_2 (int): dimensione dell'hidden state del secondo layer LSTM.
        - dropout_rate (float): rate di dropout.
        """

        super(RamoLSTM, self).__init__()

        self.lstm1 = nn.LSTM(input_size, hidden_size_1, 1, batch_first=True, bidirectional=False)
        self.dropout1 = nn.Dropout(dropout_rate)
        self.lstm2 = nn.LSTM(hidden_size_1, hidden_size_2, 1, batch_first=True, bidirectional=False)
        self.dropout2 = nn.Dropout(dropout_rate)

    def forward(self, x):
        """
        Funzione che definisce il forward pass del modello.

        Args:
        - x (torch.Tensor): input del modello.

        Returns:
        - out (torch.Tensor): output del modello.
        """

        out, _ = self.lstm1(x)
        out = self.dropout1(out)
        out, _ = self.lstm2(out)
        out = self.dropout2(out)
        out = out[:, -1, :]
        return out

class MultiInputLSTM(nn.Module):
    """
    Classe che definisce il modello LSTM a tre input.
    """

    def __init__(self, input_size_1, input_size_2, input_size_3, hidden_size_1, hidden_size_2, hidden_size_3, num_classes, dropout_rate):
        """
        Costruttore della classe MultiInputLSTM. Inizializza i layer LSTM e i layer fully connected.

        Args:
        - input_size_1 (int): dimensione dell'input del primo ramo.
        - input_size_2 (int): dimensione dell'input del secondo ramo.
        - input_size_3 (int): dimensione dell'input del terzo ramo.
        - hidden_size_1 (int): dimensione dell'hidden state del primo layer LSTM di ogni ramo.
        - hidden_size_2 (int): dimensione dell'hidden state del secondo layer LSTM di ogni ramo.
        - hidden_size_3 (int): dimensione dell'hidden state del layer fully connected.
        - num_classes (int): numero di classi.
        - dropout_rate (float): rate di dropout.
        """

        super(MultiInputLSTM, self).__init__()


        self.ramo1 = RamoLSTM(input_size_1, hidden_size_1, hidden_size_2, dropout_rate)
        self.ramo2 = RamoLSTM(input_size_2, hidden_size_1, hidden_size_2, dropout_rate)
        self.ramo3 = RamoLSTM(input_size_3, hidden_size_1, hidden_size_2, dropout_rate)

        # Concatenazione: uniamo l'output di 3 rami, quindi la dimensione diventa hidden_size_2 * 3
        self.fc1 = nn.Linear(hidden_size_2 * 3, hidden_size_3)
        self.relu = nn.ReLU()
        self.dropout_4 = nn.Dropout(dropout_rate)
        self.fc2 = nn.Linear(hidden_size_3, num_classes)
        self.sigmoid = nn.Sigmoid()

        self.init_weights()

    def init_weights(self):
        """
        Funzione che inizializza i pesi del modello.
        """

        for name, param in self.named_parameters():
            if 'weight' in name:
                init.xavier_uniform_(param)
            elif 'bias' in name:
                init.constant_(param, 0.0)

    def forward(self, x1, x2, x3):
        """
        Funzione che definisce il forward pass del modello con i tre input.

        Args:
        - x1 (torch.Tensor): input del primo ramo.
        - x2 (torch.Tensor): input del secondo ramo.
        - x3 (torch.Tensor): input del terzo ramo.

        Returns:
        - out (torch.Tensor): output del modello.
        """

        out1 = self.ramo1(x1)
        out2 = self.ramo2(x2)
        out3 = self.ramo3(x3)

        concatenated = torch.cat((out1, out2, out3), 1)
        out = self.fc1(concatenated)
        out = self.relu(out)
        out = self.dropout_4(out)
        logits = self.fc2(out) # Rinominiamo in logits per chiarezza
        # RIMOZIONE DELLA SIGMOID: restituiamo direttamente i logits grezzi
        return logits