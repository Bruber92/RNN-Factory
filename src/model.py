########################################################################################################
# The RWKV Language Model - https://github.com/BlinkDL/RWKV-LM
########################################################################################################

import os, importlib
import torch
# torch._C._jit_set_profiling_executor(True)
# torch._C._jit_set_profiling_mode(True)
import torch.nn as nn

if importlib.util.find_spec('deepspeed'):
    import deepspeed

# from deepspeed.runtime.fp16.onebit.zoadam import ZeroOneAdam

########################################################################################################
# RWKV: RWKV Time-mix + RWKV Channel-mix
########################################################################################################
import torch.nn as nn
import torch.nn.functional as F


########################################################################################################






    
class Block(nn.Module):
    def __init__(self, args, layer_id):
        super().__init__()
        self.args = args
        self.layer_id = layer_id
        self.lastlayer = args.n_layer-1

        self.ln1 = nn.LayerNorm(args.n_embd)
        self.ln2 = nn.LayerNorm(args.n_embd)
        self.ln3 = nn.LayerNorm(args.n_embd)
        self.ln4 = nn.LayerNorm(args.n_embd)
        self.ln5 = nn.LayerNorm(args.n_embd)
        self.ln6 = nn.LayerNorm(args.n_embd)
        self.ln7 = nn.LayerNorm(args.n_embd)
        
        from .RWKVTools.RNN import Short_Mem, Long_Mem, Feed_Forward
        self.att = Short_Mem(args, 2**(layer_id%12))
        # self.att2 = Short_Mem(args, 2**((layer_id)%10))
        # self.att3 = Short_Mem(args, 2**((layer_id)%8))
        # self.att4 = Short_Mem(args, 2**((layer_id)%6))
        # self.att5 = Short_Mem(args, 2**((layer_id)%4))
        # self.att6 = Short_Mem(args, 2**((layer_id)%2))
        # self.att7 = Short_Mem(args, 2**((layer_id)%1))
        self.longmem = Long_Mem(args, layer_id)
        # self.ffn = Feed_Forward(args, layer_id)

        # self.time_mix_a = nn.Parameter(torch.ones(args.n_embd))
        # self.time_mix_b = nn.Parameter(torch.ones(args.n_embd))
        # self.time_mix_c = nn.Parameter(torch.ones(args.n_embd))

   
    def forward(self, x):
        # if self.layer_id > 0:
        #     x, xstack = x
        # else:
        #     xstack = torch.zeros_like(x)
        # xstack = xstack*2 + x
        # x = xstack + x

        x = self.att(self.ln1(x)) + x
        # x = self.att2(self.ln2(x)) + x
        # x = self.att3(self.ln3(x)) + x
        # x = self.att4(self.ln4(x)) + x
        # x = self.att5(self.ln5(x)) + x
        # x = self.att6(self.ln6(x)) + x
        # x = self.att7(self.ln7(x)) + x
        
        
        x = self.longmem(self.ln2(x)) + x
        # x = self.ffn(self.ln3(x)) + x

        # if self.layer_id < self.lastlayer:
        #     return x, xstack
        return x



from .RWKVTools.RNN import LightningModel


class RWKV(LightningModel):
    def __init__(self, args):
        super().__init__()
        try:
            self.batches = args.micro_bsz
        except:
            self.batches = 1
            args.micro_bsz = 1

        try:
            args.grad_cp
        except:
            args.grad_cp = 0
        try:
            modelpath = args.load_model

        except:
            modelpath = None
        
        if modelpath:
            file = torch.load(modelpath, map_location="cpu")
            keys = list(file.keys())
            print("keys", keys)
            # remove _orig_mod from keys for compatibility with torch.compile
            newObj = {}
            for key in keys:
                if "_orig_mod." in key:
                    newKey = key.replace("_orig_mod.", "")
                    newObj[newKey] = file[key]
                else:
                    newObj[key] = file[key]
            file = newObj
            keys = list(file.keys())

            # detect model details
            vocab_size, n_embd = file[keys[0]].shape
            args.n_embd = n_embd
            args.vocab_size = vocab_size
            # model layers are model.2.x.yyy: find highest x
            n_layer = 0
            for key in keys:
                if key.startswith("model.2."):
                    layer = int(key.split(".")[2])
                    if layer > n_layer:
                        n_layer = layer
            args.n_layer = n_layer + 1
        else:
            file = None

        
        self.args = args



        emb = nn.Embedding(args.vocab_size, args.n_embd)
        ln_in = nn.LayerNorm(args.n_embd)
        blocks = nn.Sequential(*[Block(args, i) for i in range(args.n_layer)])
        ln_out = nn.LayerNorm(args.n_embd)
        head = nn.Linear(args.n_embd, args.vocab_size, bias=False)

        self.model = nn.Sequential(emb, ln_in, blocks, ln_out, head)
        
        if file:
            self.load_state_dict(file)

        # self.model = torch.compile(self.model)  
        # 


    

    def forward(self, idx):
        # if idx is list, make tensor
        if isinstance(idx, list):
            idx = torch.tensor(idx)
        # if idx is int, make tensor
        if isinstance(idx, int):
            idx = torch.tensor([idx])
        
        # if idx is not 3 dim tensor, make it 3 dim
        if len(idx.shape) == 1:
            idx = idx.unsqueeze(0)
            idx = idx.repeat(self.batches, 1)
        args = self.args
        idx = idx.to(self.device)

        if args.grad_cp == 1:
            return deepspeed.checkpointing.checkpoint(self.model, idx)
        else:
            return self.model(idx)

        
    

    