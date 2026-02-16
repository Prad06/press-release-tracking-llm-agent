import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
  IconButton,
  Paper,
  TextField,
  Typography,
} from "@mui/material";
import type { Status } from "../types";

const API = "/api";

export function IngestionPage() {
  const [company, setCompany] = useState({ ticker: "", name: "", sector: "" });
  const [pr, setPr] = useState({
    url: "",
    ticker: "",
    title: "",
    press_ts: "",
  });
  const [status, setStatus] = useState<Status | null>(null);
  const [loading, setLoading] = useState(false);

  const reset = () => setStatus(null);

  const addCompany = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatus(null);
    try {
      const r = await fetch(`${API}/companies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: company.ticker,
          name: company.name,
          sector: company.sector || null,
        }),
      });
      const j = await r.json();
      if (r.ok) {
        setStatus({ ok: true, msg: `Added ${company.ticker}` });
        setCompany({ ticker: "", name: "", sector: "" });
      } else setStatus({ ok: false, msg: j.detail || "Failed" });
    } catch (e) {
      setStatus({ ok: false, msg: String(e) });
    } finally {
      setLoading(false);
    }
  };

  const addCompanyBulk = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setLoading(true);
    setStatus(null);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const r = await fetch(`${API}/companies/bulk`, {
        method: "POST",
        body: fd,
      });
      const j = await r.json();
      if (r.ok)
        setStatus({ ok: true, msg: `Added ${j.added?.length ?? 0} companies` });
      else setStatus({ ok: false, msg: j.detail || "Failed" });
    } catch (e) {
      setStatus({ ok: false, msg: String(e) });
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  };

  const addPressRelease = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatus(null);
    try {
      const r = await fetch(`${API}/press-releases`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: pr.url,
          ticker: pr.ticker,
          title: pr.title,
          press_ts: pr.press_ts,
        }),
      });
      const j = await r.json();
      if (r.ok) {
        setStatus({ ok: true, msg: "Crawled & saved" });
        setPr({ url: "", ticker: "", title: "", press_ts: "" });
      } else setStatus({ ok: false, msg: j.detail || "Failed" });
    } catch (e) {
      setStatus({ ok: false, msg: String(e) });
    } finally {
      setLoading(false);
    }
  };

  const addPressReleaseBulk = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setLoading(true);
    setStatus(null);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const r = await fetch(`${API}/press-releases/bulk`, {
        method: "POST",
        body: fd,
      });
      const j = await r.json();
      if (r.ok) {
        const results = j.results ?? [];
        const okCount = results.filter((x: { ok: boolean }) => x.ok).length;
        const failed = results.filter((x: { ok: boolean }) => !x.ok);
        if (failed.length === 0) {
          setStatus({
            ok: true,
            msg: `Saved ${okCount} press release${okCount !== 1 ? "s" : ""}`,
          });
        } else {
          const failedMsgs = failed
            .map(
              (x: { url?: string; error?: string }) =>
                `${x.url || "?"}: ${x.error || "unknown"}`,
            )
            .join("; ");
          setStatus({
            ok: false,
            msg: `${okCount} saved, ${failed.length} failed. ${failedMsgs}`,
          });
        }
      } else {
        const detail =
          typeof j.detail === "string"
            ? j.detail
            : j.detail?.[0]?.msg || JSON.stringify(j.detail);
        setStatus({ ok: false, msg: detail || "Failed" });
      }
    } catch (e) {
      setStatus({ ok: false, msg: String(e) });
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  };

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "calc(100vh - 64px)",
        p: 3,
      }}
    >
      <Box sx={{ maxWidth: 1200, width: "100%" }}>
        {loading && (
          <Alert
            severity="info"
            sx={{ mb: 2 }}
            icon={<CircularProgress size={20} />}
          >
            Loading…
          </Alert>
        )}
        {status && !loading && (
          <Alert
            severity={status.ok ? "success" : "error"}
            sx={{ mb: 2 }}
            action={
              <IconButton size="small" onClick={reset}>
                ×
              </IconButton>
            }
          >
            {status.msg}
          </Alert>
        )}

        <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
          <Paper
            elevation={0}
            sx={{
              flex: 1,
              minWidth: 320,
              p: 2.5,
              border: "1px solid",
              borderColor: "divider",
              bgcolor: "background.paper",
            }}
          >
            <Typography
              variant="subtitle1"
              sx={{ fontWeight: 600, mb: 2, color: "primary.main" }}
            >
              Company
            </Typography>
            <Box
              component="form"
              onSubmit={addCompany}
              sx={{ display: "flex", flexDirection: "column", gap: 2 }}
            >
              <TextField
                label="Ticker"
                size="small"
                value={company.ticker}
                onChange={(e) =>
                  setCompany((c) => ({ ...c, ticker: e.target.value }))
                }
                required
                fullWidth
              />
              <TextField
                label="Name"
                size="small"
                value={company.name}
                onChange={(e) =>
                  setCompany((c) => ({ ...c, name: e.target.value }))
                }
                required
                fullWidth
              />
              <TextField
                label="Sector (optional)"
                size="small"
                value={company.sector}
                onChange={(e) =>
                  setCompany((c) => ({ ...c, sector: e.target.value }))
                }
                fullWidth
              />
              <Box sx={{ height: 56 }} aria-hidden />
              <Button
                type="submit"
                variant="contained"
                disabled={loading}
                fullWidth
              >
                Add
              </Button>
            </Box>
            <Divider sx={{ my: 2 }} />
            <Typography
              variant="caption"
              color="text.secondary"
              display="block"
              sx={{ mb: 1 }}
            >
              CSV: ticker, name, sector
            </Typography>
            <Button
              variant="outlined"
              component="label"
              disabled={loading}
              fullWidth
            >
              Upload CSV
              <input
                type="file"
                accept=".csv"
                hidden
                onChange={addCompanyBulk}
              />
            </Button>
          </Paper>

          <Divider
            orientation="vertical"
            flexItem
            sx={{ borderColor: "primary.light", opacity: 0.5 }}
          />

          <Paper
            elevation={0}
            sx={{
              flex: 1,
              minWidth: 320,
              p: 2.5,
              border: "1px solid",
              borderColor: "divider",
              bgcolor: "background.paper",
            }}
          >
            <Typography
              variant="subtitle1"
              sx={{ fontWeight: 600, mb: 2, color: "primary.main" }}
            >
              Press Release
            </Typography>
            <Box
              component="form"
              onSubmit={addPressRelease}
              sx={{ display: "flex", flexDirection: "column", gap: 2 }}
            >
              <TextField
                label="URL"
                type="url"
                size="small"
                value={pr.url}
                onChange={(e) => setPr((p) => ({ ...p, url: e.target.value }))}
                required
                fullWidth
              />
              <TextField
                label="Ticker"
                size="small"
                value={pr.ticker}
                onChange={(e) =>
                  setPr((p) => ({ ...p, ticker: e.target.value }))
                }
                required
                fullWidth
              />
              <TextField
                label="Title"
                size="small"
                value={pr.title}
                onChange={(e) =>
                  setPr((p) => ({ ...p, title: e.target.value }))
                }
                required
                fullWidth
              />
              <TextField
                label="Date (ISO required)"
                size="small"
                value={pr.press_ts}
                onChange={(e) =>
                  setPr((p) => ({ ...p, press_ts: e.target.value }))
                }
                required
                fullWidth
                placeholder="2026-01-11T17:00:00-05:00"
              />
              <Button
                type="submit"
                variant="contained"
                disabled={loading}
                fullWidth
              >
                Add
              </Button>
            </Box>
            <Divider sx={{ my: 2 }} />
            <Typography
              variant="caption"
              color="text.secondary"
              display="block"
              sx={{ mb: 1 }}
            >
              CSV: url, ticker, title, date
            </Typography>
            <Button
              variant="outlined"
              component="label"
              disabled={loading}
              fullWidth
            >
              Upload CSV
              <input
                type="file"
                accept=".csv"
                hidden
                onChange={addPressReleaseBulk}
              />
            </Button>
          </Paper>
        </Box>
      </Box>
    </Box>
  );
}
