# Wind forecast accuracy portal

## Known limitations

- A full ingest takes 2–2.5 minutes (measured 122–154 s) because the Supabase project
  is in Tokyo. The time is network-bound, not code-bound; an EU-region database would
  likely bring it under 2 minutes.
