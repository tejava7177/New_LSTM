# LSTM/model/train_lstm_ui.py
"""
단일-스텝 코드 예측용 LSTM 트레이너(UI 버전)
- 입력: datadir(X.npy, y.npy, chord_to_index.npy, index_to_chord.npy)
- 출력: outdir/chord_lstm.pt, outdir/training_log.json, outdir/metrics.json
"""

import os
import json
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from collections import Counter


class ChordLSTM(nn.Module):
    def __init__(self, vocab_size: int, emb: int = 64, hidden: int = 128):
        super().__init__()
        self.emb = nn.Embedding(vocab_size, emb)
        self.lstm = nn.LSTM(emb, hidden, batch_first=True)
        self.fc = nn.Linear(hidden, vocab_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T) long
        x = self.emb(x)                  # (B, T, E)
        o, _ = self.lstm(x)              # (B, T, H)
        logits = self.fc(o[:, -1, :])    # (B, V) - 마지막 step만
        return logits


def set_seed(seed: int = 42):
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def compute_class_weights(y_tensor: torch.Tensor, n_cls: int) -> torch.Tensor:
    """
    y_tensor: shape (N,), dtype long
    클래스 불균형 완화용 가중치(평균 1로 정규화).
    """
    counts = torch.bincount(y_tensor, minlength=n_cls).float()
    weights = counts.sum() / (counts + 1e-8)
    weights = weights / weights.mean()
    return weights


def make_loader(X, y, idxs, batch_size, shuffle, num_workers, pin_memory):
    Xt = torch.tensor(X[idxs], dtype=torch.long)
    yt = torch.tensor(y[idxs], dtype=torch.long)
    ds = TensorDataset(Xt, yt)
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle,
                      num_workers=num_workers, pin_memory=pin_memory)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", required=True, help="경로: X.npy, y.npy 등이 있는 폴더")
    ap.add_argument("--outdir", required=True, help="모델과 로그를 저장할 폴더")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--bs", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--emb", type=int, default=64)
    ap.add_argument("--hidden", type=int, default=128)
    ap.add_argument("--patience", type=int, default=5, help="early stopping patience")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workers", type=int, default=0)  # macOS 로컬이면 0이 안전
    args = ap.parse_args()

    set_seed(args.seed)

    # ---- 데이터 로드 & dtype 고정 ----
    X = np.load(os.path.join(args.datadir, "X.npy")).astype(np.int64)
    y = np.load(os.path.join(args.datadir, "y.npy")).astype(np.int64)

    # vocab 정보(있으면 통계 출력용)
    chord_to_index_path = os.path.join(args.datadir, "chord_to_index.npy")
    if os.path.exists(chord_to_index_path):
        chord_to_index = np.load(chord_to_index_path, allow_pickle=True).item()
        vocab_size = len(chord_to_index)
    else:
        vocab_size = int(np.max(y)) + 1

    n = len(X)
    n_cls = int(np.max(y)) + 1
    print(f"dataset: N={n:,}  vocab={vocab_size}")

    # ---- split ----
    idx = np.random.permutation(n)
    tr = int(n * 0.8)
    va = int(n * 0.9)
    tr_idx = idx[:tr]
    va_idx = idx[tr:va]
    te_idx = idx[va:]

    # ---- device / dataloader ----
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pin_mem = device.type == "cuda"

    dl_tr = make_loader(X, y, tr_idx, args.bs, True, args.workers, pin_mem)
    dl_va = make_loader(X, y, va_idx, args.bs, False, args.workers, pin_mem)
    dl_te = make_loader(X, y, te_idx, args.bs, False, args.workers, pin_mem)

    # ---- model, loss, opt ----
    model = ChordLSTM(vocab_size, emb=args.emb, hidden=args.hidden).to(device)

    y_tr_tensor = torch.tensor(y[tr_idx], dtype=torch.long)
    weights = compute_class_weights(y_tr_tensor, n_cls).to(device)

    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    os.makedirs(args.outdir, exist_ok=True)
    log_path = os.path.join(args.outdir, "training_log.json")
    logs = []

    best_vloss = float("inf")
    best_ep = 0

    # ---- train loop ----
    for ep in range(1, args.epochs + 1):
        model.train()
        tr_loss_sum = 0.0

        for xb, yb in dl_tr:
            xb = xb.to(device, non_blocking=True)
            yb = yb.to(device, non_blocking=True)
            optimizer.zero_grad()
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            optimizer.step()
            tr_loss_sum += loss.item() * xb.size(0)

        tr_loss = tr_loss_sum / len(tr_idx)

        # ---- validation ----
        model.eval()
        with torch.no_grad():
            va_loss_sum, acc1, acc3 = 0.0, 0, 0
            for xb, yb in dl_va:
                xb = xb.to(device, non_blocking=True)
                yb = yb.to(device, non_blocking=True)
                logits = model(xb)
                va_loss_sum += criterion(logits, yb).item() * xb.size(0)
                topk = logits.topk(3, dim=1).indices
                acc1 += (topk[:, 0] == yb).sum().item()
                acc3 += (topk.eq(yb.unsqueeze(1))).any(dim=1).sum().item()

            va_loss = va_loss_sum / len(va_idx)
            acc1 = acc1 / len(va_idx)
            acc3 = acc3 / len(va_idx)

        print(f"[{ep:02d}] train_loss={tr_loss:.4f}  val_loss={va_loss:.4f}  "
              f"acc@1={acc1*100:.1f}%  acc@3={acc3*100:.1f}%")

        logs.append({
            "epoch": ep, "train_loss": tr_loss, "val_loss": va_loss,
            "acc1": acc1, "acc3": acc3
        })
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

        # ---- checkpoint & early stopping ----
        if va_loss < best_vloss:
            best_vloss = va_loss
            best_ep = ep
            torch.save(model.state_dict(), os.path.join(args.outdir, "chord_lstm.pt"))

        if ep - best_ep >= args.patience:
            print(f"Early stopping: no val improvement for {args.patience} epochs.")
            break

    # ---- test ----
    model.load_state_dict(torch.load(os.path.join(args.outdir, "chord_lstm.pt"), map_location=device))
    model.to(device).eval()
    with torch.no_grad():
        acc1, acc3 = 0, 0
        for xb, yb in dl_te:
            xb = xb.to(device, non_blocking=True)
            yb = yb.to(device, non_blocking=True)
            logits = model(xb)
            topk = logits.topk(3, dim=1).indices
            acc1 += (topk[:, 0] == yb).sum().item()
            acc3 += (topk.eq(yb.unsqueeze(1))).any(dim=1).sum().item()

    test_metrics = {
        "test_acc1": acc1 / len(te_idx),
        "test_acc3": acc3 / len(te_idx),
        "best_val_loss": best_vloss,
        "best_epoch": best_ep
    }
    with open(os.path.join(args.outdir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(test_metrics, f, ensure_ascii=False, indent=2)

    print(f"TEST acc@1={test_metrics['test_acc1']*100:.1f}%  "
          f"acc@3={test_metrics['test_acc3']*100:.1f}%  "
          f"(best@{best_ep}, val_loss={best_vloss:.4f})")