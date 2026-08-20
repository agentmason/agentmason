'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

export default function AuthButton() {
  const router = useRouter();
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(!!localStorage.getItem('token'));
  }, []);

  if (loggedIn) {
    return (
      <button
        onClick={() => {
          localStorage.removeItem('token');
          setLoggedIn(false);
          router.push('/login');
        }}
        className="rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
      >
        Sign Out
      </button>
    );
  }

  return (
    <button
      onClick={() => router.push('/login')}
      className="rounded-lg border border-blue-300 px-4 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 transition-colors"
    >
      Sign In
    </button>
  );
}
