import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

const navCls = ({ isActive }: { isActive: boolean }) =>
  isActive ? "text-white" : "hover:text-white";

export default function Layout() {
  const loc = useLocation();
  const inJobs = loc.pathname.startsWith("/jobs");
  return (
    <div className="h-full flex flex-col">
      <header className="border-b border-slate-800 px-6 py-3 flex items-center gap-6">
        <Link to="/problems" className="font-bold tracking-tight">
          Interview Prep
        </Link>
        <nav className="flex gap-4 text-sm text-slate-300">
          <NavLink to="/problems" className={navCls}>Problems</NavLink>
          <NavLink to="/sd-cookbook" className={navCls}>SD Cookbook</NavLink>
          <NavLink to="/jobs" end className={navCls}>Jobs</NavLink>
        </nav>
        {inJobs && (
          <nav className="ml-auto flex gap-4 text-xs text-slate-400">
            <NavLink to="/jobs" end className={navCls}>Dashboard</NavLink>
            <NavLink to="/jobs/explore" className={navCls}>Explore</NavLink>
            <NavLink to="/jobs/companies" className={navCls}>Companies</NavLink>
            <NavLink to="/jobs/tracker" className={navCls}>Tracker</NavLink>
            <NavLink to="/jobs/outreach" className={navCls}>Outreach</NavLink>
            <NavLink to="/jobs/profile" className={navCls}>Profile</NavLink>
          </nav>
        )}
      </header>
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
