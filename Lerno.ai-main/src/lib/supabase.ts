import { createClient } from "@supabase/supabase-js";

// Public project URL and publishable key (safe in the browser; row level security protects the data).
const URL = import.meta.env.VITE_SUPABASE_URL || "https://oceaylrebzflgyxfjqfb.supabase.co";
const KEY = import.meta.env.VITE_SUPABASE_KEY || "sb_publishable_6XZVSO2cS78UBwjFwVpoxw_CRywY421";

export const supabase = createClient(URL, KEY, {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: "pkce" },
});
