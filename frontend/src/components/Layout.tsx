import { Link, Outlet } from "react-router-dom";

export default function Layout() {
  return (
    <div className="h-full flex flex-col">
      <header className="border-b border-slate-800 px-6 py-3 flex items-center gap-6">
        <Link to="/problems" className="font-bold tracking-tight">
          Interview Prep
        </Link>
        <nav className="flex gap-4 text-sm text-slate-300">
          <Link to="/problems" className="hover:text-white">Problems</Link>
        </nav>
      </header>
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
