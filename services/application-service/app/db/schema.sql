-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- Users Table
create table if not exists users (
    id uuid primary key default uuid_generate_v4(),
    email text unique not null,
    created_at timestamp with time zone default now()
);

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
    user_id uuid references users(id), -- Optional owner
    file_name text not null,
    storage_url text not null,
    tags text[] default array[]::text[],
    created_at timestamp with time zone default now()
);

-- Applications Table
create table if not exists applications (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid references users(id), -- Optional owner
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

-- Status History Table (Append-only)
create table if not exists status_history (
    id uuid primary key default uuid_generate_v4(),
    application_id uuid references applications(id) on delete cascade not null,
    status text not null,
    previous_status text,
    changed_at timestamp with time zone default now()
);

-- Application Resumes (Many-to-Many if needed, usually direct link is enough but requested)
create table if not exists application_resumes (
    application_id uuid references applications(id) on delete cascade,
    resume_id uuid references resumes(id) on delete cascade,
    primary key (application_id, resume_id)
);

-- Emails Table (RULE 8: Store all job-related emails)
create table if not exists emails (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid references users(id) on delete cascade,
    application_id uuid references applications(id) on delete cascade,
    gmail_message_id text unique not null,
    thread_id text not null,
    subject text not null,
    from_email text not null,
    to_email text,
    body_text text,
    received_at timestamp with time zone not null,
    internal_date bigint, -- Gmail internal date (milliseconds)
    status text not null, -- APPLIED, REJECTED, INTERVIEW, OFFER, ASSESSMENT, FOLLOW_UP, GHOSTED
    confidence_score float default 0.0,
    company_name text,
    role_title text,
    created_at timestamp with time zone default now(),
    unique(gmail_message_id)
);

-- Application Events Table (RULE 8: Timeline of events per application)
create table if not exists application_events (
    id uuid primary key default uuid_generate_v4(),
    application_id uuid references applications(id) on delete cascade not null,
    email_id uuid references emails(id) on delete set null,
    event_type text not null, -- APPLIED, REJECTED, INTERVIEW, OFFER, ASSESSMENT, FOLLOW_UP, GHOSTED
    event_date timestamp with time zone not null,
    confidence_score float default 0.0,
    metadata jsonb, -- Additional event data
    created_at timestamp with time zone default now()
);

-- Gmail Accounts Table (RULE 9: Multi-user support)
create table if not exists gmail_accounts (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid references users(id) on delete cascade not null unique,
    gmail_email text not null,
    is_active boolean default true,
    connected_at timestamp with time zone default now(),
    last_synced_at timestamp with time zone,
    last_message_internal_date bigint, -- For incremental sync
    created_at timestamp with time zone default now()
);

-- Indexes
create index if not exists idx_companies_name on companies(name);
create index if not exists idx_applications_user on applications(user_id);
create index if not exists idx_applications_status on applications(status);
create index if not exists idx_emails_user on emails(user_id);
create index if not exists idx_emails_application on emails(application_id);
create index if not exists idx_emails_thread on emails(thread_id);
create index if not exists idx_emails_gmail_message_id on emails(gmail_message_id);
create index if not exists idx_emails_received_at on emails(received_at);
create index if not exists idx_application_events_application on application_events(application_id);
create index if not exists idx_application_events_date on application_events(event_date);
create index if not exists idx_gmail_accounts_user on gmail_accounts(user_id);