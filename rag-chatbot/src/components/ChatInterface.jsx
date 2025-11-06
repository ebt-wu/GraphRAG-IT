import React, { useState } from 'react';
import axios from 'axios';
import '../styles/ChatInterface.css';

const ChatInterface = () => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [chatHistory, setChatHistory] = useState([]);

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

  const handleQueryChange = (e) => {
    setQuery(e.target.value);
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!query.trim()) {
      setError('Please enter a question');
      return;
    }

    try {
      setLoading(true);
      setError('');

      const response = await axios.post(`${API_BASE_URL}/api/chat`, {
        message: query
      });

      if (response.data.status === 'success') {
        // Add to history immediately
        setChatHistory([
          ...chatHistory,
          {
            id: Date.now(),
            query: query,
            answer: response.data.answer
          }
        ]);

        setQuery('');
      } else {
        setError(response.data.message || 'Error getting response');
      }
    } catch (err) {
      console.error('Error:', err);
      setError(
        err.response?.data?.message || 
        err.message || 
        'Failed to connect to backend'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setChatHistory([]);
    setQuery('');
    setError('');
  };

  return (
    <div className="chat-container">
      {/* Header */}
      <div className="chat-header">
        <h1>IT Infrastructure Assistant</h1>
        <p>Powered by Knowledge Graph + AI</p>
      </div>

      {/* Chat History */}
      <div className="chat-history">
        {chatHistory.length === 0 ? (
          <div className="welcome-message">
            <h2>Welcome!</h2>
            <p>Ask me anything about your infrastructure:</p>
            <ul>
              <li>Which servers are running Ubuntu 22.04?</li>
              <li>What applications are on server1?</li>
              <li>Where is server5 located?</li>
            </ul>
          </div>
        ) : (
          chatHistory.map((item) => (
            <div key={item.id} className="chat-item">
              <div className="query-bubble user-bubble">
                <strong>You:</strong> {item.query}
              </div>
              <div className="answer-bubble assistant-bubble">
                <strong>Assistant:</strong> {item.answer}
              </div>
            </div>
          ))
        )}

        {/* Error Message */}
        {error && (
          <div className="error-message">
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="loading-message">
            <div className="spinner"></div>
            <p>Thinking...</p>
          </div>
        )}
      </div>

      {/* Input Area */}
      <form className="chat-form" onSubmit={handleSubmit}>
        <div className="input-wrapper">
          <input
            type="text"
            className="chat-input"
            placeholder="Ask about your infrastructure..."
            value={query}
            onChange={handleQueryChange}
            disabled={loading}
            autoFocus
          />
          <button
            type="submit"
            className="send-btn"
            disabled={loading || !query.trim()}
          >
            {loading ? 'Sending...' : 'Send'}
          </button>
        </div>

        {chatHistory.length > 0 && (
          <button
            type="button"
            className="clear-btn"
            onClick={handleClear}
            disabled={loading}
          >
            Clear History
          </button>
        )}
      </form>
    </div>
  );
};

export default ChatInterface;
