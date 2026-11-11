import io
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.database import db_session
from app.security.session import login_required
from app.models.all_models import (
    UserSMTPAccount,
    EmailBatch,
    EmailRecipient,
    SMTPAccountStatus,
    SMTPConnectionType,
    EmailBatchStatus,
    EmailBatchSendingMode,
    EmailRecipientStatus
)
from app.security.credential_vault import encrypt_smtp_credentials
from app.services.smtp_validator import detect_provider, is_free_email_domain, validate_smtp_host_ssrf
from app.services.smtp_client import test_smtp_connection
from app.services.csv_parser import parse_csv_content
from app.services.template_renderer import render_email_preview, sanitize_email_html
from app.services.bulk_email_sender import start_batch_sending_job

bulk_email_bp = Blueprint('bulk_email', __name__, url_prefix='/api/bulk-email')


# ==============================================================================
# 1. SMTP Account Management Endpoints
# ==============================================================================

@bulk_email_bp.route('/accounts/detect-provider', methods=['POST'])
@login_required
def api_detect_provider():
    """Detects likely provider settings based on input email domain."""
    data = request.get_json() or {}
    email_address = (data.get('email_address') or '').strip().lower()

    if not email_address or '@' not in email_address:
        return jsonify({'success': False, 'error': 'A valid email address is required.'}), 400

    detection = detect_provider(email_address)
    return jsonify({'success': True, 'data': detection})


@bulk_email_bp.route('/accounts', methods=['GET'])
@login_required
def api_get_accounts():
    """Returns all connected SMTP accounts for the authenticated user. Never returns passwords."""
    user_id = request.user_id
    accounts = db_session.query(UserSMTPAccount).filter_by(user_id=user_id).order_by(
        UserSMTPAccount.is_primary.desc(),
        UserSMTPAccount.created_at.desc()
    ).all()

    account_list = []
    for acc in accounts:
        account_list.append({
            'id': acc.id,
            'email_address': acc.email_address,
            'sender_name': acc.sender_name,
            'provider': acc.provider,
            'connection_type': acc.connection_type,
            'smtp_host': acc.smtp_host,
            'smtp_port': acc.smtp_port,
            'smtp_username': acc.smtp_username,
            'use_tls': acc.use_tls,
            'use_ssl': acc.use_ssl,
            'connection_status': acc.connection_status,
            'is_primary': acc.is_primary,
            'last_tested_at': acc.last_tested_at.isoformat() if acc.last_tested_at else None,
            'last_error_message': acc.last_error_message,
            'created_at': acc.created_at.isoformat() if acc.created_at else None
        })

    return jsonify({'success': True, 'accounts': account_list})


@bulk_email_bp.route('/accounts/test', methods=['POST'])
@login_required
def api_test_account_connection():
    """Tests an SMTP connection dynamically without saving."""
    data = request.get_json() or {}
    email_address = (data.get('email_address') or '').strip().lower()
    host = (data.get('smtp_host') or '').strip()
    port = int(data.get('smtp_port') or 587)
    username = (data.get('smtp_username') or email_address).strip()
    password = data.get('smtp_password') or ''
    use_tls = bool(data.get('use_tls', True))
    use_ssl = bool(data.get('use_ssl', False))

    if is_free_email_domain(email_address):
        return jsonify({
            'success': False,
            'error': 'Personal consumer accounts (@gmail.com, @yahoo.com) cannot be used as business sending accounts.'
        }), 400

    if not host:
        return jsonify({'success': False, 'error': 'SMTP host is required.'}), 400

    success, err_msg = test_smtp_connection(
        host=host,
        port=port,
        username=username,
        password=password,
        use_tls=use_tls,
        use_ssl=use_ssl
    )

    if success:
        return jsonify({'success': True, 'message': 'SMTP connection and authentication successful!'})
    else:
        return jsonify({'success': False, 'error': err_msg}), 400


@bulk_email_bp.route('/accounts', methods=['POST'])
@login_required
def api_create_or_update_account():
    """Connects or updates an SMTP account for the user, encrypting credentials with AES-256-GCM."""
    user_id = request.user_id
    data = request.get_json() or {}

    email_address = (data.get('email_address') or '').strip().lower()
    sender_name = (data.get('sender_name') or '').strip()
    provider = (data.get('provider') or 'custom').strip()
    connection_type = (data.get('connection_type') or 'SMTP').strip().upper()
    host = (data.get('smtp_host') or '').strip()
    port = int(data.get('smtp_port') or 587)
    username = (data.get('smtp_username') or email_address).strip()
    password = data.get('smtp_password') or ''
    use_tls = bool(data.get('use_tls', True))
    use_ssl = bool(data.get('use_ssl', False))
    is_primary = bool(data.get('is_primary', False))

    if not email_address or '@' not in email_address:
        return jsonify({'success': False, 'error': 'Valid business email address is required.'}), 400

    if is_free_email_domain(email_address):
        return jsonify({
            'success': False,
            'error': 'Free personal email accounts (@gmail.com, @yahoo.com) are not allowed as business sending accounts. Use your business domain.'
        }), 400

    if not host:
        return jsonify({'success': False, 'error': 'SMTP host is required.'}), 400

    if not password:
        return jsonify({'success': False, 'error': 'SMTP password or App Password is required.'}), 400

    # Test connection live before saving
    test_ok, test_err = test_smtp_connection(
        host=host,
        port=port,
        username=username,
        password=password,
        use_tls=use_tls,
        use_ssl=use_ssl
    )

    if not test_ok:
        return jsonify({
            'success': False,
            'error': f"Failed to verify SMTP credentials: {test_err}"
        }), 400

    # Encrypt credentials using AES-256-GCM
    encrypted_data, key_version = encrypt_smtp_credentials({'password': password})

    # If is_primary or first account, ensure primary status handled
    existing_accounts = db_session.query(UserSMTPAccount).filter_by(user_id=user_id).all()
    if not existing_accounts:
        is_primary = True
    elif is_primary:
        # Demote others
        for acc in existing_accounts:
            acc.is_primary = False

    new_account = UserSMTPAccount(
        user_id=user_id,
        email_address=email_address,
        sender_name=sender_name or email_address.split('@')[0],
        provider=provider,
        connection_type=connection_type,
        smtp_host=host,
        smtp_port=port,
        smtp_username=username,
        use_tls=use_tls,
        use_ssl=use_ssl,
        encrypted_credentials=encrypted_data,
        encryption_key_version=key_version,
        connection_status=SMTPAccountStatus.CONNECTED.value,
        is_primary=is_primary,
        last_tested_at=datetime.utcnow(),
        last_error_message=None
    )

    db_session.add(new_account)
    db_session.commit()

    return jsonify({
        'success': True,
        'message': 'Business email account connected successfully!',
        'account_id': new_account.id
    })


@bulk_email_bp.route('/accounts/<int:account_id>/primary', methods=['POST'])
@login_required
def api_set_primary_account(account_id: int):
    """Sets the designated account as the primary default sending account."""
    user_id = request.user_id
    accounts = db_session.query(UserSMTPAccount).filter_by(user_id=user_id).all()
    target_account = None

    for acc in accounts:
        if acc.id == account_id:
            acc.is_primary = True
            target_account = acc
        else:
            acc.is_primary = False

    if not target_account:
        return jsonify({'success': False, 'error': 'Account not found.'}), 404

    db_session.commit()
    return jsonify({'success': True, 'message': f'{target_account.email_address} is now your default sending account.'})


@bulk_email_bp.route('/accounts/<int:account_id>', methods=['DELETE'])
@login_required
def api_delete_account(account_id: int):
    """Disconnects and removes the SMTP account."""
    user_id = request.user_id
    acc = db_session.query(UserSMTPAccount).filter_by(id=account_id, user_id=user_id).first()
    if not acc:
        return jsonify({'success': False, 'error': 'Account not found.'}), 404

    was_primary = acc.is_primary
    db_session.delete(acc)
    db_session.commit()

    if was_primary:
        # Promote next account to primary
        next_acc = db_session.query(UserSMTPAccount).filter_by(user_id=user_id).first()
        if next_acc:
            next_acc.is_primary = True
            db_session.commit()

    return jsonify({'success': True, 'message': 'Account disconnected successfully.'})


# ==============================================================================
# 2. CSV Upload & Dynamic Header Detection Endpoints
# ==============================================================================

@bulk_email_bp.route('/parse-csv', methods=['POST'])
@login_required
def api_parse_csv():
    """Uploads and parses a recipient CSV file, detecting arbitrary headers and duplicates."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded.'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'error': 'No file selected.'}), 400

    file_bytes = file.read()
    try:
        parsed = parse_csv_content(file_bytes)
        return jsonify({
            'success': True,
            'filename': file.filename,
            'summary': {
                'total_rows_read': parsed['total_rows_read'],
                'valid_count': parsed['valid_count'],
                'invalid_count': parsed['invalid_count']
            },
            'detected_headers': parsed['detected_headers'],
            'email_column_key': parsed['email_column_key'],
            'placeholders': parsed['placeholders'],
            'valid_recipients': parsed['valid_recipients'],
            'invalid_recipients': parsed['invalid_recipients'],
            'sample_preview': parsed['sample_preview']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# ==============================================================================
# 3. Email Preview & Validation
# ==============================================================================

@bulk_email_bp.route('/preview', methods=['POST'])
@login_required
def api_preview_recipient():
    """Renders personalized subject and HTML for a specific recipient, flagging missing placeholders."""
    data = request.get_json() or {}
    subject = data.get('subject', '')
    body_html = data.get('body_html', '')
    body_text = data.get('body_text')
    recipient_data = data.get('recipient_data', {})
    fallback_value = data.get('fallback_value', '')

    sanitized_html = sanitize_email_html(body_html)
    preview = render_email_preview(
        subject_template=subject,
        body_html_template=sanitized_html,
        body_text_template=body_text,
        recipient_data=recipient_data,
        fallback_value=fallback_value
    )

    return jsonify({'success': True, 'preview': preview})


# ==============================================================================
# 4. Batch Creation & Dispatch Endpoints
# ==============================================================================

@bulk_email_bp.route('/batches', methods=['POST'])
@login_required
def api_create_and_send_batch():
    """Creates an email batch with recipients and initiates sending in the background."""
    user_id = request.user_id
    data = request.get_json() or {}

    batch_name = (data.get('batch_name') or f"Campaign {datetime.utcnow().strftime('%b %d, %Y %H:%M')}").strip()
    smtp_account_id = data.get('smtp_account_id')
    original_filename = (data.get('original_filename') or 'recipients.csv').strip()
    subject = (data.get('subject') or '').strip()
    body_html = data.get('body_html') or ''
    body_text = data.get('body_text') or ''
    sending_mode = (data.get('sending_mode') or EmailBatchSendingMode.PERSONALIZED.value).strip().upper()
    valid_recipients = data.get('valid_recipients') or []
    detected_headers = data.get('detected_headers') or []
    confirmed_lawful_basis = bool(data.get('confirmed_lawful_basis', False))

    if not confirmed_lawful_basis:
        return jsonify({
            'success': False,
            'error': 'You must confirm that you have permission or a lawful basis to contact these recipients.'
        }), 400

    if not subject:
        return jsonify({'success': False, 'error': 'Email subject is required.'}), 400

    if not body_html and not body_text:
        return jsonify({'success': False, 'error': 'Email body cannot be empty.'}), 400

    if not valid_recipients:
        return jsonify({'success': False, 'error': 'No valid recipients to send to.'}), 400

    # Validate SMTP Account belongs to user
    smtp_account = None
    if smtp_account_id:
        smtp_account = db_session.query(UserSMTPAccount).filter_by(id=smtp_account_id, user_id=user_id).first()
    else:
        # Fallback to primary account
        smtp_account = db_session.query(UserSMTPAccount).filter_by(user_id=user_id, is_primary=True).first()
        if not smtp_account:
            smtp_account = db_session.query(UserSMTPAccount).filter_by(user_id=user_id).first()

    if not smtp_account:
        return jsonify({
            'success': False,
            'error': 'No connected business email account found. Please connect your email in Email Settings first.'
        }), 400

    # Sanitize HTML body
    sanitized_html = sanitize_email_html(body_html) if body_html else ""

    # Create Batch record
    batch = EmailBatch(
        user_id=user_id,
        smtp_account_id=smtp_account.id,
        batch_name=batch_name,
        original_filename=original_filename,
        subject=subject,
        body_html=sanitized_html,
        body_text=body_text,
        sending_mode=sending_mode,
        total_recipients=len(valid_recipients),
        valid_recipients=len(valid_recipients),
        invalid_recipients=int(data.get('invalid_count', 0)),
        accepted_count=0,
        failed_count=0,
        status=EmailBatchStatus.QUEUED.value,
        detected_headers=detected_headers,
        created_at=datetime.utcnow()
    )

    db_session.add(batch)
    db_session.flush() # assign batch.id

    # Create recipient rows
    recipient_objs = []
    for r in valid_recipients:
        rec_email = r.get('email', '').strip().lower()
        rec_data = r.get('data') or {}
        recipient_objs.append(EmailRecipient(
            batch_id=batch.id,
            user_id=user_id,
            email_address=rec_email,
            recipient_data=rec_data,
            status=EmailRecipientStatus.PENDING.value,
            attempt_count=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ))

    db_session.bulk_save_objects(recipient_objs)
    db_session.commit()

    # Trigger background worker using current Flask app instance
    app_instance = current_app._get_current_object()
    start_batch_sending_job(app_instance, batch.id)

    return jsonify({
        'success': True,
        'message': f"Batch '{batch_name}' queued for sending to {len(valid_recipients)} recipient(s).",
        'batch_id': batch.id
    })


# ==============================================================================
# 5. History & Progress Monitoring Endpoints
# ==============================================================================

@bulk_email_bp.route('/batches', methods=['GET'])
@login_required
def api_get_batches():
    """Lists email batches for the user."""
    user_id = request.user_id
    batches = db_session.query(EmailBatch).filter_by(user_id=user_id).order_by(EmailBatch.created_at.desc()).all()

    result = []
    for b in batches:
        result.append({
            'id': b.id,
            'batch_name': b.batch_name,
            'subject': b.subject,
            'sending_mode': b.sending_mode,
            'status': b.status,
            'total_recipients': b.total_recipients,
            'valid_recipients': b.valid_recipients,
            'accepted_count': b.accepted_count,
            'failed_count': b.failed_count,
            'created_at': b.created_at.isoformat() if b.created_at else None,
            'started_at': b.started_at.isoformat() if b.started_at else None,
            'completed_at': b.completed_at.isoformat() if b.completed_at else None,
            'error_message': b.error_message
        })

    return jsonify({'success': True, 'batches': result})


@bulk_email_bp.route('/batches/<int:batch_id>', methods=['GET'])
@login_required
def api_get_batch_details(batch_id: int):
    """Returns details and individual recipient statuses for a specific batch."""
    user_id = request.user_id
    batch = db_session.query(EmailBatch).filter_by(id=batch_id, user_id=user_id).first()
    if not batch:
        return jsonify({'success': False, 'error': 'Batch not found.'}), 404

    recipients = db_session.query(EmailRecipient).filter_by(batch_id=batch.id, user_id=user_id).order_by(EmailRecipient.id.asc()).all()

    rec_list = []
    for r in recipients:
        rec_list.append({
            'id': r.id,
            'email_address': r.email_address,
            'recipient_data': r.recipient_data,
            'rendered_subject': r.rendered_subject,
            'status': r.status,
            'attempt_count': r.attempt_count,
            'error_message': r.error_message,
            'accepted_at': r.accepted_at.isoformat() if r.accepted_at else None,
            'provider_message_id': r.provider_message_id
        })

    return jsonify({
        'success': True,
        'batch': {
            'id': batch.id,
            'batch_name': batch.batch_name,
            'subject': batch.subject,
            'sending_mode': batch.sending_mode,
            'status': batch.status,
            'total_recipients': batch.total_recipients,
            'accepted_count': batch.accepted_count,
            'failed_count': batch.failed_count,
            'created_at': batch.created_at.isoformat() if batch.created_at else None,
            'completed_at': batch.completed_at.isoformat() if batch.completed_at else None,
            'error_message': batch.error_message
        },
        'recipients': rec_list
    })


@bulk_email_bp.route('/batches/<int:batch_id>/retry-failed', methods=['POST'])
@login_required
def api_retry_failed_recipients(batch_id: int):
    """Safely resets failed recipients to PENDING and restarts the batch sending worker without re-sending to accepted recipients."""
    user_id = request.user_id
    batch = db_session.query(EmailBatch).filter_by(id=batch_id, user_id=user_id).first()
    if not batch:
        return jsonify({'success': False, 'error': 'Batch not found.'}), 404

    # Reset failed recipients only
    failed_recipients = db_session.query(EmailRecipient).filter_by(
        batch_id=batch.id,
        user_id=user_id,
        status=EmailRecipientStatus.FAILED.value
    ).all()

    if not failed_recipients:
        return jsonify({'success': False, 'message': 'No failed recipients found to retry.'})

    for r in failed_recipients:
        r.status = EmailRecipientStatus.PENDING.value
        r.error_message = None

    batch.status = EmailBatchStatus.QUEUED.value
    batch.failed_count = (batch.failed_count or len(failed_recipients)) - len(failed_recipients)
    if batch.failed_count < 0:
        batch.failed_count = 0
    db_session.commit()

    # Restart worker
    app_instance = current_app._get_current_object()
    start_batch_sending_job(app_instance, batch.id)

    return jsonify({
        'success': True,
        'message': f"Retrying {len(failed_recipients)} failed recipient(s). Already accepted recipients will not be contacted again."
    })
