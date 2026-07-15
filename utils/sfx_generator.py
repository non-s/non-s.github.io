import subprocess
import os
from pathlib import Path

def generate_cinematic_whoosh(output_path: Path):
    """Gera um efeito sonoro de 'Whoosh' cinematografico usando puro FFmpeg (Matematica Sonora)."""
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "anoisesrc=c=pink:r=44100:a=0.5,bandpass=f=1000:width_type=h:w=500,fade=t=in:st=0:d=0.1,fade=t=out:st=0.3:d=0.2",
        "-t", "0.5",
        str(output_path)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def generate_deep_impact(output_path: Path):
    """Gera um grave de impacto cinematografico (Boom/Hit)."""
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "sine=f=50:d=0.5,fade=t=in:st=0:d=0.01,fade=t=out:st=0.1:d=0.4",
        "-t", "0.5",
        str(output_path)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def ensure_sfx_library(assets_dir: Path) -> dict[str, Path]:
    sfx_dir = assets_dir / "sfx"
    sfx_dir.mkdir(parents=True, exist_ok=True)
    
    whoosh = sfx_dir / "whoosh.wav"
    impact = sfx_dir / "impact.wav"
    
    if not whoosh.exists():
        generate_cinematic_whoosh(whoosh)
    if not impact.exists():
        generate_deep_impact(impact)
        
    return {
        "whoosh": whoosh,
        "impact": impact
    }
