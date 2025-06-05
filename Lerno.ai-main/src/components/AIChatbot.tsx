import React, { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { GoogleGenerativeAI } from "@google/generative-ai";

const AIChatbot = ({ lessonTitle, lessonContent, currentQuestion }) => {
  const [messages, setMessages] = useState([
    {
      type: "bot",
      text: "Hi there! I'm your AI tutor. Ask me anything about this lesson!",
    },
  ]);
  const [inputText, setInputText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);
  const API_KEY = "AIzaSyDozMc25FJinbbERfCv35CkMLBZ8bKWgZo";

  const genAI = new GoogleGenerativeAI(API_KEY);
  const model = genAI.getGenerativeModel({ model: "gemini-2.0-flash" });

  const [chatHistory, setChatHistory] = useState([]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputText.trim()) return;

    const userMessage = { type: "user", text: inputText };
    setMessages((prev) => [...prev, userMessage]);

    const updatedHistory = [
      ...chatHistory,
      { role: "user", parts: [{ text: inputText }] },
    ];
    setChatHistory(updatedHistory);

    setInputText("");
    setIsTyping(true);

    try {
      const chat = model.startChat({
        history: updatedHistory,
        generationConfig: {
          temperature: 0.7,
          topK: 40,
          topP: 0.95,
          maxOutputTokens: 100,
        },
      });

      // Send message with context about the current lesson
      const result = await chat.sendMessage(`
        I'm learning about "${lessonTitle}". 
        The lesson content is: "${lessonContent}".
        The current quiz question is: "${currentQuestion}".
        
        My question is: ${inputText}
        
        Please give me a helpful, educational response that's relevant to what I'm learning.
      `);

      // Get the response text
      const responseText = result.response.text();

      // Update chat history with AI response
      setChatHistory([
        ...updatedHistory,
        { role: "model", parts: [{ text: responseText }] },
      ]);

      // Add AI response to chat UI
      setMessages((prev) => [...prev, { type: "bot", text: responseText }]);
    } catch (error) {
      console.error("Error with Gemini:", error);
      setMessages((prev) => [
        ...prev,
        {
          type: "bot",
          text: "Sorry, I couldn't process your request right now. Please try again later.",
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="relative group overflow-hidden rounded-xl border border-white/10 bg-zinc-900/50 backdrop-blur-sm transition-all duration-300 hover:border-white/30 hover:bg-zinc-900/70 h-full">
      {/* Gradient background effect */}
      <div className="absolute inset-0 bg-gradient-to-br from-violet-500/20 via-fuchsia-500/20 to-blue-500/20 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
      <div className="absolute inset-0 bg-grid-white/[0.02] bg-[size:20px_20px]"></div>

      {/* Chat interface */}
      <div className="relative z-10 flex flex-col h-full p-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="w-4 h-4"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z"
              />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-white">AI Tutor</h3>
        </div>

        {/* Messages container - flex-grow to take up available space */}
        <div className="flex-grow overflow-y-auto pr-2 mb-3 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
          {messages.map((msg, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className={`mb-2 ${
                msg.type === "user" ? "flex justify-end" : "flex justify-start"
              }`}
            >
              <div
                className={`px-3 py-2 rounded-lg max-w-[85%] ${
                  msg.type === "user"
                    ? "bg-indigo-500/30 text-white"
                    : "bg-white/10 text-white/80"
                }`}
              >
                {msg.text}
              </div>
            </motion.div>
          ))}
          {isTyping && (
            <div className="flex justify-start mb-2">
              <div className="px-3 py-2 rounded-lg bg-white/10 text-white/80">
                <div className="flex space-x-1">
                  <div
                    className="w-2 h-2 rounded-full bg-white/50 animate-bounce"
                    style={{ animationDelay: "0ms" }}
                  ></div>
                  <div
                    className="w-2 h-2 rounded-full bg-white/50 animate-bounce"
                    style={{ animationDelay: "150ms" }}
                  ></div>
                  <div
                    className="w-2 h-2 rounded-full bg-white/50 animate-bounce"
                    style={{ animationDelay: "300ms" }}
                  ></div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input form */}
        <form onSubmit={handleSendMessage} className="relative">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Ask about this lesson..."
            className="w-full bg-white/5 text-white/80 placeholder-white/40 rounded-full px-4 py-2 pr-10 focus:outline-none focus:ring-1 focus:ring-purple-500/50 border border-white/10"
          />
          <button
            type="submit"
            className="absolute right-1 top-1 bottom-1 px-2 rounded-full bg-purple-500/20 hover:bg-purple-500/40 transition-colors duration-200"
            disabled={isTyping}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="w-5 h-5 text-white"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"
              />
            </svg>
          </button>
        </form>
      </div>

      {/* Glowing border effect */}
      <div className="absolute -inset-px bg-gradient-to-r from-violet-500/30 via-transparent to-blue-500/30 rounded-xl opacity-0 group-hover:opacity-100 blur-xl transition-opacity duration-500"></div>
    </div>
  );
};

export default AIChatbot;
