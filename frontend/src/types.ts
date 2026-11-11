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

export type Report = {
  date_from: string | null;
  date_to: string | null;
  items: Array<{
    agent_id: number;
    name: string;
    phone: string;
    is_active: boolean;
    listings_count: number;
  }>;
};

export type Listing = {
  id: number;
  title: string;
  divar_url: string;
  divar_token: string;
  area: number | null;
  price: number | null;
  bedrooms: number | null;
  structured_text: string;
  unique_code: string;
  llm_used: boolean;
  searchable: boolean;
  image_count: number;
  archived: boolean;
  created_at_jalali: string;
  warnings: string[];
};
