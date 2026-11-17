#!/usr/bin/env python3
"""render_b.py - AI代班中 B 版（淺色＋3D 角色主持）成片合成器
用法：python3 render_b.py <集數資料夾>
資料夾內需要 episode.json、audio/NN.mp3；本工具資料夾需要 f_closed/f_half/f_open/f_blink.png、style_b.css、demo.*
輸出：final.mp4、captions.srt、chapters.txt、thumbnail.jpg、render.log
scene 可加 "demo": "sheet_formula" 使用試算表示範動畫；第一個與最後一個場景用大角色版面。
"""
import html, json, os, re, subprocess, sys, shutil
import numpy as np
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); FPS = 30; PAD = 0.4; MAXC = 30

def dur(p): return float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p],capture_output=True,text=True,check=True).stdout.strip())
def sentences(t):
    parts = [p.strip() for p in re.split(r"(?<=[。！？!?：])", t) if p.strip()]; out = []
    for p in parts:
        while len(p) > MAXC:
            cands = [i for i, ch in enumerate(p[:MAXC]) if ch in "，、； " and i >= 2]
            cut = cands[-1] + 1 if cands else MAXC
            out.append(p[:cut]); p = p[cut:].strip()
        if p: out.append(p)
    return out
def ts(s):
    ms = int(round(s*1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s2, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s2:02d},{ms:03d}"
def split_title(body):
    tag = re.match(r"\s*<span class='tag'>(.*?)</span>", body)
    rest = body[tag.end():] if tag else body
    h2 = re.match(r"\s*<h2[^>]*>(.*?)</h2>", rest)
    if not h2: return (tag.group(1) if tag else ""), "", body if not tag else rest
    return (tag.group(1) if tag else ""), h2.group(1), rest[h2.end():]

def main(ep):
    data = json.load(open(os.path.join(ep, "episode.json"), encoding="utf-8"))
    scenes = data["scenes"]; n = len(scenes); work = os.path.abspath(os.path.join(ep, "_work_b"))
    shutil.rmtree(work, ignore_errors=True); os.makedirs(os.path.join(work, "fr"))
    for f in ["f_closed.png","f_half.png","f_open.png","f_blink.png"]: shutil.copy(os.path.join(HERE, f), work)
    # timeline
    tl = []; t0 = 0.0; srt = []; chapters = []
    for i, sc in enumerate(scenes, 1):
        a = os.path.join(ep, "audio", f"{i:02d}.mp3"); ad = dur(a); d = ad + PAD
        caps = sentences(sc["narration"]); w = [max(len(c), 4) for c in caps]; W = sum(w); acc = 0.0; ct = []
        for j, c in enumerate(caps):
            cd = ad * w[j] / W + (PAD if j == len(caps)-1 else 0)
            ct.append((acc, acc+cd, c)); srt.append(f"{len(srt)+1}\n{ts(t0+acc)} --> {ts(t0+acc+cd)}\n{c}\n"); acc += cd
        if sc.get("chapter"): chapters.append((t0, sc["chapter"]))
        tl.append(dict(start=t0, dur=d, caps=ct)); t0 += d
    T = t0; N = int(T * FPS)
    # audio track
    with open(os.path.join(work, "a.txt"), "w") as f:
        for i in range(1, n+1):
            p = os.path.join(work, f"a{i}.wav")
            subprocess.run(["ffmpeg","-v","error","-y","-i",os.path.join(ep,"audio",f"{i:02d}.mp3"),"-af","apad","-t",f"{tl[i-1]['dur']:.3f}","-ar","44100","-ac","1",p],check=True)
            f.write(f"file '{os.path.abspath(p)}'\n")
    full = os.path.join(work, "full.wav")
    subprocess.run(["ffmpeg","-v","error","-y","-f","concat","-safe","0","-i",os.path.join(work,"a.txt"),"-c","copy",full],check=True)
    pcm = subprocess.run(["ffmpeg","-v","error","-i",full,"-ac","1","-ar","16000","-f","s16le","-"],capture_output=True).stdout
    x = np.frombuffer(pcm, np.int16).astype(float); hop = 16000 // FPS
    rms = np.array([np.sqrt(np.mean(x[k*hop:(k+1)*hop]**2)) if (k+1)*hop <= len(x) else 0 for k in range(N)])
    rms = np.convolve(rms, [0.25,0.5,0.25], "same"); r = rms / max(np.percentile(rms, 95), 1)
    face = np.where(r < 0.15, 0, np.where(r < 0.5, 1, 2))
    for k in range(1, N-1):
        if face[k] != face[k-1] and face[k] != face[k+1]: face[k] = face[k-1]
    bt = 1.7
    while bt < T: face[int(bt*FPS):int(bt*FPS)+4] = 3; bt += 3.1 + (bt*7 % 1.6)
    # page
    demo_html = open(os.path.join(HERE,"demo.html"),encoding="utf-8").read()
    parts = []
    for i, sc in enumerate(scenes):
        hero = i == 0 or i == n-1
        if hero:
            parts.append(f"<div class='scene hero' id='s{i}'><div class='c'>{sc['body']}</div></div>")
        elif sc.get("demo") == "sheet_formula":
            tag, h2, _ = split_title(sc["body"])
            parts.append(f"<div class='scene' id='s{i}'><div id='demo'><div class='ttl'><span class='chip'>{tag}</span><h2>{h2}</h2></div>{demo_html}</div></div>")
        else:
            tag, h2, rest = split_title(sc["body"])
            chip = f"<span class='chip'>{tag}</span>" if tag else ""
            parts.append(f"<div class='scene' id='s{i}'><div class='ttl'>{chip}<h2>{h2}</h2></div><div class='win'><div class='c'>{rest}</div></div></div>")
    page = ("<html><head><meta charset='utf-8'><style>" + open(os.path.join(HERE,"style_b.css"),encoding="utf-8").read()
            + open(os.path.join(HERE,"demo.css"),encoding="utf-8").read() + "</style></head><body><div class='prog' id='prog'></div>"
            + "".join(parts) + "<div class='av'><img id='i0' src='f_closed.png'><img id='i1' src='f_half.png'><img id='i2' src='f_open.png'><img id='i3' src='f_blink.png'></div>"
            + "<div class='bubble' id='bub'></div><div class='brand'>AI代班中</div><script>" + open(os.path.join(HERE,"demo.js"),encoding="utf-8").read()
            + open(os.path.join(HERE,"anim_b.js"),encoding="utf-8").read() + "</script></body></html>")
    hp = os.path.join(work, "page.html"); open(hp, "w", encoding="utf-8").write(page)
    durs = [s["dur"] for s in tl]
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width":1920,"height":1080})
        pg.goto("file://" + os.path.abspath(hp)); pg.wait_for_timeout(800)
        ends = pg.evaluate("d=>initB(d)", [durs, [bool(s.get('demo')) for s in scenes]])
        # avatar sprites (small / hero) with transparent background
        sprites = {}
        pg.evaluate("()=>{document.body.style.background='transparent';document.querySelectorAll('.scene,.bubble,.brand,.prog').forEach(e=>e.style.visibility='hidden')}")
        for hero, si0 in ((False, 1), (True, 0)):
            pg.evaluate("a=>renderB(a[0],0,0,'',0)", [si0])
            box = pg.locator(".av").bounding_box(); pad = 30
            clip = {"x": box["x"]-pad, "y": box["y"]-pad, "width": box["width"]+2*pad, "height": box["height"]+2*pad}
            for f in range(4):
                pg.evaluate("f=>{[0,1,2,3].forEach(k=>document.getElementById('i'+k).style.opacity=(k==f?1:0))}", f)
                path = os.path.join(work, f"av_{int(hero)}_{f}.png"); pg.screenshot(path=path, clip=clip, omit_background=True)
            sprites[hero] = (int(clip["x"]), int(clip["y"]))
        pg.evaluate("()=>{document.body.style.background='';document.querySelectorAll('.scene,.bubble,.brand,.prog').forEach(e=>e.style.visibility='')}")
        PV = {int((x['start']+0.75*x['dur'])*FPS) for x in tl} if os.environ.get('PREVIEW') else None
        si = 0; last_key = None; last_path = None; shots = 0; seq = []
        for k in range(N):
            t = k / FPS
            while si < n-1 and t >= tl[si+1]["start"]: si += 1
            lt = t - tl[si]["start"]; cap = ""
            for a0, a1, c in tl[si]["caps"]:
                if a0 <= lt < a1: cap = c; break
            if not cap: cap = tl[si]["caps"][-1][2]
            hero = si == 0 or si == n-1
            seq.append((hero, int(face[k])))
            if PV is not None and k not in PV: continue
            key = (si, k if lt <= ends[si] else -1, cap)
            path = os.path.join(work, "fr", f"{k:05d}.jpg")
            if key == last_key and PV is None:
                os.link(last_path, path); continue
            pg.evaluate("a=>renderB(a[0],a[1],-1,a[2],a[3])", [si, lt, html.escape(cap), (si+1)/n])
            pg.screenshot(path=path, type="jpeg", quality=90); shots += 1
            last_key, last_path = key, path
        b.close()
    if PV is not None: print('preview', sorted(PV)); return
    print("screenshots", shots, "of", N)
    blank = os.path.join(work, "blank.png")
    from PIL import Image
    w0, h0 = Image.open(os.path.join(work, "av_0_0.png")).size; w1, h1 = Image.open(os.path.join(work, "av_1_0.png")).size
    Image.new("RGBA", (max(w0, w1), max(h0, h1)), (0,0,0,0)).save(blank)
    for hero in (False, True):
        runs = []
        for hh, f in seq:
            img = os.path.join(work, f"av_{int(hero)}_{f}.png") if hh == hero else blank
            if runs and runs[-1][0] == img: runs[-1][1] += 1
            else: runs.append([img, 1])
        with open(os.path.join(work, f"av{int(hero)}.txt"), "w") as fo:
            for img, c in runs: fo.write(f"file '{img}'\nduration {c/FPS:.5f}\n")
            fo.write(f"file '{runs[-1][0]}'\n")
    (x0, y0), (x1, y1) = sprites[False], sprites[True]
    out = os.path.join(ep, "final.mp4")
    fc = (f"[1:v]fps={FPS},format=rgba[s];[2:v]fps={FPS},format=rgba[h];[0:v][s]overlay={x0}:{y0}:eof_action=pass[a];"
          f"[a][h]overlay={x1}:{y1}:eof_action=pass,format=yuv420p[v]")
    subprocess.run(["ffmpeg","-v","error","-y","-framerate",str(FPS),"-i",os.path.join(work,"fr","%05d.jpg"),
                    "-f","concat","-safe","0","-i",os.path.join(work,"av0.txt"),"-f","concat","-safe","0","-i",os.path.join(work,"av1.txt"),
                    "-i",full,"-filter_complex",fc,"-map","[v]","-map","3:a","-t",f"{T:.3f}",
                    "-c:v","libx264","-preset","medium","-crf","21","-c:a","aac","-b:a","160k","-ar","44100","-movflags","+faststart",out],check=True)
    open(os.path.join(ep,"captions.srt"),"w",encoding="utf-8").write("\n".join(srt))
    def mmss(t): t = int(t); return f"{t//60}:{t%60:02d}"
    if chapters:
        if chapters[0][0] > 0: chapters.insert(0, (0.0, "開場"))
        open(os.path.join(ep,"chapters.txt"),"w",encoding="utf-8").write("\n".join(f"{mmss(t)} {c}" for t, c in chapters) + "\n")
    size = os.path.getsize(out); msg = f"OK B版 場景 {n}、字幕 {len(srt)} 句、片長 {T:.1f}s、檔案 {size/1e6:.1f} MB"
    open(os.path.join(ep,"render.log"),"w").write(msg+"\n"); print(msg)

if __name__ == "__main__": main(sys.argv[1])
