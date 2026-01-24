import React, { createContext, useContext, useEffect, useState } from "react";
import { loadProfile, Profile } from "./api";

type ProfileState = {
  profile: Profile | null;
  loading: boolean;
  refresh: () => Promise<void>;
};

const ProfileContext = createContext<ProfileState>({
  profile: null,
  loading: true,
  refresh: async () => {},
});

export const ProfileProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [hadProfile, setHadProfile] = useState(false);

  const refresh = async () => {
    setLoading(true);
    const p = await loadProfile();
    if (p) {
      setProfile(p);
      setHadProfile(true);
    } else {
      setProfile(null);
      if (hadProfile) {
        // if we previously had a profile and now don't, bounce to login
        window.location.href = "/login";
      } else {
        window.location.href = "/login";
      }
    }
    setLoading(false);
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <ProfileContext.Provider value={{ profile, loading, refresh }}>
      {children}
    </ProfileContext.Provider>
  );
};

export function useProfile() {
  return useContext(ProfileContext);
}
