# 어떤 디렉토리를 보고 있는지 확실히!
import os, numpy as np
DIR = "/Users/simjuheun/Desktop/myProject/New_LSTM/LSTM/model/LSTM/model/jazz/New2"  # predict에서 쓰는 경로와 동일하게
v = np.load(os.path.join(DIR, "chord_to_index.npy"), allow_pickle=True).item()
print("vocab_size =", len(v))
print([k for k in v.keys() if "maj7" in k][:20])