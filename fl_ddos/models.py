"""Các mô hình dùng trong FL.

  resvgg_swin   ResVGG-SwinNet (paper mục 3.7): ResNet block -> VGG block -> Swin-Transformer -> softmax
  resnet, resnet_vgg, resnet_swin   các biến thể ablation (paper Bảng 12)
  mlp           DDoSNet (MLP chỉ dành cho pipeline cũ S1–S4)
  lstm, lstm_gru   baseline FL-LSTM [12] và Hybrid LSTM-GRU [17]

Dữ liệu là vector đặc trưng flow, không phải ảnh. Paper không nói cách đưa vào CNN, nên ở đây
một lớp Linear chiếu F đặc trưng thành lưới 8×8 (1 kênh) để mô hình tự học cách sắp xếp,
thay vì gán cứng thứ tự cột vào ô. Dùng GroupNorm thay BatchNorm: FedAvg trung bình hóa
running-stats của BatchNorm giữa các client có phân phối khác nhau sẽ làm lệch mô hình.
"""
import torch
import torch.nn as nn

ARCHS = ("resvgg_swin", "resnet", "resnet_vgg", "resnet_swin", "mlp", "lstm", "lstm_gru")
ARCH_NAMES = {"resvgg_swin": "ResVGG-SwinNet", "resnet": "ResNet-only", "resnet_vgg": "ResNet+VGG",
              "resnet_swin": "ResNet+Swin", "mlp": "MLP", "lstm": "FL-LSTM", "lstm_gru": "LSTM-GRU"}


class DDoSNet(nn.Module):
    def __init__(self, n_in: int, n_classes: int = 2, dropout: float = 0.2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_in, 128), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(128, 64), nn.ReLU(),
            nn.Linear(64, n_classes))

    def forward(self, x):
        return self.net(x)


# ---------------------------------------------------------------- ResNet / VGG
def conv_gn(c_in, c_out):
    return nn.Sequential(nn.Conv2d(c_in, c_out, 3, padding=1, bias=False), nn.GroupNorm(8, c_out))


class ResBlock(nn.Module):
    """Eq.17: F_R(z) = H(z) + z."""

    def __init__(self, c):
        super().__init__()
        self.h = nn.Sequential(conv_gn(c, c), nn.ReLU(), conv_gn(c, c))

    def forward(self, z):
        return torch.relu(self.h(z) + z)


# ---------------------------------------------------------------- Swin-Transformer
def window_partition(x, w):  # (B, H, W, C) -> (B·nW, w·w, C)
    b, h, wd, c = x.shape
    return x.view(b, h // w, w, wd // w, w, c).permute(0, 1, 3, 2, 4, 5).reshape(-1, w * w, c)


def window_reverse(x, w, h, wd):  # ngược lại window_partition
    b = x.shape[0] // ((h // w) * (wd // w))
    return x.view(b, h // w, wd // w, w, w, -1).permute(0, 1, 3, 2, 4, 5).reshape(b, h, wd, -1)


class WindowAttention(nn.Module):
    """Self-attention trong từng cửa sổ w×w, có relative position bias như Swin gốc."""

    def __init__(self, dim, window, heads):
        super().__init__()
        self.heads, self.scale = heads, (dim // heads) ** -0.5
        self.qkv, self.proj = nn.Linear(dim, dim * 3), nn.Linear(dim, dim)
        self.rel_bias = nn.Parameter(torch.zeros(heads, (2 * window - 1) ** 2))
        g = torch.stack(torch.meshgrid(torch.arange(window), torch.arange(window), indexing="ij")).flatten(1)
        rel = (g[:, :, None] - g[:, None, :]).permute(1, 2, 0) + window - 1
        self.register_buffer("rel_idx", rel[..., 0] * (2 * window - 1) + rel[..., 1], persistent=False)

    def forward(self, x, mask=None):
        b, n, c = x.shape
        q, k, v = self.qkv(x).reshape(b, n, 3, self.heads, c // self.heads).permute(2, 0, 3, 1, 4)
        attn = (q @ k.transpose(-2, -1)) * self.scale + self.rel_bias[:, self.rel_idx]
        if mask is not None:  # cửa sổ dịch: chặn attention giữa các vùng không liền kề
            nw = mask.shape[0]
            attn = (attn.view(b // nw, nw, self.heads, n, n) + mask[None, :, None]).view(b, self.heads, n, n)
        return self.proj((attn.softmax(-1) @ v).transpose(1, 2).reshape(b, n, c))


class SwinBlock(nn.Module):
    """Eq.19: một khối Swin (W-MSA nếu shift = 0, SW-MSA nếu shift > 0) + MLP."""

    def __init__(self, dim, res, window, shift, heads, dropout):
        super().__init__()
        self.res, self.window, self.shift = res, window, shift
        self.norm1, self.norm2 = nn.LayerNorm(dim), nn.LayerNorm(dim)
        self.attn = WindowAttention(dim, window, heads)
        self.mlp = nn.Sequential(nn.Linear(dim, 2 * dim), nn.GELU(), nn.Dropout(dropout), nn.Linear(2 * dim, dim))
        mask = None
        if shift:
            img = torch.zeros(1, res, res, 1)
            sl = (slice(0, -window), slice(-window, -shift), slice(-shift, None))
            for i, (hs, ws) in enumerate((h, w) for h in sl for w in sl):
                img[:, hs, ws, :] = i
            mw = window_partition(img, window).squeeze(-1)
            mask = (mw[:, None, :] - mw[:, :, None]).ne(0).float() * -100.0
        self.register_buffer("mask", mask, persistent=False)

    def forward(self, x):  # x: (B, H·W, C)
        b, n, c = x.shape
        h = self.norm1(x).view(b, self.res, self.res, c)
        if self.shift:
            h = torch.roll(h, (-self.shift, -self.shift), (1, 2))
        h = window_reverse(self.attn(window_partition(h, self.window), self.mask), self.window, self.res, self.res)
        if self.shift:
            h = torch.roll(h, (self.shift, self.shift), (1, 2))
        x = x + h.reshape(b, n, c)
        return x + self.mlp(self.norm2(x))


class ResVGGSwinNet(nn.Module):
    """Eq.22: y = softmax(F_S(F_V(F_R(z)))). use_vgg / use_swin = False cho các biến thể ablation."""

    def __init__(self, n_in, n_classes, dropout=0.3, use_vgg=True, use_swin=True,
                 grid=8, c_res=32, c_vgg=64, window=4, heads=4):
        super().__init__()
        self.grid = grid
        self.stem = nn.Linear(n_in, grid * grid)
        self.res = nn.Sequential(conv_gn(1, c_res), nn.ReLU(), ResBlock(c_res), ResBlock(c_res))
        # Eq.18: F_V = σ(W * F_R + b), hai lớp conv 3×3 kiểu VGG
        self.vgg = nn.Sequential(conv_gn(c_res, c_vgg), nn.ReLU(), conv_gn(c_vgg, c_vgg), nn.ReLU()) \
            if use_vgg else nn.Identity()
        dim = c_vgg if use_vgg else c_res
        self.swin = nn.Sequential(SwinBlock(dim, grid, window, 0, heads, dropout),
                                  SwinBlock(dim, grid, window, window // 2, heads, dropout),
                                  nn.LayerNorm(dim)) if use_swin else nn.Identity()
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(dim, n_classes))

    def forward(self, x):
        z = self.stem(x).view(-1, 1, self.grid, self.grid)
        z = self.vgg(self.res(z))                   # (B, C, 8, 8)
        z = self.swin(z.flatten(2).transpose(1, 2))  # (B, 64 token, C)
        return self.head(z.mean(1))                  # logits; softmax nằm trong loss / predict


# ---------------------------------------------------------------- baseline tuần tự
class SeqNet(nn.Module):
    """Coi F đặc trưng là chuỗi F bước (mỗi bước 1 giá trị): LSTM, hoặc LSTM rồi GRU."""

    def __init__(self, n_in, n_classes, dropout=0.3, gru=False, emb=16, hidden=64):
        super().__init__()
        self.emb = nn.Linear(1, emb)
        self.lstm = nn.LSTM(emb, hidden, batch_first=True)
        self.gru = nn.GRU(hidden, hidden, batch_first=True) if gru else None
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(hidden, n_classes))

    def forward(self, x):
        h, _ = self.lstm(self.emb(x.unsqueeze(-1)))
        if self.gru is not None:
            h, _ = self.gru(h)
        return self.head(h[:, -1])


def build_model(arch: str, n_in: int, n_classes: int, dropout: float = 0.3) -> nn.Module:
    if arch == "mlp":
        return DDoSNet(n_in, n_classes, dropout)
    if arch in ("lstm", "lstm_gru"):
        return SeqNet(n_in, n_classes, dropout, gru=arch == "lstm_gru")
    if arch in ("resvgg_swin", "resnet", "resnet_vgg", "resnet_swin"):
        return ResVGGSwinNet(n_in, n_classes, dropout,
                             use_vgg=arch in ("resvgg_swin", "resnet_vgg"),
                             use_swin=arch in ("resvgg_swin", "resnet_swin"))
    raise ValueError(f"arch không hợp lệ: {arch} (chọn trong {ARCHS})")
