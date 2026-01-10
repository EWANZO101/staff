import os, hashlib, uuid, requests
from datetime import datetime, timedelta
from flask import render_template, request

_license_cache = {'valid': None, 'info': None, 'checked_at': None, 'features': [], 'max_users': 0, 'error': None}
CACHE_DURATION = timedelta(seconds=10)

def get_hardware_id():
    identifiers = []
    try:
        with open('/etc/machine-id', 'r') as f:
            identifiers.append(f.read().strip())
    except: pass
    try:
        import socket
        identifiers.append(socket.gethostname())
    except: pass
    if not identifiers:
        identifiers.append(str(uuid.getnode()))
    return hashlib.sha256('|'.join(identifiers).encode()).hexdigest()[:32]

def get_license_key():
    key = os.environ.get('LICENSE_KEY')
    if key: return key.strip()
    try:
        f = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'license.key')
        if os.path.exists(f):
            with open(f, 'r') as file: return file.read().strip()
    except: pass
    return None

def get_license_server():
    return os.environ.get('LICENSE_SERVER', 'http://localhost:5010')

def validate_license(force=False):
    global _license_cache
    if not force and _license_cache['checked_at']:
        if datetime.now() - _license_cache['checked_at'] < CACHE_DURATION:
            if _license_cache['valid']: return {'valid': True, 'info': _license_cache['info']}
            else: return {'valid': False, 'error': _license_cache.get('error', 'License invalid')}
    
    license_key = get_license_key()
    if not license_key:
        _license_cache['valid'] = False
        _license_cache['error'] = 'No license key configured'
        _license_cache['checked_at'] = datetime.now()
        return {'valid': False, 'error': 'No license key configured. Set LICENSE_KEY environment variable.'}
    
    try:
        server_url = get_license_server()
        domain = 'localhost'
        try:
            if request: domain = request.host
        except: pass
        
        response = requests.post(f'{server_url}/api/validate', json={
            'license_key': license_key,
            'hardware_id': get_hardware_id(),
            'domain': domain
        }, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('valid'):
                _license_cache.update({'valid': True, 'info': data, 'features': data.get('features', []), 'max_users': data.get('max_users', 0), 'checked_at': datetime.now(), 'error': None})
                return {'valid': True, 'info': data}
            else:
                _license_cache.update({'valid': False, 'error': data.get('error', 'License validation failed'), 'checked_at': datetime.now()})
                return {'valid': False, 'error': data.get('error', 'License validation failed')}
    except requests.exceptions.ConnectionError:
        if _license_cache['valid'] and _license_cache['checked_at']:
            if datetime.now() - _license_cache['checked_at'] < timedelta(days=7):
                return {'valid': True, 'info': _license_cache['info'], 'offline': True}
        _license_cache.update({'valid': False, 'error': 'Cannot connect to license server', 'checked_at': datetime.now()})
        return {'valid': False, 'error': 'Cannot connect to license server.'}
    except Exception as e:
        _license_cache.update({'valid': False, 'error': str(e), 'checked_at': datetime.now()})
        return {'valid': False, 'error': f'License error: {str(e)}'}

def license_context():
    return {'license_valid': _license_cache.get('valid', False), 'license_info': _license_cache.get('info'), 'license_features': _license_cache.get('features', [])}

def is_feature_enabled(feature):
    if _license_cache['valid'] and _license_cache['features']:
        return 'all' in _license_cache['features'] or feature in _license_cache['features']
    return False
