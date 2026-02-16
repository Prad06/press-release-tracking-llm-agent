const API = "/api";

export type Company = { _id: string; ticker: string; name: string; sector?: string };

export type PressRelease = {
  _id: string;
  ticker: string;
  title?: string;
  source_url: string;
  press_release_timestamp: string;
  crawl_timestamp: string;
  unprocessed: boolean;
  raw_result?: {
    source_url: string;
    markdown_content: string;
    main_content: string;
    all_links: Array<{ url: string; text: string; title: string }>;
  };
};

export async function fetchCompanies(): Promise<Company[]> {
  const r = await fetch(`${API}/companies`);
  const j = await r.json();
  if (!r.ok) throw new Error(j.detail || "Failed");
  return j.companies ?? [];
}

export async function fetchPressReleases(ticker: string): Promise<PressRelease[]> {
  const r = await fetch(`${API}/press-releases?ticker=${encodeURIComponent(ticker)}`);
  const j = await r.json();
  if (!r.ok) throw new Error(j.detail || "Failed");
  return j.press_releases ?? [];
}

export async function fetchPressRelease(id: string): Promise<PressRelease> {
  const r = await fetch(`${API}/press-releases/${id}`);
  const j = await r.json();
  if (!r.ok) throw new Error(j.detail || "Failed");
  return j;
}
