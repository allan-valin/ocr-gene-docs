"""One self-contained page anybody can read a manifest into, away from this repo.

The labels this repository measured itself against turned out to be mostly the
assistant's own reading of the same scans (docs/TASKS-honest-measurement.md),
so the held-out set has to be read by a person, somewhere else, probably on a
machine with none of this installed. That means a single file: the page images
already inside it, the engine's own row numbering drawn on them, and somewhere
to type.

The row numbers are the point. Names typed against the wrong rows is not a
small error — it is what made every character-error figure taken before
2026-09-04 a name scored against a neighbour's handwriting — so each band the
engine cut is outlined and numbered on the image itself, and the boxes to type
into carry the same numbers.

    .venv/bin/python scripts/make_reading_sheet.py --out sheet.html
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from desembarque.identity import cached_hash          # noqa: E402

# The draw of 2026-09-07, seed 20260907, recorded in
# docs/TASKS-honest-measurement.md. Taken in order; a prefix of a random list
# is still a random sample, so stopping early keeps the estimate honest.
DRAWN = [
    "BR_RJANRIO_BS_0_RPV_ENT_016429_d0001de0001.pdf",
    "BR_RJANRIO_BS_0_RPV_ENT_016079_d0001de0001.pdf",
    "BR_RJANRIO_OL_0_RPV_PRJ_17318_d0001de0001.pdf",
    "BR_RJANRIO_BS_0_RPV_ENT_016317_d0001de0001.pdf",
    "BR_RJANRIO_OL_0_RPV_PRJ_19747_d0001de0001.pdf",
    "BR_RJANRIO_BS_0_RPV_ENT_016762_d0001de0001.pdf",
    "BR_RJANRIO_OL_0_RPV_PRJ_17627_d0001de0001.pdf",
    "BR_RJANRIO_BS_0_RPV_ENT_016890_d0001de0001.pdf",
    "BR_RJANRIO_OL_0_RPV_PRJ_18396_d0001de0001.pdf",
    "BR_RJANRIO_BS_0_RPV_ENT_015306_d0001de0001.pdf",
]


def pick_page(record: dict) -> tuple[int, dict] | None:
    """The page worth reading: the most rows, with a usable measurement.

    Not page 2 by convention — page 2 is sometimes the cover's reverse and
    sometimes the fullest list in the dossier, and a sheet of eight rows wastes
    the reading.
    """
    best = None
    counts: dict[int, int] = {}
    for r in record.get("rows") or ():
        counts[r.get("page")] = counts.get(r.get("page"), 0) + 1
    for p in record.get("pages") or ():
        geo = (p or {}).get("geometry") or {}
        rows, cols = geo.get("rows") or [], geo.get("columns") or []
        if len(rows) < 5 or len(cols) < 2:
            continue
        n = counts.get(p.get("n"), 0)
        if best is None or n > best[2]:
            best = (p.get("n"), geo, n)
    return (best[0], best[1]) if best else None


def _font(size: int):
    """A real font: the default bitmap one is unreadable once the page is
    scaled to fit a screen, and an unreadable row number is a name typed
    against the wrong row."""
    from PIL import ImageFont
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def strip(image: Path, geo: dict, pad: float = 0.02, width: int = 1000):
    """The name column of the page, with every band outlined and numbered."""
    from PIL import Image, ImageDraw

    im = Image.open(image).convert("RGB")
    W, H = im.size
    cols = geo["columns"]
    # `columns` is the name column alone on a page measured off the rules, and
    # every boundary on a page that printed its headings.
    x0, x1 = (cols[0], cols[1]) if len(cols) >= 2 else (0.05, 0.35)
    rows = [tuple(b) for b in geo["rows"] if b and len(b) == 2]
    top = max(0.0, min(r[0] for r in rows) - pad)
    bot = min(1.0, max(r[1] for r in rows) + pad)
    # room on the left for the number, and a little past the column for the
    # ditto marks and whatever the clerk wrote into the margin
    left = max(0.0, x0 - 0.055)
    right = min(1.0, x1 + 0.03)
    box = (int(left * W), int(top * H), int(right * W), int(bot * H))
    cut = im.crop(box)
    scale = width / cut.width
    cut = cut.resize((width, max(1, int(cut.height * scale))))

    draw = ImageDraw.Draw(cut, "RGBA")
    font = _font(int(width * 0.032))
    gut = int(width * 0.062)          # the numbered gutter down the left
    marks = []
    for i, (a, b) in enumerate(rows, start=1):
        ya = (a * H - box[1]) * scale
        yb = (b * H - box[1]) * scale
        if yb < 0 or ya > cut.height:
            continue
        # the band shaded rather than outlined: on a faint page a hairline
        # rule is indistinguishable from the clerk's own ruling
        draw.rectangle([gut, ya, cut.width - 1, yb],
                       fill=(210, 60, 60, 26) if i % 2 else (50, 100, 210, 26),
                       outline=(200, 40, 40, 150) if i % 2 else (40, 90, 200, 150))
        draw.rectangle([0, ya, gut, yb], fill=(250, 250, 248, 235),
                       outline=(150, 150, 150, 120))
        draw.text((gut / 2, (ya + yb) / 2), str(i), fill=(20, 20, 20),
                  font=font, anchor="mm")
        marks.append(i)
    buf = io.BytesIO()
    cut.save(buf, "JPEG", quality=62, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii"), marks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pages", type=int, default=10, help="how many documents")
    ap.add_argument("--width", type=int, default=1000)
    ap.add_argument("--scans", type=Path, default=ROOT / "data" / "scans")
    ap.add_argument("--records", type=Path,
                    default=ROOT / "data" / "transcriptions")
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "pagecache")
    a = ap.parse_args(argv)

    from page_geometry import page_image

    sheets = []
    for name in DRAWN[:a.pages]:
        pdf = a.scans / name
        if not pdf.exists():
            print(f"  {name}: not on disk, skipped")
            continue
        rec = a.records / f"{cached_hash(pdf)}.json"
        if not rec.exists():
            print(f"  {name}: never read, skipped")
            continue
        got = pick_page(json.loads(rec.read_text(encoding="utf-8")))
        if not got:
            print(f"  {name}: no measured page, skipped")
            continue
        page, geo = got
        img = page_image(pdf, page, a.work)
        if img is None:
            print(f"  {name} p{page}: no image, skipped")
            continue
        b64, marks = strip(img, geo, width=a.width)
        sheets.append({"pdf": name, "page": page, "rows": marks, "jpg": b64})
        print(f"  {name} p{page}: {len(marks)} rows, {len(b64) * 3 // 4 >> 10} KB")

    a.out.write_text(render(sheets), encoding="utf-8")
    size = a.out.stat().st_size >> 10
    print(f"\nwrote {a.out} — {len(sheets)} pages, {size} KB"
          f"{'  (too big to email, use --pages)' if size > 20000 else ''}")
    return 0


def render(sheets: list[dict]) -> str:
    from string import Template
    body = []
    for i, s in enumerate(sheets):
        opts = "".join(
            f'<div class=r><label>{n}</label>'
            f'<input data-s="{i}" data-n="{n}" autocomplete=off spellcheck=false>'
            f'</div>' for n in s["rows"])
        body.append(f'''
<section class=sheet data-pdf="{s['pdf']}" data-page="{s['page']}">
  <h2>{i + 1}. {s['pdf'][:-4]} — page {s['page']}</h2>
  <div class=hand><b>Mark which this page is</b> — it is the split that matters most:
    <label><input type=radio name=h{i} value=typed> typed</label>
    <label><input type=radio name=h{i} value=cursive> handwritten</label>
    <label><input type=radio name=h{i} value=mixed> both</label>
  </div>
  <div class=cols>
    <div class=img><img onclick="this.classList.toggle('big')" title="click to enlarge" src="data:image/jpeg;base64,{s['jpg']}" alt=""></div>
    <div class=rows>{opts}</div>
  </div>
</section>''')
    return Template(TEMPLATE).safe_substitute(BODY="\n".join(body),
                                              N=str(len(sheets)))


TEMPLATE = """<!doctype html>
<meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Desembarque — reading sheet</title>
<style>
 :root{color-scheme:light}
 body{margin:0;font:15px/1.5 system-ui,sans-serif;background:#f6f5f2;color:#1a1a1a}
 header,section{max-width:1180px;margin:0 auto;padding:18px 20px}
 header{background:#fff;border-bottom:1px solid #ddd}
 h1{font-size:20px;margin:0 0 6px}
 h2{font-size:15px;font-weight:600;margin:26px 0 8px}
 table{border-collapse:collapse;margin:10px 0}
 td{border:1px solid #ddd;padding:4px 9px;vertical-align:top}
 td:first-child{font-family:ui-monospace,monospace;white-space:nowrap;background:#faf9f7}
 .sheet{background:#fff;border:1px solid #e2e0dc;border-radius:8px;margin:20px auto}
 .cols{display:flex;gap:16px;align-items:flex-start}
 .img{flex:0 0 auto;position:sticky;top:8px}
 .img img{max-width:none;width:var(--w,620px);border:1px solid #ccc;background:#fff;cursor:zoom-in}
 .img img.big{--w:1400px;cursor:zoom-out}
 .rows{flex:1;min-width:240px;display:flex;flex-direction:column;gap:3px}
 .r{display:flex;align-items:center;gap:8px}
 .r label{flex:0 0 30px;text-align:right;color:#777;font-family:ui-monospace,monospace;font-size:12px}
 .r input{flex:1;padding:4px 7px;border:1px solid #ccc;border-radius:4px;font-size:14px}
 .r input:focus{outline:2px solid #4a7;border-color:#4a7}
 .hand{margin:0 0 10px;color:#555;font-size:13px}
 .hand label{margin-right:10px}
 .bar{position:sticky;bottom:0;background:#fff;border-top:1px solid #ddd;padding:12px 20px;text-align:center}
 button{font:inherit;padding:9px 16px;border:1px solid #333;background:#222;color:#fff;border-radius:6px;cursor:pointer}
 button.ghost{background:#fff;color:#222}
 #out{width:100%;max-width:1140px;height:180px;font-family:ui-monospace,monospace;font-size:12px;margin-top:10px;display:none}
 @media(max-width:900px){.cols{flex-direction:column}.img{position:static}.img img{width:100%}}
</style>
<header>
<h1>Desembarque — reading sheet</h1>
<p>$N pages, drawn at random from the archive (seed 20260907) so neither of us
picked the easy ones. <b>Take them in order and stop whenever you like</b> — a
prefix of a random list is still a random sample.</p>
<p><b>Click any image to enlarge it.</b> The red and blue bands are the rows
<em>the machine</em> cut, numbered as it numbers them — so the first name on
the page is often row 3, because the machine counts the printed heading and its
rules as rows too. That is not a mistake to correct: type the name beside
whatever number its band carries. Type what each row says beside its number. The numbers are the
part that matters: a name typed against the wrong row is worse than no name.</p>
<table>
<tr><td>José Fernandes</td><td>you read it and you are sure</td></tr>
<tr><td>?José Guberti</td><td>you read it, <b>not</b> sure — a leading <b>?</b> marks the row uncertain</td></tr>
<tr><td>?Lorenzo ?</td><td>sure of one word, the other you cannot make out</td></tr>
<tr><td><i>leave empty</i></td><td><b>you cannot read it at all.</b> This is an answer, not a gap — it is the most useful row on the page</td></tr>
<tr><td>-</td><td>there is no row there: a ruled line, a blank, empty space</td></tr>
</table>
<p><b>Please do not skip the illegible ones.</b> Every previous measurement in
this project quietly left them out, which is why it flattered itself.</p>
</header>
$BODY
<div class=bar>
  <button onclick="save()">Download the file</button>
  <button class=ghost onclick="copy()">Copy instead</button>
  <p style="font-size:13px;color:#666;margin:8px 0 0">Send it back however is
  easiest. Your work is kept in this browser as you type, so a closed tab is
  not a lost page.</p>
  <textarea id=out readonly></textarea>
</div>
<script>
const KEY='desembarque-reading-sheet';
function load(){try{const w=JSON.parse(localStorage.getItem(KEY)||'{}');
  document.querySelectorAll('.rows input').forEach(i=>{
    const k=i.dataset.s+':'+i.dataset.n; if(w[k]!==undefined)i.value=w[k];});
  if(w.__hand)Object.entries(w.__hand).forEach(([n,v])=>{
    const r=document.querySelector(`input[name=h${n}][value="${v}"]`); if(r)r.checked=true;});
 }catch(e){}}
function keep(){try{const w={__hand:{}};
  document.querySelectorAll('.rows input').forEach(i=>{
    if(i.value)w[i.dataset.s+':'+i.dataset.n]=i.value;});
  document.querySelectorAll('.sheet').forEach((s,i)=>{
    const c=document.querySelector(`input[name=h${i}]:checked`);
    if(c)w.__hand[i]=c.value;});
  localStorage.setItem(KEY,JSON.stringify(w));}catch(e){}}
function collect(){
  return [...document.querySelectorAll('.sheet')].map((s,i)=>{
    const rows={};
    s.querySelectorAll('.rows input').forEach(inp=>{rows[inp.dataset.n]=inp.value.trim();});
    const c=document.querySelector(`input[name=h${i}]:checked`);
    return {pdf:s.dataset.pdf,page:+s.dataset.page,hand:c?c.value:null,
            reader:'Allan',read_on:new Date().toISOString().slice(0,10),
            complete:true,rows};
  }).filter(s=>Object.values(s.rows).some(v=>v!==''));
}
function save(){const b=new Blob([JSON.stringify(collect(),null,1)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(b);
  a.download='reading-sheet.json';a.click();}
function copy(){const t=document.getElementById('out');
  t.style.display='block';t.value=JSON.stringify(collect(),null,1);
  t.select();try{document.execCommand('copy')}catch(e){}}
addEventListener('input',keep); addEventListener('change',keep); load();
</script>
"""


if __name__ == "__main__":
    raise SystemExit(main())
