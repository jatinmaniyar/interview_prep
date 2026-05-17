import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import "./index.css";
import Problems from "./pages/Problems";
import ProblemDetail from "./pages/ProblemDetail";
import SDCookbook from "./pages/SDCookbook";
import Layout from "./components/Layout";
import JobsDashboard from "./pages/jobs/Dashboard";
import JobExplorer from "./pages/jobs/JobExplorer";
import JobDetail from "./pages/jobs/JobDetail";
import CompanyExplorer from "./pages/jobs/CompanyExplorer";
import CompanyDetail from "./pages/jobs/CompanyDetail";
import Outreach from "./pages/jobs/Outreach";
import Tracker from "./pages/jobs/Tracker";
import Profile from "./pages/jobs/Profile";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/problems" replace />} />
          <Route path="/problems" element={<Problems />} />
          <Route path="/problems/:id" element={<ProblemDetail />} />
          <Route path="/sd-cookbook" element={<SDCookbook />} />
          <Route
            path="/sd-problems"
            element={<Navigate to="/sd-cookbook" replace />}
          />
          <Route
            path="/sd-problems/:id"
            element={<Navigate to="/sd-cookbook" replace />}
          />
          <Route path="/jobs" element={<JobsDashboard />} />
          <Route path="/jobs/explore" element={<JobExplorer />} />
          <Route path="/jobs/companies" element={<CompanyExplorer />} />
          <Route path="/jobs/companies/:slug" element={<CompanyDetail />} />
          <Route path="/jobs/outreach" element={<Outreach />} />
          <Route path="/jobs/tracker" element={<Tracker />} />
          <Route path="/jobs/profile" element={<Profile />} />
          <Route path="/jobs/:id" element={<JobDetail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
