import { Box, Typography } from "@mui/material";

type Props = { title: string };

export function PlaceholderPage({ title }: Props) {
  return (
    <Box sx={{ p: 3, textAlign: "center", color: "text.secondary" }}>
      <Typography variant="h6">{title}</Typography>
      <Typography variant="body2" sx={{ mt: 1 }}>
        Coming soon
      </Typography>
    </Box>
  );
}
