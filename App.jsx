import React, { useState, useRef, useEffect } from 'react';
import './App.css';

const API_BASE = 'https://learn-english-wa5d.onrender.com'; // 確保呼叫正確的 Flask 端口

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

  // === 模式二：Socratic (蘇格拉底對話) ===
  const [chatHistory, setChatHistory] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const chatEndRef = useRef(null);

  // === 模式三：Mastery (精熟測驗) ===
  const [masteryInput, setMasteryInput] = useState('');

  // 初始化載入題目
  useEffect(() => {
    const fetchQuestions = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/questions`);
        const data = await response.json();
        if (data.status === 'success' && data.data.length > 0) {
          // 隨機挑選一題
          const randomIndex = Math.floor(Math.random() * data.data.length);
          const q = data.data[randomIndex];
          setCurrentQuestion(q);
          const qText = q.Chinese || q.chinese || q.Question || q.question;
          
          // 使用 AI 幫這題產出 Chaining 的提示
          fetch(`${API_BASE}/api/generate_hint`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: qText })
          }).then(res => res.json()).then(hintData => {
             if (hintData.status === 'success') setAiChainingHint(hintData.hint);
             setHintLoading(false);
          });

          // 初始化聊天室
          setChatHistory([{ 
            role: 'model', 
            content: `哈囉！我是你的專屬翻譯家教。我們來練習這句翻譯：「${qText}」您可以試試看先翻一部分喔？` 
          }]);
        } else {
          throw new Error('No data');
        }
      } catch (error) {
        console.warn("無法從資料庫獲取題目，改用預設題目", error);
        // 預設後備題目
        const fallbackQ = {
          Chinese: "我們最好現在就出發，以免遇到塞車。",
        };
        setCurrentQuestion(fallbackQ);
        setAiChainingHint("您可以試著先把「我們最好現在就出發」翻出來，然後我們再來解決「以免遇到塞車」。");
        setHintLoading(false);
        setChatHistory([{ 
          role: 'model', 
          content: `哈囉！我是你的專屬翻譯家教。我們來練習這句翻譯：「${fallbackQ.Chinese}」你可以先試著翻出來嗎？` 
        }]);
      } finally {
        setQuestionLoading(false);
      }
    };
    fetchQuestions();
  }, []);

  // 自動捲動到最新訊息
  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (activeTab === 'Socratic') {
      scrollToBottom();
    }
  }, [chatHistory, activeTab]);

  // 共用日誌寫入函數 (/api/log)
  const handleLog = async (sheetName, rowData) => {
    try {
      const response = await fetch(`${API_BASE}/api/log`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer 12345'
        },
        body: JSON.stringify({
          sheet_name: sheetName,
          row_data: rowData
        })
      });
      const data = await response.json();
      if (data.status === 'success') {
        console.log(`[${sheetName}] 紀錄已備份至雲端。`);
      } else {
        alert(`Google Sheets 記錄失敗: ${data.message} \n請確認工作表 "${sheetName}" 是否已建立！`);
      }
    } catch (error) {
      console.error('日誌寫入時連線異常:', error);
    }
  };

  const submitChaining = () => {
    if (!chainingInput.trim()) return;
    const timestamp = new Date().toLocaleString('zh-TW');
    const qText = currentQuestion.Chinese || currentQuestion.chinese || currentQuestion.Question;
    handleLog('Chaining', [timestamp, qText, chainingInput]);
    alert("已送出逐步翻譯答案！");
    setChainingInput('');
  };

  const submitMastery = () => {
    if (!masteryInput.trim()) return;
    const timestamp = new Date().toLocaleString('zh-TW');
    const qText = currentQuestion.Chinese || currentQuestion.chinese || currentQuestion.Question;
    handleLog('Mastery', [timestamp, qText, masteryInput]);
    alert("已送出精熟測驗翻譯解答！測驗完成。");
    setMasteryInput('');
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
      // 呼叫 Gemini AI
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

      {/* 根據不同模式渲染不同區塊 */}
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
              placeholder="請輸入您的答案..."
              value={chainingInput}
              onChange={(e) => setChainingInput(e.target.value)}
            />
            <button className="action-btn" onClick={submitChaining}>送出答案並記錄</button>
          </div>
        </div>
      )}

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
            />
            <button className="action-btn" onClick={submitMastery}>提交精熟測驗並記錄</button>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;