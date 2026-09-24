import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth.jsx';
import Layout from './Layout.jsx';
import Login from './pages/Login.jsx';
import Search from './pages/Search.jsx';
import ToolForm from './pages/ToolForm.jsx';
import ToolDetail from './pages/ToolDetail.jsx';
import Admin from './pages/Admin.jsx';

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8 text-slate-500">Loading…</div>;
  return user ? children : <Navigate to="/login" replace />;
}

function AdminRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8 text-slate-500">Loading…</div>;
  if (user?.isAdmin === false) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<Protected><Layout /></Protected>}>
            <Route path="/" element={<Search />} />
            <Route path="/tools/new" element={<ToolForm />} />
            <Route path="/tools/:id" element={<ToolDetail />} />
            <Route path="/tools/:id/edit" element={<ToolForm edit />} />
            <Route path="/admin" element={<AdminRoute><Admin /></AdminRoute>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
