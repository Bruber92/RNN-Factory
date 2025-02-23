import torch
from torch import nn

from .TimeShift import TimeShift

# FFN
class Feed_Forward(nn.Module):
    def __init__(self, args, layer_id):
        super().__init__()
        self.args = args
        self.layer_id = layer_id
        self.time_shift = TimeShift(args.n_embd, shiftAmount=1, batch=args.micro_bsz)

        with torch.no_grad():  # fancy init of time_mix
            ratio_1_to_almost0 = 1.0 - (layer_id / args.n_layer)  # 1 to ~0
            ddd = torch.ones(1, 1, args.n_embd)
            for i in range(args.n_embd):
                ddd[0, 0, i] = i / args.n_embd
            self.time_mix_k = nn.Parameter(torch.pow(ddd, ratio_1_to_almost0))
            self.time_mix_r = nn.Parameter(torch.pow(ddd, ratio_1_to_almost0))
        
        self.key = nn.Linear(args.n_embd,args.dim_ffn, bias=False, dtype=torch.bfloat16)
        self.receptance = nn.Linear(args.n_embd, args.n_embd, bias=False, dtype=torch.bfloat16)
        self.value = nn.Linear(args.dim_ffn, args.n_embd, bias=False, dtype=torch.bfloat16)

    
    def forward(self, x):
        xx = self.time_shift(x)
        xk = x * self.time_mix_k + xx * (1 - self.time_mix_k)
        xr = x * self.time_mix_r + xx * (1 - self.time_mix_r)
        k = self.key(xk)
        k = torch.relu(k) ** 2
        kv = self.value(k)
        return torch.sigmoid(self.receptance(xr)) * kv
    
# Wavenet ffn
class WNFFN(Feed_Forward):
    def __init__(self, args, layer_id):
        super().__init__(args, layer_id)
        self.time_shift = TimeShift(args.n_embd, shiftAmount=2**(layer_id%12), batch=args.micro_bsz)
    
