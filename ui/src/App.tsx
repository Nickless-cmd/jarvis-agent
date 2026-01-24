import React, { useEffect, useMemo, useState } from "react";
import { Routes, Route, useLocation, useNavigate } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { ChatView } from "./components/ChatView";
import { AdminDrawer } from "./components/AdminDrawer";
import { SettingsModal } from "./components/SettingsModal";
import { useProfile } from "./profile";
import "./App.css";

export default function App() {
  const { profile, loading } = useProfile();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const isAdmin = !!profile?.is_admin;
  const adminRoute = location.pathname.startsWith("/admin");
  const [adminOpen, setAdminOpen] = useState(adminRoute);

  useEffect(() => {
    setAdminOpen(adminRoute);
  }, [adminRoute]);

  useEffect(() => {
    if (!loading && !profile) {
      window.location.href = "/login";
    }
  }, [loading, profile]);

  useEffect(() => {
    if (location.pathname === "/settings") {
      setSettingsOpen(true);
      navigate("/", { replace: true });
    }
  }, [location, navigate]);

  const shellClass = useMemo(() => {
    const classes = ["app-shell"];
    if (adminOpen && isAdmin) classes.push("has-admin");
    return classes.join(" ");
  }, [adminOpen, isAdmin]);

  return (
    <div className="app-root">
      {loading && <div className="loading">Indlæser…</div>}
      {!loading && profile && (
        <div className={shellClass}>
          <Sidebar
            username={profile.username}
            isAdmin={isAdmin}
            onOpenSettings={() => setSettingsOpen(true)}
            onToggleAdmin={() => setAdminOpen((v) => !v)}
          />
          <main className="main-pane">
            <Routes>
              <Route path="/" element={<ChatView />} />
              <Route path="/admin" element={<ChatView />} />
            </Routes>
          </main>
          {isAdmin && <AdminDrawer open={adminOpen} onClose={() => setAdminOpen(false)} />}
          <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
        </div>
      )}
    </div>
  );
}
