"use client";
import { useState, useRef, useEffect } from "react";
import { Send, Paperclip, Bot, User, Loader2 } from "lucide-react";

// --- 1. Simple ID Generator ---
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

export default function Home() {
  const [messages, setMessages] = useState([
    { role: "ai", content: "Hello, I'm Vera, an AI Research Agent. How can I assist you today?" },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  
  // --- 2. Store Thread ID ---
  const [threadId, setThreadId] = useState("");

  // Generate ID only once when page loads
  useEffect(() => {
    setThreadId(generateUUID());
  }, []);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append("file", file);

    setUploadStatus("Uploading...");

    try {
      // CHANGE IP IF NEEDED
      const res = await fetch("http://192.168.20.166:8000/upload", {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        setUploadStatus("✅ Document Uploaded: " + file.name);
        setMessages((prev) => [
            ...prev,
            { role: "ai", content: `I have read ${file.name}. You can now ask me questions about it.` }
        ]);
      } else {
        setUploadStatus("❌ Upload Failed");
      }
    } catch (error) {
      console.error(error);
      setUploadStatus("⚠️ Error connecting to server");
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg = input;
    setInput("");
    
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setIsLoading(true);

    try {
      // CHANGE IP IF NEEDED
      const res = await fetch("http://192.168.20.166:8000/chat", { 
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // --- 3. SEND THE THREAD ID ---
        body: JSON.stringify({ 
            message: userMsg, 
            thread_id: threadId // <--- This is the key fix!
        }),
      });

      if (!res.ok) throw new Error("API Error");

      const data = await res.json();
      
      setMessages((prev) => [...prev, { role: "ai", content: data.response }]);
    } catch (error) {
      console.error(error);
      setMessages((prev) => [
        ...prev,
        { role: "ai", content: "⚠️ Error: Could not connect to Vera." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-[#0f172a] text-gray-100 font-sans">
      {/* Header */}
      <header className="p-4 border-b border-gray-800 flex items-center gap-3 bg-[#1e293b] shadow-md">
        <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center">
             🧬
        </div>
        <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-purple-400">
          Project Vera
        </h1>
      </header>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-gray-700">
        
        {/* Upload Status Banner */}
        {uploadStatus && (
            <div className={`p-3 rounded-lg text-sm font-medium ${uploadStatus.includes("✅") ? "bg-green-900/30 text-green-400 border border-green-800" : "bg-red-900/30 text-red-400"}`}>
                {uploadStatus}
            </div>
        )}

        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex items-start gap-3 ${
              msg.role === "user" ? "flex-row-reverse" : ""
            }`}
          >
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                msg.role === "ai" ? "bg-purple-600" : "bg-blue-600"
              }`}
            >
              {msg.role === "ai" ? <Bot size={18} /> : <User size={18} />}
            </div>
            <div
              className={`max-w-[80%] p-3 rounded-2xl text-sm leading-relaxed shadow-sm ${
                msg.role === "user"
                  ? "bg-blue-600 text-white rounded-tr-none"
                  : "bg-[#1e293b] text-gray-200 border border-gray-700 rounded-tl-none"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        
        {isLoading && (
            <div className="flex items-center gap-2 text-gray-400 text-sm ml-12">
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}/>
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}/>
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}/>
            </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-[#1e293b] border-t border-gray-800">
        <div className="max-w-4xl mx-auto flex items-center gap-3 bg-[#0f172a] p-2 rounded-xl border border-gray-700 focus-within:border-cyan-500 transition-all">
          <label className="p-2 text-gray-400 hover:text-cyan-400 cursor-pointer transition-colors">
            <Paperclip size={20} />
            <input type="file" className="hidden" accept=".pdf" onChange={handleFileUpload} />
          </label>
          
          <input
            className="flex-1 bg-transparent border-none outline-none text-white placeholder-gray-500"
            placeholder="Send a message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          />
          
          <button
            onClick={sendMessage}
            disabled={isLoading || !input.trim()}
            className="p-2 bg-blue-600 rounded-lg hover:bg-blue-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-white"
          >
            {isLoading ? <Loader2 className="animate-spin" size={20} /> : <Send size={20} />}
          </button>
        </div>
      </div>
    </div>
  );
}