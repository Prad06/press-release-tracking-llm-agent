import { Routes, Route } from "react-router-dom";
import { Box, ThemeProvider } from "@mui/material";
import { theme } from "./theme";
import { Navbar } from "./components/Navbar";
import { PlaceholderPage } from "./components/PlaceholderPage";
import { IngestionPage } from "./pages/IngestionPage.tsx";
import { ReleaseSpacePage } from "./pages/ReleaseSpacePage.tsx";

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
        <Navbar />
        <Routes>
          <Route path="/" element={<IngestionPage />} />
          <Route path="/ingestion" element={<IngestionPage />} />
          <Route path="/release-space" element={<ReleaseSpacePage />} />
          <Route path="/agent-space" element={<PlaceholderPage title="Agent Space" />} />
          <Route path="/chat" element={<PlaceholderPage title="Chat" />} />
        </Routes>
      </Box>
    </ThemeProvider>
  );
}
