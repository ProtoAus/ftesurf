"""Convert the owner's weather WAVs to native-playable mono64kbps Ogg Vorbis.
Do not modify originals. Disk Opus is not compiled into the shipped FTE sound
loader (voice Opus is separate); no native/DLL change is needed for Vorbis.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import wave


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--ffmpeg',type=Path,required=True);ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=True);rows=[]
    for name in ['rainloop','snowloop','thunder']:
        source=a.source/(name+'.wav');target=a.output/(name+'.ogg')
        original=source.read_bytes();digest=hashlib.sha256(original).hexdigest()
        with wave.open(str(source),'rb') as w:
            params={'channels':w.getnchannels(),'rate':w.getframerate(),'frames':w.getnframes(),'sample_bytes':w.getsampwidth()};duration=w.getnframes()/w.getframerate()
        if target.exists():raise FileExistsError('refuse overwrite: '+str(target))
        subprocess.run([str(a.ffmpeg),'-nostdin','-hide_banner','-loglevel','error','-i',str(source),'-map_metadata','-1','-vn','-ac','1','-ar','44100','-c:a','libvorbis','-b:a','64k',str(target)],check=True)
        data=target.read_bytes()
        if not data.startswith(b'OggS') or b'vorbis' not in data[:100] or len(data)>=len(original):raise ValueError('not a smaller native Vorbis file')
        if source.read_bytes()!=original:raise ValueError('owner source changed during conversion')
        rows.append({'name':name,'input_sha256':digest,'input_bytes':len(original),'input_pcm':params,'duration_seconds':duration,'output_sha256':hashlib.sha256(data).hexdigest(),'output_bytes':len(data),'codec':'vorbis','channels':1,'nominal_bitrate':64000})
    a.report.write_text(json.dumps({'owner_supplied_originals_untouched':True,'native_disk_codec':'vorbis','target':'mono64kbps','files':rows},indent=2)+'\n');print(json.dumps({'original_bytes':sum(x['input_bytes'] for x in rows),'compressed_bytes':sum(x['output_bytes'] for x in rows),'files':3}))

if __name__=='__main__':main()
