"""Sons do laboratório: marimba sintetizada (originais da ProEnglish)."""
import numpy as np, subprocess, sys, os
SR = 44100
def nota(f, dur=0.5, vol=1.0, brilho=1.0):
    t = np.arange(int(SR*dur))/SR
    # marimba: fundamental + 4.0x e 9.9x (barra afinada), decaimento rápido nos harmónicos
    s = np.sin(2*np.pi*f*t)*np.exp(-t*7) + 0.35*brilho*np.sin(2*np.pi*f*4*t)*np.exp(-t*30) + 0.08*brilho*np.sin(2*np.pi*f*9.9*t)*np.exp(-t*60)
    ataque = np.minimum(1, t/0.004)
    return s*ataque*vol
def mistura(partes, total):
    out = np.zeros(int(SR*total))
    for ini, sinal in partes:
        i = int(SR*ini); n = min(len(sinal), len(out)-i); out[i:i+n] += sinal[:n]
    return out
def hz(n):  # nome MIDI
    return 440*2**((n-69)/12)
C5,D5,E5,F5,G5,A5,B5,C6,E6,G6 = [hz(n) for n in (72,74,76,77,79,81,83,84,88,91)]
A3,F3,D4,C4,E4 = hz(57),hz(53),hz(62),hz(60),hz(64)
SONS = {
 'certo':      (mistura([(0, nota(E6,.45)), (0.07, nota(G6*1.0,.5)), (0.07, nota(C6,.5,.5))], .55), -3),
 'errado':     (mistura([(0, nota(E4,.35,1,.4)), (0.11, nota(C4,.45,1,.4))], .55), -9),
 'sequencia':  (mistura([(0, nota(C6,.4)), (0.07, nota(E6,.4)), (0.14, nota(G6,.6)), (0.14, nota(C6*2,.6,.4))], .75), -3),
 'sem-vidas':  (mistura([(0, nota(G5,.5,1,.5)), (0.16, nota(E5,.5,1,.5)), (0.32, nota(C5,.9,1,.5)), (0.32, nota(C5/2,.9,.6,.3))], 1.2), -8),
 'concluida':  (mistura([(0, nota(C5,.6)), (0.12, nota(E5,.6)), (0.24, nota(G5,.6)), (0.40, nota(C6,1.2)), (0.40, nota(E5,1.2,.6)), (0.40, nota(G5,1.2,.6)), (0.40, nota(C5/2,1.2,.5))], 1.6), -3),
 'meta':       (mistura([(0, nota(G5,.5)), (0.10, nota(C6,.5)), (0.20, nota(E6,.5)), (0.30, nota(G6,.5)), (0.46, nota(C6*2,1.2)), (0.46, nota(E6,1.2,.6)), (0.46, nota(G6,1.2,.5)), (0.46, nota(C5,1.2,.5))], 1.7), -3),
}
destino = sys.argv[1]; os.makedirs(destino, exist_ok=True)
for nome, (sinal, db) in SONS.items():
    sinal = sinal/np.abs(sinal).max()*10**(db/20)
    fade = int(SR*.03); sinal[-fade:] *= np.linspace(1, 0, fade)
    pcm = (sinal*32767).astype('<i2').tobytes()
    subprocess.run(['ffmpeg','-loglevel','error','-y','-f','s16le','-ar',str(SR),'-ac','1','-i','-','-b:a','64k',f'{destino}/{nome}.mp3'], input=pcm, check=True)
    print(nome, f'{len(sinal)/SR:.2f}s', os.path.getsize(f'{destino}/{nome}.mp3'), 'bytes')
