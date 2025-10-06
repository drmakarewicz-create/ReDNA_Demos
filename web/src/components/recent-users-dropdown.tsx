// web/src/components/recent-users-dropdown.tsx
'use client';

import { useEffect, useState } from 'react';
import { getRecentUsers, type RecentUser } from '../lib/user-history';

export interface RecentUsersDropdownProps {
  currentUserId: string;
  onSelectUser: (userId: string) => void;
}

export function RecentUsersDropdown({ currentUserId, onSelectUser }: RecentUsersDropdownProps) {
  const [recentUsers, setRecentUsers] = useState<RecentUser[]>([]);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    setRecentUsers(getRecentUsers());
  }, [currentUserId]); // Refresh when user changes

  const filteredUsers = recentUsers.filter(u => u.id !== currentUserId);

  if (filteredUsers.length === 0) {
    return null;
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center gap-2 px-3 py-1.5 text-sm text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
        aria-label="Recent users"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        Recent
        <svg className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute right-0 mt-2 w-64 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg z-20">
            <div className="p-2">
              <div className="text-xs font-medium text-slate-500 dark:text-slate-400 px-3 py-1">
                Recent Users
              </div>
              {filteredUsers.map(user => (
                <button
                  key={user.id}
                  onClick={() => {
                    onSelectUser(user.id);
                    setIsOpen(false);
                  }}
                  className="w-full text-left px-3 py-2 rounded-md hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                >
                  <div className="text-sm font-medium text-slate-900 dark:text-slate-100">
                    {user.label || user.id}
                  </div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">
                    {user.id}
                  </div>
                  <div className="text-xs text-slate-400 dark:text-slate-500">
                    {new Date(user.lastUsed).toLocaleDateString()}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
