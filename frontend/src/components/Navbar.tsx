import { Link, useLocation } from "react-router-dom";
import { AppBar, Button, Toolbar } from "@mui/material";

const LINKS: { path: string; label: string }[] = [
  { path: "/ingestion", label: "Ingestion" },
  { path: "/release-space", label: "Release Space" },
  { path: "/agent-space", label: "Agent Space" },
  { path: "/chat", label: "Chat" },
];

export function Navbar() {
  const location = useLocation();
  const isActive = (path: string) =>
    location.pathname === path || (path === "/ingestion" && location.pathname === "/");
  return (
    <AppBar
      position="static"
      sx={{
        bgcolor: "white",
        color: "primary.main",
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
      }}
    >
      <Toolbar sx={{ justifyContent: "flex-end", gap: 1 }}>
        {LINKS.map(({ path, label }) => (
          <Button
            key={path}
            color="inherit"
            component={Link}
            to={path}
            sx={{ textTransform: "none", fontWeight: isActive(path) ? 700 : 400 }}
          >
            {label}
          </Button>
        ))}
      </Toolbar>
    </AppBar>
  );
}
