"""Generate the voiceover for the reel in the current folder with the ElevenLabs API.

Run from a reel folder:  python3 <engine>/tools/tts_elevenlabs.py audio/vo_el.mp3
Needs ELEVENLABS_API_KEY in the environment (or in a .env file in the reel folder).
Optional: ELEVEN_VOICE_ID (default: Jeremy - Casual Guy Next Door), ELEVEN_MODEL, ELEVEN_STABILITY, ELEVEN_STYLE.
One take per run (about 1 credit per character on v2/v3/v4 models, about half on eleven_flash_v2_5).
"""
import json, os, sys, urllib.request, urllib.error

env_file = os.path.join(os.getcwd(), '.env')
if os.path.exists(env_file):
    for line in open(env_file):
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.strip().split('=', 1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

key = os.environ.get('ELEVENLABS_API_KEY')
if not key:
    sys.exit('Set ELEVENLABS_API_KEY (export it, or put ELEVENLABS_API_KEY=... in a .env file in the reel folder)')
voice = os.environ.get('ELEVEN_VOICE_ID', '5gaEGrWSk4v20HMfIhgC')
model = os.environ.get('ELEVEN_MODEL', 'eleven_multilingual_v2')
out = sys.argv[1] if len(sys.argv) > 1 else 'audio/vo_el.mp3'

text = ' '.join(json.load(open('script.json')))
body = json.dumps({
    'text': text,
    'model_id': model,
    'voice_settings': {
        'stability': float(os.environ.get('ELEVEN_STABILITY', 0.45)),
        'similarity_boost': 0.75,
        'style': float(os.environ.get('ELEVEN_STYLE', 0.3)),
        'use_speaker_boost': True,
    },
}).encode()
req = urllib.request.Request(
    f'https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128',
    data=body, headers={'xi-api-key': key, 'Content-Type': 'application/json', 'Accept': 'audio/mpeg'})
try:
    with urllib.request.urlopen(req, timeout=180) as r:
        os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
        open(out, 'wb').write(r.read())
except urllib.error.HTTPError as e:
    sys.exit(f'ElevenLabs error {e.code}: {e.read().decode(errors="replace")[:500]}')
print(f'wrote {out} ({len(text)} characters, model {model}, voice {voice})')
