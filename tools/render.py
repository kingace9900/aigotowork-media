#!/usr/bin/env python3
"""render.py - AI代班中 成片合成器
用法：python3 render.py <集數資料夾>
資料夾內需要：
  episode.json  {"title":..., "scenes":[{"body": "<html>", "narration": "旁白全文", "chapter": "可選：章節名"}...], "thumbnail": {"big":"縮圖大字","small":"小字"}}
  audio/01.mp3, audio/02.mp3 ...  每個場景一段配音（Runway 產生後下載）
輸出：final.mp4（1920x1080）、captions.srt、chapters.txt、thumbnail.jpg、render.log
每個場景依句號切成字幕，字幕時間按字數比例分配在該段配音裡。
"""
import html, json, os, re, subprocess, sys
CSS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.css"), encoding="utf-8").read()
CHROME = next(p for p in ["/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"] if os.path.exists(p))

def run(cmd): subprocess.run(cmd, check=True, capture_output=True)
def dur(p): return float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p],capture_output=True,text=True,check=True).stdout.strip())
def shot(htmlpath, png, w=1920, h=1080):
    run([CHROME,"--headless=new","--no-sandbox","--disable-gpu","--hide-scrollbars",f"--window-size={w},{h}",f"--screenshot={png}",f"file://{os.path.abspath(htmlpath)}"])
def page(body, cap, n, total):
    capdiv = f"<div class='cap'><span>{html.escape(cap)}</span></div>" if cap else ""
    return (f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='brand'>AI代班中</div>"
            f"<div class='prog'><i style='width:{n/total*100:.1f}%'></i></div><div class='wrap'>{body}</div>{capdiv}</body></html>")
def sentences(t):
    parts = [p.strip() for p in re.split(r"(?<=[。！？!?])", t) if p.strip()]
    out = []
    for p in parts:  # 太長的句子再用逗號切，字幕一行不超過 26 字
        while len(p) > 26:
            cut = max(p.rfind("，", 0, 26), p.rfind("、", 0, 26))
            cut = cut + 1 if cut > 6 else 26
            while 6 < cut < len(p) and p[cut-1].isascii() and p[cut-1].isalnum() and p[cut].isascii() and p[cut].isalnum():
                cut -= 1  # 不要把英文字切成兩半
            out.append(p[:cut]); p = p[cut:].strip()
        if p: out.append(p)
    return out
def ts(s):
    ms = int(round(s*1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s2, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s2:02d},{ms:03d}"

def main(ep):
    data = json.load(open(os.path.join(ep, "episode.json"), encoding="utf-8"))
    work = os.path.join(ep, "_work"); os.makedirs(work, exist_ok=True)
    scenes = data["scenes"]; segs = []; srt = []; t0 = 0.0; k = 0; chapters = []
    for i, sc in enumerate(scenes, 1):
        audio = os.path.join(ep, "audio", f"{i:02d}.mp3")
        if not os.path.exists(audio): sys.exit(f"缺少配音 {audio}")
        ad = dur(audio); pad = 0.4; total = ad + pad
        if sc.get("chapter"): chapters.append((t0, sc["chapter"]))
        caps = sentences(sc["narration"]); weights = [max(len(c), 4) for c in caps]; W = sum(weights)
        lst = []; acc = 0.0
        for j, c in enumerate(caps):
            d = ad * weights[j] / W + (pad if j == len(caps)-1 else 0)
            k += 1; hp = os.path.join(work, f"{k}.html"); pp = os.path.join(work, f"{k}.png")
            open(hp, "w", encoding="utf-8").write(page(sc["body"], c, i, len(scenes))); shot(hp, pp)
            lst.append((pp, d)); srt.append(f"{len(srt)+1}\n{ts(t0+acc)} --> {ts(t0+acc+d)}\n{c}\n"); acc += d
        cl = os.path.join(work, f"s{i}.txt")
        with open(cl, "w") as f:
            for pp, d in lst: f.write(f"file '{os.path.abspath(pp)}'\nduration {d:.3f}\n")
            f.write(f"file '{os.path.abspath(lst[-1][0])}'\n")
        seg = os.path.join(work, f"s{i}.mp4")
        run(["ffmpeg","-y","-f","concat","-safe","0","-i",cl,"-i",audio,"-af","apad","-t",f"{total:.3f}",
             "-vf","fps=30,format=yuv420p","-c:v","libx264","-preset","veryfast","-crf","20","-c:a","aac","-ar","44100","-b:a","160k",seg])
        segs.append(seg); t0 += total
    with open(os.path.join(work, "all.txt"), "w") as f:
        for s in segs: f.write(f"file '{os.path.abspath(s)}'\n")
    run(["ffmpeg","-y","-f","concat","-safe","0","-i",os.path.join(work,"all.txt"),"-c","copy","-movflags","+faststart",os.path.join(ep,"final.mp4")])
    open(os.path.join(ep, "captions.srt"), "w", encoding="utf-8").write("\n".join(srt))
    def mmss(t): t = int(t); return f"{t//60}:{t%60:02d}"
    if chapters:
        if chapters[0][0] > 0: chapters.insert(0, (0.0, "開場"))
        open(os.path.join(ep, "chapters.txt"), "w", encoding="utf-8").write("\n".join(f"{mmss(t)} {c}" for t, c in chapters) + "\n")
    th = data.get("thumbnail", {})
    if th:
        hp = os.path.join(work, "thumb.html")
        open(hp, "w", encoding="utf-8").write(f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body class='thumb'>"
            f"<div class='tb'>{html.escape(th.get('big',''))}</div><div class='ts'>{html.escape(th.get('small',''))}</div>"
            f"{th.get('extra','')}<div class='brand'>AI代班中</div></body></html>")
        shot(hp, os.path.join(work, "thumb.png"), 1280, 720)
        run(["ffmpeg","-y","-i",os.path.join(work,"thumb.png"),"-q:v","3",os.path.join(ep,"thumbnail.jpg")])
    size = os.path.getsize(os.path.join(ep, "final.mp4"))
    msg = f"OK 場景 {len(scenes)}、字幕 {len(srt)} 句、片長 {t0:.1f}s、檔案 {size/1e6:.1f} MB"
    open(os.path.join(ep, "render.log"), "w").write(msg + "\n"); print(msg)

if __name__ == "__main__": main(sys.argv[1])
