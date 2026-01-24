import React from "react";
import "./Sidebar.css";

type Props = {
  username?: string;
  onOpenSettings: () => void;
  onToggleAdmin?: () => void;
  isAdmin?: boolean;
};

const sampleSessions = ["Projekt Alpha", "Ideer til pitch", "Opsummering af møde", "Planlægning af sprint"];

export const Sidebar: React.FC<Props> = ({ username, onOpenSettings, onToggleAdmin, isAdmin }) => {
  return (
    <aside className="sidebar">
      <div className="sidebar__header">
        <div className="sidebar__brand">
          <div className="logo-dot" />
          <span className="logo-text">Jarvis</span>
        </div>
        <button className="btn-ghost" title="New chat">+ Ny chat</button>
      </div>
      <div className="sidebar__search">
        <input placeholder="Søg chats..." />
      </div>
      <div className="sidebar__section">
        <div className="sidebar__section-title">Dine chats</div>
        <div className="sidebar__list">
          {sampleSessions.map((s) => (
            <div key={s} className="sidebar__item">{s}</div>
          ))}
        </div>
      </div>
      <div className="sidebar__footer">
        <div className="sidebar__user">
          <div className="avatar">{username?.charAt(0).toUpperCase() || "?"}</div>
          <div className="user-meta">
            <div className="user-name">{username || "Ukendt bruger"}</div>
          </div>
        </div>
        <div className="sidebar__actions">
          <button className="btn-ghost" onClick={onOpenSettings}>Indstillinger</button>
          {isAdmin && <button className="btn-ghost" onClick={onToggleAdmin}>Admin panel</button>}
          <button className="btn-ghost" onClick={() => (window.location.href = "/logout")}>Log ud</button>
        </div>
      </div>
    </aside>
  );
};
