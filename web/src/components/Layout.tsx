import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { getMe, logout } from '../api/client';

const Layout = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState<{ email: string; display_name: string } | null>(null);

  useEffect(() => {
    getMe()
      .then(setUser)
      .catch(() => {
        navigate('/device');
      });
  }, [navigate]);

  const handleLogout = async () => {
    await logout();
    navigate('/device');
  };

  return (
    <div>
      <header className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Link to="/" style={{ fontSize: '1.4rem', fontWeight: 700, color: '#38bdf8' }}>
          Access Hub
        </Link>
        <nav style={{ display: 'flex', gap: '1rem' }}>
          <NavLink to="/" end>Home</NavLink>
          <NavLink to="/catalog">Catalog</NavLink>
          <NavLink to="/request">Request Access</NavLink>
          <NavLink to="/access">My Access</NavLink>
          <NavLink to="/audit">Audit</NavLink>
        </nav>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          {user && (
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontWeight: 600 }}>{user.display_name}</div>
              <div style={{ fontSize: '0.85rem', opacity: 0.8 }}>{user.email}</div>
            </div>
          )}
          <button style={{ marginLeft: '1rem' }} onClick={handleLogout}>Sign out</button>
        </div>
      </header>
      <main className="container">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
