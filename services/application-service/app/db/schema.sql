-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- Companies Table
create table if not exists companies (
    id uuid primary key default uuid_generate_v4(),
    name text unique not null,
    created_at timestamp with time zone default now()
);

-- Roles Table
create table if not exists roles (
    id uuid primary key default uuid_generate_v4(),
    company_id uuid references companies(id) on delete cascade not null,
    title text not null,
    created_at timestamp with time zone default now(),
    unique(company_id, title)
);

-- Resumes Table
create table if not exists resumes (
    id uuid primary key default uuid_generate_v4(),
    file_name text not null,
    storage_url text not null,
    tags text[] default array[]::text[],
    created_at timestamp with time zone default now()
);

-- Applications Table
create table if not exists applications (
    id uuid primary key default uuid_generate_v4(),
    company_id uuid references companies(id) on delete cascade not null,
    role_id uuid references roles(id) on delete cascade not null,
    status text not null default 'Applied',
    status_confidence float default 0.0,
    applied_count int default 1,
    last_email_date timestamp with time zone,
    ghosted boolean default false,
    resume_id uuid references resumes(id) on delete set null,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique(company_id, role_id)
);

-- Application Events Audit Log
create table if not exists application_events (
    id uuid primary key default uuid_generate_v4(),
    application_id uuid references applications(id) on delete cascade not null,
    event_type text not null,
    raw_payload jsonb,
    created_at timestamp with time zone default now()
);

-- Indexes for performance
create index if not exists idx_companies_name on companies(name);
create index if not exists idx_applications_ghosted on applications(ghosted);
create index if not exists idx_applications_status on applications(status);
create index if not exists idx_applications_last_email on applications(last_email_date);
