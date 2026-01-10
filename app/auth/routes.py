from app.auth import bp
from flask import request, redirect, url_for, flash
import os

@bp.route('/activate-license', methods=['GET', 'POST'])
def activate_license():
    if request.method == 'GET':
        return redirect(url_for('main.index'))
    
    license_key = request.form.get('license_key', '').strip().upper()
    
    if not license_key:
        flash('Please enter a license key', 'error')
        return redirect(url_for('main.index'))
    
    # Save to license.key file (overwrites any existing key)
    license_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'license.key')
    try:
        with open(license_file, 'w') as f:
            f.write(license_key)
        
        # Clear cache to force re-validation
        from app.license import _license_cache
        _license_cache['checked_at'] = None
        _license_cache['valid'] = None
        _license_cache['info'] = None
        _license_cache['features'] = []
        _license_cache['error'] = None
        
        flash('License key updated. Validating...', 'info')
        return redirect('/')
    except Exception as e:
        flash(f'Failed to save license: {str(e)}', 'error')
        return redirect('/')
