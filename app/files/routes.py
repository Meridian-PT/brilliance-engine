from flask import Blueprint, send_file, abort
from flask_login import login_required
from io import BytesIO
from app.models import FileAttachment

files_bp = Blueprint('files', __name__)


@files_bp.route('/files/<int:file_id>/download')
@login_required
def download(file_id):
    attachment = FileAttachment.query.get_or_404(file_id)
    return send_file(
        BytesIO(attachment.file_data),
        download_name=attachment.original_filename,
        mimetype=attachment.mime_type or 'application/octet-stream',
        as_attachment=True,
    )


@files_bp.route('/files/<int:file_id>/view')
@login_required
def view(file_id):
    attachment = FileAttachment.query.get_or_404(file_id)
    viewable = ['application/pdf', 'image/png', 'image/jpeg', 'image/gif', 'text/plain']
    if attachment.mime_type not in viewable:
        return download(file_id)
    return send_file(
        BytesIO(attachment.file_data),
        download_name=attachment.original_filename,
        mimetype=attachment.mime_type,
        as_attachment=False,
    )
