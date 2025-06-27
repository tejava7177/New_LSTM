import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import os

# LSTM 모델 정의
class ChordLSTM(nn.Module):
    def __init__(self, vocab_size, embed_dim=64, hidden_dim=128):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.lstm = nn.LSTM(embed_dim, hidden_dim, batch_first=True)
        self.fc = nn.Linear(hidden_dim, vocab_size)

    def forward(self, x):
        x = self.embedding(x)
        _, (h_n, _) = self.lstm(x)
        out = self.fc(h_n[-1])
        return out

if __name__ == '__main__':
    # 경로
    model_dir = "./LSTM/model"
    X = np.load(os.path.join(model_dir, "X.npy"))
    y = np.load(os.path.join(model_dir, "y.npy"))
    chord_to_index = np.load(os.path.join(model_dir, "chord_to_index.npy"), allow_pickle=True).item()
    index_to_chord = np.load(os.path.join(model_dir, "index_to_chord.npy"), allow_pickle=True).item()

    vocab_size = len(chord_to_index)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    X_tensor = torch.tensor(X, dtype=torch.long)
    y_tensor = torch.tensor(y, dtype=torch.long)

    model = ChordLSTM(vocab_size).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    num_epochs = 20
    batch_size = 128

    for epoch in range(num_epochs):
        permutation = torch.randperm(X_tensor.size(0))
        epoch_loss = 0.0
        for i in range(0, X_tensor.size(0), batch_size):
            indices = permutation[i:i+batch_size]
            batch_x = X_tensor[indices].to(device)
            batch_y = y_tensor[indices].to(device)

            optimizer.zero_grad()
            outputs = model(batch_x)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()

        print(f"Epoch [{epoch+1}/{num_epochs}] Loss: {epoch_loss:.4f}")

    # 모델 저장
    torch.save(model.state_dict(), os.path.join(model_dir, "chord_lstm.pt"))
    print("✅ LSTM 모델 저장 완료")