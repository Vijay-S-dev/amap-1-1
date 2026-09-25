import urllib.request
import json
import io

login_req = urllib.request.Request(
    'http://127.0.0.1:8000/api/v1/auth/login',
    headers={'Content-Type': 'application/json', 'X-Organization-Id': '9a61e05d-7a32-4112-9c17-1833d7b42f65'},
    data=json.dumps({
        'organization_id': '9a61e05d-7a32-4112-9c17-1833d7b42f65',
        'email': 'alex.worker@amap.com',
        'password': 'SecurePassword123!'
    }).encode('utf-8')
)
with urllib.request.urlopen(login_req) as resp:
    token = json.loads(resp.read().decode('utf-8'))['access_token']

with open('scripts/agla.wav', 'rb') as f:
    wav_data = f.read()

boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
body = io.BytesIO()
body.write(b'--' + boundary.encode() + b'\r\n')
body.write(b'Content-Disposition: form-data; name="audio"; filename="voice-command.wav"\r\n')
body.write(b'Content-Type: audio/wav\r\n\r\n')
body.write(wav_data)
body.write(b'\r\n--' + boundary.encode() + b'\r\n')
body.write(b'Content-Disposition: form-data; name="language"\r\n\r\n')
body.write(b'hi\r\n')
body.write(b'--' + boundary.encode() + b'--\r\n')
content = body.getvalue()

transcribe_req = urllib.request.Request(
    'http://127.0.0.1:8000/api/v1/voice/transcribe',
    headers={
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Authorization': f'Bearer {token}',
        'X-Organization-Id': '9a61e05d-7a32-4112-9c17-1833d7b42f65'
    },
    data=content
)

with urllib.request.urlopen(transcribe_req) as resp:
    stt_resp = json.loads(resp.read().decode('utf-8'))
    print('STT RESP:', stt_resp)

cmd_req = urllib.request.Request(
    'http://127.0.0.1:8000/api/v1/voice/process-command',
    headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}',
        'X-Organization-Id': '9a61e05d-7a32-4112-9c17-1833d7b42f65'
    },
    data=json.dumps({
        'raw_transcript': stt_resp['transcript'],
        'confidence': stt_resp['confidence'],
        'language': stt_resp['detected_language']
    }).encode('utf-8')
)
with urllib.request.urlopen(cmd_req) as resp:
    print('CMD RESP:', json.loads(resp.read().decode('utf-8')))
