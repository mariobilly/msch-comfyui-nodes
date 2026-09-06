"""Explicit one-time download. The runtime analyzer never downloads a model."""
import argparse
from pathlib import Path
import torch

parser = argparse.ArgumentParser()
parser.add_argument('--models', required=True)
args = parser.parse_args()
directory = Path(args.models).resolve()
directory.mkdir(parents=True, exist_ok=True)
target = directory / '955717e8-8726e21a.th'
if not target.exists():
    torch.hub.download_url_to_file('https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/955717e8-8726e21a.th',
                                  str(target), hash_prefix='8726e21a')
print(target)
