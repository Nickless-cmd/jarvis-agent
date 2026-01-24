import React from "react";
import "./SettingsModal.css";

type Props = {
  open: boolean;
  onClose: () => void;
};

const sections = ["Generelt", "Notifikationer", "Personlig tilpasning", "Apps", "Tidsplaner", "Datasikkerhed", "Konto"];

export const SettingsModal: React.FC<Props> = ({ open, onClose }) => {
  if (!open) return null;
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card">
        <div className="modal-header">
          <h2>Indstillinger</h2>
          <button className="btn-ghost" onClick={onClose}>✕</button>
        </div>
        <div className="modal-content">
          <nav className="modal-nav">
            {sections.map((s) => (
              <div key={s} className="modal-nav-item">{s}</div>
            ))}
          </nav>
          <div className="modal-panel">
            <p>Vælg en sektion for at ændre indstillinger (kommer snart).</p>
          </div>
        </div>
      </div>
    </div>
  );
};
