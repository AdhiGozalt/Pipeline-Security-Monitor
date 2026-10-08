-- Setup Supabase: tabel laporan, RLS, realtime, dan trigger webhook bertanda tangan HMAC-SHA256.
-- Ganti __HMAC_SECRET__ dan __WEBHOOK_URL__ sebelum dijalankan di SQL Editor.
create extension if not exists pg_net;
create extension if not exists pgcrypto;

create table if not exists public.threat_reports (
  id bigint generated always as identity primary key,
  status text not null check (status in ('Aman', 'Waspada', 'Bahaya Nasional')),
  level int not null default 0,
  pesan text not null,
  created_at timestamptz not null default now()
);

alter table public.threat_reports enable row level security;
drop policy if exists "baca publik" on public.threat_reports;
create policy "baca publik" on public.threat_reports for select to anon using (true);
alter publication supabase_realtime add table public.threat_reports;

-- Secret disimpan di Supabase Vault, bukan di kode
select vault.create_secret('__HMAC_SECRET__', 'webhook_hmac_secret')
where not exists (select 1 from vault.secrets where name = 'webhook_hmac_secret');

create or replace function public.notify_threat_webhook()
returns trigger language plpgsql security definer set search_path = public, extensions as $$
declare
  payload jsonb := jsonb_build_object('type', TG_OP, 'table', TG_TABLE_NAME, 'record', to_jsonb(NEW));
  secret text := (select decrypted_secret from vault.decrypted_secrets where name = 'webhook_hmac_secret');
begin
  perform net.http_post(
    url := '__WEBHOOK_URL__',
    body := payload,
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-signature', encode(hmac(payload::text, secret, 'sha256'), 'hex')
    )
  );
  return NEW;
end $$;

drop trigger if exists threat_reports_webhook on public.threat_reports;
create trigger threat_reports_webhook after insert on public.threat_reports
  for each row execute function public.notify_threat_webhook();
