"""Monta a pasta de um story ou reels a partir de um MP4.

Uso:
  python scripts/preparar_video.py <slug> <story|reels> video.mp4 [legenda.txt]

Reencoda para o padrão do Instagram (H.264, 30 fps, AAC 48 kHz, 1080x1920),
copia para posts/<data>-<slug>/video.mp4 e grava post.json com status "rascunho".
Story tem até 60 s e não tem legenda; reels usa a legenda.
"""

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def main():
    if len(sys.argv) < 4 or sys.argv[2] not in ("story", "reels"):
        sys.exit(__doc__)
    slug, tipo, video = sys.argv[1:4]
    legenda = Path(sys.argv[4]).read_text(encoding="utf-8").strip() if len(sys.argv) > 4 else ""
    pasta = RAIZ / "posts" / f"{date.today().isoformat()}-{slug}"
    pasta.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video,
                    "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=30",
                    "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-crf", "20",
                    "-c:a", "aac", "-ar", "48000", "-b:a", "128k", "-movflags", "+faststart",
                    str(pasta / "video.mp4")], check=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(pasta / "video.mp4")], capture_output=True, text=True).stdout)
    # o servidor de arquivos que a Meta usa para baixar o vídeo (jsDelivr) não entrega arquivos acima de 20 MB
    if (pasta / "video.mp4").stat().st_size > 19_000_000:
        kbps = int(19_000_000 * 8 / dur / 1000) - 160
        bruto = pasta / "bruto.mp4"
        (pasta / "video.mp4").rename(bruto)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(bruto), "-c:v", "libx264", "-profile:v", "high",
                        "-pix_fmt", "yuv420p", "-b:v", f"{kbps}k", "-maxrate", f"{kbps}k", "-bufsize", f"{2 * kbps}k",
                        "-c:a", "aac", "-ar", "48000", "-b:a", "128k", "-movflags", "+faststart",
                        str(pasta / "video.mp4")], check=True)
        bruto.unlink()
    if tipo == "story" and dur > 60:
        sys.exit(f"story tem até 60 s, o vídeo tem {dur:.1f} s")
    post = {"status": "rascunho", "tipo": tipo, "video": "video.mp4", "legenda": legenda}
    (pasta / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(pasta, f"{dur:.1f}s")


if __name__ == "__main__":
    main()
