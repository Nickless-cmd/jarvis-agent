import React, { useState } from "react";
import "./AdminDrawer.css";

type Props = {
  open: boolean;
  onClose: () => void;
};

const tabs = ["Dashboard", "Users", "Sessions", "Tools", "Config", "Logs", "Tickets", "Jobs"];

export const AdminDrawer: React.FC<Props> = ({ open, onClose }) => {
  const [active, setActive] = useState("Dashboard");
  return (
    <aside className={`admin-drawer ${open ? "open" : ""}`}>
      <div className="admin-drawer__header">
        <div>Admin</div>
        <button className="btn-ghost" onClick={onClose}>Luk</button>
      </div>
      <div className="admin-drawer__tabs">
        {tabs.map((t) => (
          <button
            key={t}
            className={`tab ${active === t ? "active" : ""}`}
            onClick={() => setActive(t)}
          >
            {t}
          </button>
        ))}
      </div>
      <div className="admin-drawer__body">
        <p>{active} (kommer snart)</p>
      </div>
    </aside>
  );
};
