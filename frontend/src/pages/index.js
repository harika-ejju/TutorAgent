import { useState, useEffect, useRef } from 'react';

export default function TutoringApp() {
  // Router and state management
  const [currentView, setCurrentView] = useState('login');
  const [user, setUser] = useState(null);
  
  // Chat state
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [ws, setWs] = useState(null);
  const [conversations, setConversations] = useState([]);
  
  // Assessment state
  const [currentAssessment, setCurrentAssessment] = useState(null);
  const [selectedAnswers, setSelectedAnswers] = useState({});
  const [assessmentResult, setAssessmentResult] = useState(null);
  const [evaluatingAssessment, setEvaluatingAssessment] = useState(false);
  const [aiThinking, setAiThinking] = useState(false);
  const [loadingAssessment, setLoadingAssessment] = useState(false);
  
  // Analytics state
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [analyticsData, setAnalyticsData] = useState(null);
  
  const messagesEndRef = useRef(null);

  // Initialize app
  useEffect(() => {
    const token = localStorage.getItem('token');
    const userData = localStorage.getItem('user');
    
    if (token && userData) {
      setUser(JSON.parse(userData));
      setCurrentView('dashboard');
      initializeWebSocket(JSON.parse(userData));
    } else {
      setCurrentView('login');
    }
  }, []);

  // WebSocket initialization
  const initializeWebSocket = (userData) => {
    if (ws) {
      console.log('WebSocket already exists, skipping initialization');
      return;
    }
    
    console.log('Initializing WebSocket for user:', userData.id);
    const websocket = new WebSocket(`ws://localhost:8000/ws/tutor/${userData.id}`);
    
    websocket.onopen = () => {
      console.log('WebSocket connected successfully');
      setWs(websocket);
      loadConversations(userData);
    };
    
    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('Received WebSocket message:', data);
      
      if (data.type === 'message') {
        console.log('Processing tutor message:', data.content);
        setAiThinking(false);
        setMessages(prev => [...prev, {
          type: 'tutor',
          content: data.content,
          timestamp: new Date().toISOString()
        }]);
      } else if (data.type === 'assessment_offer') {
        setMessages(prev => [...prev, {
          type: 'assessment_offer',
          content: data.content,
          topic: data.topic,
          timestamp: new Date().toISOString()
        }]);
      } else if (data.type === 'assessment') {
        setAiThinking(false);
        setLoadingAssessment(false);
        setCurrentAssessment(data.assessment);
        setCurrentView('assessment');
      } else if (data.type === 'assessment_result') {
        // Handle assessment results - navigate to results page
        console.log('Assessment result:', data.result);
        setEvaluatingAssessment(false);
        const result = data.result;
        
        // Format feedback properly
        let feedbackText = '';
        if (result.feedback && Array.isArray(result.feedback)) {
          feedbackText = result.feedback.map(fb => 
            `${fb.question}: ${fb.user_answer} ${fb.is_correct ? '✅' : '❌'}`
          ).join('\n');
        } else {
          feedbackText = result.overall_feedback || 'No feedback available';
        }
        
        setAssessmentResult({
          ...result,
          feedbackText,
          topic: result.topic || assessmentResult?.topic || currentAssessment?.topic
        });
        
        // Clear assessment data now that we have results
        setCurrentAssessment(null);
        setSelectedAnswers({});
        
        // Go directly to results
        setCurrentView('assessment_result');
      }
    };
    
    websocket.onclose = () => {
      console.log('WebSocket disconnected - attempting reconnection');
      setWs(null);
      // Reconnect after a short delay if user is still logged in
      if (user) {
        setTimeout(() => {
          console.log('Reconnecting WebSocket...');
          initializeWebSocket(user);
        }, 2000);
      }
    };
    
    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
      setWs(null);
    };
  };

  // Login handler
  const handleLogin = (username) => {
    const userData = { id: `user_${username}`, username };
    localStorage.setItem('token', 'dummy_token');
    localStorage.setItem('user', JSON.stringify(userData));
    setUser(userData);
    setCurrentView('dashboard');
    initializeWebSocket(userData);
  };

  // Logout handler
  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    if (ws) ws.close();
    setWs(null);
    setUser(null);
    setMessages([]);
    setCurrentView('login');
  };

  // Send message
  const sendMessage = () => {
    console.log('Send button clicked');
    console.log('Input value:', inputValue);
    console.log('WebSocket state:', ws?.readyState);
    
    if (!inputValue.trim()) {
      console.log('Cannot send message - empty input');
      return;
    }
    
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.log('WebSocket not ready - attempting to reconnect');
      if (user) {
        initializeWebSocket(user);
      }
      // Store the message to send after reconnection
      setTimeout(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          const message = { type: 'message', content: inputValue };
          console.log('Sending delayed message:', message);
          setAiThinking(true);
          ws.send(JSON.stringify(message));
          
          setMessages(prev => [...prev, {
            type: 'user',
            content: inputValue,
            timestamp: new Date().toISOString()
          }]);
          
          setInputValue('');
        }
      }, 3000);
      return;
    }
    
    const message = { type: 'message', content: inputValue };
    console.log('Sending message:', message);
    console.log('Setting AI thinking to true');
    setAiThinking(true);
    ws.send(JSON.stringify(message));
    
    setMessages(prev => [...prev, {
      type: 'user',
      content: inputValue,
      timestamp: new Date().toISOString()
    }]);
    
    setInputValue('');
  };

  // Start assessment
  const startAssessment = (topic) => {
    console.log('Starting assessment for topic:', topic);
    if (ws && ws.readyState === WebSocket.OPEN) {
      setLoadingAssessment(true);
      ws.send(JSON.stringify({ type: 'start_assessment', topic }));
    }
  };

  // Submit assessment
  const submitAssessment = () => {
    if (!currentAssessment || !ws) return;
    
    console.log('Submitting assessment:', currentAssessment.id);
    console.log('Setting evaluatingAssessment to true');
    setEvaluatingAssessment(true);
    ws.send(JSON.stringify({
      type: 'submit_assessment',
      assessment_id: currentAssessment.id,
      answers: selectedAnswers
    }));
    
    // Keep assessment and answers until evaluation is complete
  };

  // Load conversations
  const loadConversations = async (userData) => {
    try {
      const response = await fetch(`http://localhost:8000/api/conversations/${userData.id}`);
      if (response.ok) {
        const data = await response.json();
        setConversations(data.conversations || []);
      }
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const loadConversation = (conversation) => {
    setMessages(conversation.chat_history || []);
    setCurrentView('dashboard');
  };

  // Load analytics
  const loadAnalytics = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/analytics/${user.id}`);
      if (response.ok) {
        const data = await response.json();
        setAnalyticsData(data);
        setShowAnalytics(true);
      }
    } catch (error) {
      console.error('Failed to load analytics:', error);
    }
  };

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Render functions
  const renderLogin = () => (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="bg-white p-8 rounded-lg shadow-md w-96">
        <h1 className="text-2xl font-bold text-center mb-6">AI Tutor Login</h1>
        <form onSubmit={(e) => {
          e.preventDefault();
          const username = e.target.username.value.trim();
          if (username) handleLogin(username);
        }}>
          <input
            name="username"
            type="text"
            placeholder="Enter your username"
            className="w-full p-3 border border-gray-300 rounded-lg mb-4"
            required
          />
          <button
            type="submit"
            className="w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700"
          >
            Start Learning
          </button>
        </form>
      </div>
    </div>
  );

  const renderDashboard = () => (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <div className="w-64 bg-white shadow-lg flex flex-col">
        <div className="p-4 border-b">
          <h2 className="font-bold text-lg">AI Tutor</h2>
          <p className="text-sm text-gray-600">Welcome, {user?.username}</p>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4">
          <button
            onClick={() => setMessages([])}
            className="w-full mb-4 bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700"
          >
            New Conversation
          </button>
          
          <div className="space-y-2">
            {conversations.map((conv, idx) => (
              <div 
                key={idx} 
                className="p-2 bg-gray-50 rounded cursor-pointer hover:bg-gray-100"
                onClick={() => loadConversation(conv)}
              >
                <p className="text-sm font-medium truncate">{conv.title || `Conversation ${idx + 1}`}</p>
              </div>
            ))}
          </div>
        </div>
        
        <div className="p-4 border-t space-y-2">
          <button
            onClick={loadAnalytics}
            className="w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700"
          >
            View Analytics
          </button>
          <button
            onClick={handleLogout}
            className="w-full bg-black text-white py-2 px-4 rounded hover:bg-gray-800"
          >
            Logout
          </button>
        </div>
      </div>

      {/* Main Chat */}
      <div className="flex-1 flex flex-col">
        {showAnalytics ? (
          <div className="flex-1 p-6 overflow-y-auto">
            <div className="max-w-4xl mx-auto">
              <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-bold">Learning Analytics</h1>
                <button
                  onClick={() => setShowAnalytics(false)}
                  className="bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700"
                >
                  Back to Chat
                </button>
              </div>
              
              {analyticsData ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="bg-white p-6 rounded-lg shadow">
                    <h3 className="text-lg font-semibold mb-2">Total Lessons</h3>
                    <p className="text-3xl font-bold text-blue-600">{analyticsData.total_lessons || 0}</p>
                  </div>
                  <div className="bg-white p-6 rounded-lg shadow">
                    <h3 className="text-lg font-semibold mb-2">Assessments Taken</h3>
                    <p className="text-3xl font-bold text-green-600">{analyticsData.assessments_taken || 0}</p>
                  </div>
                  <div className="bg-white p-6 rounded-lg shadow">
                    <h3 className="text-lg font-semibold mb-2">Pass Rate</h3>
                    <p className="text-3xl font-bold text-purple-600">{analyticsData.pass_rate || 0}%</p>
                  </div>
                </div>
              ) : (
                <p>Loading analytics...</p>
              )}
            </div>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="flex justify-center items-center h-full">
                  <div className="text-center">
                    <div className="text-4xl mb-4">👋</div>
                    <h2 className="text-2xl font-bold text-gray-800 mb-2">Hi, I&apos;m your Tutor Agent!</h2>
                    <p className="text-lg text-gray-600">Ask me about any topic and I&apos;ll teach you in 5 simple steps</p>
                    <p className="text-sm text-gray-500 mt-2">Try: &quot;Teach me about machine learning&quot; or &quot;Explain photosynthesis&quot;</p>
                  </div>
                </div>
              ) : (
                messages.map((message, idx) => (
                <div key={idx} className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                    message.type === 'user'
                      ? 'bg-blue-600 text-white'
                      : message.type === 'assessment_offer'
                      ? 'bg-green-50 text-green-800 border border-green-200'
                      : 'bg-gray-200 text-gray-800'
                  }`}>
                    {message.type === 'assessment_offer' ? (
                      <div>
                        <p className="mb-2">{message.content}</p>
                        <button 
                          onClick={() => startAssessment(message.topic)}
                          className="px-3 py-1 bg-green-600 text-white text-sm rounded hover:bg-green-700"
                        >
                          Take Assessment
                        </button>
                      </div>
                    ) : message.type === 'assessment_result' ? (
                      <div>
                        <div className="prose prose-sm max-w-none mb-4">
                          {message.content.split('\n').map((line, i) => {
                            if (line.startsWith('**') && line.endsWith('**')) {
                              return <h4 key={i} className="font-bold text-lg mt-4 mb-2">{line.slice(2, -2)}</h4>;
                            }
                            return <p key={i} className="mb-2">{line}</p>;
                          })}
                        </div>
                        <div className="flex gap-2">
                          {message.passed ? (
                            <button 
                              onClick={() => setCurrentView('dashboard')}
                              className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                            >
                              Continue Learning
                            </button>
                          ) : (
                            <>
                              <button 
                                onClick={() => startAssessment(message.topic)}
                                className="px-3 py-1 bg-orange-600 text-white text-sm rounded hover:bg-orange-700"
                              >
                                Retake Assessment
                              </button>
                              <button 
                                onClick={() => {
                                  if (ws && ws.readyState === WebSocket.OPEN) {
                                    ws.send(JSON.stringify({ type: 'message', content: `Review lesson about ${message.topic}` }));
                                  }
                                }}
                                className="px-3 py-1 bg-purple-600 text-white text-sm rounded hover:bg-purple-700"
                              >
                                Review Lesson
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="prose prose-sm max-w-none">
                        {message.content.split('\n').map((line, i) => {
                          if (line.startsWith('**') && line.endsWith('**')) {
                            return <h4 key={i} className="font-bold text-lg mt-4 mb-2">{line.slice(2, -2)}</h4>;
                          }
                          return <p key={i} className="mb-2">{line}</p>;
                        })}
                      </div>
                    )}
                  </div>
                </div>
              )))}
              
              {aiThinking && (
                <div className="flex justify-start mb-4">
                  <div className="bg-blue-100 p-3 rounded-lg">
                    <div className="flex space-x-1">
                      <div className="w-3 h-3 bg-blue-600 rounded-full animate-bounce" style={{animationDelay: '0ms'}}></div>
                      <div className="w-3 h-3 bg-blue-600 rounded-full animate-bounce" style={{animationDelay: '200ms'}}></div>
                      <div className="w-3 h-3 bg-blue-600 rounded-full animate-bounce" style={{animationDelay: '400ms'}}></div>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>
            
            <div className="p-4 border-t bg-white">
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                  placeholder="Ask me anything..."
                  className="flex-1 p-3 border border-gray-300 rounded-lg"
                />
                <button
                  onClick={sendMessage}
                  className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Send
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );

  const renderAssessment = () => (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-2xl mx-auto bg-white rounded-lg shadow-lg p-6">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Assessment: {currentAssessment?.topic}</h1>
          <button
            onClick={() => setCurrentView('dashboard')}
            className="bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700"
          >
            Back to Chat
          </button>
        </div>
        
        {currentAssessment?.questions.map((question, idx) => (
          <div key={question.id} className="mb-6 p-4 border border-gray-200 rounded-lg">
            <h3 className="font-semibold mb-3">{idx + 1}. {question.question}</h3>
            <div className="space-y-2">
              {question.options.map((option, optIdx) => (
                <label key={optIdx} className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="radio"
                    name={question.id}
                    value={option}
                    checked={selectedAnswers[question.id] === option}
                    onChange={(e) => setSelectedAnswers(prev => ({
                      ...prev,
                      [question.id]: e.target.value
                    }))}
                    className="text-blue-600"
                  />
                  <span>{option}</span>
                </label>
              ))}
            </div>
          </div>
        ))}
        
        <button
          onClick={() => {
            console.log('Submit button clicked');
            console.log('Selected answers:', selectedAnswers);
            console.log('Current assessment questions:', currentAssessment?.questions?.length);
            submitAssessment();
          }}
          disabled={Object.keys(selectedAnswers).length === 0}
          className="w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
        >
          Submit Assessment ({Object.keys(selectedAnswers).length}/{currentAssessment?.questions?.length || 0} answered)
        </button>
      </div>
    </div>
  );

  const renderLoadingAssessment = () => (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="bg-white rounded-lg shadow-lg p-8 text-center">
        <div className="mb-6">
          <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <h2 className="text-2xl font-bold text-gray-800 mb-2">Preparing Assessment</h2>
          <p className="text-lg text-gray-600">Creating personalized questions for you</p>
        </div>
        <div className="text-sm text-gray-500">
          This will take just a moment
        </div>
      </div>
    </div>
  );

  const renderAssessmentResult = () => (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-2xl mx-auto bg-white rounded-lg shadow-lg p-6">
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold mb-4">Assessment Results</h1>
          <div className="text-6xl font-bold text-blue-600 mb-4">
            {assessmentResult?.score}%
          </div>
        </div>
        
        <div className="mb-6">
          <h3 className="text-xl font-semibold mb-4">Detailed Feedback:</h3>
          <div className="space-y-3">
            {assessmentResult?.feedback && assessmentResult.feedback.map((fb, index) => (
              <div key={index} className={`p-3 rounded-lg border ${fb.is_correct ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                <div className="font-medium mb-1">{fb.question}</div>
                <div className={`text-sm ${fb.is_correct ? 'text-green-700' : 'text-red-700'}`}>
                  Your answer: {fb.user_answer} {fb.is_correct ? '✅' : '❌'}
                </div>
                {!fb.is_correct && (
                  <div className="text-sm text-gray-600 mt-1">
                    Correct answer: {fb.correct_answer}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
        
        <div className="text-center">
          {(assessmentResult?.score === 100) ? (
            <div>
              <p className="text-lg text-green-700 mb-4">🎉 Perfect! You have mastered this topic completely!</p>
              <div className="space-x-4">
                <button 
                  onClick={() => {
                    setCurrentView('dashboard');
                    setAssessmentResult(null);
                  }}
                  className="px-6 py-3 bg-blue-600 text-white text-lg rounded-lg hover:bg-blue-700"
                >
                  Continue Learning
                </button>
              </div>
            </div>
          ) : (
            <div>
              <p className="text-lg text-orange-700 mb-4">📖 Keep learning to improve your understanding!</p>
              <div className="space-x-4">
                <button 
                  onClick={() => {
                    setCurrentView('dashboard');
                    setAssessmentResult(null);
                  }}
                  className="px-6 py-3 bg-blue-600 text-white text-lg rounded-lg hover:bg-blue-700"
                >
                  Continue Learning
                </button>
                <button 
                  onClick={() => {
                    setCurrentView('dashboard');
                    setAssessmentResult(null);
                    // Send message to get lesson content again
                    if (ws && ws.readyState === WebSocket.OPEN && assessmentResult?.topic) {
                      ws.send(JSON.stringify({ 
                        type: 'message', 
                        content: `Explain ${assessmentResult.topic}` 
                      }));
                    }
                  }}
                  className="px-6 py-3 bg-orange-600 text-white text-lg rounded-lg hover:bg-orange-700"
                >
                  Take Lesson Again
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  // Main render
  if (currentView === 'login') return renderLogin();
  
  // Show loading page when generating assessment
  if (loadingAssessment) {
    return renderLoadingAssessment();
  }
  
  if (currentView === 'assessment') return renderAssessment();
  if (currentView === 'assessment_result') return renderAssessmentResult();
  return renderDashboard();
}