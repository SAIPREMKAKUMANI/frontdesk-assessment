import React,{ useState, useEffect } from 'react';
import './App.css';

const API_BASE_URL = 'http://localhost:5000/api';

function App() {
  const [activeTab, setActiveTab] = useState('pending');
  const [requests, setRequests] = useState([]);
  const [knowledge, setKnowledge] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [responseText, setResponseText] = useState('');
  const [selectedRequest, setSelectedRequest] = useState(null);

  // Fetch requests based on active tab
  useEffect(() => {
    fetchRequests();
    console.log(`Fetching requests for tab: ${activeTab}`);

    // Reload data every 30 seconds
    const interval = setInterval(fetchRequests, 30000);

    return () => clearInterval(interval);
  }, [activeTab]);

  // Fetch knowledge base
  useEffect(() => {
    if (activeTab === 'knowledge') {
      fetchKnowledgeBase();
    }
  }, [activeTab]);

  const fetchRequests = async () => {
    try {
      setLoading(true);
      let url = `${API_BASE_URL}/help-requests`;

      // Add filter if not viewing all requests
      if (activeTab !== 'all') {
        url += `?status=${activeTab}`;
      }

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error('Failed to fetch requests');
      }

      const data = await response.json();
      setRequests(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchKnowledgeBase = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/knowledge-base`);

      if (!response.ok) {
        throw new Error('Failed to fetch knowledge base');
      }

      const data = await response.json();
      setKnowledge(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitResponse = async (requestId) => {
    if (!responseText.trim()) {
      alert('Please enter a response');
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/help-requests/${requestId}/respond`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({response: responseText}),
      });

      if (!response.ok) {
        throw new Error('Failed to submit response');
      }

      // Reset response text and selected request
      setResponseText('');
      setSelectedRequest(null);

      // Refresh the requests list
      fetchRequests();

      alert('Response submitted successfully! The customer will be notified.');
    } catch (err) {
      setError(err.message);
      alert(`Error: ${err.message}`);
    }
  };

  const handleSelectRequest = (request) => {
    setSelectedRequest(request);
    // Pre-fill response box with a template
    setResponseText(`Hello, regarding your question "${request.question}", `);
  };

  // Render tabs
  const renderTabs = () => (
      <div className="tabs">
        <button
            className={activeTab === 'pending' ? 'active' : ''}
            onClick={() => setActiveTab('pending')}
        >
          Pending Requests
        </button>
        <button
            className={activeTab === 'resolved' ? 'active' : ''}
            onClick={() => setActiveTab('resolved')}
        >
          Resolved Requests
        </button>
        <button
            className={activeTab === 'unresolved' ? 'active' : ''}
            onClick={() => setActiveTab('unresolved')}
        >
          Unresolved Requests
        </button>
        <button
            className={activeTab === 'all' ? 'active' : ''}
            onClick={() => setActiveTab('all')}
        >
          All Requests
        </button>
        <button
            className={activeTab === 'knowledge' ? 'active' : ''}
            onClick={() => setActiveTab('knowledge')}
        >
          Knowledge Base
        </button>
      </div>
  );

  // Render requests list
  const renderRequests = () => {
    if (loading) return <p className="loading">Loading...</p>;
    if (error) return <p className="error">Error: {error}</p>;
    if (requests.length === 0) return <p>No requests found.</p>;

    return (
        <div className="requests-list">
          {requests.map((request) => (
              <div
                  key={request.id}
                  className={`request-card ${request.status} ${selectedRequest?.id === request.id ? 'selected' : ''}`}
                  onClick={() => handleSelectRequest(request)}
              >
                <div className="request-header">
                  <span className="status-badge">{request.status}</span>
                  <span className="timestamp">{request.timestamp}</span>
                </div>
                <div className="phone">{request.customerPhone}</div>
                <div className="question">{request.question}</div>

                {request.responseText && (
                    <div className="response">
                      <strong>Response:</strong> {request.responseText}
                      <div className="response-time">
                        <em>Responded at {request.respondedAt}</em>
                      </div>
                    </div>
                )}

                {request.status === 'pending' && (
                    <button
                        className="respond-button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelectRequest(request);
                        }}
                    >
                      Respond
                    </button>
                )}
              </div>
          ))}
        </div>
    );
  };

  // Render knowledge base
  const renderKnowledgeBase = () => {
    if (loading) return <p className="loading">Loading...</p>;
    if (error) return <p className="error">Error: {error}</p>;
    if (knowledge.length === 0) return <p>No knowledge base entries found.</p>;

    return (
        <div className="knowledge-list">
          <h2>Learned Answers</h2>
        </div>
    )
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Customer Support Dashboard</h1>
        {renderTabs()}
      </header>

      <main className="app-main">
        <div className="content-area">
          {activeTab === 'knowledge' ? renderKnowledgeBase() : renderRequests()}
        </div>

        {/* Response Form */}
        {selectedRequest && selectedRequest.status === 'pending' && (
          <div className="response-form">
            <h3>Respond to Request</h3>
            <textarea
              value={responseText}
              onChange={(e) => setResponseText(e.target.value)}
              placeholder="Enter your response..."
              rows={4}
            />
            <div className="button-group">
              <button
                className="submit-button"
                onClick={() => handleSubmitResponse(selectedRequest.id)}
              >
                Submit Response
              </button>
              <button
                className="cancel-button"
                onClick={() => {
                  setSelectedRequest(null);
                  setResponseText('');
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;