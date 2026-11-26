export type Role = "admin" | "agent";

export type Session = {
  role: Role;
  name: string;
};

export type Agent = {
  id: number;
  name: string;
  phone: string;
  is_active: boolean;
  listings_count: number;
  created_at: string;
};

export type DivarColleague = {
  id: number;
  name: string;
  phone: string;
};

export type DivarSyncChange = {
  label: string;
  old: string;
  new: string;
};

export type DivarSyncReport = {
  colleagues_added: string[];
  colleagues_removed: string[];
  colleague_phones: { name: string; old_phone: string; new_phone: string }[];
  colleague_renames: { old_name: string; new_name: string }[];
  ads_added: { title: string; consultant: string }[];
  ads_removed: { title: string; consultant: string }[];
  unchanged: number;
  consultant_changes: { title: string; old_name: string; new_name: string }[];
  spec_changes: { title: string; consultant: string; changes: DivarSyncChange[] }[];
  errors: { title: string; reason: string }[];
  deletions_applied: boolean;
  list_ready: boolean;
};

export type DivarColleagues = {
  url: string;
  posts_url: string;
  items: DivarColleague[];
  last_sync_at: string;
  last_sync_note: string;
  last_sync_report: DivarSyncReport | null;
};

export type DivarSync = {
  running: boolean;
  needs_login: boolean;
  colleagues_ready: boolean;
  total: number;
  completed: number;
  sent: number;
  skipped: number;
  removed: number;
  errors: string[];
  message: string;
  phase: string;
  current_index: number;
  current_title: string;
  current_author: string;
  paused: boolean;
};

export type DivarRefresh = {
  needs_login: boolean;
  added: number;
  removed: number;
  updated: number;
  url: string;
  items: DivarColleague[];
};

export type Listing = {
  id: number;
  title: string;
  divar_url: string;
  divar_token: string;
  area: number | null;
  price: number | null;
  bedrooms: number | null;
  category: string;
  deal_type: string;
  deposit: number | null;
  rent: number | null;
  deposit_min: number | null;
  deposit_max: number | null;
  rent_min: number | null;
  rent_max: number | null;
  rent_convertible: boolean;
  structured_text: string;
  unique_code: string;
  llm_used: boolean;
  searchable: boolean;
  image_count: number;
  archived: boolean;
  created_at_jalali: string;
  warnings: string[];
};
