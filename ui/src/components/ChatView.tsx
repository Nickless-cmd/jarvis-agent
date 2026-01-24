import React from "react";
import "./ChatView.css";

export const ChatView: React.FC = () => {
  return (
    <div className="chat-view">
      <div className="chat-feed">
        <div className="chat-message assistant">
          <div className="msg-label">Jarvis</div>
          <div className="msg-body">Hej! Jeg er klar. Hvad vil du gerne arbejde på i dag?</div>
        </div>
        <div className="chat-message user">
          <div className="msg-label">Dig</div>
          <div className="msg-body">Vis mig de seneste nyheder.</div>
        </div>
      </div>
      <div className="composer">
        <button className="composer-btn">+</button>
        <textarea placeholder="Skriv dit spørgsmål..." rows={1}></textarea>
        <div className="composer-actions">
          <button className="composer-btn">🎤</button>
          <button className="composer-btn primary">Send</button>
        </div>
      </div>
    </div>
  );
};
