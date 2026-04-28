"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/hedge", label: "Hedge" },
  { href: "/analytics", label: "Analytics" },
  { href: "/agents", label: "Agents" },
  { href: "/journal", label: "Journal" },
  { href: "/weather", label: "Weather" },
  { href: "/portfolio", label: "Portfolio" },
];

export default function MobileNav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  return (
    <div className="sm:hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Toggle menu"
        aria-expanded={open}
        className="p-2 text-[#7b8aab] hover:text-[#e8edf5] transition-colors"
      >
        {open ? (
          // X icon
          <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
            <path d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" />
          </svg>
        ) : (
          // Hamburger icon
          <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
            <path d="M3 5h14a1 1 0 000-2H3a1 1 0 000 2zm0 6h14a1 1 0 000-2H3a1 1 0 000 2zm0 6h14a1 1 0 000-2H3a1 1 0 000 2z" />
          </svg>
        )}
      </button>

      {open && (
        <div className="absolute top-14 left-0 right-0 bg-[#0d1117] border-b border-[#1e2535] z-50 px-4 py-2">
          {LINKS.map(({ href, label }) => (
            <a
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className={`block py-3 text-sm border-b border-[#1e2535] last:border-0 transition-colors ${
                pathname === href
                  ? "text-[#e8edf5] font-medium"
                  : "text-[#7b8aab] hover:text-[#e8edf5]"
              }`}
            >
              {label}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
