# make_assets.py
from PIL import Image, ImageDraw
import numpy as np, wave, os

# 경로 준비
os.makedirs("static/images/emotions", exist_ok=True)
os.makedirs("static/sounds", exist_ok=True)

# 감정 아이콘 만들기
emotions = ['happy','sad','angry','surprise','fear','neutral','disgust']
colors = {
    'happy':(255,220,100),'sad':(120,150,255),'angry':(255,120,120),
    'surprise':(255,200,120),'fear':(180,140,255),'neutral':(200,200,200),'disgust':(150,255,150)
}

for e in emotions:
    img = Image.new('RGB',(64,64),colors[e])
    d = ImageDraw.Draw(img)
    d.ellipse((17,20,23,26), fill=(0,0,0))  # 눈
    d.ellipse((41,20,47,26), fill=(0,0,0))
    d.line((22,46,42,46), fill=(0,0,0), width=3)  # 입
    img.save(f'static/images/emotions/{e}.png')
print("emotion icons created")

# 비프 사운드 만들기 (wav)
def make_beep(path, freq, dur=0.3, sr=22050):
    t = np.linspace(0, dur, int(sr*dur), False)
    x = (np.sin(2*np.pi*freq*t)*32767).astype('<i2')
    with wave.open(path, 'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(x.tobytes())

make_beep("static/sounds/beep1.wav", 800)
make_beep("static/sounds/beep2.wav", 600)
make_beep("static/sounds/beep3.wav", 400)
print("beep sounds created")
