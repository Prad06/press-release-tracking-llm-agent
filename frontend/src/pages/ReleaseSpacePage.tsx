import { useState } from "react";
import {
  Box,
  Button,
  ButtonGroup,
  Chip,
  CircularProgress,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { fetchCompanies, fetchPressReleases, fetchPressRelease } from "../api";
import type { Company, PressRelease } from "../api";

export function ReleaseSpacePage() {
  const [selected, setSelected] = useState<Company | null>(null);
  const [selectedPrId, setSelectedPrId] = useState<string | null>(null);
  const [agentLoading] = useState(false);

  const { data: companies = [], isLoading: loading } = useQuery({
    queryKey: ["companies"],
    queryFn: () => fetchCompanies(),
  });

  const { data: pressReleases = [], isLoading: prLoading } = useQuery({
    queryKey: ["press-releases", selected?.ticker ?? ""],
    queryFn: () => fetchPressReleases(selected!.ticker),
    enabled: !!selected?.ticker,
  });

  const { data: selectedPr, isLoading: detailLoading } = useQuery({
    queryKey: ["press-release", selectedPrId ?? ""],
    queryFn: () => fetchPressRelease(selectedPrId!),
    enabled: !!selectedPrId,
  });

  const handleSelectPr = (pr: PressRelease) => {
    setSelectedPrId(pr._id);
  };

  // Agent execution is handled via CLI / API for this POC; frontend no longer
  // exposes run controls here.

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        height: "calc(100vh - 64px)",
        overflow: "hidden",
      }}
    >
      {/* File browser */}
      <Box sx={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Left: Companies */}
        <Paper
          elevation={0}
          sx={{
            width: 240,
            minWidth: 240,
            borderRight: "1px solid",
            borderColor: "divider",
            overflow: "auto",
          }}
        >
          <Typography
            variant="overline"
            sx={{ px: 2, pt: 2, display: "block", color: "text.secondary" }}
          >
            Companies
          </Typography>
          {loading ? (
            <Box sx={{ p: 2, display: "flex", justifyContent: "center" }}>
              <CircularProgress size={24} />
            </Box>
          ) : (
            <List dense>
              {companies.map((c) => (
                <ListItemButton
                  key={c._id}
                  selected={selected?.ticker === c.ticker}
                  onClick={() => {
                    setSelected(c);
                    setSelectedPrId(null);
                  }}
                >
                  <ListItemText primary={c.ticker} secondary={c.name} />
                </ListItemButton>
              ))}
            </List>
          )}
        </Paper>

        {/* Center: Releases (ordered by ts) */}
        <Paper
          elevation={0}
          sx={{
            width: 300,
            minWidth: 300,
            borderRight: "1px solid",
            borderColor: "divider",
            overflow: "auto",
          }}
        >
          <Typography
            variant="overline"
            sx={{ px: 2, pt: 2, display: "block", color: "text.secondary" }}
          >
            {selected ? `${selected.ticker} — Releases` : "Select a company"}
          </Typography>
          {prLoading ? (
            <Box sx={{ p: 2, display: "flex", justifyContent: "center" }}>
              <CircularProgress size={24} />
            </Box>
          ) : (
            <List dense>
              {pressReleases.map((pr) => (
                <ListItemButton
                  key={pr._id}
                  selected={selectedPr?._id === pr._id}
                  onClick={() => handleSelectPr(pr)}
                >
                  <ListItemText
                    primary={pr.title || pr.source_url || "Untitled"}
                    secondary={
                      <Box
                        component="span"
                        sx={{
                          display: "flex",
                          gap: 0.5,
                          alignItems: "center",
                          mt: 0.5,
                          flexWrap: "wrap",
                        }}
                      >
                        <Typography variant="caption" color="text.secondary">
                          {new Date(
                            pr.press_release_timestamp,
                          ).toLocaleDateString()}
                        </Typography>
                        {pr.unprocessed && (
                          <Chip
                            label="Unprocessed"
                            size="small"
                            color="warning"
                            sx={{ height: 18, fontSize: "0.7rem" }}
                          />
                        )}
                      </Box>
                    }
                  />
                </ListItemButton>
              ))}
            </List>
          )}
        </Paper>

        {/* Right: Content */}
        <Box sx={{ flex: 1, overflow: "auto", p: 2 }}>
          {detailLoading ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
              <CircularProgress />
            </Box>
          ) : selectedPr ? (
            <Paper
              elevation={0}
              sx={{ p: 2, border: "1px solid", borderColor: "divider" }}
            >
              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  flexWrap: "wrap",
                  gap: 1,
                  mb: 2,
                }}
              >
                <Box>
                  <Typography variant="h6" sx={{ mb: 1 }}>
                    {selectedPr.title || selectedPr.source_url || "Untitled"}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    component="a"
                    href={selectedPr.source_url}
                    target="_blank"
                    rel="noreferrer"
                    sx={{ display: "block", mb: 0.5 }}
                  >
                    {selectedPr.source_url}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    display="block"
                    sx={{ mb: 1 }}
                  >
                    Press date {selectedPr.press_release_timestamp}
                  </Typography>
                  {selectedPr.unprocessed && (
                    <Chip label="Unprocessed" color="warning" size="small" />
                  )}
                </Box>
                <ButtonGroup size="small" variant="outlined">
                  <Button disabled>Run all till today</Button>
                  <Button disabled>Run only this</Button>
                </ButtonGroup>
              </Box>
              <Typography
                component="pre"
                sx={{
                  whiteSpace: "pre-wrap",
                  fontFamily: "inherit",
                  fontSize: "0.9rem",
                  maxHeight: 400,
                  overflow: "auto",
                  bgcolor: "grey.50",
                  p: 2,
                  borderRadius: 1,
                }}
              >
                {selectedPr.raw_result?.markdown_content ||
                  selectedPr.raw_result?.main_content ||
                  "No content"}
              </Typography>
            </Paper>
          ) : (
            <Typography color="text.secondary">
              Select a press release to view content.
            </Typography>
          )}
        </Box>
      </Box>
    </Box>
  );
}
