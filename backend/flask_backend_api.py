# app.py
import threading

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import logging
from datetime import datetime,timedelta,timezone
import time
# Import our AI agent
from ai_agent import AIAgent, db
from google.cloud.firestore_v1._helpers import DatetimeWithNanoseconds

# Initialize Flask app
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AI agent
ai_agent = AIAgent()

@socketio.on('connect')
def handle_connect():
    logger.info("Client connected")

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected")

# Start timeout checker background task
def check_request_timeouts():
    """Background task to check for timed out help requests"""
    while True:
        try:
            # Get pending requests that are older than the timeout threshold (e.g., 4 hours)
            timeout_threshold = datetime.now() - timedelta(hours=4)
            timeout_threshold = timeout_threshold.replace(tzinfo=timezone.utc)

            # Fetch only 'pending' requests
            pending_requests = db.collection('help_requests') \
                .where('status', '==', 'pending') \
                .stream()

            # Filter by timestamp in Python
            filtered_requests = [req for req in pending_requests if req.to_dict().get('timestamp') is not None and req.to_dict()['timestamp'] < timeout_threshold]

            for request_doc in filtered_requests:
                request_id = request_doc.id
                # Mark as unresolved
                db.collection('help_requests').document(request_id).update({
                    'status': 'unresolved',
                    'responseText': 'Request timed out without supervisor response',
                    'respondedAt': datetime.now()
                })
                logger.info(f"Request {request_id} marked as unresolved due to timeout")

        except Exception as e:
            logger.error(f"Error checking timeouts: {e}")

        # Sleep for 15 minutes before checking again
        time.sleep(15 * 60)

# Start timeout checker in a separate thread
timeout_thread = threading.Thread(target=check_request_timeouts, daemon=True)
timeout_thread.start()

@socketio.on('simulate_call')
def simulate_call():
    """Endpoint to simulate a customer call"""
    data = request.json

    if not data or 'phone' not in data or 'question' not in data:
        return jsonify({'error': 'Missing required fields'}), 400

    customer_phone = data['phone']
    customer_question = data['question']

    # Process the call with our AI agent
    result = ai_agent.process_call(customer_phone, customer_question)

    emit('call_response', result)

@socketio.on('get_help_requests')
def get_help_requests(data):
    """Get all help requests with optional filtering"""
    status = data.get('status',None) if data else None

    query = db.collection('help_requests')

    if status:
        query = query.where('status', '==', status)

    # Fetch documents (without order_by)
    docs = query.stream()

    # Sort manually by timestamp descending
    def get_timestamp(doc):
        timestamp = doc.to_dict().get('timestamp')
        if timestamp is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        # Ensure timestamp has timezone info
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp

    sorted_docs = sorted(
        docs,
        key=get_timestamp,
        reverse=True
    )

    def serialize_firestore_data(data):
        for key, value in data.items():
            if isinstance(value, DatetimeWithNanoseconds):
                data[key] = value.strftime('%Y-%m-%d %H:%M:%S')
        return data

    # Convert to list of dictionaries
    requests = []
    for doc in sorted_docs:
        request_data = doc.to_dict()
        request_data = serialize_firestore_data(request_data)
        request_data['id'] = doc.id
        requests.append(request_data)
    logger.info(f"Found {len(requests)} help requests")

    emit('help_requests', requests)

@socketio.on('get_help_request')
def get_help_request(data):
    """Get a specific help request by ID"""
    if not data or 'request_id' not in data:
        emit('error', {'message': 'Missing request ID'})
        return

    request_id = data['request_id']
    doc = db.collection('help_requests').document(request_id).get()

    if not doc.exists:
        return jsonify({'error': 'Request not found'}), 404

    request_data = doc.to_dict()
    # Convert timestamps to strings for JSON serialization
    if 'timestamp' in request_data:
        request_data['timestamp'] = str(request_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S'))
    if 'respondedAt' in request_data and request_data['respondedAt']:
        request_data['respondedAt'] = str(request_data['respondedAt'].strftime('%Y-%m-%d %H:%M:%S'))
    if 'followupTimestamp' in request_data and request_data['followupTimestamp']:
        request_data['followupTimestamp'] = str(request_data['followupTimestamp'].strftime('%Y-%m-%d %H:%M:%S'))

    request_data['id'] = doc.id

    emit('help_request', request_data)

@socketio.on('respond_to_request')
def respond_to_request(data):
    """Endpoint for supervisor to respond to a help request"""
    if not data or 'request_id' not in data or 'response' not in data:
        emit('error', {'message': 'Missing required fields'})
        return

    response_text = data['response']
    request_id = data['request_id']

    # Get the request document
    request_ref = db.collection('help_requests').document(request_id)
    request_doc = request_ref.get()

    if not request_doc.exists:
        emit('error', {'message': 'Request not found'})

    request_data = request_doc.to_dict()

    if request_data['status'] != 'pending':
        emit('error', {'message': 'Request already processed'})
        return

    # Update the request with supervisor's response
    request_ref.update({
        'status': 'resolved',
        'responseText': response_text,
        'respondedAt': datetime.now()
    })

    # Follow up with customer
    ai_agent.follow_up_with_customer(request_id, response_text)

    emit('response_success', {
        'success': True,
        'message': 'Response sent and customer notified'
    })

@socketio.on('get_knowledge_base')
def get_knowledge_base():
    """Get all knowledge base entries"""
    logger.info("Entered get_knowledge_base")
    try:
        # Query knowledge base
        docs = db.collection('knowledge_base').order_by('createdAt', direction='DESCENDING').stream()

        # Convert to list of dictionaries
        kb_items = []
        for doc in docs:
            kb_data = doc.to_dict()
            # Convert timestamps to strings for JSON serialization
            if 'createdAt' in kb_data:
                kb_data['createdAt'] = kb_data['createdAt'].strftime('%Y-%m-%d %H:%M:%S')
            if 'lastUsedAt' in kb_data:
                kb_data['lastUsedAt'] = kb_data['lastUsedAt'].strftime('%Y-%m-%d %H:%M:%S')

            kb_data['id'] = doc.id
            logger.info('Knowledge Base Doc ID: {}'.format(kb_data['id']))
            kb_items.append(kb_data)

        logger.info(f"Found {len(kb_items)} knowledge base entries")
        emit('knowledge_base', kb_items)
    except Exception as e:
        logger.error(e)
        emit('error', {'message': f'Error fetching knowledge base: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)