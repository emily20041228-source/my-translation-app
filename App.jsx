import React, { useState, useRef, useEffect } from 'react';
import './App.css';

const API_BASE = 'http://10.220.79.190:5000'; // 自動換成本機區域網路 IP

const App = () => {
  const [activeTab, setActiveTab] = useState('Chaining');
  const [loading, setLoading] = useState(false);
  const [questionLoading, setQuestionLoading] = useState(true);

  // 當前題目與 AI 提示狀態
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [aiChainingHint, setAiChainingHint] = useState('');
  const [hintLoading, setHintLoading] = useState(true);

  // === 模式一：Chaining (逐步引導) ===
  const [chainingInput, setChainingInput] = useState('');
  const [chainingFeedback, setChainingFeedback] = useState(null);
  const [isChainingEvalLoading, setIsChainingEvalLoading] = useState(false);

  // === 模式二：Socratic (蘇格拉底對話) ===
  const [chatHistory, setChatHistory] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const chatEndRef = useRef(null);

  // === 模式三：Mastery (精熟測驗) ===
  const [masteryInput, setMasteryInput] = useState('');
  const [masteryScoreCard, setMasteryScoreCard] = useState(null);
  const [isMasteryEvalLoading, setIsMasteryEvalLoading] = useState(false);

  // 初始化載入題目
  useEffect(() => {
    const fetchQuestions = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/questions`);
        const data = await response.json();
        if (data.status === 'success' && data.data.length > 0) {
          const randomIndex = Math.floor(Math.random() * data.data.length);
          const q = data.data[randomIndex];
          setCurrentQuestion(q);
          const qText = q.Chinese || q.chinese || q.Question || q.question;
          
          fetch(`${API_BASE}/api/generate_hint`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: qText })
          }).then(res => res.json()).then(hintData => {
             if (hintData.status === 'success') setAiChainingHint(hintData.hint);
             setHintLoading(false);
          });

          setChatHistory([{ 
            role: 'model', 
            content: `哈囉！我是你的專屬翻譯家教。我們來練習這句翻譯：「${qText}」您可以試試看先找主詞動詞嗎？` 
          }]);
        } else {
          throw new Error('No data');
        }
      } catch (error) {
        console.warn("無法從資料庫獲取題目，改用預設題目", error);
        const fallbackQ = {
          Chinese: "我們最好現在就出發，以免遇到塞車。",
        };
        setCurrentQuestion(fallbackQ);
        setAiChainingHint("您可以試著先把「我們最好現在就出發」翻出來，然後我們再來解決「以免遇到塞車」。");
        setHintLoading(false);
        setChatHistory([{ 
          role: 'model', 
          content: `哈囉！我是你的專屬翻譯家教。我們來練習這句翻譯：「${fallbackQ.Chinese}」你可以先試著找出主詞和動詞嗎？` 
        }]);
      } finally {
        setQuestionLoading(false);
      }
    };
    fetchQuestions();
  }, []);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (activeTab === 'Socratic') {
      scrollToBottom();
    }
  }, [chatHistory, activeTab]);

  const handleLog = async (sheetName, rowData) => {
    try {
      await fetch(`${API_BASE}/api/log`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer 12345' },
        body: JSON.stringify({ sheet_name: sheetName, row_data: rowData })
      });
    } catch (error) {
      console.error('日誌寫入時連線異常:', error);
    }
  };

  const submitChaining = async () => {
    if (!chainingInput.trim() || isChainingEvalLoading) return;
    setIsChainingEvalLoading(true);
    const timestamp = new Date().toLocaleString('zh-TW');
    const qText = currentQuestion.Chinese || currentQuestion.chinese || currentQuestion.Question;
    
    // 寫入日誌
    handleLog('Chaining', [timestamp, qText, chainingInput]);

    try {
      const response = await fetch(`${API_BASE}/api/eval_chaining`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: qText, input: chainingInput })
      });
      const data = await response.json();
      if (data.status === 'success') {
        setChainingFeedback(data.feedback);
      } else {
        alert('AI 回饋發生錯誤: ' + data.message);
      }
    } catch (error) {
      alert('無法連線到 AI 伺服器');
    } finally {
      setIsChainingEvalLoading(false);
    }
  };

  const submitMastery = async () => {
    if (!masteryInput.trim() || isMasteryEvalLoading || masteryScoreCard) return;
    setIsMasteryEvalLoading(true);
    const timestamp = new Date().toLocaleString('zh-TW');
    const qText = currentQuestion.Chinese || currentQuestion.chinese || currentQuestion.Question;
    
    // 寫入日誌
    handleLog('Mastery', [timestamp, qText, masteryInput]);

    try {
      const response = await fetch(`${API_BASE}/api/eval_mastery`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: qText, input: masteryInput })
      });
      const data = await response.json();
      if (data.status === 'success') {
        setMasteryScoreCard(data.data);
      } else {
        alert('AI 評分發生錯誤: ' + data.message);
      }
    } catch (error) {
      alert('無法連線到 AI 伺服器');
    } finally {
      setIsMasteryEvalLoading(false);
    }
  };

  const submitChat = async () => {
    if (!chatInput.trim() || loading) return;
    const userMessage = { role: 'user', content: chatInput };
    const newHistory = [...chatHistory, userMessage];
    setChatHistory(newHistory);
    setChatInput('');
    setLoading(true);

    const timestamp = new Date().toLocaleString('zh-TW');
    handleLog('Socratic', [timestamp, 'Student', userMessage.content]);

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ history: newHistory })
      });
      const data = await response.json();
      
      if (data.status === 'success') {
        const aiMessage = { role: 'model', content: data.reply };
        setChatHistory(prev => [...prev, aiMessage]);
        
        const aiTimestamp = new Date().toLocaleString('zh-TW');
        handleLog('Socratic', [aiTimestamp, 'AI Tutor', aiMessage.content]);
      } else {
        alert('AI 回覆發生錯誤: ' + data.message);
      }
    } catch (error) {
      alert('無法連線到 AI 對話伺服器，請確保 app.py 已啟動');
    } finally {
      setLoading(false);
    }
  };

  if (questionLoading) {
    return <div className="app-container"><h2 style={{textAlign: "center"}}>正在從題庫載入題目...</h2></div>;
  }

  const currentChinese = currentQuestion.Chinese || currentQuestion.chinese || currentQuestion.Question || "（無中文題目）";

  return (
    <div className="app-container">
      <header className="header">
        <h1 className="title">學測英文翻譯 AI 訓練系統</h1>
        <div className="tabs">
          {['Chaining', 'Socratic', 'Mastery'].map(tab => (
            <button 
              key={tab}
              className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab === 'Chaining' ? '逐步引導(Chaining)' : 
               tab === 'Socratic' ? '蘇格拉底對談(Socratic)' : '綜合測驗(Mastery)'}
            </button>
          ))}
        </div>
      </header>

      {/* Chaining 模式 */}
      {activeTab === 'Chaining' && (
        <div className="content-area">
          <div className="instruction-box">
            <strong>翻譯題目：</strong> {currentChinese}<br/><br/>
            <strong>AI 老師提示：</strong> {hintLoading ? <span className="loading-indicator" style={{marginLeft: 0}}>AI 正在思考這題的最佳提示...</span> : aiChainingHint}
          </div>
          
          <div className="input-area">
            <textarea 
              className="custom-input" 
              rows="4" 
              placeholder="請試著拼湊或打出部分翻譯..."
              value={chainingInput}
              onChange={(e) => setChainingInput(e.target.value)}
            />
            <button className="action-btn" onClick={submitChaining} disabled={isChainingEvalLoading}>
              {isChainingEvalLoading ? 'AI 正在檢查...' : '送出檢查錯誤'}
            </button>
          </div>

          {chainingFeedback && (
            <div className="ai-feedback-box">
              <strong>✨ 助教回饋：</strong> {chainingFeedback}
            </div>
          )}
        </div>
      )}

      {/* Socratic 模式 */}
      {activeTab === 'Socratic' && (
        <div className="content-area">
          <div className="chat-window">
            {chatHistory.map((msg, index) => (
              <div key={index} className={`chat-bubble ${msg.role}`}>
                {msg.content}
              </div>
            ))}
            {loading && <div className="loading-indicator">AI 老師正在思考中...</div>}
            <div ref={chatEndRef} />
          </div>
          <div className="chat-input-wrapper">
            <input 
              type="text" 
              className="custom-input" 
              placeholder="跟老師說點什麼..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submitChat()}
              disabled={loading}
            />
            <button className="action-btn" onClick={submitChat} disabled={loading}>
              送出
            </button>
          </div>
        </div>
      )}

      {/* Mastery 模式 */}
      {activeTab === 'Mastery' && (
        <div className="content-area">
          <div className="instruction-box">
            <strong>最終挑戰：</strong><br/>
            請不靠任何提示，獨立翻譯出完整的句子：<br/>
            「{currentChinese}」
          </div>
          <div className="input-area">
            <textarea 
              className="custom-input" 
              rows="5" 
              placeholder="請寫下您最終完成的翻譯句子..."
              value={masteryInput}
              onChange={(e) => setMasteryInput(e.target.value)}
              disabled={masteryScoreCard !== null} // 評分後鎖定
            />
            {!masteryScoreCard && (
              <button className="action-btn" onClick={submitMastery} disabled={isMasteryEvalLoading}>
                 {isMasteryEvalLoading ? '大考中心閱卷中...' : '提交終極測驗'}
              </button>
            )}
          </div>

          {masteryScoreCard && (
            <div className="score-card">
              <div className="score-header">
                <h3 className="score-title">🏆 學測級分評鑑</h3>
                <span className="score-points">{masteryScoreCard.score} / 5 分</span>
              </div>
              
              <div className="score-section">
                <h4>⚠️ 需改進或錯誤之處：</h4>
                {masteryScoreCard.mistakes.length > 0 ? (
                  <ul className="mistake-list">
                    {masteryScoreCard.mistakes.map((m, i) => <li key={i}>{m}</li>)}
                  </ul>
                ) : <span style={{color: '#94a3b8', paddingLeft: 20}}>完美！沒有任何被扣分的錯誤。</span>}
              </div>

              <div className="score-section">
                <h4>✨ 寫得好的地方：</h4>
                {masteryScoreCard.good_points.length > 0 ? (
                  <ul className="good-list">
                    {masteryScoreCard.good_points.map((g, i) => <li key={i}>{g}</li>)}
                  </ul>
                ) : <span style={{color: '#94a3b8', paddingLeft: 20}}>尚可，可以再用更精準的詞彙。</span>}
              </div>

              <div className="score-section" style={{marginTop: 20}}>
                <h4>📝 大考中心參考解答：</h4>
                <p className="standard-answer">{masteryScoreCard.standard_answer}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default App;