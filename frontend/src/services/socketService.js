// frontend/src/services/socketService.js
import { io } from 'socket.io-client';

class SocketService {
    constructor() {
        this.socket = io('http://localhost:5000');
        this.setupListeners();
    }

    setupListeners() {
        this.socket.on('connect', () => {
            console.log('Connected to WebSocket server');
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from WebSocket server');
        });
    }

    simulateCall(phone, question) {
        return new Promise((resolve) => {
            this.socket.emit('simulate_call', { phone, question });
            this.socket.once('call_response', (response) => {
                resolve(response);
            });
        });
    }

    getHelpRequests(status = null) {
        return new Promise((resolve) => {
            this.socket.emit('get_help_requests', { status });
            this.socket.once('help_requests', (requests) => {
                resolve(requests);
            });
        });
    }

    getHelpRequest(requestId) {
        return new Promise((resolve) => {
            this.socket.emit('get_help_request', { request_id: requestId });
            this.socket.once('help_request', (request) => {
                resolve(request);
            });
        });
    }

    respondToRequest(requestId, response) {
        return new Promise((resolve) => {
            this.socket.emit('respond_to_request', {
                request_id: requestId,
                response: response
            });
            this.socket.once('response_success', (result) => {
                resolve(result);
            });
        });
    }

    getKnowledgeBase() {
        console.log('Fetching knowledge base...');
        return new Promise((resolve) => {
            this.socket.emit('get_knowledge_base');
            this.socket.once('knowledge_base', (items) => {
                resolve(items);
            });
        });
    }

    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
    }
}

export const socketService = new SocketService();