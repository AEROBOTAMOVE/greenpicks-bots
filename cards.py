# -*- coding: utf-8 -*-
"""
GREEN PICKS — генератор на визуални картички (като фиш-слиповете, но честни + по-добри).
Рендира PNG за: мач-преглед, ПЕЧЕЛИВШ фиш, ГУБЕЩ фиш (честно!), седмичен отчет.
Тъмна тема, зелен акцент, 🦖 GREEN PICKS бранд. Без емоджи-шрифт (рисувани баджове).
"""
from PIL import Image, ImageDraw, ImageFont
import os

# cross-platform шрифтове (Windows локално / Linux на GitHub Actions), с кирилица
_CANDS = {
  "arialbd.ttf": ["C:/Windows/Fonts/arialbd.ttf",
                  "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
  "arial.ttf":   ["C:/Windows/Fonts/arial.ttf",
                  "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}
def F(name, size):
    for p in _CANDS.get(name, [name]):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

# палитра
BG1=(11,18,32); BG2=(15,28,46); CARD=(20,30,48); LINE=(30,44,66)
WHITE=(237,243,250); GRAY=(140,156,178); GREEN=(22,199,132); RED=(240,72,90)
BLUE=(56,150,240); GOLD=(240,190,70); DGREEN=(12,60,45); DRED=(60,20,28)

W=H=1080

def _grad(draw):
    for y in range(H):
        t=y/H
        c=tuple(int(BG1[i]+(BG2[i]-BG1[i])*t) for i in range(3))
        draw.line([(0,y),(W,y)], fill=c)

def _round(draw, box, r, fill=None, outline=None, width=2):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)

def _center(draw, text, font, y, fill=WHITE):
    w=draw.textbbox((0,0),text,font=font)[2]
    draw.text(((W-w)//2, y), text, font=font, fill=fill)

def _badge(draw, cx, y, text, color, dark):
    f=F("arialbd.ttf",34)
    tw=draw.textbbox((0,0),text,font=f)[2]
    pad=34; bw=tw+pad*2; bh=64
    x=cx-bw//2
    _round(draw,[x,y,x+bw,y+bh],32,fill=dark,outline=color,width=3)
    draw.text((x+pad, y+13), text, font=f, fill=color)
    return y+bh

def _check(draw, cx, cy, r, color):
    _round(draw,[cx-r,cy-r,cx+r,cy+r],r,fill=color)
    draw.line([(cx-r*0.4,cy),(cx-r*0.05,cy+r*0.4),(cx+r*0.5,cy-r*0.4)], fill=BG1, width=8, joint="curve")
def _cross(draw, cx, cy, r, color):
    _round(draw,[cx-r,cy-r,cx+r,cy+r],r,fill=color)
    d=r*0.42
    draw.line([(cx-d,cy-d),(cx+d,cy+d)], fill=BG1, width=8)
    draw.line([(cx-d,cy+d),(cx+d,cy-d)], fill=BG1, width=8)

def _header(draw):
    draw.rectangle([0,0,W,10], fill=GREEN)
    draw.text((44,40), "GREEN PICKS", font=F("arialbd.ttf",44), fill=WHITE)
    draw.polygon([(30,62),(20,80),(30,98),(40,80)], fill=GREEN)
    hf=F("arial.ttf",28)
    tw=draw.textbbox((0,0),"@greenpicksbg",font=hf)[2]
    draw.text((W-tw-44,52), "@greenpicksbg", font=hf, fill=GRAY)

def _footer(draw, line):
    draw.line([(44,H-96),(W-44,H-96)], fill=LINE, width=2)
    draw.text((44,H-78), line, font=F("arial.ttf",24), fill=GRAY)
    draw.text((44,H-46), "18+ · Прогноза, не съвет · Залагай отговорно", font=F("arial.ttf",22), fill=GRAY)

def base():
    img=Image.new("RGB",(W,H),BG1); d=ImageDraw.Draw(img); _grad(d); _header(d); return img,d

def match_card(home, away, league, when, lines, out):
    img,d=base()
    _badge(d, W//2, 150, "АНАЛИЗ НА ДЕНЯ", BLUE, (14,34,58))
    _center(d, home, F("arialbd.ttf",60), 250)
    _center(d, "срещу", F("arial.ttf",34), 330, GRAY)
    _center(d, away, F("arialbd.ttf",60), 380)
    _center(d, f"{league}  ·  {when}", F("arial.ttf",30), 470, GRAY)
    _round(d,[70,540,W-70,900],28, fill=CARD, outline=LINE, width=2)
    y=580
    for label,val in lines:
        d.text((110,y), label, font=F("arial.ttf",32), fill=GRAY)
        vw=d.textbbox((0,0),val,font=F("arialbd.ttf",32))[2]
        d.text((W-110-vw,y), val, font=F("arialbd.ttf",32), fill=WHITE)
        y+=64
    _footer(d, "Статистика, не гаранция · виж пика в канала")
    img.save(out); return out

def result_card(home, away, market, coef, units, won, score, out):
    img,d=base()
    coef=float(coef)
    color=GREEN if won else RED
    dark=DGREEN if won else DRED
    _badge(d, W//2, 150, "ПЕЧЕЛИВШ" if won else "ГУБЕЩ", color, dark)
    (_check if won else _cross)(d, W//2, 300, 62, color)
    _center(d, f"{home} — {away}", F("arialbd.ttf",50), 400)
    _center(d, f"Резултат: {score}", F("arial.ttf",34), 480, GRAY)
    _round(d,[70,560,W-70,880],28, fill=CARD, outline=color, width=2)
    rows=[("Пазар", market),("Коефициент", str(coef)),
          ("Залог", f"{units} ед."),
          ("Резултат", f"+{round((coef-1)*units,2)} ед." if won else f"−{units} ед.")]
    y=600
    for label2,val in rows:
        d.text((110,y), label2, font=F("arial.ttf",32), fill=GRAY)
        vc = color if label2=="Резултат" else WHITE
        vw=d.textbbox((0,0),val,font=F("arialbd.ttf",34))[2]
        d.text((W-110-vw,y), val, font=F("arialbd.ttf",34), fill=vc)
        y+=66
    _footer(d, "Всеки резултат — зелен И червен — е в дневника")
    img.save(out); return out

def recap_card(period, wins, losses, net, roi, out):
    img,d=base()
    net=float(net); roi=float(roi)
    _badge(d, W//2, 150, "ОТЧЕТ", GOLD, (58,44,14))
    _center(d, period, F("arialbd.ttf",54), 250, WHITE)
    total=wins+losses
    _round(d,[70,360,W-70,820],28, fill=CARD, outline=LINE, width=2)
    stats=[("Пикове", str(total), WHITE),
           ("Печеливши", str(wins), GREEN),
           ("Губещи", str(losses), RED),
           ("Успеваемост", f"{round(100*wins/max(total,1))}%", WHITE),
           ("Нето", f"{'+' if net>=0 else ''}{net} ед.", GREEN if net>=0 else RED),
           ("ROI", f"{'+' if roi>=0 else ''}{roi}%", GREEN if roi>=0 else RED)]
    y=400
    for label,val,c in stats:
        d.text((110,y), label, font=F("arial.ttf",34), fill=GRAY)
        vw=d.textbbox((0,0),val,font=F("arialbd.ttf",38))[2]
        d.text((W-110-vw,y-4), val, font=F("arialbd.ttf",38), fill=c)
        y+=70
    _footer(d, "Прозрачност или нищо · нищо не се трие")
    img.save(out); return out

def morning_card(date_bg, total, sports, out):
    img,d=base()
    _badge(d, W//2, 160, "ДОБРО УТРО", GOLD, (58,44,14))
    cx,cy=W//2,330
    _round(d,[cx-52,cy-52,cx+52,cy+52],52,fill=GOLD)
    for ang in range(0,360,30):
        import math
        x1=cx+math.cos(math.radians(ang))*70; y1=cy+math.sin(math.radians(ang))*70
        x2=cx+math.cos(math.radians(ang))*92; y2=cy+math.sin(math.radians(ang))*92
        d.line([(x1,y1),(x2,y2)], fill=GOLD, width=7)
    _center(d, "GREEN PICKS", F("arialbd.ttf",56), 440, WHITE)
    _center(d, date_bg, F("arial.ttf",32), 512, GRAY)
    _round(d,[90,600,W-90,820],28, fill=CARD, outline=LINE, width=2)
    _center(d, f"{total}", F("arialbd.ttf",96), 630, GREEN)
    _center(d, f"мача днес в {sports} спорта", F("arial.ttf",34), 745, GRAY)
    _footer(d, "Кафето е горещо · следим пазара за теб")
    img.save(out); return out

def logo_avatar(out, size=1024):
    import math
    img=Image.new("RGB",(size,size),BG1); d=ImageDraw.Draw(img)
    for y in range(size):
        t=y/size; c=tuple(int(BG1[i]+(BG2[i]-BG1[i])*t) for i in range(3)); d.line([(0,y),(size,y)],fill=c)
    cx=size//2; cy=int(size*0.42); R=int(size*0.24)
    d.polygon([(cx,cy-R-18),(cx+R+18,cy),(cx,cy+R+18),(cx-R-18,cy)], outline=GREEN, width=10)
    d.polygon([(cx,cy-R),(cx+R,cy),(cx,cy+R),(cx-R,cy)], fill=GREEN)
    mf=F("arialbd.ttf",int(size*0.20))
    tw=d.textbbox((0,0),"GP",font=mf); w=tw[2]-tw[0]; h=tw[3]-tw[1]
    d.text((cx-w/2-tw[0], cy-h/2-tw[1]), "GP", font=mf, fill=BG1)
    nf=F("arialbd.ttf",int(size*0.105))
    _c=lambda txt,f,y,fill: d.text(((size-(d.textbbox((0,0),txt,font=f)[2]))/2,y),txt,font=f,fill=fill)
    _c("GREEN PICKS", nf, int(size*0.70), WHITE)
    tf=F("arial.ttf",int(size*0.042))
    _c("Честни спортни прогнози", tf, int(size*0.83), GRAY)
    d.rectangle([int(size*0.30),int(size*0.905),int(size*0.70),int(size*0.912)], fill=GREEN)
    img.save(out); return out

def room_welcome(title, subtitle, bullets, accent_name, out):
    acc={"green":GREEN,"blue":BLUE,"gold":GOLD,"red":RED}.get(accent_name,GREEN)
    img,d=base()
    d.rectangle([0,0,W,10], fill=acc)
    _round(d,[60,150,W-60,260],24, fill=CARD, outline=acc, width=3)
    _center(d, title, F("arialbd.ttf",58), 172)
    _center(d, subtitle, F("arial.ttf",32), 300, GRAY)
    _round(d,[70,380,W-70,H-140],28, fill=CARD, outline=LINE, width=2)
    y=430
    for b in bullets:
        d.ellipse([110,y+12,126,y+28], fill=acc)
        d.text((150,y), b, font=F("arial.ttf",32), fill=WHITE)
        y+=72
    _footer(d, "🦖 GREEN PICKS · честни прогнози · 18+")
    img.save(out); return out

if __name__=="__main__":
    os.makedirs("cards_samples", exist_ok=True)
    morning_card("вторник, 22.07", 47, 8, "cards_samples/morning.png")
    logo_avatar("cards_samples/logo.png")
    print("Готово.")
