#!/usr/bin/env python3
"""compose_host.py - AI代班中 真人主持版合成器（淺色版型）
用法：python3 compose_host.py <集數資料夾>
資料夾內需要：
  episode.json   同 render.py；每個 scene 可加 "layout": "side"（主持人左、內容右）或 "pip"（內容全版＋主持人小窗）
  audio/NN.wav   每段配音
  host/NN.mp4    每段主持人對嘴影片（WanGP LongCat 輸出，544x720）
輸出：final_host.mp4（1920x1080）、captions.srt、chapters.txt
"""
import html, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import run, dur, shot, sentences, ts

CSS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "style_light.css"), encoding="utf-8").read()
DEFAULT_LAYOUT = {1: "side", 3: "side", 4: "side", 6: "side", 9: "side", 13: "side", 14: "side", 15: "side", 16: "side"}

def page(body, cap, n, total, layout):
    capdiv = f"<div class='cap'><span>{html.escape(cap)}</span></div>" if cap else ""
    return (f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body class='{layout}'><div class='hostbg'></div>"
            f"<div class='brand'>AI代班中</div><div class='prog'><i style='width:{n/total*100:.1f}%'></i></div>"
            f"<div class='wrap'>{body}</div>{capdiv}</body></html>")

def main(ep):
    data = json.load(open(os.path.join(ep, "episode.json"), encoding="utf-8"))
    work = os.path.join(ep, "_hostwork"); os.makedirs(work, exist_ok=True)
    scenes = data["scenes"]; segs = []; srt = []; t0 = 0.0; k = 0; chapters = []
    for i, sc in enumerate(scenes, 1):
        layout = sc.get("layout") or DEFAULT_LAYOUT.get(i, "pip")
        audio = os.path.join(ep, "audio", f"{i:02d}.wav"); host = os.path.join(ep, "host", f"{i:02d}.mp4")
        for p in (audio, host):
            if not os.path.exists(p): sys.exit(f"缺少 {p}")
        ad = dur(audio); pad = 0.4; total = ad + pad
        if sc.get("chapter"): chapters.append((t0, sc["chapter"]))
        caps = sentences(sc["narration"]); weights = [max(len(c), 4) for c in caps]; W = sum(weights)
        lst = []; acc = 0.0
        for j, c in enumerate(caps):
            d = ad * weights[j] / W + (pad if j == len(caps) - 1 else 0)
            k += 1; hp = os.path.join(work, f"{k}.html"); pp = os.path.join(work, f"{k}.png")
            open(hp, "w", encoding="utf-8").write(page(sc["body"], c, i, len(scenes), layout)); shot(hp, pp)
            lst.append((pp, d)); srt.append(f"{len(srt)+1}\n{ts(t0+acc)} --> {ts(t0+acc+d)}\n{c}\n"); acc += d
        cl = os.path.join(work, f"s{i}.txt")
        with open(cl, "w") as f:
            for pp, d in lst: f.write(f"file '{os.path.abspath(pp)}'\nduration {d:.3f}\n")
            f.write(f"file '{os.path.abspath(lst[-1][0])}'\n")
        if layout == "side":
            hv = "scale=-2:1080,crop=min(iw\\,860):1080"; x, y = "(860-w)/2", "0"
        else:
            hv = "scale=330:437"; x, y = "1530", "110"
        fc = (f"[1:v]{hv},setsar=1,fps=25,tpad=stop_mode=clone:stop_duration=3[h];"
              f"[0:v]fps=25,format=yuv420p[b];[b][h]overlay={x}:{y}:shortest=0,format=yuv420p[v]")
        seg = os.path.join(work, f"s{i}.mp4")
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cl, "-i", host, "-i", audio,
             "-filter_complex", fc, "-map", "[v]", "-map", "2:a", "-af", "apad", "-t", f"{total:.3f}",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-ar", "44100", "-b:a", "160k", seg])
        segs.append(seg); t0 += total
        print(f"scene {i:02d} {layout} {total:.1f}s", flush=True)
    with open(os.path.join(work, "all.txt"), "w") as f:
        for s in segs: f.write(f"file '{os.path.abspath(s)}'\n")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(work, "all.txt"), "-c", "copy",
         "-movflags", "+faststart", os.path.join(ep, "final_host.mp4")])
    open(os.path.join(ep, "captions.srt"), "w", encoding="utf-8").write("\n".join(srt))
    def mmss(t): t = int(t); return f"{t//60}:{t%60:02d}"
    if chapters:
        if chapters[0][0] > 0: chapters.insert(0, (0.0, "開場"))
        open(os.path.join(ep, "chapters.txt"), "w", encoding="utf-8").write("\n".join(f"{mmss(t)} {c}" for t, c in chapters) + "\n")
    print(f"OK 場景 {len(scenes)}、字幕 {len(srt)} 句、片長 {t0:.1f}s")

if __name__ == "__main__": main(sys.argv[1])
